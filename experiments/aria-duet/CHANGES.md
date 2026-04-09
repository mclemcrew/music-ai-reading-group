# Aria Duet — Changes & Debugging Notes

Notes from getting the real-time piano duet demo running with a CASIO
USB-MIDI keyboard, Ableton Live, and the Aria 0.7B model via MLX on
Apple Silicon.

---

## 1. Portability & Configuration

### Problem
Paths and MIDI port names were hardcoded (e.g. `/Users/mclemens/Development/aria`,
`IAC Driver Bus 1`). Others downloading the repo couldn't run it without
editing scripts by hand. Not everyone is on macOS, and people may have
multiple MIDI controllers.

### What we did
- **`config.example.sh`** — checked-in template with `ARIA_DIR` and
  optional `MIDI_OUT` / `MIDI_THROUGH` / `MIDI_IN` presets.
- **`config.sh`** — local copy (gitignored) sourced by every run script.
  Auto-created from the template on first run.
- **`pick-midi-port.py`** — interactive port picker. Scans available
  ports at runtime, auto-selects if only one exists, uses preset
  silently if configured, and falls back to a numbered menu. Prompts go
  to stderr; the chosen name goes to stdout for shell capture.
- **`setup.sh`**, **`run-demo-live.sh`**, **`run-demo-file.sh`**,
  **`run-playback-only.sh`** — all updated to source `config.sh` and
  call `pick-midi-port.py` instead of using hardcoded values.

---

## 2. ariautils Version Compatibility

### Problem
The installed `ariautils` (HEAD, commit `93da092`) requires
`include_drums`, `include_pedal`, and `include_delimiter` keys in
`config.json`. The demo's config didn't have them, causing a `KeyError`.

### What we did
- Tested all 8 combinations of `(drums, pedal, delimiter)` against the
  model checkpoint embedding shape of **17729**.
- Correct combo: `include_drums: true, include_pedal: true,
  include_delimiter: false` → vocab size 17729. Added to
  `demo/config.json`.

---

## 3. Decoder Crashes from Pedal Token Runs

The model sometimes generates degenerate token sequences with pedal
tokens in unexpected positions. We hit (and fixed) four distinct crash
patterns:

### 3a. Pedal tokens between note and onset
**Buffer:** `[('piano',54,40), '<PED_ON>', '<PED_OFF>'×40, ('onset',1550)]`

The decoder expected `[note, onset, dur]` or `[pedal, onset]` but got
pedal tokens wedged between a note instrument and its onset.

### 3b. No `dur` tokens generated
**Buffer:** `[('piano',51,60), ('onset',1430), ('onset',2570), ...]`

**Root cause:** `last_tok_is_pedal` was only reset when the next token
was a `"piano"` instrument tuple. After any pedal token, duration logits
stayed masked indefinitely — through onset tokens, time tokens, etc.

**Fix:** Reset `last_tok_is_pedal = False` on ALL non-pedal tokens, not
just piano instrument tokens.

### 3c. Time tokens interleaved in pedal runs
**Buffer:** `['<PED_OFF>', '<T>', '<PED_OFF>', '<PED_ON>', ..., ('onset',1780)]`

Time tokens embedded inside pedal runs broke the pattern-based
stripping.

**Fix:** Rewrote the decoder buffer cleanup to:
1. Count and remove `<T>` tokens from anywhere in the buffer.
2. For pedal messages: save any note instrument tuple for the next
   iteration, keep only the last pedal token + onset.
3. For note messages: strip all pedal tokens, keep note + onset + dur.
4. Skip degenerate note buffers that have no instrument after stripping
   (e.g. `[PED_ON, PED_ON, onset, dur]` → `[onset, dur]`).

### 3d. Buffer with no instrument after pedal stripping
**Buffer:** `[<PED_ON>, <PED_ON>, ('onset', ...), ('dur', ...)]`

After stripping pedals from what was classified as a "note" message,
only `[onset, dur]` remained — no instrument tuple.

