from pathlib import Path


OUTPUT_SLUG = "ailive-mixer"
PRESENTER = "Michael Clemens"
READING_GROUP_DATE = "April 2026"

PAPER_PATHS = {
    "ailive": Path("/Users/mclemens/Downloads/Zurale et al. 2026 - arXiv [eess.AS].pdf"),
    "dmc": Path("/Users/mclemens/Downloads/2010.10291v1.pdf"),
    "channel_ai": Path("/Users/mclemens/Downloads/Tsiros and Palladini 2020.pdf"),
}

PDF_PAGE_ASSETS = [
    {"key": "ailive_system", "pdf_key": "ailive", "page": 2},
    {"key": "ailive_results", "pdf_key": "ailive", "page": 4},
    {"key": "dmc_architecture", "pdf_key": "dmc", "page": 2},
    {"key": "channel_ai_framework", "pdf_key": "channel_ai", "page": 4},
]

SUMMARY_MARKDOWN = """# AILIVE MIXER Summary

## Core claim

Zurale et al. argue that automatic music mixing for live performance is not just "offline multitrack mixing, but faster." The live setting introduces two constraints that dominate the design space:

- every microphone channel contains acoustic bleed from nearby sources
- the system has to react with effectively zero added latency to preserve audio-visual synchrony and stage usability

The paper presents **AiLive Mixer (ALM)** as a gain-prediction system for live multitrack mixing that tries to satisfy both constraints at once.

## Why this paper matters

The most useful way to read this paper is as a deployment-oriented successor to the 2020 **Differentiable Mixing Console (DMC)** paper. DMC showed that a model with a strong mixing-console inductive bias could learn human-readable mix parameters from raw multitracks. AILIVE keeps that spirit, but retools the architecture around live constraints:

- it narrows the output space to **mono gain only**
- it explicitly trains on **bleed-contaminated inputs**
- it reorganizes inference around **multi-rate, one-frame-ahead prediction**

That makes it a practical systems paper, not just a better benchmark score paper.

## Architecture in one paragraph

Each input channel first passes through a finetuned VGGish embedding model over a long context window `F1 = 975 ms`. The network then mixes three kinds of information:

- channel identity / timbre from the audio embedding
- channel loudness via RMS conditioning on short frames
- temporal context via a GRU

Transformer encoder blocks are inserted at multiple stages to model inter-channel dependencies, and a small MLP predicts one gain value per channel. The predicted gains are then applied to the waveforms and summed into a mono mix.

## The key systems idea

The paper's main insight is not just "use a smaller frame size." It is to **split the system into two rates**:

- a long-rate branch for context extraction (`F1 = 975 ms`)
- a short-rate branch for control (`F2 = 50 ms` in the multi-rate model)

At inference time, the model processes the current `F2` frame but predicts the gain for the **next** `F2` frame. That converts the problem from "react after audio arrives" into "predict one short control step ahead," which is how the authors justify the zero-latency claim.

## Training setup

The authors train on MedleyDB songs with isolated stems (`<= 8` raw tracks), using a `35 / 8` train-validation split from a total of 43 songs. Because they do not have a live-performance bleed dataset with ground-truth mixes, they simulate bleed on the fly with **pyroomacoustics**, randomizing:

- room-response parameters
- bleed severity
- input levels before and after bleed simulation

They keep the original MedleyDB human mix as the supervision target and optimize a multi-resolution STFT loss using window sizes 440, 884, and 3528 samples with 25 percent hop size.

## Evaluation

The evaluation is deliberately perceptual rather than objective. The listening study uses:

- 15 participants with critical listening experience
- 8 live-performance song segments
- 5 presented mixes per segment: `ALM-MR`, `ALM-SR`, `DMC-B-0L`, `DMC-OG`, and `RAW`

The ranking reported by the paper is:

`ALM-MR > ALM-SR > DMC-B-0L > DMC-OG > RAW`

The paper also reports a Kruskal-Wallis test of `H = 156.485` with `p = 8.293 x 10^-33`, suggesting that some model differences are statistically significant. Pairwise tests separate both ALM variants from the rest, but the paper says there is not enough evidence to claim significance between `ALM-MR` and `ALM-SR`.

## What seems to drive the gain

The authors' qualitative explanation is coherent:

- DMC variants produce abrupt gain jumps because they lack an explicit temporal model
- ALM-SR is smoother than DMC but reacts more slowly because it still operates on 975 ms control windows
- ALM-MR reacts on 50 ms control frames, which helps with transients, clipping avoidance, and more stable gains

This is an important reading-group point: the paper is really arguing that **control rate matters**, not only model capacity.

## Limits worth discussing

- The system predicts **only mono gain**, not panning, EQ, compression, delay, or reverb.
- Ground-truth targets come from offline studio-style mixes, even when the inputs are bleed-simulated live approximations.
- The evaluation is perceptual and useful, but it is still a relatively small listening study rather than a deployment or workflow study.
- The paper does not yet answer how well the approach would integrate into a real console workflow with expert engineers in the loop.

## Bottom line

AILIVE is best understood as a strong **systems adaptation of DMC for live use**. Its contribution is not a radically new learning objective. The contribution is a coherent package:

- architecture changes for temporal and inter-channel context
- data augmentation for realistic bleed conditions
- multi-rate control for low-latency prediction
- a listening-study argument that the multi-rate version is the most usable variant
"""

