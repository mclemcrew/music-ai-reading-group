# ARIA Duet — Research Notes & Continuation Guide

Investigation session: 2026-04-09

---

## 2026-04-10 Update

Use `faithful_headless_demo.py` as the fidelity baseline for the NeurIPS
demo path. It replays a prompt MIDI file through the actual capture /
continuous-prefill / duration-recalc / beam-handoff pipeline, with
conditioning enabled by default.

`test_chunked_gen.py` remains useful as a standalone comparison, but it is
not a faithful reproduction of the live demo because it repeats beam search
per chunk and adds hard masking / density-forcing behavior that the original
demo does not use.

---

## What We Learned

### The NeurIPS Demo Architecture
The "Ghost in the Keys" demo (https://youtu.be/8s3V922h3CU) is an
**interactive turn-taking system**, not a standalone generator. The quality
comes from:
1. **Short bursts** (~2-5s of AI generation per turn)
2. **Beam search** (width=3) for the first 2 tokens with TIME_TOK_WEIGHTING=-5
3. **Duration recalculation** (speculative decoding to fix hanging notes)
4. **Human context refresh** (KV cache continuously filled as human plays)
5. **Style embedding** injected into KV cache position 0 via `fill_condition_kv()`
6. **Disklavier hardware** (real acoustic piano, velocity-dependent latency compensation)

The paper explicitly says nothing about sampling parameters. Upstream
defaults are `temp=0.95, min_p=0.03` for the interactive demo.

### Three Model Checkpoints
| Checkpoint | Vocab | Config | Purpose |
|------------|-------|--------|---------|
| `model-demo.safetensors` | 17729 (pedal) | `medium-emb` | Interactive demo with embedding adapter |
| `model-gen.safetensors` | 17727 (no pedal) | `medium` | Standalone generation (HF quickstart) |
| `model-embedding.safetensors` | 17727 | `medium-emb` | Compute style embeddings (`TransformerEMB`) |

HuggingFace repos:
- https://huggingface.co/loubb/aria-medium-base (base + gen + demo checkpoints)
- https://huggingface.co/loubb/aria-medium-embedding (embedding model)

### Key Technical Findings

**1. HuggingFace custom code has NO grammar constraints.**
`modeling_aria.py` is a standard transformer with `GenerationMixin`.
No `LogitsProcessor`, no custom `generate()`. The quickstart
(`temp=0.97, top_p=0.95`) is the entire recipe.

**2. Grammar constraints are essential for valid sequences.**
Without them, both model-demo and model-gen produce invalid token
sequences (note→note without onset/dur, pedal spam, instrument drift).
The model was NOT trained to output valid sequences autonomously at
long generation lengths.

**3. model-demo has extreme pedal bias.**
At free positions, `<PED_OFF>` has 30-95% probability. The PED_OFF +3
boost makes this worse. The `last_tok_is_pedal` reset bug (only resets
on "piano" tuples, not all non-pedal tokens) causes duration masking
to persist through non-pedal tokens.

**4. Vocabulary asymmetry causes `<T>` dominance.**
One `<T>` token absorbs ~18% of "silence" probability. Hundreds of
note tokens split ~40% collectively (<0.5% each). `min_p` sampling
catastrophically filters all note tokens. `top_p` works because it
considers cumulative probability.

**5. Style prefix tokens significantly improve density.**
The model was trained with `('prefix', 'form', 'waltz')` etc. Adding
these before `<S>` conditions the model's output distribution.

**6. Conditioned generation (embedding) improves quality.**
The style embedding from `model-embedding.safetensors` is the mechanism
the NeurIPS demo uses to stay on-style. Without it, standalone output
drifts and thins. With it, classical output reached 195 notes/min.

**7. Four upstream MLX bugs blocked conditioned generation.**
- `fill_condition_kv` passes wrong args (missing `max_kv_pos`)
- `pad_idxs` shape mismatch with causal mask
- `prefill`/`decode_one` missing `max_kv_pos`
- `sample_batch_cfg` cache size off-by-one
All four fixed directly in the local aria repo (CHANGES.md S19).
No more monkey-patching needed.

**8. The density problem was an architecture mismatch, not a model limitation.**
The model degenerates during long autoregressive runs because:
- `<T>` dominance: one token absorbs ~18% probability at free positions
- Without beam search, the model starts chunks with silence/pedal
- Small errors compound → sparsity snowball

The NeurIPS demo avoids this with short bursts + beam search + human
context refresh. Replicating this loop headlessly (chunked generation
with periodic beam search) solved the density problem completely.

**9. Producing chords requires masking `<T>` until enough notes are generated.**
Even with chunked beam search, the model generates 1-2 single notes
then immediately emits `<T>` (5s of silence). The fix: `min_notes_before_time`
parameter fully masks `<T>` until N notes are generated in the chunk.
Combined with `TIME_PENALTY=3.0`, this forces the model to produce
chords and passages instead of isolated notes.

---

## Files Created This Session

| File | Purpose |
|------|---------|
| `sweep_generate.py` | Rewritten standalone gen (model-gen, grammar, prefixes, time penalty) |
| `test_demo_generation.py` | Headless test of demo pipeline (model-demo, beam search, dur recalc) |
| `test_conditioned_gen.py` | Conditioned gen with style embedding (model-demo + model-embedding) |
| `test_cfg_gen.py` | CFG double-model approach (conditioned vs unconditioned blending) |
| `test_batched_cfg.py` | Batched CFG: single model, batch=2 (conditioned + unconditioned) |
| `test_chunked_gen.py` | **BEST**: chunked beam search + time penalty + min_notes (chords, 329-1123 n/min) |
| `recordings/all-demos/*.mid` | Final outputs for all 6 prompts |
| `recordings/test-run/*.mid` | Earlier test outputs for comparison |

---

## Next Steps to Improve Generation Quality

### ~~Priority 1: Fix upstream MLX bugs~~ DONE
Fixed 4 bugs directly in local aria repo (CHANGES.md S19). No monkey-patching.

### ~~Priority 2: Batched CFG on MLX~~ DONE
`test_batched_cfg.py` — single model, batch=2, shared KV cache.

### ~~Priority 3: Headless demo pipeline~~ DONE
`test_chunked_gen.py` — chunked beam search replicates the demo loop.

### ~~Priority 4: Fix density / produce chords~~ DONE
`TIME_PENALTY=3.0` + `min_notes_before_time` forces chords.
All 6 prompts produce dense multi-note output (329–1123 n/min).

### Priority 1 (CURRENT): Musical quality evaluation
- Listen to `recordings/all-demos/*.mid` in a DAW
- Evaluate: harmonic coherence, rhythm, style matching, transitions
- Density is solved — the question is whether the notes sound GOOD
- Per-style parameter tuning: `--min_notes`, `--max_notes_per_chunk`

### Priority 2: Duration recalculation between chunks
The demo's speculative decoding for hanging notes (`recalc_dur_tokens_chunked`)
prevents notes from consuming entire time segments. `test_demo_generation.py`
has a working implementation. Adding this between chunks would improve
note timing and make room for more notes within segments.

### Priority 3: Combine chunked gen with CFG
The batched CFG and chunked gen are separate scripts. Combining them
(chunked beam search + CFG logit blending) might improve style adherence
while maintaining density.

### Priority 4: First-chunk pedal spam
Chunks 1 sometimes generates excessive pedal events (13-22 pedal tokens)
because the prompt context is pedal-heavy. This settles by chunk 2.
Could mask PED_ON/PED_OFF entirely for the first chunk, or increase
pedal penalty for the first N tokens.

### Priority 5: Try the ISMIR 2025 model
The GitHub README references "Scaling Self-Supervised Representation
Learning for Symbolic Piano Performance (ISMIR 2025)" — newer paper,
possibly updated checkpoints with better generation quality.

### Priority 6: Submit upstream PRs
The 4 MLX bug fixes should be upstreamed to the aria repo:
- `fill_condition_kv` arg fix
- `pad_idxs` shape slice
- `max_kv_pos` in prefill/decode_one
- `sample_batch_cfg` cache size

---

## How to Resume This Work

### Prompt for next session

```
We've been working on /Users/mclemens/Development/music-ai-reading-group/experiments/aria-duet
to get the ARIA piano model generating music that matches the NeurIPS demo quality.

Read CHANGES.md (sections 1-20) and RESEARCH-NOTES.md for full context.

Current state: test_chunked_gen.py produces dense, multi-note output
with chords for all 6 example prompts (329-1123 n/min). The density
problem is solved. 4 upstream MLX bugs were fixed directly in the aria
repo, no monkey-patching needed.

Best approach: chunked generation with periodic beam search + time
penalty + min_notes_before_time. Per-style tuning via CLI args.

Output MIDI files: recordings/all-demos/*.mid

Next priorities:
1. Listen to outputs and evaluate musical quality (not just density)
2. Add duration recalculation between chunks
3. Combine chunked gen with CFG for better style adherence
4. Fix first-chunk pedal spam

All three checkpoints in checkpoints/:
  model-demo.safetensors (vocab 17729, interactive + embedding adapter)
  model-gen.safetensors (vocab 17727, generation-finetuned)
  model-embedding.safetensors (style embedding computation)
```

### Key files to read first
1. `CHANGES.md` — full debugging history (sections 1-20)
2. `RESEARCH-NOTES.md` — this file
3. `test_chunked_gen.py` — **BEST approach** (chunked beam search + time penalty)
4. `test_conditioned_gen.py` — single-pass conditioned gen (simpler)
5. `test_batched_cfg.py` — batched CFG (works, not yet combined with chunked)
6. `/Users/mclemens/Development/aria/aria/inference/model_mlx.py` — upstream fixes
7. `/Users/mclemens/Development/aria/demo/demo_mlx.py` — reference demo