**Fix:** Detect `len(note_buffer) < 3` after pedal stripping and skip
the degenerate buffer instead of crashing.

---

## 4. CC64 Pedal Message Flooding

### Problem
The CASIO keyboard sends **continuous CC64** sustain pedal values
(half-pedaling support). A single pedal press/release generates **30+
CC64 messages** ramping through values like
0,2,4,8,12,20,26,34,40,48,54,61,67,75,82,88,95,98,104,110,115,120,123,125,126,127.

The capture code forwarded every CC64 message to the queue. When
tokenized, values oscillating around the 64 threshold created many
`PED_ON`/`PED_OFF` tokens. The priming sequence became dominated by
pedal tokens, causing the model to generate almost exclusively pedal
tokens.

`remove_redundant_pedals()` helps but can't fully counteract the flood
of threshold-crossing events.

### Fix
Track pedal state transitions instead of forwarding every CC64 value:

```python
case "control_change" if msg.control == 64:
    was_down = pedal_down
    if msg.value >= 64:
        pedal_down = True
        pitches_sustained_by_pedal.update(pitches_held_down)
    else:
        pedal_down = False
        pitches_sustained_by_pedal.clear()
    # Only forward state changes, not continuous CC64 values
    if pedal_down != was_down:
        received_messages_queue.put(msg)
```

Pitch tracking (`pitches_sustained_by_pedal`) still updates on every
CC64 message for correct note-off behavior — only the queue message is
gated.

Logging was also moved inside the forwarding branches so only actual
state changes appear in the stream.

---

## 5. Beam Search Pedal Bias

### Problem
Even after fixing the CC64 flood, the beam search for the first two
generated tokens kept choosing `('<PED_ON>', '<PED_ON>')` (combined
score ≈ −1.4) over actual notes like `(('piano', 68, 70), '<PED_ON>')`
(score ≈ −3.5). The second `<PED_ON>` is grammatically invalid — after
`PED_ON` the next token must be an onset.

The beam search masked `PED_OFF` as a second token but not `PED_ON`,
allowing the degenerate pair.

### Fix
Added a grammar constraint: when the first beam token is `PED_ON`, mask
everything except onset token IDs for the second position:

```python
if tok_id == ped_on_id:
    mask = mx.full(next_log_probs.shape, float("-inf"))
    for oid in onset_ids:
        mask[:, oid] = 0.0
    next_log_probs = next_log_probs + mask
```

`PED_ON` can still win as the first token if the model wants it, but
the second token is forced to be an onset — producing a valid
`(PED_ON, onset)` pedal message.

---

## 6. Full Grammar Constraints in Generation Loop

### Problem
After fixing the beam search (section 5), the first two tokens were
valid but the autoregressive generation loop (`decode_tokens`) had no
grammar enforcement. The model could generate any token at any
position, producing sequences like:

- Note without onset: `('piano', 82, 60), ('dur', 5000)` — skipped
  by decoder as degenerate