DISCUSSION_QUESTIONS_MARKDOWN = """# Discussion Questions

## Methodology

1. The model is trained on MedleyDB with simulated bleed, then evaluated on real live recordings. How close is that train-test bridge to the real deployment problem, and what important bleed patterns might still be missing?
2. The listening study uses 15 critical listeners and 8 song segments. Is that enough to support the practical claims the paper makes about live usability, or only enough to support a weaker perceptual claim?

## Theory and systems

3. The zero-latency claim depends on predicting gains one `F2` frame ahead. Under what musical conditions does that assumption become fragile? Sudden entrances, drastic dynamics jumps, meter changes, improvisation?
4. The multi-rate story says long context is needed for semantic understanding, while short context is needed for control. Is this decomposition fundamentally right, or is it a workaround for the current embedding stack?
5. DMC struggled with abrupt gain jumps because it lacked an explicit temporal model. If we replaced the GRU with a stronger temporal module, would that matter less than the 50 ms control rate?

## Human-centered audio questions

6. Tsiros and Palladini argue that live engineers want assistance without workflow disruption. Where on that automation ladder does AILIVE belong right now: assistive suggestion, conditional automation, or something riskier?
7. The output is limited to mono gain. Is that a weakness, or is it exactly the right scope for a first deployable live-mixing assistant?
8. Would you trust this system more if it stayed human-readable and parametric, or if it directly rendered the mixed audio end to end?

## Critical questions

9. What experiment is missing that would most strengthen the paper: a console workflow study, a stronger baseline, gain-trajectory diagnostics, or a broader listener pool?
10. The paper says objective metrics do not map well to perceptual mix quality. What would a useful intermediate diagnostic look like anyway: clipping rate, gain smoothness, transient response, or something else?
"""

