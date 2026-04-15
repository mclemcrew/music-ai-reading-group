#!/usr/bin/env python3
"""Faithful headless replay harness for ARIA's real-time demo path.

This script keeps the demo's real takeover architecture intact:
1. Replay a prompt MIDI file into the live capture/prefill path
2. Trigger takeover at a controlled wall-clock offset
3. Recalculate trailing prompt durations
4. Run the demo's 2-token beam search handoff
5. Continue with the demo's autoregressive sampler

Unlike the chunked standalone experiments, this path does not add
repeated beam search, hard note quotas, top-p sampling, or custom
time/pedal penalties. The goal is fidelity to the released demo.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import math
import os
import pathlib
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import mido
import mlx.core as mx
import mlx.nn as nn

ARIA_DIR = "/Users/mclemens/Development/aria"
EXPERIMENT_DIR = pathlib.Path(__file__).resolve().parent

import sys

sys.path.insert(0, ARIA_DIR)

from aria.config import load_model_config
from aria.embedding import get_global_embedding_from_midi
from aria.inference.model_mlx import TransformerLM
from aria.model import ModelConfig, TransformerEMB
from ariautils.midi import MidiDict, midi_to_dict
from ariautils.tokenizer import AbsTokenizer
from safetensors.torch import load_file

DTYPE = mx.bfloat16
MAX_SEQ_LEN = 4096
KV_CHUNK_SIZE = 256
PREFILL_CHUNK_SIZE_L = 128
PREFILL_CHUNK_SIZE = 16
RECALC_DUR_PREFILL_CHUNK_SIZE = 8
RECALC_DUR_BUFFER_MS = 100
BEAM_WIDTH = 3
TIME_TOK_WEIGHTING = -5
FIRST_ONSET_BUFFER_MS = -200
MAX_STREAM_DELAY_MS = 100

MIN_NOTE_DELTA_MS = 0
MIN_PEDAL_DELTA_MS = 0
MIN_NOTE_LENGTH_MS = 10
HARDWARE_INPUT_LATENCY_MS = 0
BASE_OUTPUT_LATENCY_MS = 0
VELOCITY_OUTPUT_LATENCY_MS = {v: 0 for v in range(0, 127, 10)}

EMBEDDING_OFFSET = 0


@dataclass
class DurationReplacement:
    position: int
    old_token: str
    new_token: str


@dataclass
class BeamDecision:
    first: str
    second: str
    score: float


@dataclass
class RunMetadata:
    prompt_midi: str
    output_midi: str
    metadata_json: str
    checkpoint: str
    embedding_checkpoint: str | None
    embedding_midi: str | None
    takeover_ms: int
    temperature: float
    min_p: float
    wait_for_close: bool
    midi_out: str | None
    midi_through: str | None
    used_embedding: bool
    prompt_token_count: int = 0
    prompt_note_count: int = 0
    num_preceding_active_pitches: int = 0
    first_on_msg_epoch_ms: int | None = None
    duration_recalc_count: int = 0
    duration_replacements: list[DurationReplacement] = field(default_factory=list)
    beam_choice: BeamDecision | None = None
    generated_token_count: int = 0
    generated_token_trace: list[str] = field(default_factory=list)
    generated_note_token_count: int = 0
    generated_time_token_count: int = 0
    generated_pedal_token_count: int = 0
    output_note_count: int = 0
    output_duration_ms: int = 0
    started_at_epoch_ms: int = 0
    finished_at_epoch_ms: int = 0


class NullMidiOut:
    def send(self, msg: mido.Message) -> None:
        del msg


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def get_epoch_time_ms() -> int:
    return round(time.time() * 1000)


def set_calibration_settings(load_path: str) -> None:
    with open(load_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    global MIN_NOTE_DELTA_MS
    global MIN_PEDAL_DELTA_MS
    global MIN_NOTE_LENGTH_MS
    global HARDWARE_INPUT_LATENCY_MS
    global BASE_OUTPUT_LATENCY_MS
    global VELOCITY_OUTPUT_LATENCY_MS

    MIN_NOTE_DELTA_MS = settings["MIN_NOTE_DELTA_MS"]
    MIN_PEDAL_DELTA_MS = settings["MIN_PEDAL_DELTA_MS"]
    MIN_NOTE_LENGTH_MS = settings["MIN_NOTE_LENGTH_MS"]
    HARDWARE_INPUT_LATENCY_MS = settings["HARDWARE_INPUT_LATENCY_MS"]
    BASE_OUTPUT_LATENCY_MS = settings["BASE_OUTPUT_LATENCY_MS"]
    VELOCITY_OUTPUT_LATENCY_MS = {
        int(k): v for k, v in settings["VELOCITY_OUTPUT_LATENCY_MS"].items()
    }


def _get_input_latency_ms(velocity: int) -> int:
    return BASE_OUTPUT_LATENCY_MS + VELOCITY_OUTPUT_LATENCY_MS[velocity]


def _max_kv_pos(input_pos: mx.array) -> int:
    last = input_pos[-1].item()
    return math.ceil(last / KV_CHUNK_SIZE) * KV_CHUNK_SIZE


def prefill(model: TransformerLM, idxs: mx.array, input_pos: mx.array) -> mx.array:
    return model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=_max_kv_pos(input_pos + EMBEDDING_OFFSET),
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )


def decode_one(
    model: TransformerLM,
    idxs: mx.array,
    input_pos: mx.array,
) -> mx.array:
    assert input_pos.shape[-1] == 1
    return model(
        idxs=idxs,
        input_pos=input_pos + EMBEDDING_OFFSET,
        max_kv_pos=_max_kv_pos(input_pos + EMBEDDING_OFFSET),
        offset=input_pos[0] + EMBEDDING_OFFSET,
    )[:, -1]


def sample_min_p(logits: mx.array, p_base: float) -> mx.array:
    if p_base <= 0.0:
        return mx.argmax(logits, axis=-1, keepdims=True)
    if p_base >= 1.0:
        return mx.random.categorical(logits, num_samples=1)

    log_p_max = mx.max(logits, axis=-1, keepdims=True)
    log_p_scaled = mx.log(p_base) + log_p_max
    mask = logits >= log_p_scaled
    masked_logits = mx.where(~mask, -mx.inf, logits)
    return mx.random.categorical(masked_logits, num_samples=1)


def load_tokenizer(config_path: pathlib.Path) -> AbsTokenizer:
    return AbsTokenizer(config_path=config_path)


def load_model(checkpoint_path: str, tokenizer: AbsTokenizer) -> TransformerLM:
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(tokenizer.vocab_size)

    weights = mx.load(checkpoint_path)
    for key, weight in weights.items():
        if weight.dtype != DTYPE:
            weights[key] = weight.astype(DTYPE)

    model = TransformerLM(model_config)
    model.load_weights(list(weights.items()), strict=False)
    model.eval()
    model.setup_cache(batch_size=1, max_seq_len=MAX_SEQ_LEN, dtype=DTYPE)
    mx.eval(model.parameters())
    return model


def compute_embedding(checkpoint_path: str, midi_path: str) -> list[float]:
    # The released embedding checkpoint uses the default tokenizer vocab
    # (17727, no demo pedal extension), not the demo tokenizer vocab (17729).
    embedding_tokenizer = AbsTokenizer()
    model_config = ModelConfig(**load_model_config("medium-emb"))
    model_config.set_vocab_size(embedding_tokenizer.vocab_size)
    model = TransformerEMB(model_config)
    model.load_state_dict(load_file(checkpoint_path), strict=True)
    embedding = get_global_embedding_from_midi(
        model=model.cpu(),
        midi_path=midi_path,
        device="cpu",
    )
    return embedding.tolist()


def insert_embedding(model: TransformerLM, embedding: list[float]) -> None:
    global EMBEDDING_OFFSET
    model.fill_condition_kv(mx.array([embedding], dtype=DTYPE))
    EMBEDDING_OFFSET = 1


def convert_msgs_to_midi(msgs: list[mido.Message]) -> mido.MidiFile:
    channel_to_track = {
        chan: mido.MidiTrack() for chan in list({msg.channel for msg in msgs})
    }

    for msg in msgs:
        channel_to_track[msg.channel].append(msg)

    for msg in channel_to_track[0]:
        if msg.type == "note_on" and msg.velocity > 0:
            msg.time = 0
            break
        msg.time = 0

    mid = mido.MidiFile(type=1)
    mid.ticks_per_beat = 500

    for channel, track in channel_to_track.items():
        track.insert(0, mido.MetaMessage("set_tempo", tempo=500000, time=0))
        track.insert(
            0,
            mido.Message("program_change", program=0, channel=channel, time=0),
        )
        mid.tracks.append(track)

    return mid


def _find_divergence(
    prev_context: list[int],
    curr_context: list[int],
    tokenizer: AbsTokenizer,
) -> tuple[int, list[int]]:
    agreement_index = 0
    for prev_val, curr_val in zip(prev_context, curr_context):
        if prev_val == curr_val:
            agreement_index += 1
        else:
            logging.info(
                "Found divergence at idx %s: %s vs %s",
                agreement_index,
                tokenizer.id_to_tok[curr_val],
                tokenizer.id_to_tok[prev_val],
            )
            break

    return agreement_index, curr_context[agreement_index:]


def chunked_prefill(
    model: TransformerLM,
    tokenizer: AbsTokenizer,
    prev_context: list[int],
    curr_context: list[int],
    full: bool = False,
) -> list[int]:
    assert isinstance(curr_context[0], int)
    assert tokenizer.pad_id not in prev_context
    assert tokenizer.pad_id not in curr_context

    while True:
        prefill_idx, prefill_toks = _find_divergence(
            prev_context=prev_context,
            curr_context=curr_context,
            tokenizer=tokenizer,
        )
        num_prefill_toks = len(prefill_toks)

        if num_prefill_toks > PREFILL_CHUNK_SIZE_L:
            mx.eval(
                prefill(
                    model,
                    idxs=mx.array(
                        [prefill_toks[:PREFILL_CHUNK_SIZE_L]], dtype=mx.int32
                    ),
                    input_pos=mx.arange(
                        prefill_idx,
                        prefill_idx + PREFILL_CHUNK_SIZE_L,
                        dtype=mx.int32,
                    ),
                )
            )
            prev_context = curr_context[: prefill_idx + PREFILL_CHUNK_SIZE_L]
        elif num_prefill_toks > PREFILL_CHUNK_SIZE:
            mx.eval(
                prefill(
                    model,
                    idxs=mx.array([prefill_toks[:PREFILL_CHUNK_SIZE]], dtype=mx.int32),
                    input_pos=mx.arange(
                        prefill_idx,
                        prefill_idx + PREFILL_CHUNK_SIZE,
                        dtype=mx.int32,
                    ),
                )
            )
            prev_context = curr_context[: prefill_idx + PREFILL_CHUNK_SIZE]
        elif num_prefill_toks > 0 and full:
            padded = prefill_toks + (PREFILL_CHUNK_SIZE - len(prefill_toks)) * [
                tokenizer.pad_id
            ]
            mx.eval(
                prefill(
                    model,
                    idxs=mx.array([padded], dtype=mx.int32),
                    input_pos=mx.arange(
                        prefill_idx,
                        prefill_idx + PREFILL_CHUNK_SIZE,
                        dtype=mx.int32,
                    ),
                )
            )
            prev_context = curr_context
            break
        else:
            break

    logging.info(
        "KV stored up to idx=%s (curr_context_len=%s)",
        max(0, len(prev_context) - 1),
        len(curr_context),
    )
    return prev_context


def _first_bad_dur_index(
    tokenizer: AbsTokenizer,
    priming_seq: list[Any],
    pred_ids: list[int],
    chunk_start: int,
    last_offset_ms: int,
) -> int | None:
    num_time_toks = priming_seq[:chunk_start].count(tokenizer.time_tok)
    local_onset_ms = tokenizer.calc_length_ms(
        priming_seq[: chunk_start + 1], onset=True
    )

    for pos, tok_id in enumerate(
        pred_ids[: len(priming_seq) - chunk_start], start=chunk_start
    ):
        prim_tok = priming_seq[pos]
        pred_tok = tokenizer.id_to_tok[tok_id]

        if isinstance(prim_tok, tuple) and prim_tok[0] == "onset":
            local_onset_ms = num_time_toks * 5000 + prim_tok[1]
        elif prim_tok == tokenizer.time_tok:
            num_time_toks += 1
        elif isinstance(prim_tok, tuple) and prim_tok[0] == "dur":
            dur_true = prim_tok[1]
            dur_pred = pred_tok[1]
            if dur_pred > dur_true and (
                local_onset_ms + dur_true >= last_offset_ms - RECALC_DUR_BUFFER_MS
            ):
                return pos

    return None


def recalc_dur_tokens_chunked(
    model: TransformerLM,
    priming_seq: list[Any],
    enc_seq: mx.array,
    tokenizer: AbsTokenizer,
    start_idx: int,
    metadata: RunMetadata,
) -> tuple[mx.array, list[Any], mx.array]:
    assert start_idx > 0
    priming_len = len(priming_seq)
    last_offset = tokenizer.calc_length_ms(priming_seq, onset=False)

    idx = start_idx
    replacements: list[DurationReplacement] = []
    while idx <= priming_len:
        end_idx = idx + RECALC_DUR_PREFILL_CHUNK_SIZE
        window_ids = mx.array(
            enc_seq[:, idx - 1 : end_idx - 1].tolist(),
            dtype=mx.int32,
        )
        window_pos = mx.arange(idx - 1, end_idx - 1, dtype=mx.int32)

        logits = prefill(model, idxs=window_ids, input_pos=window_pos)
        pred_ids = mx.argmax(logits, axis=-1).flatten().tolist()

        bad_pos = _first_bad_dur_index(
            tokenizer=tokenizer,
            priming_seq=priming_seq,
            pred_ids=pred_ids,
            chunk_start=idx,
            last_offset_ms=last_offset,
        )

        if bad_pos is None:
            idx = end_idx
            continue

        new_id = pred_ids[bad_pos - idx]
        old_tok = priming_seq[bad_pos]
        new_tok = tokenizer.id_to_tok[new_id]
        enc_seq[0, bad_pos] = new_id
        priming_seq[bad_pos] = new_tok
        replacements.append(
            DurationReplacement(
                position=bad_pos,
                old_token=repr(old_tok),
                new_token=repr(new_tok),
            )
        )
        idx = bad_pos + 1

    metadata.duration_recalc_count = len(replacements)
    metadata.duration_replacements = replacements
    next_logits = logits[:, priming_len - idx]
    return enc_seq, priming_seq, next_logits


def decode_first_tokens(
    model: TransformerLM,
    first_token_logits: mx.array,
    enc_seq: mx.array,
    priming_seq: list[Any],
    tokenizer: AbsTokenizer,
    generated_tokens_queue: queue.Queue,
    first_on_msg_epoch_ms: int,
    trace: list[str],
    metadata: RunMetadata,
) -> tuple[mx.array, int]:
    buffer_ms = FIRST_ONSET_BUFFER_MS
    time_tok_id = tokenizer.tok_to_id[tokenizer.time_tok]
    eos_tok_id = tokenizer.tok_to_id[tokenizer.eos_tok]
    dim_tok_id = tokenizer.tok_to_id[tokenizer.dim_tok]
    ped_off_id = tokenizer.tok_to_id[tokenizer.ped_off_tok]
    ped_on_id = tokenizer.tok_to_id[tokenizer.ped_on_tok]
    onset_ids = [tokenizer.tok_to_id[token] for token in tokenizer.onset_tokens]

    logits = first_token_logits
    time_since_first_onset_ms = get_epoch_time_ms() - first_on_msg_epoch_ms
    idx = len(priming_seq) + 1

    num_time_toks_required = (time_since_first_onset_ms + buffer_ms) // 5000
    num_time_toks_in_priming_seq = priming_seq.count(tokenizer.time_tok)
    num_time_toks_to_add = num_time_toks_required - num_time_toks_in_priming_seq

    while num_time_toks_to_add > 0:
        generated_tokens_queue.put(tokenizer.time_tok)
        trace.append(repr(tokenizer.time_tok))
        logits = decode_one(
            model,
            idxs=mx.array([[time_tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )
        enc_seq[:, idx - 1] = time_tok_id
        num_time_toks_to_add -= 1
        idx += 1

    logits[:, dim_tok_id] = float("-inf")
    logits[:, eos_tok_id] = float("-inf")
    logits[:, ped_off_id] = float("-inf")

    log_probs = nn.log_softmax(logits, axis=-1)
    top_ids = mx.argsort(log_probs, axis=-1)[0, -BEAM_WIDTH:]
    top_log_probs = log_probs[0, top_ids]

    if time_tok_id not in top_ids.tolist():
        top_ids[0] = time_tok_id
        top_log_probs[0] = log_probs[0, time_tok_id]

    time_tok_idx = top_ids.tolist().index(time_tok_id)
    top_log_probs[time_tok_idx] += TIME_TOK_WEIGHTING
    top_toks = [tokenizer.id_to_tok[token_id] for token_id in top_ids.tolist()]

    priming_seq_last_onset_ms = tokenizer.calc_length_ms(priming_seq, onset=True)
    if priming_seq_last_onset_ms < time_since_first_onset_ms + buffer_ms:
        masked_onset_ids = [
            tokenizer.tok_to_id[token]
            for token in tokenizer.onset_tokens
            if token[1] < ((time_since_first_onset_ms + buffer_ms) % 5000)
        ]
    else:
        masked_onset_ids = []

    best_score = float("-inf")
    best_tok_id_1 = None
    best_tok_id_2 = None
    for i in range(BEAM_WIDTH):
        tok = top_toks[i]
        tok_id = top_ids[i].item()
        tok_log_prob = top_log_probs[i]

        next_logits = decode_one(
            model,
            idxs=mx.array([[tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        next_log_probs = nn.log_softmax(next_logits, axis=-1)
        next_log_probs[:, eos_tok_id] = float("-inf")
        next_log_probs[:, dim_tok_id] = float("-inf")
        next_log_probs[:, ped_off_id] = float("-inf")

        if masked_onset_ids:
            next_log_probs[:, masked_onset_ids] = float("-inf")
        if tok_id == time_tok_id:
            next_log_probs[:, time_tok_id] = float("-inf")

        is_instrument = isinstance(tok, tuple) and (
            (len(tok) == 3 and tok[0] != "prefix")
            or (len(tok) == 2 and tok[0] == "drum")
        )
        if tok_id == ped_on_id or is_instrument:
            mask = mx.full(next_log_probs.shape, float("-inf"))
            for onset_id in onset_ids:
                mask[:, onset_id] = 0.0
            next_log_probs = next_log_probs + mask

        next_tok_log_prob = mx.max(next_log_probs, axis=-1)
        next_tok_id = mx.argmax(next_log_probs, axis=-1)
        score = tok_log_prob + next_tok_log_prob

        if score > best_score:
            best_tok_id_1 = tok_id
            best_tok_id_2 = next_tok_id.item()
            best_score = score.item()

    assert best_tok_id_1 is not None and best_tok_id_2 is not None
    best_tok_1 = tokenizer.id_to_tok[best_tok_id_1]
    best_tok_2 = tokenizer.id_to_tok[best_tok_id_2]
    metadata.beam_choice = BeamDecision(
        first=repr(best_tok_1),
        second=repr(best_tok_2),
        score=best_score,
    )

    enc_seq[:, idx - 1] = best_tok_id_1
    enc_seq[:, idx] = best_tok_id_2
    generated_tokens_queue.put(best_tok_1)
    generated_tokens_queue.put(best_tok_2)
    trace.extend([repr(best_tok_1), repr(best_tok_2)])

    mx.eval(
        decode_one(
            model,
            idxs=mx.array([[best_tok_id_1]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )
    )

    return enc_seq, idx + 1


def decode_tokens(
    model: TransformerLM,
    enc_seq: mx.array,
    tokenizer: AbsTokenizer,
    control_sentinel: threading.Event,
    generated_tokens_queue: queue.Queue,
    idx: int,
    temperature: float,
    min_p: float,
    is_ending: bool,
    trace: list[str],
    max_new_tokens: int | None,
) -> None:
    if control_sentinel.is_set():
        control_sentinel.clear()

    last_tok_is_pedal = False
    dur_ids = [tokenizer.tok_to_id[token] for token in tokenizer.dur_tokens]
    dur_mask_ids = [
        tokenizer.tok_to_id[("dur", dur_ms)]
        for dur_ms in range(0, MIN_NOTE_LENGTH_MS, 10)
    ]

    start_idx = idx
    while (not control_sentinel.is_set()) and idx < MAX_SEQ_LEN:
        if max_new_tokens is not None and (idx - start_idx) >= max_new_tokens:
            generated_tokens_queue.put(None)
            return

        prev_tok_id = enc_seq[0, idx - 1]
        logits = decode_one(
            model,
            idxs=mx.array([[prev_tok_id]], dtype=mx.int32),
            input_pos=mx.array([idx - 1], dtype=mx.int32),
        )

        logits[:, tokenizer.tok_to_id[tokenizer.ped_off_tok]] += 3
        logits[:, tokenizer.tok_to_id[tokenizer.dim_tok]] = float("-inf")
        logits[:, dur_mask_ids] = float("-inf")
        if last_tok_is_pedal:
            logits[:, dur_ids] = float("-inf")
        if not is_ending:
            logits[:, tokenizer.tok_to_id[tokenizer.eos_tok]] = float("-inf")

        if temperature > 0.0:
            next_token_ids = sample_min_p(logits / temperature, min_p).flatten()
        else:
            next_token_ids = mx.argmax(logits, axis=-1).flatten()

        enc_seq[:, idx] = next_token_ids
        next_token = tokenizer.id_to_tok[next_token_ids[0].item()]

        if next_token in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}:
            last_tok_is_pedal = True
        else:
            # Keep the demo's intended behavior, but fix the latent reset bug so
            # pedal-state masking does not persist through unrelated tokens.
            last_tok_is_pedal = False

        trace.append(repr(next_token))
        if next_token == tokenizer.eos_tok:
            generated_tokens_queue.put(next_token)
            return

        generated_tokens_queue.put(next_token)
        idx += 1

    generated_tokens_queue.put(None)


def _adjust_previous_off_time(
    pitch_to_prev_msg: dict[Any, tuple[dict | None, dict | None]],
    key: str | int,
    new_on_send_time: int,
    min_delta_ms: int,
) -> None:
    prev_on, prev_off = pitch_to_prev_msg.get(key, (None, None))
    if prev_on is None or prev_off is None or min_delta_ms <= 0:
        return

    adjusted_time = max(
        min(prev_off["send_epoch_time_ms"], new_on_send_time - min_delta_ms),
        prev_on["send_epoch_time_ms"],
    )
    if adjusted_time != prev_off["send_epoch_time_ms"]:
        prev_off["send_epoch_time_ms"] = adjusted_time
        prev_off["adjusted"] = True


def _decode_pedal_double(
    note_buffer: list[Any],
    first_on_msg_epoch_ms: int,
    num_time_toks: int,
    pitch_to_prev_msg: dict[Any, tuple[dict | None, dict | None]],
    outbound_midi_msg_queue: queue.Queue,
    tokenizer: AbsTokenizer,
) -> int:
    pedal_tok, onset_tok = note_buffer
    velocity = 127 if pedal_tok == tokenizer.ped_on_tok else 0
    _, onset = onset_tok

    onset_epoch_ms = first_on_msg_epoch_ms + (num_time_toks * 5000) + onset
    send_onset_epoch_ms = onset_epoch_ms - BASE_OUTPUT_LATENCY_MS
    pedal_msg = {
        "pitch": "pedal",
        "vel": velocity,
        "epoch_time_ms": onset_epoch_ms,
        "send_epoch_time_ms": send_onset_epoch_ms,
        "uuid": "pedal",
    }

    if pedal_tok == tokenizer.ped_on_tok:
        _adjust_previous_off_time(
            pitch_to_prev_msg=pitch_to_prev_msg,
            key="pedal",
            new_on_send_time=send_onset_epoch_ms,
            min_delta_ms=MIN_PEDAL_DELTA_MS,
        )
        pitch_to_prev_msg["pedal"] = (pedal_msg, None)
    else:
        prev_on, _ = pitch_to_prev_msg.get("pedal", (None, None))
        pitch_to_prev_msg["pedal"] = (prev_on, pedal_msg)

    outbound_midi_msg_queue.put(pedal_msg)
    return onset_epoch_ms


def _decode_note_triple(
    note_buffer: list[Any],
    first_on_msg_epoch_ms: int,
    num_time_toks: int,
    pitch_to_prev_msg: dict[Any, tuple[dict | None, dict | None]],
    outbound_midi_msg_queue: queue.Queue,
) -> int:
    note_tok, onset_tok, dur_tok = note_buffer
    _, pitch, vel = note_tok
    _, onset = onset_tok
    _, dur = dur_tok

    msg_uuid = uuid.uuid4()
    onset_epoch_ms = first_on_msg_epoch_ms + (num_time_toks * 5000) + onset
    offset_epoch_ms = onset_epoch_ms + dur
    send_onset_epoch_ms = onset_epoch_ms - _get_input_latency_ms(vel)
    send_offset_epoch_ms = offset_epoch_ms - BASE_OUTPUT_LATENCY_MS

    on_msg = {
        "pitch": pitch,
        "vel": vel,
        "epoch_time_ms": onset_epoch_ms,
        "send_epoch_time_ms": send_onset_epoch_ms,
        "uuid": msg_uuid,
    }
    off_msg = {
        "pitch": pitch,
        "vel": 0,
        "epoch_time_ms": offset_epoch_ms,
        "send_epoch_time_ms": send_offset_epoch_ms,
        "uuid": msg_uuid,
    }

    _adjust_previous_off_time(
        pitch_to_prev_msg=pitch_to_prev_msg,
        key=pitch,
        new_on_send_time=send_onset_epoch_ms,
        min_delta_ms=MIN_NOTE_DELTA_MS,
    )

    pitch_to_prev_msg[pitch] = (on_msg, off_msg)
    outbound_midi_msg_queue.put(on_msg)
    outbound_midi_msg_queue.put(off_msg)
    return offset_epoch_ms


def decode_tokens_to_midi(
    generated_tokens_queue: queue.Queue,
    outbound_midi_msg_queue: queue.Queue,
    tokenizer: AbsTokenizer,
    first_on_msg_epoch_ms: int,
    priming_seq_last_onset_ms: int,
) -> None:
    assert (
        first_on_msg_epoch_ms + priming_seq_last_onset_ms
        < get_epoch_time_ms() + HARDWARE_INPUT_LATENCY_MS
    )

    pitch_to_prev_msg: dict[Any, tuple[dict | None, dict | None]] = {}
    note_buffer: list[Any] = []
    saved_note: Any | None = None
    num_time_toks = priming_seq_last_onset_ms // 5000
    offset_epoch_ms = first_on_msg_epoch_ms + priming_seq_last_onset_ms

    while True:
        if saved_note is not None and not note_buffer:
            note_buffer.append(saved_note)
            saved_note = None

        while True:
            tok = generated_tokens_queue.get()
            if tok is tokenizer.eos_tok:
                msg_uuid = uuid.uuid4()
                end_msg = {
                    "pitch": -1,
                    "vel": -1,
                    "epoch_time_ms": offset_epoch_ms + 100,
                    "send_epoch_time_ms": offset_epoch_ms + 100,
                    "uuid": msg_uuid,
                }
                outbound_midi_msg_queue.put(end_msg)
                return
            if tok is None:
                msg_uuid = uuid.uuid4()
                end_msg = {
                    "pitch": -1,
                    "vel": -1,
                    "epoch_time_ms": offset_epoch_ms + 100,
                    "send_epoch_time_ms": offset_epoch_ms + 100,
                    "uuid": msg_uuid,
                }
                outbound_midi_msg_queue.put(end_msg)
                return

            note_buffer.append(tok)
            if isinstance(tok, tuple) and tok[0] == "dur":
                msg_type = "note"
                break
            if (
                isinstance(tok, tuple)
                and tok[0] == "onset"
                and note_buffer[-2] in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}
            ):
                msg_type = "pedal"
                break

        num_time_toks += sum(1 for tok in note_buffer if tok == tokenizer.time_tok)
        note_buffer = [tok for tok in note_buffer if tok != tokenizer.time_tok]

        if msg_type == "note":
            note_buffer = [
                tok
                for tok in note_buffer
                if tok not in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}
            ]
            note_tokens = [
                tok
                for tok in note_buffer
                if isinstance(tok, tuple) and len(tok) == 3 and tok[0] != "prefix"
            ]
            onset_tokens = [
                tok
                for tok in note_buffer
                if isinstance(tok, tuple) and tok[0] == "onset"
            ]
            dur_tokens = [
                tok for tok in note_buffer if isinstance(tok, tuple) and tok[0] == "dur"
            ]
            if not note_tokens or not onset_tokens or not dur_tokens:
                logging.warning("Skipping degenerate note buffer: %s", note_buffer)
                note_buffer = []
                continue

            note_buffer = [note_tokens[-1], onset_tokens[-1], dur_tokens[-1]]
            offset_epoch_ms = _decode_note_triple(
                note_buffer=note_buffer,
                first_on_msg_epoch_ms=first_on_msg_epoch_ms,
                num_time_toks=num_time_toks,
                pitch_to_prev_msg=pitch_to_prev_msg,
                outbound_midi_msg_queue=outbound_midi_msg_queue,
            )
        else:
            note_tokens = [
                tok
                for tok in note_buffer
                if isinstance(tok, tuple) and len(tok) == 3 and tok[0] != "prefix"
            ]
            if note_tokens:
                saved_note = note_tokens[-1]

            pedal_tokens = [
                tok
                for tok in note_buffer
                if tok in {tokenizer.ped_on_tok, tokenizer.ped_off_tok}
            ]
            onset_tokens = [
                tok
                for tok in note_buffer
                if isinstance(tok, tuple) and tok[0] == "onset"
            ]
            if not pedal_tokens or not onset_tokens:
                logging.warning("Skipping degenerate pedal buffer: %s", note_buffer)
                note_buffer = []
                continue

            note_buffer = [pedal_tokens[-1], onset_tokens[-1]]
            offset_epoch_ms = _decode_pedal_double(
                note_buffer=note_buffer,
                first_on_msg_epoch_ms=first_on_msg_epoch_ms,
                num_time_toks=num_time_toks,
                pitch_to_prev_msg=pitch_to_prev_msg,
                outbound_midi_msg_queue=outbound_midi_msg_queue,
                tokenizer=tokenizer,
            )

        note_buffer = []


def _create_mido_message(
    msg_dict: dict[str, Any],
    channel: int,
    time_delta_ms: int,
) -> mido.Message:
    if msg_dict["pitch"] == "pedal":
        return mido.Message(
            "control_change",
            control=64,
            value=msg_dict["vel"],
            channel=channel,
            time=time_delta_ms,
        )

    return mido.Message(
        "note_on",
        note=msg_dict["pitch"],
        velocity=msg_dict["vel"],
        channel=channel,
        time=time_delta_ms,
    )


def stream_midi_or_archive(
    inbound_midi_msg_queue: queue.Queue,
    msgs: list[mido.Message],
    last_channel_msg_epoch_time_ms: float,
    midi_output_port: str | None,
    control_sentinel: threading.Event,
    midi_stream_channel: int,
    results_queue: queue.Queue,
) -> None:
    active_pitch_uuid: dict[Any, uuid.UUID | str] = {}
    pending_msgs: list[dict[str, Any]] = []
    msgs_to_archive: list[dict[str, Any]] = []
    archive_only = midi_output_port is None

    if archive_only:
        output_cm = contextlib.nullcontext(NullMidiOut())
    else:
        output_cm = mido.open_output(midi_output_port)

    with output_cm as midi_out:
        while not control_sentinel.is_set():
            while not inbound_midi_msg_queue.empty():
                try:
                    msg = inbound_midi_msg_queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    if msg:
                        pending_msgs.append(msg)

            pending_msgs.sort(
                key=lambda item: (item["send_epoch_time_ms"], item["vel"])
            )

            while pending_msgs:
                curr_epoch_time_ms = (
                    float("inf") if archive_only else get_epoch_time_ms()
                )
                msg = pending_msgs[0]

                if not archive_only and msg["send_epoch_time_ms"] > curr_epoch_time_ms:
                    break
                if (
                    not archive_only
                    and curr_epoch_time_ms - msg["send_epoch_time_ms"]
                    > MAX_STREAM_DELAY_MS
                ):
                    pending_msgs.pop(0)
                    continue

                if msg["pitch"] == -1:
                    control_sentinel.set()
                    break

                should_send = False
                should_archive = False
                if msg["vel"] > 0:
                    active_pitch_uuid[msg["pitch"]] = msg["uuid"]
                    should_send = True
                    should_archive = True
                else:
                    if msg.get("adjusted", False):
                        should_send = True
                        should_archive = msg["pitch"] == "pedal"
                    elif active_pitch_uuid.get(msg["pitch"]) == msg["uuid"]:
                        should_send = True
                        should_archive = True
                        active_pitch_uuid.pop(msg["pitch"], None)

                if should_send:
                    midi_out.send(
                        _create_mido_message(
                            msg_dict=msg,
                            channel=0,
                            time_delta_ms=0,
                        )
                    )
                if should_archive:
                    msgs_to_archive.append(msg)

                pending_msgs.pop(0)

            if control_sentinel.is_set():
                break

            time.sleep(0.005)

        last_archive_time_ms = last_channel_msg_epoch_time_ms
        msgs_to_archive.sort(key=lambda item: (item["epoch_time_ms"], item["vel"]))
        for msg in msgs_to_archive:
            time_delta_ms = round(msg["epoch_time_ms"] - last_archive_time_ms)
            msgs.append(
                _create_mido_message(
                    msg_dict=msg,
                    channel=midi_stream_channel,
                    time_delta_ms=time_delta_ms,
                )
            )
            last_archive_time_ms = msg["epoch_time_ms"]

        remaining_off_msgs = [
            msg
            for msg in pending_msgs
            if msg["vel"] == 0
            and msg["pitch"] != "pedal"
            and active_pitch_uuid.get(msg["pitch"]) == msg["uuid"]
        ]
        remaining_off_msgs.sort(key=lambda item: item["epoch_time_ms"])
        for msg in remaining_off_msgs:
            midi_out.send(
                _create_mido_message(
                    msg_dict=msg,
                    channel=0,
                    time_delta_ms=0,
                )
            )
            time_delta_ms = round(msg["epoch_time_ms"] - last_archive_time_ms)
            msgs.append(
                _create_mido_message(
                    msg_dict=msg,
                    channel=midi_stream_channel,
                    time_delta_ms=time_delta_ms,
                )
            )
            last_archive_time_ms = msg["epoch_time_ms"]

        midi_out.send(
            mido.Message("control_change", control=64, value=0, channel=0, time=0)
        )

    results_queue.put(msgs)


def generate_tokens(
    priming_seq: list[Any],
    tokenizer: AbsTokenizer,
    model: TransformerLM,
    prev_context: list[int],
    control_sentinel: threading.Event,
    generated_tokens_queue: queue.Queue,
    num_preceding_active_pitches: int,
    first_on_msg_epoch_ms: int,
    temperature: float,
    min_p: float,
    is_ending: bool,
    trace: list[str],
    metadata: RunMetadata,
    max_new_tokens: int | None,
) -> None:
    priming_seq_len = len(priming_seq)
    start_idx = max(2, priming_seq_len - 3 * (num_preceding_active_pitches + 2) - 1)
    enc_seq = mx.array(
        [
            tokenizer.encode(
                priming_seq + [tokenizer.pad_tok] * (MAX_SEQ_LEN - len(priming_seq))
            )
        ],
        dtype=mx.int32,
    )

    chunked_prefill(
        model=model,
        tokenizer=tokenizer,
        prev_context=prev_context,
        curr_context=enc_seq[0, :start_idx].tolist(),
        full=True,
    )

    enc_seq, priming_seq, next_token_logits = recalc_dur_tokens_chunked(
        model=model,
        priming_seq=priming_seq,
        enc_seq=enc_seq,
        tokenizer=tokenizer,
        start_idx=start_idx,
        metadata=metadata,
    )

    enc_seq, idx = decode_first_tokens(
        model=model,
        first_token_logits=next_token_logits,
        enc_seq=enc_seq,
        priming_seq=priming_seq,
        tokenizer=tokenizer,
        generated_tokens_queue=generated_tokens_queue,
        first_on_msg_epoch_ms=first_on_msg_epoch_ms,
        trace=trace,
        metadata=metadata,
    )

    decode_tokens(
        model=model,
        enc_seq=enc_seq,
        tokenizer=tokenizer,
        control_sentinel=control_sentinel,
        generated_tokens_queue=generated_tokens_queue,
        idx=idx,
        temperature=temperature,
        min_p=min_p,
        is_ending=is_ending,
        trace=trace,
        max_new_tokens=max_new_tokens,
    )


def stream_msgs_headless(
    model: TransformerLM,
    tokenizer: AbsTokenizer,
    msgs: list[mido.Message],
    prev_context: list[int],
    midi_output_port: str | None,
    first_on_msg_epoch_ms: int,
    temperature: float,
    min_p: float,
    num_preceding_active_pitches: int,
    metadata: RunMetadata,
    max_new_tokens: int | None,
    is_ending: bool = False,
) -> tuple[list[mido.Message], list[str]]:
    midi = convert_msgs_to_midi(msgs=msgs)
    midi_dict = MidiDict(**midi_to_dict(midi))
    midi_dict.remove_redundant_pedals()
    priming_seq = tokenizer.tokenize(midi_dict=midi_dict, add_dim_tok=False)
    priming_seq = priming_seq[: priming_seq.index(tokenizer.eos_tok)]

    if priming_seq[-2] == tokenizer.ped_off_tok:
        priming_seq = priming_seq[:-2]
    if is_ending:
        priming_seq.append(tokenizer.dim_tok)

    generated_tokens_queue: queue.Queue = queue.Queue()
    midi_messages_queue: queue.Queue = queue.Queue()
    control_sentinel = threading.Event()
    generated_trace: list[str] = []

    generate_tokens_thread = threading.Thread(
        target=generate_tokens,
        kwargs={
            "priming_seq": priming_seq,
            "tokenizer": tokenizer,
            "model": model,
            "prev_context": prev_context,
            "control_sentinel": control_sentinel,
            "generated_tokens_queue": generated_tokens_queue,
            "temperature": temperature,
            "min_p": min_p,
            "num_preceding_active_pitches": num_preceding_active_pitches,
            "first_on_msg_epoch_ms": first_on_msg_epoch_ms,
            "is_ending": is_ending,
            "trace": generated_trace,
            "metadata": metadata,
            "max_new_tokens": max_new_tokens,
        },
    )
    generate_tokens_thread.start()

    decode_tokens_to_midi_thread = threading.Thread(
        target=decode_tokens_to_midi,
        kwargs={
            "generated_tokens_queue": generated_tokens_queue,
            "outbound_midi_msg_queue": midi_messages_queue,
            "tokenizer": tokenizer,
            "first_on_msg_epoch_ms": first_on_msg_epoch_ms,
            "priming_seq_last_onset_ms": tokenizer.calc_length_ms(
                priming_seq, onset=True
            ),
        },
    )
    decode_tokens_to_midi_thread.start()

    prev_channel_msg_epoch_time_ms = (
        first_on_msg_epoch_ms + tokenizer.calc_length_ms(priming_seq, onset=False)
        if not is_ending
        else first_on_msg_epoch_ms
    )

    stream_midi_results_queue: queue.Queue = queue.Queue()
    stream_midi_thread = threading.Thread(
        target=stream_midi_or_archive,
        kwargs={
            "inbound_midi_msg_queue": midi_messages_queue,
            "msgs": msgs,
            "last_channel_msg_epoch_time_ms": prev_channel_msg_epoch_time_ms,
            "midi_output_port": midi_output_port,
            "control_sentinel": control_sentinel,
            "midi_stream_channel": 0,
            "results_queue": stream_midi_results_queue,
        },
    )
    stream_midi_thread.start()

    generate_tokens_thread.join()
    decode_tokens_to_midi_thread.join()
    stream_midi_thread.join()
    archived_msgs = stream_midi_results_queue.get()
    return archived_msgs, generated_trace


def continuous_prefill(
    model: TransformerLM,
    tokenizer: AbsTokenizer,
    msgs: list[mido.Message],
    received_messages_queue: queue.Queue,
    prev_context: list[int],
) -> tuple[list[mido.Message], list[int]]:
    msg_count = 0
    seen_sentinel = False

    while not seen_sentinel:
        while not seen_sentinel:
            try:
                msg = received_messages_queue.get_nowait()
            except queue.Empty:
                break
            else:
                if msg is None:
                    seen_sentinel = True
                else:
                    msgs.append(msg)
                    msg_count += 1

        if msg_count < 10:
            time.sleep(0.01)
            continue

        midi = convert_msgs_to_midi(msgs=msgs)
        midi_dict = MidiDict(**midi_to_dict(midi))
        midi_dict.remove_redundant_pedals()

        if midi_dict.note_msgs:
            curr_context = tokenizer.encode(
                tokenizer.tokenize(midi_dict, add_dim_tok=False)
            )
            prev_context = chunked_prefill(
                model=model,
                tokenizer=tokenizer,
                prev_context=prev_context,
                curr_context=curr_context,
                full=False,
            )

        msg_count = 0

    return msgs, prev_context


def capture_midi_input(
    midi_performance_queue: queue.Queue,
    control_sentinel: threading.Event,
    reset_sentinel: threading.Event,
    received_messages_queue: queue.Queue,
    midi_capture_channel: int,
    results_queue: queue.Queue,
    first_msg_epoch_time_ms: int | None = None,
    wait_for_close: bool = False,
) -> None:
    first_on_msg_epoch_ms = None
    prev_msg_epoch_time_ms = first_msg_epoch_time_ms
    pedal_down = False
    pitches_held_down: set[int] = set()
    pitches_sustained_by_pedal: set[int] = set()

    while not midi_performance_queue.empty():
        try:
            midi_performance_queue.get_nowait()
        except queue.Empty:
            break

    while True:
        epoch_time_ms = get_epoch_time_ms()
        active_notes = pitches_held_down.union(pitches_sustained_by_pedal)
        should_stop = (not wait_for_close) or (not active_notes)
        if reset_sentinel.is_set() or (control_sentinel.is_set() and should_stop):
            break

        try:
            msg = midi_performance_queue.get(block=True, timeout=0.01)
        except queue.Empty:
            continue

        if msg.is_meta or msg.type == "program_change":
            continue

        msg.channel = midi_capture_channel
        if prev_msg_epoch_time_ms is None:
            msg.time = 0
        else:
            msg.time = epoch_time_ms - prev_msg_epoch_time_ms

        prev_msg_epoch_time_ms = epoch_time_ms

        match msg.type:
            case "note_on" if msg.velocity > 0:
                if first_on_msg_epoch_ms is None:
                    first_on_msg_epoch_ms = (
                        get_epoch_time_ms() - HARDWARE_INPUT_LATENCY_MS
                    )
                pitches_held_down.add(msg.note)
                if pedal_down:
                    pitches_sustained_by_pedal.add(msg.note)
                received_messages_queue.put(msg)
            case "note_off" | "note_on":
                pitches_held_down.discard(msg.note)
                received_messages_queue.put(msg)
            case "control_change" if msg.control == 64:
                was_down = pedal_down
                if msg.value >= 64:
                    pedal_down = True
                    pitches_sustained_by_pedal.update(pitches_held_down)
                else:
                    pedal_down = False
                    pitches_sustained_by_pedal.clear()
                if pedal_down != was_down:
                    received_messages_queue.put(msg)

    active_pitches = pitches_held_down.union(pitches_sustained_by_pedal)
    num_active_pitches = len(active_pitches)
    time_offset = (
        0
        if prev_msg_epoch_time_ms is None
        else get_epoch_time_ms() - prev_msg_epoch_time_ms
    )

    for pitch in pitches_held_down:
        note_off_msg = mido.Message(
            "note_off",
            note=pitch,
            channel=midi_capture_channel,
            time=time_offset,
        )
        received_messages_queue.put(note_off_msg)
        time_offset = 0

    received_messages_queue.put(
        mido.Message(
            "control_change",
            control=64,
            value=0,
            channel=midi_capture_channel,
            time=0,
        )
    )
    received_messages_queue.put(None)
    results_queue.put((first_on_msg_epoch_ms, num_active_pitches))


def capture_and_update_kv(
    model: TransformerLM,
    tokenizer: AbsTokenizer,
    msgs: list[mido.Message],
    prev_context: list[int],
    control_sentinel: threading.Event,
    reset_sentinel: threading.Event,
    wait_for_close: bool,
    midi_performance_queue: queue.Queue,
) -> tuple[list[mido.Message], list[int], int | None, int]:
    received_messages_queue: queue.Queue = queue.Queue()
    results_queue: queue.Queue = queue.Queue()

    capture_thread = threading.Thread(
        target=capture_midi_input,
        kwargs={
            "midi_performance_queue": midi_performance_queue,
            "control_sentinel": control_sentinel,
            "reset_sentinel": reset_sentinel,
            "received_messages_queue": received_messages_queue,
            "midi_capture_channel": 0,
            "results_queue": results_queue,
            "wait_for_close": wait_for_close,
        },
    )
    capture_thread.start()

    msgs, prev_context = continuous_prefill(
        model=model,
        tokenizer=tokenizer,
        msgs=msgs,
        received_messages_queue=received_messages_queue,
        prev_context=prev_context,
    )
    capture_thread.join()
    first_on_msg_epoch_ms, num_active_pitches = results_queue.get()
    return msgs, prev_context, first_on_msg_epoch_ms, num_active_pitches


def replay_midi_file(
    midi_path: str,
    midi_performance_queue: queue.Queue,
    midi_through_port: str | None,
    currently_generating_sentinel: threading.Event,
    reset_sentinel: threading.Event,
    takeover_started_event: threading.Event,
    first_note_started_event: threading.Event,
    first_note_epoch_holder: dict[str, int],
) -> None:
    def _enqueue_message(msg: mido.Message) -> None:
        midi_performance_queue.put(msg)

    if BASE_OUTPUT_LATENCY_MS > 0:
        midi_dict = MidiDict.from_midi(midi_path)
        midi_dict.remove_redundant_pedals()
        midi_dict.enforce_gaps(min_gap_ms=MIN_NOTE_DELTA_MS)
        mid = midi_dict.to_midi()
    else:
        mid = mido.MidiFile(midi_path)

    time.sleep(1)
    if midi_through_port is None:
        output_cm = contextlib.nullcontext(NullMidiOut())
    else:
        output_cm = mido.open_output(midi_through_port)

    with output_cm as through_port:
        for msg in mid.play():
            if reset_sentinel.is_set() or takeover_started_event.is_set():
                return

            if (
                not first_note_started_event.is_set()
                and msg.type == "note_on"
                and msg.velocity > 0
            ):
                first_note_epoch_holder["epoch_ms"] = get_epoch_time_ms()
                first_note_started_event.set()

            if not currently_generating_sentinel.is_set():
                through_port.send(msg)

            timer = threading.Timer(
                interval=HARDWARE_INPUT_LATENCY_MS / 1000.0,
                function=_enqueue_message,
                args=[msg],
            )
            timer.start()


def auto_trigger_takeover(
    control_sentinel: threading.Event,
    reset_sentinel: threading.Event,
    first_note_started_event: threading.Event,
    first_note_epoch_holder: dict[str, int],
    takeover_ms: int,
) -> None:
    if not first_note_started_event.wait(timeout=30):
        return

    target_epoch_ms = first_note_epoch_holder["epoch_ms"] + takeover_ms
    while not reset_sentinel.is_set() and not control_sentinel.is_set():
        remaining_ms = target_epoch_ms - get_epoch_time_ms()
        if remaining_ms <= 0:
            control_sentinel.set()
            return
        time.sleep(min(0.01, remaining_ms / 1000))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Faithful headless replay harness for demo_mlx.py."
    )
    parser.add_argument(
        "prompt_midi",
        nargs="?",
        default=os.path.join(ARIA_DIR, "example-prompts", "waltz.mid"),
    )
    parser.add_argument(
        "--takeover-ms",
        type=int,
        default=10000,
        help="Wall-clock offset from first prompt note to trigger AI takeover.",
    )
    parser.add_argument(
        "--checkpoint",
        default=str(EXPERIMENT_DIR / "checkpoints" / "model-demo.safetensors"),
    )
    parser.add_argument(
        "--embedding-checkpoint",
        default=str(EXPERIMENT_DIR / "checkpoints" / "model-embedding.safetensors"),
    )
    parser.add_argument(
        "--embedding-midi",
        default=None,
        help="Reference MIDI used for the style embedding. Defaults to prompt_midi.",
    )
    parser.add_argument("--no-embedding", action="store_true")
    parser.add_argument(
        "--midi-out",
        default=None,
        help="Optional MIDI output port for generated notes.",
    )
    parser.add_argument(
        "--midi-through",
        default=None,
        help="Optional MIDI output port for replaying the prompt during capture.",
    )
    parser.add_argument(
        "--hardware",
        default=str(EXPERIMENT_DIR / "hardware" / "software-routing.json"),
    )
    parser.add_argument("--temp", type=float, default=0.95)
    parser.add_argument("--min-p", type=float, default=0.03)
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512,
        help="Cap offline generation length for faithful one-shot analysis.",
    )
    parser.add_argument("--wait-for-close", action="store_true")
    parser.add_argument(
        "--save",
        default=None,
        help="Path for the output MIDI file. Defaults to recordings/faithful-*.mid.",
    )
    return parser


def save_metadata(metadata: RunMetadata) -> None:
    data = asdict(metadata)
    data["duration_replacements"] = [
        asdict(item) for item in metadata.duration_replacements
    ]
    data["beam_choice"] = (
        asdict(metadata.beam_choice) if metadata.beam_choice is not None else None
    )
    with open(metadata.metadata_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def enrich_output_stats(output_path: str, metadata: RunMetadata) -> None:
    midi_dict = MidiDict.from_midi(output_path)
    notes = midi_dict.note_msgs
    metadata.output_note_count = len(notes)
    if notes:
        last_tick = max(note["data"]["end"] for note in notes)
        metadata.output_duration_ms = midi_dict.tick_to_ms(last_tick)


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    prompt_midi = os.path.abspath(args.prompt_midi)
    embedding_midi = (
        None
        if args.no_embedding
        else os.path.abspath(args.embedding_midi or args.prompt_midi)
    )

    if not os.path.isfile(prompt_midi):
        raise FileNotFoundError(f"Prompt MIDI not found: {prompt_midi}")
    if not os.path.isfile(args.checkpoint):
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")
    if not args.no_embedding and not os.path.isfile(args.embedding_checkpoint):
        raise FileNotFoundError(
            f"Embedding checkpoint not found: {args.embedding_checkpoint}"
        )
    if embedding_midi and not os.path.isfile(embedding_midi):
        raise FileNotFoundError(f"Embedding MIDI not found: {embedding_midi}")

    set_calibration_settings(args.hardware)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_path = args.save or str(
        EXPERIMENT_DIR / "recordings" / f"faithful-{timestamp}.mid"
    )
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    metadata_path = str(pathlib.Path(output_path).with_suffix(".json"))

    metadata = RunMetadata(
        prompt_midi=prompt_midi,
        output_midi=output_path,
        metadata_json=metadata_path,
        checkpoint=os.path.abspath(args.checkpoint),
        embedding_checkpoint=(
            None if args.no_embedding else os.path.abspath(args.embedding_checkpoint)
        ),
        embedding_midi=embedding_midi,
        takeover_ms=args.takeover_ms,
        temperature=args.temp,
        min_p=args.min_p,
        wait_for_close=args.wait_for_close,
        midi_out=args.midi_out,
        midi_through=args.midi_through,
        used_embedding=not args.no_embedding,
        started_at_epoch_ms=get_epoch_time_ms(),
    )

    config_path = pathlib.Path(ARIA_DIR, "demo", "config.json")
    tokenizer = load_tokenizer(config_path=config_path)
    model = load_model(checkpoint_path=args.checkpoint, tokenizer=tokenizer)

    if not args.no_embedding:
        logging.info("Computing conditioning embedding from %s", embedding_midi)
        embedding = compute_embedding(
            checkpoint_path=args.embedding_checkpoint,
            midi_path=embedding_midi,
        )
        insert_embedding(model=model, embedding=embedding)

    prompt_midi_dict = MidiDict.from_midi(prompt_midi)
    metadata.prompt_note_count = len(prompt_midi_dict.note_msgs)

    midi_performance_queue: queue.Queue = queue.Queue()
    control_sentinel = threading.Event()
    reset_sentinel = threading.Event()
    currently_generating_sentinel = threading.Event()
    takeover_started_event = threading.Event()
    first_note_started_event = threading.Event()
    first_note_epoch_holder: dict[str, int] = {}

    replay_thread = threading.Thread(
        target=replay_midi_file,
        kwargs={
            "midi_path": prompt_midi,
            "midi_performance_queue": midi_performance_queue,
            "midi_through_port": args.midi_through,
            "currently_generating_sentinel": currently_generating_sentinel,
            "reset_sentinel": reset_sentinel,
            "takeover_started_event": takeover_started_event,
            "first_note_started_event": first_note_started_event,
            "first_note_epoch_holder": first_note_epoch_holder,
        },
    )
    replay_thread.start()

    takeover_thread = threading.Thread(
        target=auto_trigger_takeover,
        kwargs={
            "control_sentinel": control_sentinel,
            "reset_sentinel": reset_sentinel,
            "first_note_started_event": first_note_started_event,
            "first_note_epoch_holder": first_note_epoch_holder,
            "takeover_ms": args.takeover_ms,
        },
    )
    takeover_thread.start()

    msgs, prev_context, first_on_msg_epoch_ms, num_active_pitches = (
        capture_and_update_kv(
            model=model,
            tokenizer=tokenizer,
            msgs=[],
            prev_context=[],
            control_sentinel=control_sentinel,
            reset_sentinel=reset_sentinel,
            wait_for_close=args.wait_for_close,
            midi_performance_queue=midi_performance_queue,
        )
    )

    takeover_started_event.set()
    currently_generating_sentinel.set()
    replay_thread.join()
    takeover_thread.join()

    if first_on_msg_epoch_ms is None:
        raise RuntimeError("No note-on was captured before takeover.")

    metadata.first_on_msg_epoch_ms = first_on_msg_epoch_ms
    metadata.num_preceding_active_pitches = num_active_pitches

    prompt_archive = convert_msgs_to_midi(msgs=msgs)
    prompt_archive_path = str(
        pathlib.Path(output_path).with_name(
            f"{pathlib.Path(output_path).stem}-prompt.mid"
        )
    )
    prompt_archive.save(prompt_archive_path)

    logging.info(
        "Captured %s MIDI messages before takeover (%s active pitches).",
        len(msgs),
        num_active_pitches,
    )

    archived_msgs, generated_trace = stream_msgs_headless(
        model=model,
        tokenizer=tokenizer,
        msgs=msgs,
        prev_context=prev_context,
        midi_output_port=args.midi_out,
        first_on_msg_epoch_ms=first_on_msg_epoch_ms,
        temperature=args.temp,
        min_p=args.min_p,
        num_preceding_active_pitches=num_active_pitches,
        metadata=metadata,
        max_new_tokens=args.max_new_tokens,
    )

    result_midi = convert_msgs_to_midi(archived_msgs)
    result_midi.save(output_path)

    captured_midi_dict = MidiDict(**midi_to_dict(prompt_archive))
    captured_midi_dict.remove_redundant_pedals()
    prompt_tokens = tokenizer.tokenize(captured_midi_dict, add_dim_tok=False)
    metadata.prompt_token_count = max(
        0,
        (
            prompt_tokens.index(tokenizer.eos_tok)
            if tokenizer.eos_tok in prompt_tokens
            else len(prompt_tokens)
        ),
    )
    metadata.generated_token_count = len(generated_trace)
    metadata.generated_token_trace = generated_trace[:20]
    metadata.generated_note_token_count = sum(
        1 for token in generated_trace if token.startswith("('piano',")
    )
    metadata.generated_time_token_count = generated_trace.count(
        repr(tokenizer.time_tok)
    )
    metadata.generated_pedal_token_count = sum(
        1
        for token in generated_trace
        if token in {repr(tokenizer.ped_on_tok), repr(tokenizer.ped_off_tok)}
    )
    metadata.finished_at_epoch_ms = get_epoch_time_ms()
    enrich_output_stats(output_path=output_path, metadata=metadata)
    save_metadata(metadata)

    logging.info("Saved prompt capture to %s", prompt_archive_path)
    logging.info("Saved faithful demo output to %s", output_path)
    logging.info("Saved run metadata to %s", metadata_path)
    logging.info(
        "Generated %s tokens (%s notes, %s time, %s pedal).",
        metadata.generated_token_count,
        metadata.generated_note_token_count,
        metadata.generated_time_token_count,
        metadata.generated_pedal_token_count,
    )


if __name__ == "__main__":
    main()
