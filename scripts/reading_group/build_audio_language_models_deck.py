#!/usr/bin/env python3
"""Build the audio-language-models reading-group Excalidraw deck."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/excalidraw-diagrams/scripts"))
from excalidraw_generator import SlideDeck, DiagramStyle  # noqa: E402

OUTPUT = (
    "/Users/mclemens/Development/music-ai-reading-group/"
    "reading-group/audio-language-models/slides/audio-language-models.excalidraw"
)

deck = SlideDeck(diagram_style=DiagramStyle(roughness=1, stroke_width=1))


# Slide 1 — Cover
s = deck.slide("Cover")
s.title("Audio Language Models")
s.text("LTU · LLark · Music Flamingo · Audio Flamingo Next", 40, 90, font_size=20)
s.text("How sound is fused with text", 40, 130, font_size=18)
s.footer("music-ai-reading-group · 2026")


# Slide 2 — Agenda
s = deck.slide("Agenda")
s.title("What we'll cover")
s.text("1. Three things that always confuse people", 60, 100, font_size=18)
s.text("2. The LLaVA / BLIP-2 analogy", 60, 140, font_size=18)
s.text("3. The projector ladder (Linear / MLP / Q-Former / Perceiver)", 60, 180, font_size=18)
s.text("4. Soft prompt vs. gated cross-attention", 60, 220, font_size=18)
s.text("5. Freeze schedule fundamentals", 60, 260, font_size=18)
s.text("6. Per-paper deep dives x 4", 60, 300, font_size=18)
s.text("7. Side-by-side and discussion", 60, 340, font_size=18)


# Slide 3 — What is an audio LM
s = deck.slide("What is an audio LM")
s.title("What is an Audio Language Model?")
s.text("A regular causal LM, taught to read sound the way it reads text.", 40, 90, font_size=18)
wave = s.box(60, 160, "waveform", width=140, height=60, role="input")
enc = s.box(260, 160, "audio encoder", width=140, height=60, role="process")
proj = s.box(460, 160, "projector", width=140, height=60, role="param")
llm = s.box(660, 160, "LLM", width=140, height=60, role="output")
out = s.box(860, 160, "text", width=120, height=60, role="output")
s.arrow_between(wave, enc)
s.arrow_between(enc, proj)
s.arrow_between(proj, llm)
s.arrow_between(llm, out)
s.text("waveform → encoder → projection → prepend → LLM → text", 40, 290, font_size=14)
s.footer("Same skeleton across all four papers in this session.")


# Slide 4 — Confusion 1: audio tokens are just vectors
s = deck.slide("Confusion 1")
s.title("Audio tokens are just vectors")
s.text("Text tokens: integer ID → embedding table → vector ∈ ℝ^d_llm", 40, 90, font_size=16)
s.text("Audio tokens: encoder output → projector → vector ∈ ℝ^d_llm", 40, 130, font_size=16)
s.text("After projection, indistinguishable in type.", 40, 170, font_size=18)
a1 = s.box(80, 240, "audio", width=80, height=40, role="input")
a2 = s.box(170, 240, "audio", width=80, height=40, role="input")
a3 = s.box(260, 240, "audio", width=80, height=40, role="input")
a4 = s.box(350, 240, "audio", width=80, height=40, role="input")
t1 = s.box(450, 240, "text", width=80, height=40, role="neutral")
t2 = s.box(540, 240, "text", width=80, height=40, role="neutral")
t3 = s.box(630, 240, "text", width=80, height=40, role="neutral")
lm = s.box(220, 350, "Causal LM (one sequence)", width=400, height=60, role="output")
s.arrow_between(a1, lm)
s.arrow_between(t3, lm)
s.footer("No special tokens, no extended vocabulary — just continuous prefix vectors.")


# Slide 5 — Confusion 2: the projector
s = deck.slide("Confusion 2")
s.title("The projector is the adapter")
s.text("Bridges encoder space (d_audio) to LLM space (d_llm).", 40, 90, font_size=18)
s.text("Often also compresses sequence length (T frames → N tokens).", 40, 130, font_size=18)
enc_box = s.box(60, 220, "encoder out\n(T, d_audio)", width=180, height=80, role="input")
proj_box = s.box(310, 220, "projector\nP", width=160, height=80, role="param")
llm_box = s.box(540, 220, "LLM input\n(N, d_llm)", width=180, height=80, role="output")
s.arrow_between(enc_box, proj_box)
s.arrow_between(proj_box, llm_box)
s.note("Linear / MLP / Q-Former /\nPerceiver Resampler — all\ndoing the same job.", 800, 220)
s.footer("Almost every architectural choice in this literature is about how fancy P should be.")


# Slide 6 — Confusion 3: freeze schedule
s = deck.slide("Confusion 3")
s.title("Freeze, then thaw carefully")
s.text("Stage 1: encoder ❄ + projector 🔥 + LLM ❄", 60, 100, font_size=18)
s.text("Stage 2: encoder ❄ + projector 🔥 + LLM (LoRA or full)", 60, 140, font_size=18)
s.text("Stage 3+: progressively introduce open-ended tasks", 60, 180, font_size=18)
s.note(
    "Why freeze first?\nProjector is the only random module.\nIf trained end-to-end, garbage gradients\ndestabilize the pretrained encoder & LLM.",
    700, 100,
)
s.text("Encoder stays frozen — always.", 60, 280, font_size=20)
s.footer("LTU calls this 'perception → understanding' curriculum.")


# Slide 7 — Confusion 4: Flamingo naming trap
s = deck.slide("Confusion 4")
s.title("The Flamingo naming trap")
s.text("Despite the name, NONE of these use gated cross-attention:", 40, 100, font_size=18)
s.text("• Audio Flamingo 1 / 2 / 3 / Next", 80, 150, font_size=18)
s.text("• Music Flamingo", 80, 190, font_size=18)
s.text("They all use prepended soft prompts (the LLaVA / BLIP-2 lineage).", 40, 250, font_size=18)
s.note(
    'Only the original DeepMind\nFlamingo (2022) uses\ntanh(α) gated xattn.\n\nOpenFlamingo and IDEFICS\nare the rare descendants.',
    750, 100,
)
s.footer("If you walk in expecting tanh(α) gates everywhere, you'll be confused.")


# Slide 8 — Quick stop: what are LLaVA and BLIP-2?
s = deck.slide("Vision-LM primer")
s.title("Quick stop: what are LLaVA and BLIP-2?")
s.text("Both are image + text models from 2023.", 40, 90, font_size=18)
s.text("They do the same thing audio LMs do, but for pictures.", 40, 120, font_size=18)
img = s.box(40, 200, "image", width=110, height=50, role="input")
clip = s.box(170, 200, "CLIP ViT\n(frozen)", width=140, height=50, role="process")
proj = s.box(330, 200, "projector\n(trained)", width=140, height=50, role="param")
llm = s.box(490, 200, "LLM\n(LoRA)", width=120, height=50, role="output")
s.arrow_between(img, clip)
s.arrow_between(clip, proj)
s.arrow_between(proj, llm)
s.text("LLaVA: image goes through a frozen vision encoder (CLIP ViT),", 40, 290, font_size=14)
s.text("a small projector remaps the features to LLM space, and a LoRA-trained", 40, 315, font_size=14)
s.text("LLM answers questions about the image.", 40, 340, font_size=14)
s.text("BLIP-2: same idea, but the projector is a Q-Former (learned queries", 40, 380, font_size=14)
s.text("that cross-attend to the image features and emit a fixed token bundle).", 40, 405, font_size=14)
s.note(
    "Why we care:\nthe four audio papers\nin this session are\nthe SAME RECIPE,\njust with sound instead\nof images.",
    830, 200,
)
s.footer("If this slide makes sense, the next four papers will too.")


# Slide 8b — Mapping image → audio
s = deck.slide("Image-to-audio mapping")
s.title("Same recipe, swap images for audio")
s.text("LLaVA / BLIP-2 (image input)", 60, 90, font_size=16)
v1 = s.box(60, 130, "image", width=110, height=50, role="input")
v2 = s.box(190, 130, "CLIP ViT", width=130, height=50, role="process")
v3 = s.box(340, 130, "projector", width=130, height=50, role="param")
v4 = s.box(490, 130, "LLM", width=110, height=50, role="output")
s.arrow_between(v1, v2)
s.arrow_between(v2, v3)
s.arrow_between(v3, v4)

s.text("Audio LM (waveform input)", 60, 240, font_size=16)
a1 = s.box(60, 280, "waveform", width=110, height=50, role="input")
a2 = s.box(190, 280, "AF-Whisper / AST /\nJukebox", width=160, height=50, role="process")
a3 = s.box(370, 280, "projector", width=130, height=50, role="param")
a4 = s.box(520, 280, "LLM", width=110, height=50, role="output")
s.arrow_between(a1, a2)
s.arrow_between(a2, a3)
s.arrow_between(a3, a4)

s.text("ViT → audio encoder. Image patches → audio frames.", 60, 380, font_size=15)
s.text('"describe this image" → "describe this clip."', 60, 410, font_size=15)
s.footer("Only the encoder changes. The fusion math is identical.")


# Slide 9 — Projector ladder overview
s = deck.slide("Projector ladder")
s.title("The projector ladder")
s.text("Linear → MLP → Q-Former → Perceiver Resampler", 40, 90, font_size=20)
s.box(60, 160, "Linear", width=200, height=80, role="input")
s.text("1 matrix\n~10M params", 80, 250, font_size=12)
s.box(290, 160, "MLP", width=200, height=80, role="process")
s.text("Linear → GeLU → Linear", 305, 250, font_size=12)
s.box(520, 160, "Q-Former", width=200, height=80, role="param")
s.text("K learned queries\nfixed N output", 540, 250, font_size=12)
s.box(750, 160, "Perceiver Resampler", width=240, height=80, role="output")
s.text("Stacked Q-Formers\nFlamingo's choice", 770, 250, font_size=12)
s.footer("All four do the same conceptual job. Differ in compression and compute.")


# Slide 10 — Linear vs MLP
s = deck.slide("Linear vs MLP")
s.title("Linear vs MLP — used by LTU, LLark, and the Flamingos")
s.text("Linear: y = Wx", 60, 100, font_size=20)
s.text("• Single matrix W ∈ ℝ^(d_audio × d_llm)", 80, 140, font_size=16)
s.text("• ~10M params", 80, 170, font_size=16)
s.text("• Used by LTU, LLark", 80, 200, font_size=16)
s.text("MLP: y = W₂ · GeLU(W₁ x)", 60, 270, font_size=20)
s.text("• Two layers + one nonlinearity", 80, 310, font_size=16)
s.text("• Used by Music Flamingo, Audio Flamingo Next", 80, 340, font_size=16)
s.note(
    "Both are 1-to-1:\nevery encoder frame\n→ one LLM token.\n\nNo compression.",
    750, 100,
)


# Slide 11 — Q-Former / Perceiver
s = deck.slide("Q-Former / Perceiver")
s.title("Q-Former and Perceiver Resampler — fixed-size summarizers")
s.text("K learned queries cross-attend to ALL encoder frames.", 60, 100, font_size=18)
s.text("Output is exactly K tokens — regardless of input length.", 60, 140, font_size=18)
s.text("How you turn 1024 audio frames into 32 LLM tokens.", 60, 180, font_size=18)
inp = s.box(60, 250, "T frames\n(arbitrary)", width=160, height=80, role="input")
qf = s.box(280, 250, "K queries\ncross-attend", width=160, height=80, role="param")
out = s.box(500, 250, "K tokens\nfixed", width=160, height=80, role="output")
s.arrow_between(inp, qf)
s.arrow_between(qf, out)
s.footer("BLIP-2 = Q-Former. Original Flamingo = Perceiver Resampler. Same idea, different names.")


# Slide 12 — Soft prompt
s = deck.slide("Soft prompt")
s.title("Soft prompt: what the four papers actually do")
a1 = s.box(60, 130, "audio", width=80, height=40, role="input")
a2 = s.box(150, 130, "audio", width=80, height=40, role="input")
a3 = s.box(240, 130, "audio", width=80, height=40, role="input")
a4 = s.box(330, 130, "audio", width=80, height=40, role="input")
t1 = s.box(440, 130, "text", width=80, height=40, role="neutral")
t2 = s.box(530, 130, "text", width=80, height=40, role="neutral")
t3 = s.box(620, 130, "text", width=80, height=40, role="neutral")
b1 = s.box(220, 230, "LM block 1", width=300, height=40, role="output")
b2 = s.box(220, 280, "LM block 2", width=300, height=40, role="output")
b3 = s.box(220, 330, "LM block 3", width=300, height=40, role="output")
b4 = s.box(220, 380, "LM block 4", width=300, height=40, role="output")
s.arrow_between(a1, b1)
s.arrow_between(b1, b2)
s.arrow_between(b2, b3)
s.arrow_between(b3, b4)
s.note("Audio is part of\nthe input sequence.\n\nLM is unchanged.", 800, 130)
s.footer("LLaVA / LTU / LLark / Audio Flamingo all do this.")


# Slide 13 — Gated cross-attention
s = deck.slide("Gated cross-attention")
s.title("Gated cross-attention — original Flamingo only")
t1 = s.box(60, 130, "text", width=80, height=40, role="neutral")
t2 = s.box(150, 130, "text", width=80, height=40, role="neutral")
t3 = s.box(240, 130, "text", width=80, height=40, role="neutral")
res = s.box(420, 130, "Perceiver\nResampler", width=160, height=80, role="param")
b1 = s.box(60, 240, "LM block 1", width=300, height=40, role="output")
b2 = s.box(60, 290, "LM block 2 + xattn", width=300, height=40, role="output")
b3 = s.box(60, 340, "LM block 3", width=300, height=40, role="output")
b4 = s.box(60, 390, "LM block 4 + xattn", width=300, height=40, role="output")
s.arrow_between(t1, b1)
s.arrow_between(b1, b2)
s.arrow_between(b2, b3)
s.arrow_between(b3, b4)
s.line_between(res, b2)
s.line_between(res, b4)
s.math("y ← y + tanh(α) · xattn(y, audio)", 480, 280)
s.text("α initialized to 0 → LM is bit-identical at step 0", 460, 320, font_size=14)
s.text("α opens during training", 460, 350, font_size=14)
s.footer("Elegant 2022 trick. Doesn't compose with HF / LoRA, so the field moved on.")


# Slide 14 — Freeze schedule canonical
s = deck.slide("Freeze canonical")
s.title("The canonical freeze schedule")
enc = s.box(60, 130, "Audio Encoder", width=200, height=70, role="neutral")
s.text("❄ frozen always", 60, 210, font_size=14)
proj = s.box(330, 130, "Projector", width=200, height=70, role="process")
s.text("🔥 trainable always", 330, 210, font_size=14)
llm = s.box(600, 130, "LLM", width=200, height=70, role="output")
s.text("❄ → LoRA → full", 600, 210, font_size=14)
s.text("Stage 1: encoder ❄ · proj 🔥 · LLM ❄ → closed-ended only", 60, 290, font_size=16)
s.text("Stage 2: encoder ❄ · proj 🔥 · LLM LoRA → closed-ended", 60, 330, font_size=16)
s.text("Stage 3+: encoder ❄ · proj 🔥 · LLM LoRA/full → open-ended", 60, 370, font_size=16)
s.footer("Encoder is frozen across every paper, every stage, every dataset.")


# Slide 15 — Why freeze
s = deck.slide("Why freeze")
s.title("Why this order?")
s.text("• Encoder pretrained on far more audio than your SFT set", 60, 110, font_size=18)
s.text("  → unfreezing causes overfitting to caption distribution", 80, 145, font_size=15)
s.text("• LLM is the language prior — you don't want to corrupt it", 60, 195, font_size=18)
s.text("  → LoRA = low-rank deltas, full fine-tune only with enough data", 80, 230, font_size=15)
s.text("• Projector is the new module — it must align spaces FIRST", 60, 280, font_size=18)
s.text("  → if random projector emits noise, gradients break the rest", 80, 315, font_size=15)
s.note(
    "LTU's framing:\n'Perception → Understanding'\n\nFirst the model learns\nTHAT the clip contains a sax.\nLater it learns to\nTALK about the sax.",
    750, 100,
)


# Slide 16 — End-to-end pipeline
s = deck.slide("End-to-end pipeline")
s.title("End-to-end pipeline")
w = s.box(40, 200, "waveform", width=120, height=50, role="input")
enc = s.box(180, 200, "encoder ❄", width=130, height=50, role="process")
t1 = s.box(330, 200, "(T, d_audio)", width=120, height=50, role="param")
proj = s.box(470, 200, "projector 🔥", width=130, height=50, role="process")
t2 = s.box(620, 200, "(N, d_llm)", width=120, height=50, role="param")
combined = s.box(760, 200, "+ text\n(N+M, d_llm)", width=140, height=70, role="param")
llm = s.box(920, 200, "LLM", width=110, height=50, role="output")
s.arrow_between(w, enc)
s.arrow_between(enc, t1)
s.arrow_between(t1, proj)
s.arrow_between(proj, t2)
s.arrow_between(t2, combined)
s.arrow_between(combined, llm)
s.footer("Same shape language at every stage. After projection, audio = vectors of d_llm.")


# Slide 17 — LTU architecture
s = deck.slide("LTU architecture")
s.title("LTU — Listen, Think, Understand")
s.text("Gong et al., 2024", 40, 80, font_size=14)
w = s.box(40, 150, "10s waveform\n16kHz", width=140, height=70, role="input")
ast = s.box(220, 150, "AST encoder ❄\n128-bin Mel\n16x16 patches", width=180, height=80, role="process")
proj = s.box(440, 150, "Linear projector 🔥\n→ 32 audio tokens\n× 4096 dim", width=200, height=80, role="param")
llm = s.box(680, 150, "LLaMA-7B (Vicuna)\n+ LoRA", width=180, height=80, role="output")
s.arrow_between(w, ast)
s.arrow_between(ast, proj)
s.arrow_between(proj, llm)
s.text("4-stage curriculum: closed-ended classification → open-ended QA", 40, 280, font_size=16)
s.text("Data: OpenAQA-5M (1.9M closed + 3.7M open, GPT-3.5-generated)", 40, 320, font_size=16)
s.text("5% intentionally unanswerable — teaches refusal", 40, 360, font_size=16)
s.footer("First paper to formalize 'perception → understanding' curriculum.")


# Slide 18 — LTU stages
s = deck.slide("LTU stages")
s.title("LTU — training stages")
s.text("Stage 1: proj 🔥 only · closed-ended classification + acoustic features", 40, 100, font_size=15)
s.text("Stage 2: + LoRA on LLM · still closed-ended", 40, 145, font_size=15)
s.text("Stage 3: + all closed-ended tasks", 40, 190, font_size=15)
s.text("Stage 4: + open-ended QA (perception → understanding)", 40, 235, font_size=15)
s.note(
    "Quote:\n'Open-ended tasks are too\ndifficult at the start. The\nmodel uses its language prior\ninstead of conditioning\non the audio.'",
    700, 100,
)
s.text("AST stays frozen across all four stages.", 40, 320, font_size=18)


# Slide 19 — LLark architecture
s = deck.slide("LLark architecture")
s.title("LLark — A music specialist")
s.text("Gardner et al., ICML 2024", 40, 80, font_size=14)
w = s.box(40, 150, "25s waveform", width=140, height=70, role="input")
jbx = s.box(220, 150, "Jukebox-5B ❄\nlayer 36\n10Hz pool", width=180, height=80, role="process")
proj = s.box(440, 150, "Linear projector 🔥\n→ 32 tokens × 4096", width=220, height=80, role="param")
llm = s.box(700, 150, "LLaMA-2-7B-Chat\n+ LoRA", width=180, height=80, role="output")
s.arrow_between(w, jbx)
s.arrow_between(jbx, proj)
s.arrow_between(proj, llm)
s.text("Generative encoder (Jukebox) instead of discriminative (AST).", 40, 280, font_size=16)
s.text("Argument: generative reps richer than label-trained reps for music.", 40, 320, font_size=16)
s.text("Projector adds <0.1% additional params.", 40, 360, font_size=16)
s.footer("Same skeleton as LTU. Only the encoder changes.")


# Slide 20 — LLark data
s = deck.slide("LLark data")
s.title("LLark — instruction tuning data")
s.text("~1.2M (audio, query, response) triplets", 40, 100, font_size=18)
s.text("From 6 datasets: MusicCaps, YouTubeM, MusicNet,", 40, 145, font_size=16)
s.text("                 FMA, MTG-Jamendo, MagnaTagATune", 40, 175, font_size=16)
s.text("Generation: GPT-3.5 + Jukebox-derived metadata", 40, 230, font_size=16)
s.text("            (tempo, key, mode, chords)", 40, 260, font_size=16)
s.text("Three task families:", 40, 320, font_size=16)
s.text("  • Music understanding · key, tempo, genre, instruments", 60, 350, font_size=14)
s.text("  • Captioning", 60, 380, font_size=14)
s.text("  • Reasoning", 60, 410, font_size=14)


# Slide 21 — Music Flamingo architecture
s = deck.slide("Music Flamingo architecture")
s.title("Music Flamingo — Built on AF3")
s.text("NVIDIA · Ghosh et al., Nov 2025", 40, 80, font_size=14)
w = s.box(40, 150, "music\n90s chunks", width=140, height=70, role="input")
afw = s.box(220, 150, "AF-Whisper ❄\n1280-dim", width=180, height=70, role="process")
proj = s.box(440, 150, "2-layer MLP 🔥\nadapter", width=180, height=70, role="param")
llm = s.box(660, 150, "Llama 2 + RoTE\nfull fine-tune", width=200, height=70, role="output")
s.arrow_between(w, afw)
s.arrow_between(afw, proj)
s.arrow_between(proj, llm)
s.text("RoTE: Rotary Time Embeddings — θ from absolute timestamps τᵢ", 40, 270, font_size=16)
s.text("       (replaces RoPE; grounds positional reasoning in time)", 40, 300, font_size=16)
s.text("MF-Skills: ~4.3M captions across ~3M hours of music", 40, 350, font_size=16)
s.footer("No gated cross-attention despite the name. Soft-prompt fusion.")


# Slide 22 — Music Flamingo stages
s = deck.slide("Music Flamingo stages")
s.title("Music Flamingo — 4 training stages")
s.text("AF3-SFT: improve AF3 base on music + multi-speaker ASR + singing", 40, 100, font_size=15)
s.text("MF-SFT: MF-Skills + MF-Think · introduce RoTE", 40, 145, font_size=15)
s.text("MF-WarmUp: 300K cold-start CoT (gpt-oss-120b)", 40, 190, font_size=15)
s.text("MF-GRPO: format + accuracy + structured-thinking rewards", 40, 235, font_size=15)
s.note(
    "Departure from LTU/LLark:\nLLM trained at FULL rank,\nnot LoRA.\n\nAF-Whisper still ❄ always.",
    700, 100,
)
s.text("MF-Think: 300K CoT examples generated by gpt-oss-120b", 40, 320, font_size=15)
s.text("Final filtered: ~176K QA + ~59K captions", 40, 350, font_size=15)


# Slide 23 — Audio Flamingo Next architecture
s = deck.slide("AF-Next architecture")
s.title("Audio Flamingo Next — long audio + voice")
s.text("NVIDIA · Ghosh et al., Apr 2026", 40, 80, font_size=14)
w = s.box(40, 150, "audio\nup to 30 min", width=140, height=70, role="input")
afw = s.box(220, 150, "AF-Whisper ❄", width=160, height=70, role="process")
proj = s.box(400, 150, "2-layer MLP 🔥", width=170, height=70, role="param")
llm = s.box(590, 150, "Qwen-2.5-7B\n128k context", width=180, height=70, role="output")
tts = s.box(790, 150, "Streaming TTS\nvoice-out", width=170, height=70, role="output")
s.arrow_between(w, afw)
s.arrow_between(afw, proj)
s.arrow_between(proj, llm)
s.arrow_between(llm, tts)
s.text("Three deltas vs Music Flamingo:", 40, 270, font_size=18)
s.text("  1. Long audio: up to 30 min via Sequence Packing + Hybrid SP", 60, 305, font_size=15)
s.text("  2. Time-grounded CoT: AF-Think-Time (43K samples, ~446 words/chain)", 60, 335, font_size=15)
s.text("  3. Streaming TTS: voice-to-voice without external synthesizer", 60, 365, font_size=15)
s.footer("Speech + sound + music — generalizes beyond music-only.")


# Slide 24 — AF-Next stages
s = deck.slide("AF-Next stages")
s.title("Audio Flamingo Next — 6 training stages")
s.text("Pre-train 1: audio adapter alignment · 30s · 8K context", 40, 95, font_size=14)
s.text("Pre-train 2: + multilingual ASR · 1 min · 8K context", 40, 130, font_size=14)
s.text("Mid-train 1: AudioSkills-XL + MF-Skills · 10 min · 24K context", 40, 165, font_size=14)
s.text("Mid-train 2: long audio · 30 min · 128K context (Sequence Packing)", 40, 200, font_size=14)
s.text("Post-train: GRPO + 386K safety samples", 40, 235, font_size=14)
s.text("CoT-train: AF-Think-Time SFT → second GRPO pass", 40, 270, font_size=14)
s.text("Encoder ❄ across all 6 stages.", 40, 340, font_size=18)
s.text("LLM trained at full rank.", 40, 380, font_size=18)
s.footer("Progressive curriculum: short → long, no-reason → reasoning, text-out → voice-out.")


# Slide 25 — Comparison matrix
s = deck.slide("Comparison")
s.title("Side-by-side")
y = 90
rows = [
    ("Year",              "2024",        "2024",            "Nov 2025",       "Apr 2026"),
    ("Encoder",           "AST",         "Jukebox L36",     "AF-Whisper",     "AF-Whisper"),
    ("Encoder frozen?",   "Always",      "Always",          "Always",         "Always"),
    ("Projector",         "Linear",      "Linear",          "2-layer MLP",    "2-layer MLP"),
    ("LLM",               "LLaMA-7B",    "LLaMA-2-7B",      "Llama 2",        "Qwen-2.5-7B"),
    ("LLM training",      "LoRA",        "LoRA",            "Full",           "Full"),
    ("Context",           "2k",          "2k",              "32k",            "128k"),
    ("Audio dur",         "10s",         "25s",             "20 min",         "30 min"),
    ("Distinctive",       "P→U curriculum", "Generative enc", "RoTE + GRPO",  "AF-Think-Time + TTS"),
    ("Domain",            "General",     "Music",           "Music",          "Speech+sound+music"),
]
s.text("Axis", 40, y, font_size=13)
s.text("LTU", 240, y, font_size=13)
s.text("LLark", 420, y, font_size=13)
s.text("Music Flamingo", 590, y, font_size=13)
s.text("AF Next", 800, y, font_size=13)
for i, (axis, a, b, c, d) in enumerate(rows):
    yy = y + 35 + i * 30
    s.text(axis, 40, yy, font_size=12)
    s.text(a, 240, yy, font_size=12)
    s.text(b, 420, yy, font_size=12)
    s.text(c, 590, yy, font_size=12)
    s.text(d, 800, yy, font_size=12)
s.footer("Architectural variety is small. Data + training-recipe variety is huge.")


# Slide 26 — Naming trap revisit
s = deck.slide("Naming trap revisit")
s.title("Recap: the Flamingo naming trap")
s.text("✅ Original DeepMind Flamingo (2022)", 40, 110, font_size=16)
s.text("    → Perceiver Resampler + tanh(α) gated xattn", 80, 140, font_size=14)
s.text("✅ OpenFlamingo, IDEFICS", 40, 180, font_size=16)
s.text("    → Inherit the gated xattn design", 80, 210, font_size=14)
s.text("❌ Audio Flamingo 1 / 2 / 3 / Next", 40, 260, font_size=16)
s.text("    → Soft prompt prepend, no gates", 80, 290, font_size=14)
s.text("❌ Music Flamingo", 40, 330, font_size=16)
s.text("    → Soft prompt prepend, no gates", 80, 360, font_size=14)
s.footer("'Flamingo' = audio + LM. NOT = gated cross-attention.")


# Slide 27 — Open questions
s = deck.slide("Open questions")
s.title("Open questions for discussion")
s.text("1. LoRA → full fine-tune (LTU/LLark → MF/AF-Next):", 40, 100, font_size=15)
s.text("   data-scale artifact, or LoRA actually loses quality?", 60, 130, font_size=13)
s.text("2. Why does no one use Q-Former / Perceiver for audio anymore?", 40, 175, font_size=15)
s.text("   Is bigger context window what killed the resampler?", 60, 205, font_size=13)
s.text("3. AF-Whisper frozen even with 1M hours of music in MF-Skills?", 40, 250, font_size=15)
s.text("   Is the regularization argument still load-bearing at scale?", 60, 280, font_size=13)
s.text("4. Music Flamingo built on AF3, not on LLark.", 40, 325, font_size=15)
s.text("   What does that imply about music-specific research direction?", 60, 355, font_size=13)


# Slide 28 — Resources
s = deck.slide("Resources")
s.title("Papers")
s.text("• Listen, Think, Understand (LTU) — arxiv.org/abs/2305.10790", 40, 100, font_size=14)
s.text("• LLark — arxiv.org/abs/2310.07160", 40, 130, font_size=14)
s.text("• Music Flamingo — arxiv.org/abs/2511.10289", 40, 160, font_size=14)
s.text("• Audio Flamingo Next — arxiv.org/abs/2604.10905", 40, 190, font_size=14)
s.text("• Original Flamingo — arxiv.org/abs/2204.14198", 40, 220, font_size=14)
s.text("• LLaVA — arxiv.org/abs/2304.08485", 40, 250, font_size=14)
s.text("• BLIP-2 — arxiv.org/abs/2301.12597", 40, 280, font_size=14)
s.title2 = "Code & demos"
s.text("Code & demos:", 40, 330, font_size=16)
s.text("• github.com/YuanGongND/ltu", 60, 360, font_size=14)
s.text("• github.com/spotify-research/llark", 60, 385, font_size=14)
s.text("• github.com/NVIDIA/audio-flamingo", 60, 410, font_size=14)


# Slide 29 — Closing
s = deck.slide("Closing")
s.title("Three things to take away")
s.text("1. Audio tokens are vectors. Same shape language as text tokens.", 40, 110, font_size=18)
s.text("2. The projector is the only architectural variety.", 40, 175, font_size=18)
s.text("3. Encoder is always frozen. Projector trains first. LLM follows.", 40, 240, font_size=18)
s.text("Everything else is data and training recipe.", 40, 320, font_size=20)
s.footer("Thanks for reading along.")


deck.save(OUTPUT)
print(f"Wrote {OUTPUT}")