- Pedal consuming a note's onset: `note → onset → PED_ON →
  onset(stolen) → dur(orphaned)`
- Stray `dur` tokens at free positions with no preceding note+onset
- Prefix metadata tokens mid-generation: `('prefix', 'instrument',
  'piano'), ('piano', 86, 50), ('onset', 660), ('dur', 3090)` —
  caused assertion errors in the decoder

A `+3` logit boost on `PED_OFF` (manual adjustment from the original
demo code) also amplified pedal bias.

### What we did
Removed the PED_OFF boost and added comprehensive grammar constraints
to `decode_tokens()`:

1. **Mask prefix tokens** — prefix tuples are metadata, never valid
   during generation.
2. **After note/drum/pedal → force onset** — only onset token IDs
   are unmasked.
3. **After onset → force dur if preceded by note/drum** — checks
   `prev_prev_tok` to determine if this is a note triple or pedal
   pair.
4. **After pedal+onset → mask mid-event tokens** — `dur` and `onset`
   masked so only event starters remain.
5. **Free positions (after dur, time, etc.) → mask mid-event tokens**
   — same masking so only note/pedal/time tokens are valid.

Also added prefix stripping in the decoder (`decode_tokens_to_midi`)
as a safety net for any prefix tokens that slip through.

---

## 7. Beam Search Grammar Constraint for Note Instruments

### Problem
The beam search constraint from section 5 only handled `PED_ON` as
the first token. When a note instrument token like `('piano', 75, 70)`
won the first beam position, `PED_ON` could still win the second
position — producing the invalid pair `(note, PED_ON)` instead of the
required `(note, onset)`.

The orphaned note re-entered the decoder buffer every iteration via
the `saved_note` mechanism, but the model never generated a matching
onset+duration, resulting in an infinite loop of pedal CC64 messages.

### Fix
Added a grammar constraint for note/drum instrument tokens in
`decode_first_tokens()`: when the first beam token is a note
(3-tuple with instrument != "prefix") or drum (2-tuple with "drum"),
mask everything except onset token IDs for the second position.

```python
if isinstance(tok, tuple) and (
    (len(tok) == 3 and tok[0] != "prefix")
    or (len(tok) == 2 and tok[0] == "drum")
):
    mask = mx.full(next_log_probs.shape, float("-inf"))
    for oid in onset_ids:
        mask[:, oid] = 0.0
    next_log_probs = next_log_probs + mask