CITATIONS_MARKDOWN = """# Citation Notes

## Reading strategy

This package treats the three local papers as a compact lineage rather than as a citation-count report. No live Semantic Scholar lookup was used in this build, so the emphasis here is on conceptual relationships that can be supported directly from the PDFs.

## 1. Technical predecessor: DMC (Steinmetz et al., 2020)

**Paper:** *Automatic Multitrack Mixing with a Differentiable Mixing Console of Neural Audio Effects*

Why it matters for AILIVE:

- It gives the clearest baseline architecture for "mixing-console-shaped" learning.
- It predicts human-readable parameters instead of directly emitting final audio.
- It introduces the stereo sum/difference loss that avoids forcing everything toward the center.

What AILIVE keeps:

- the basic idea that mixing should be parameter prediction, not opaque audio synthesis
- a channel-wise architecture with shared structure across tracks
- inductive bias from the signal chain rather than a generic waveform-to-waveform model

What AILIVE changes:

- AILIVE narrows the task to **mono gain prediction**
- adds explicit temporal modeling with a GRU
- adds multiple transformer stages for inter-channel context
- adds bleed-aware training and a multi-rate control path
- reframes the whole problem around live zero-latency deployment

## 2. Workflow framing: Tsiros and Palladini (2020)

**Paper:** *Towards a Human-Centric Design Framework for AI Assisted Music Production*

Why it matters for AILIVE:

- It explains why a technically competent live-mixing system can still fail in practice.
- It emphasizes trust calibration, workflow compatibility, and gradual automation.
- It describes a live-console context with effectively zero tolerance for visible mistakes.

What it contributes to the reading:

- AILIVE answers the engineering question: "Can we predict useful gains under bleed and latency constraints?"
- Channel-AI answers the deployment question: "How much autonomy should the system have, and how should engineers invoke or override it?"

Together, they suggest that **low latency is necessary but not sufficient**. A real product also needs explicit control boundaries.

## 3. The combined story

If we place the three papers on one line, the progression looks like this:

1. **Channel-AI (2020):** human-in-the-loop console assistance and trust-aware design
2. **DMC (2020):** a strong parametric baseline for learning mix parameters from waveforms
3. **AILIVE (2026):** a live-performance adaptation of the parametric approach with bleed simulation and short-horizon control

That is why the slide deck uses DMC as the architectural foil and Channel-AI as the deployment foil.

## Suggested next-paper directions

- follow-ups that extend live mixing beyond gain into EQ, dynamics, or spatialization
- user-study papers on console-integrated AI assistance rather than offline listening studies
- work on perceptual diagnostics for gain smoothness, clipping, and transient handling in live settings
"""

MATH_WALKTHROUGH_MARKDOWN = """# Math Walkthrough

## 1. DMC's stereo loss solves a real ambiguity

The 2020 DMC paper explicitly writes the stereo channels in sum/difference form:

```text
y_sum  = y_left + y_right
y_diff = y_left - y_right
```

and defines the stereo loss as:

```text
L_stereo(y_hat, y) =
    L_MR(y_hat_sum,  y_sum) +
    L_MR(y_hat_diff, y_diff)
```

where `L_MR` is a multi-resolution STFT loss.

### Why this matters

A direct left-channel / right-channel waveform loss over-penalizes a prediction that gets the stereo *spread* right but flips the absolute orientation. For example, if the model understands that a guitar should be off-center but does not know whether the reference mix places it left or right, a naive loss pushes it toward the center. The sum/difference formulation makes the loss care more about stereo balance than about an arbitrary sign choice.

### Failure mode if you ignore this

Without a left-right invariant formulation, the model can collapse toward safer, more centered predictions. In audio terms: the model avoids making a bold panning move because the penalty for guessing the wrong side is too high.

## 2. AILIVE keeps the spectral loss but changes the control problem

The AILIVE paper states that training uses a **multi-resolution STFT loss** with:

- window sizes `440`, `884`, and `3528`
- 25 percent hop size
- FFT sizes `512`, `1024`, and `4196`

The paper does not print a compact single equation for the whole training objective, so the expression below is **our notation for the training description**, not a verbatim equation from the PDF:

```text
L_ALM =
    sum_{r in R} L_MR-STFT(m_hat[t+1], m[t+1]; r)
```

with `R = {(440, 512), (884, 1024), (3528, 4196)}` and `m[t+1]` denoting the next short-horizon target mix frame.

### Why this is the interesting part

The novelty is not the STFT loss itself. The novelty is that the loss is applied to a system that predicts **the next control frame** instead of the current one.

## 3. The zero-latency shift

Operationally, the paper's deployment logic can be summarized as:

```text
given current features phi(x_t),
predict gains g_hat[t+1],
apply g_hat[t+1] to the upcoming waveform frame x[t+1]
```

### Intuition

Think of the model as a live engineer who must move the fader just before the next phrase arrives, not just after hearing it. Multi-rate processing helps because the prediction horizon is only `50 ms` in the MR case, instead of `975 ms` in the SR case.

### Failure mode

If the control horizon is too long, the model reacts sluggishly and misses fast transients or sudden entrances. If the horizon is short but the context model is weak, the system becomes twitchy and inconsistent. AILIVE's design is trying to get both:

- long context for semantics
- short control frames for responsiveness

## 4. What to emphasize in discussion

- DMC's math solves a **representation ambiguity**.
- AILIVE's systems design solves a **timing and deployment ambiguity**.
- The most important "equation" in AILIVE may actually be the frame-shifted control loop, not the loss.
"""