```

---

## 8. Pedal Probability Bias

### Problem
Even with all grammar constraints in place, the model has a strong
intrinsic bias toward pedal tokens at free positions (~90% probability
for `PED_ON` at event boundaries). Output was dominated by
`PED_ON`/`PED_OFF` events with sparse notes between them.

### Fix
Added a negative logit bias (`PEDAL_PENALTY = 5.0`) on `PED_ON` and
`PED_OFF` at free positions in `decode_tokens()` — both after
pedal+onset completes and at general event boundaries (after dur,
time, etc.). This shifts probability toward note instrument tokens
without completely blocking pedal events.

Also applied a `-4.0` penalty on `PED_ON` in the beam search
(`decode_first_tokens()`) before top-K candidate selection, preventing
pedal from dominating the first generated token.

---

## 9. Alternative Checkpoints & Temperature

### Investigation
Explored using `model-gen.safetensors` from `loubb/aria-medium-base`
(a checkpoint finetuned specifically for generation). However, it has
vocab size **17727** vs the demo checkpoint's **17729** — the gen model
was trained without pedal tokens (`include_pedal: false`), making it
incompatible with the demo code's pedal handling logic.

The base pretrained `model.safetensors` (also 17727) has the same
incompatibility.

### Current tuning
Raised temperature to **0.95** (upstream default) and min_p to
**0.03**. Earlier attempts at 0.5 were catastrophically low —
see section 10.

---

## 10. Temperature & Penalty Retuning

### Problem
Output was severely degenerate: only 3–4 notes per generation,
all the same pitch (G4), separated by 5+ seconds of silence, then
infinite `<T>` tokens (the model "giving up").

### Root cause
The token vocabulary is highly asymmetric: one `<T>` (time/silence)
token vs. hundreds of individual note tokens. At temp=0.5, logits
are divided by 0.5 (effectively doubled), making the distribution
extremely peaked. The single `<T>` token's concentrated probability
mass wins at nearly every free position.

Additionally, the aggressive `PEDAL_PENALTY` of 5.0 on PED_ON/PED_OFF
was shifting probability mass to `<T>` rather than to notes — making
sparseness worse.

**Historical note:** Upstream commit `b0486c8` ("Fix temperature in
demo") added `logits / temperature` to the decode loop. Before this
fix, temperature had no effect on autoregressive generation — it was
always effective temp=1.0. The NeurIPS demo may have been running
with this bug.

### What we did
1. **Raised temperature** from 0.5 to **0.95** (upstream default).
   At this temperature the distribution is flat enough for diverse
   note tokens to compete against `<T>`.
2. **Raised min_p** from 0.05 to **0.03** (upstream default). Less
   filtering of low-probability tokens allows more diversity.
3. **Reduced PEDAL_PENALTY** from 5.0 to **2.0** in `decode_tokens()`
   and from 4.0 to **2.0** in `decode_first_tokens()`. Still
   discourages pedal dominance without pushing mass to `<T>`.
4. **Added constant `<T>` penalty** (`TIME_PENALTY = 2.0`) at all
   free positions in `decode_tokens()`. The model has a strong
   intrinsic bias toward `<T>` (a single token with concentrated
   probability mass vs. hundreds of individual note tokens). Without
   this penalty, ~12.7% of generated tokens are `<T>`, producing
   only ~7 notes per minute instead of the hundreds expected for a
   waltz. The penalty shifts probability toward note instruments.
5. **Added consecutive `<T>` limiter**: after 1 consecutive `<T>`
   token (5 seconds of silence), an additional −5.0 penalty is
   applied. Prevents the model from generating long silence runs.

---

## 11. Penalties A/B Toggle & Upstream-Minimal Mode

### Problem
After all the fixes in sections 3–10, we had accumulated significant
custom logit penalties (pedal, time, consecutive `<T>` limiter) on top
of the upstream demo code. Comparing against the HuggingFace quickstart
(`temp=0.97, top_p=0.95`) and the upstream defaults raised the question:
are our custom penalties actually helping, or are they fighting the
model's natural behavior?

### What we did
Added a `--penalties` CLI flag to `demo_mlx.py` that toggles between
two modes:

**Default: upstream-minimal (no `--penalties` flag)**
- Restores the upstream `PED_OFF +3` logit boost
- No pedal penalty, no time penalty, no consecutive `<T>` limiter
- Grammar constraints remain active (crash prevention, sections 3–7)

**Penalized mode (`--penalties`)**
- `PEDAL_PENALTY = 2.0` on `PED_ON`/`PED_OFF` at free positions +
  beam search
- `TIME_PENALTY = 2.0` on `<T>` at free positions
- Consecutive `<T>` limiter (max 1, then −5.0 additional penalty)
- No `PED_OFF +3` boost

The flag threads through the full call chain:
`main()` → `run()` → `stream_msgs()` → `generate_tokens()` →
`decode_first_tokens()` / `decode_tokens()`

Run scripts use `${PENALTIES:+--penalties}` so the flag can be
set via `config.sh` (`PENALTIES=1`) or inline
(`PENALTIES=1 ./run-demo-file.sh`).

### Result
**Upstream-minimal mode produces noticeably better output** — more
musical, denser notes, better continuation of the waltz prompt.
The custom penalties were over-constraining the model at higher
temperatures where the distribution is already flat enough for notes
to compete naturally.

### Temperature bump
Also raised temperature from **0.95** to **0.97** to match the
HuggingFace quickstart recommendation (`temp=0.97, top_p=0.95`).
Updated in both `run-demo-file.sh` and `run-demo-live.sh`.

---

## 12. min_p Sampling Kills Note Tokens (Critical Bug)

### Problem
All output — across every temperature, every prompt, every code
path — was extremely sparse (15–18 notes/min vs the 300–600
expected for a waltz). Switching from our code to the completely
unmodified upstream `aria generate` CLI produced the same sparse
output. The problem wasn't our local modifications.

### Root cause
**`min_p` sampling is catastrophically wrong for this model's
tokenizer.** At free positions (after dur/time), the probability
distribution looks like:

| Token | Probability | Count |
|-------|------------|-------|
| `<PED_OFF>` | **73%** (with +3 boost) / **36%** (without) | 1 token |
| `<T>` | **18%** | 1 token |
| All notes combined | **~40%** | **hundreds** of tokens |

Each individual note token has <0.5% probability because the ~40%
mass is spread across hundreds of pitch/velocity combinations.

`min_p=0.05` sets a threshold of `5% × max_prob`. When `PED_OFF`
is at 73%, threshold = 3.7%. Every individual note token is below
this. **All note tokens are filtered out.** Only `PED_OFF` and
`<T>` survive sampling — producing sparse output with huge silence
gaps.

### Why this wasn't caught earlier
- Section 11 concluded "upstream-minimal mode produces better
  output" — but that A/B test used min_p. With min_p, penalties
  shift probability to even fewer tokens (worse). The conclusion
  was correct for min_p but wrong for top_p.
- The upstream demo works with min_p because (a) beam search
  initializes generation well, (b) the model generates short
  bursts with continuous human context refreshing the KV cache,
  and (c) the interactive setting never requires long autonomous
  generation.

### Fix
**Switch from `min_p` to `top_p=0.95`** for all standalone
generation. `top_p` considers cumulative probability, so hundreds
of note tokens that collectively represent 40% of the distribution
are included even though each individual one is tiny.

Results (waltz prompt, 2048 tokens):

| Sampling | Notes | Duration | Notes/min |
|----------|-------|----------|-----------|
| min_p=0.05, temp=0.95 | 123 | 480s | **15** |
| top_p=0.95, temp=0.95 | 658 | 409s | **97** |

**5–7× improvement** by changing one parameter.

The HuggingFace model card quickstart also recommends `top_p=0.95`
(not min_p). The upstream CLI's `min_p=0.035` default is likely a
mismatch for standalone generation.

### When to use min_p vs top_p
- **Interactive demo** (demo_mlx.py with live MIDI): min_p=0.03
  is fine — beam search + continuous context keeps generation
  on track, and bursts are short.
- **Standalone generation** (sweep_generate.py, headless batch):
  **always use top_p=0.95**. min_p kills note tokens.

---

## 13. PED_OFF +3 Boost Inflates Pedal Dominance

### Problem
The upstream demo applies `logits[:, ped_off_id] += 3` (a manual
logit boost). This was intended to ensure proper pedal-off events
in the interactive demo. However, in standalone generation it
inflates `PED_OFF` probability from ~36% to ~73%, which:
1. Makes `PED_OFF` the dominant token at nearly every free position
2. Raises the min_p threshold (making the min_p problem worse)
3. Generates excessive pedal events even with top_p sampling

### Fix
**Remove the PED_OFF +3 boost for standalone generation.**

| Config | Notes | Pedal tokens | Notes/min |
|--------|-------|-------------|-----------|
| With boost | 404 | 399 | 104 |
| Without boost | 658 | 64 | 97 |

Without the boost, pedal tokens drop from 399 to 64 while note
count increases from 404 to 658. Note density is slightly lower
(97 vs 104) because the piece is longer (more time tokens), but
the token distribution is much healthier.

### When to use the boost
- **Interactive demo**: Yes — helps with real-time pedal handling
- **Standalone generation**: No — causes pedal domination

---

## 14. `<T>` Token Dominance and Penalties

### Problem
Even with top_p and no PED_OFF boost, output still has long gaps
of silence. Each `<T>` token represents **5 full seconds**. With
54 `<T>` tokens in a 2048-token generation, that's 270 seconds of
dead air scattered through the piece.

The model has an intrinsic bias toward `<T>` (~18% probability as
a single token). At a waltz tempo, even 2–3 consecutive `<T>`
tokens create 10–15 seconds of silence — musically unacceptable.

### Root cause
This is a vocabulary design issue. One `<T>` token absorbs all
"do nothing for 5 seconds" probability mass, while hundreds of
note tokens split the "play something" mass. The model isn't
broken — its prior over silence vs activity just doesn't match
what we want for standalone generation.

### Fix
Apply logit penalties at free positions (after dur, time, or
pedal+onset):

```
TIME_PENALTY  = 1.5–2.0  on <T> at free positions
PEDAL_PENALTY = 1.5–2.0  on PED_ON/PED_OFF at free positions
Max consecutive <T> = 1–2 (additional −10.0 after limit)
```

**Important:** These penalties only work correctly with `top_p`
sampling. With `min_p`, penalties shift mass to fewer surviving
tokens (making things worse). With `top_p`, penalties shift mass
toward note tokens (the desired behavior).

Results (waltz prompt, top_p=0.95, no PED_OFF boost, 2048 tokens):

| Penalties | Notes | `<T>` toks | Duration | Notes/min |
|-----------|-------|-----------|----------|-----------|
| None | 673 | 54 | 287s | 141 |
| Moderate (1.5/1.5, max 2 `<T>`) | 674 | 16 | 99s | **410** |
| Balanced (2.0/2.0, max 1 `<T>`) | 736 | 4 | 39s | 1140 |

The "moderate" setting produces the most musically appropriate
density (~400 notes/min, ~100s of music). "Balanced" is too dense
(notes crammed into 39s). No penalties produces the familiar
sparse output with big silence gaps.

### Why section 11 was wrong
Section 11 concluded penalties hurt output quality. That test was
done with **min_p** sampling, where penalties DO make things worse
by concentrating probability on fewer tokens. With **top_p**,
penalties correctly redirect mass toward notes. The section 11
conclusion should be disregarded for top_p configurations.

---

## 15. Upstream `sample_mlx.py` Bug: Missing `max_kv_pos`

### Problem
`aria generate --backend mlx` crashes with:
```
TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'
```

### Root cause
`aria/inference/sample_mlx.py`'s `prefill()` and `decode_one()`
don't pass `max_kv_pos` to the model's `__call__`. The model
expects this parameter for KV-cache chunk alignment.

The demo's `demo_mlx.py` computes this correctly:
```python
max_kv_pos = math.ceil(input_pos[-1].item() / KV_CHUNK_SIZE) * KV_CHUNK_SIZE
```

but `sample_mlx.py` was never updated to match.

### Fix
Added `_max_kv_pos()` helper and passed `max_kv_pos` to both
`prefill()` and `decode_one()` in `sample_mlx.py`. This change
is in the local `aria` repo (unstaged).

---

## 16. Interactive Demo vs Standalone Generation

### Key insight
The interactive demo (`demo_mlx.py`) and standalone generation
(`aria generate` / `sweep_generate.py`) are fundamentally different:

| Feature | Interactive demo | Standalone generation |
|---------|-----------------|----------------------|
| Generation length | Short bursts (100–500 tokens) | Long (2048+ tokens) |
| Context refresh | Human plays between bursts | None — self-conditioning |
| Beam search | Yes (first 2 tokens) | No |
| Duration recalculation | Yes | No |
| KV-cache context | Rich, continuous | Fixed prompt only |
| Optimal sampling | min_p=0.03 works | **Must use top_p=0.95** |
| PED_OFF +3 boost | Helps | Hurts |
| Penalties | Not needed | **Required** |

The YouTube demo quality comes from all of these factors working
together. For standalone generation, we need compensating
mechanisms (top_p, penalties, no pedal boost) to achieve similar
density and coherence.

---

## Status

**Current recommended settings for standalone generation:**
- `top_p=0.95` (NOT min_p — see section 12)
- `temp=0.95`
- `TIME_PENALTY=1.5` at free positions
- `PEDAL_PENALTY=1.5` at free positions
- Max 2 consecutive `<T>` tokens (additional −10.0 after limit)
- No `PED_OFF +3` boost
- Grammar constraints active (sections 3–7)

**Current recommended settings for interactive demo:**
- `top_p=0.95` (safer) or `min_p=0.03` (upstream default)
- `temp=0.95`
- Grammar constraints active
- `PED_OFF +3` boost active
- No penalties needed (short bursts + human context)

Run scripts updated: `--temp 0.95 --top_p 0.95`.
