# Papers Similar to FlueBricks / RealJam / Ghost in the Keys

Session theme: **real-time human-AI music co-performance & interactive instrument systems**

---

## Tier 1 — Closest Matches (human-AI co-performance)

### 1. Live Music Models (Magenta RealTime)
- **Authors:** Lyria Team, Google DeepMind
- **Venue:** arXiv 2025
- **Link:** [arXiv:2508.04651](https://arxiv.org/abs/2508.04651)
- **Summary:** Real-time streaming music generation with synchronized user control via text/audio prompts. 800M-param open-weights autoregressive transformer trained on ~190K hours of music.
- **Why it fits:** Direct successor to the RealJam line of work — real-time generative music with live human control.

### 2. Esteso: Interactive AI Music Duet Based on Player-Idiosyncratic Extended Double Bass Techniques
- **Authors:** Domenico Stefani, Matteo Tomasetti, Filippo Angeloni, Luca Turchet
- **Venue:** NIME 2024
- **Link:** [NIME proceedings](https://nime.org/proceedings/2024/nime2024_72.pdf)
- **Summary:** Improvisation between a double bassist and AI using extended technique recognition, live electronics, and timbre-transfer models. Turn-taking improvisational exchange where recognized playing techniques drive the AI's response strategy.
- **Why it fits:** Turn-taking duet system like Ghost in the Keys, but for double bass.

### 3. Developing Symbiotic Virtuosity: AI-Augmented Musical Instruments and Their Use in Live Music Performances
- **Authors:** Lancelot Blanchard, Perry Naseck, Eran Egozy, Joseph A. Paradiso
- **Venue:** MIT Media Lab 2024
- **Link:** [MIT](https://www.media.mit.edu/publications/developing-symbiotic-virtuosity-ai-augmented-musical-instruments-and-their-use-in-live-music-performances/)
- **Summary:** Introduces "symbiotic virtuosity" where AI augments a performer's musical identity in real-time. Demonstrated with GRAMMY-winning keyboardist Jordan Rudess using jam_bot. Features a sold-out performance at MIT Media Lab and a 16-foot kinetic sculpture with AI-driven music-to-motion mapping.
- **Why it fits:** Frames the exact design space of real-time human-AI co-performance.

### 4. AI Harmonizer: Expanding Vocal Expression with a Generative Neurosymbolic Music AI System
- **Authors:** Lancelot Blanchard, Cameron Holt, Joseph Paradiso (MIT Media Lab)
- **Venue:** NIME 2025
- **Link:** [arXiv:2506.18143](https://arxiv.org/abs/2506.18143)
- **Summary:** Real-time system that generates four-part choral harmonies from a singer's vocal melody using Basic Pitch for voice-to-MIDI conversion and a custom-trained Anticipatory Music Transformer for harmony generation.
- **Why it fits:** Builds on AMT (covered in music generation week) for live performance.

### 5. Exploring the Needs of Practising Musicians in Co-Creative AI Through Co-Design
- **Venue:** CHI 2025
- **Link:** [ACM](https://dl.acm.org/doi/10.1145/3706598.3713894)
- **Summary:** Co-design study with professional musicians; human performer plays an OP-1 synthesiser while AI agent controls a 0-Coast synthesiser, supporting 8 MIDI inputs/outputs.
- **Why it fits:** User-centered design research on this exact problem space.

---

## Tier 2 — Strong Related Work (interactive music + AI tools)

### 6. Amuse: Human-AI Collaborative Songwriting with Multimodal Inspirations
- **Authors:** Yewon Kim et al. (KAIST)
- **Venue:** CHI 2025
- **Link:** [arXiv:2412.18940](https://arxiv.org/abs/2412.18940) | [GitHub](https://github.com/elianakim/Amuse)
- **Summary:** Songwriting assistant that transforms multimodal inputs (images, text, audio) into chord progressions using multimodal LLMs for keyword extraction and a unimodal chord model for filtering.
- **Why it fits:** AI co-creation but for composition rather than performance.

### 7. Hookpad Aria: A Copilot for Songwriters
- **Authors:** Chris Donahue et al.
- **Venue:** ISMIR 2024 (Late-Breaking Demo)
- **Link:** [arXiv:2502.08122](https://arxiv.org/abs/2502.08122)
- **Summary:** Generative AI copilot in Hookpad (web-based lead sheet editor) supporting continuation, infilling, and harmony-from-melody generation. Built on the Anticipatory Music Transformer. Since release, 3K users have accepted 74K of 318K generated suggestions.
- **Why it fits:** Deployed system with real users, builds on AMT.

### 8. Revival: Collaborative Artistic Creation through Human-AI Interactions in Musical Creativity
- **Venue:** NeurIPS 2024 Workshop
- **Link:** [arXiv:2503.15498](https://arxiv.org/abs/2503.15498)
- **Summary:** Live audiovisual performance blending human and AI musicianship — percussionist and electronic artist improvise with AI agents (MASOM, SpireMuse) trained on compositions by deceased composers. AI-driven visual synthesizer (Autolume) produces synchronized audio-reactive visuals.
- **Why it fits:** Actual staged performance with AI co-performers.

### 9. AI See, You See: Human-AI Musical Collaboration in Augmented Reality
- **Venue:** CHI EA 2025
- **Link:** [ACM](https://dl.acm.org/doi/10.1145/3706599.3720052)
- **Summary:** AR co-creative musical system that visualizes AI's musical actions (MIDI outputs, control parameters) through real-time AR visualizations embedded in the performance space. Tested in trio improvisation with two humans and an AI agent.
- **Why it fits:** Addresses the legibility problem — how do you "see" what the AI is doing?

### 10. Diff-A-Riff: Musical Accompaniment Co-creation via Latent Diffusion Models
- **Venue:** ISMIR 2024 (Sony CSL / IRCAM)
- **Link:** [arXiv:2406.08384](https://arxiv.org/abs/2406.08384)
- **Summary:** Latent diffusion model for generating single-instrument accompaniments conditioned on musical audio context, text prompts, or both. Produces 48kHz pseudo-stereo audio with significantly reduced inference time and memory.
- **Why it fits:** Audio-domain accompaniment generation.

---

## Tier 3 — Acoustic Reasoning & Physical Modeling (connects to FlueBricks)

### 11. Data-Driven Room Acoustic Modeling Via Differentiable Feedback Delay Networks With Learnable Delay Lines
- **Authors:** Alessandro Ilic Mezza, Riccardo Giampiccolo, Enzo De Sena, Alberto Bernardini
- **Venue:** EURASIP 2024
- **Link:** [arXiv:2404.00082](https://arxiv.org/abs/2404.00082)
- **Summary:** Makes the classic Feedback Delay Network reverberator fully differentiable, including the delay lines themselves. All parameters learned end-to-end via backpropagation using a perceptual loss for energy decay and echo density.
- **Why it fits:** Differentiable physical acoustics — computational analog to FlueBricks' modularity.

### 12. DDSP-Based Neural Waveform Synthesis of Polyphonic Guitar Performance from String-wise MIDI Input
- **Authors:** Nicolas Jonason, Xin Wang, Erica Cooper, Lauri Juvela, Bob L. T. Sturm, Junichi Yamagishi
- **Venue:** DAFx 2024
- **Link:** [arXiv:2309.07658](https://arxiv.org/abs/2309.07658)
- **Summary:** Per-string DDSP synthesis from MIDI. Finds that the simplest approach — directly predicting synthesis parameters from MIDI — outperforms more complex designs.
- **Why it fits:** Extends DDSP (previously covered) to polyphonic instrument modeling.

### 13. Neural Audio Instruments: Epistemological and Phenomenological Perspectives on Musical Embodiment of Deep Learning
- **Venue:** Frontiers in Computer Science, 2025
- **Link:** [Frontiers](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1575168/full)
- **Summary:** Examines how neural audio synthesis embedded in digital musical instruments shapes embodied interaction. Argues neural methods can both exacerbate and restore close physical interplay in digital instruments.
- **Why it fits:** Theory paper on what it means to "embody" a neural model as an instrument.

### 14. Pianist Transformer: Towards Expressive Piano Performance Rendering via Scalable Self-Supervised Pre-Training
- **Authors:** Hong-Jie You, Jie-Jing Shao, Xiao-Wen Yang, Lin-Han Jia, Lan-Zhe Guo, Yu-Feng Li
- **Venue:** arXiv 2025
- **Link:** [arXiv:2512.02652](https://arxiv.org/abs/2512.02652)
- **Summary:** 135M-param asymmetric Transformer pre-trained on 10B MIDI tokens for expressive piano rendering. Quality statistically indistinguishable from human artists in subjective evaluations.
- **Why it fits:** Expressive performance modeling — the rendering side of Ghost in the Keys.

---

## Bonus — Robots & Embodiment

### 15. Learning to Play Piano in the Real World
- **Authors:** Yves-Simon Zeulner, Sandeep Selvaraj, Roberto Calandra
- **Venue:** arXiv 2025
- **Link:** [arXiv:2503.15481](https://arxiv.org/abs/2503.15481)
- **Summary:** First piano-playing robotic system using Sim2Real RL on a real dexterous robot hand. Trains entirely in simulation with domain randomization and deploys on physical hardware.

### 16. Music, Body, and Machine: Gesture-Based Synchronization in Human-Robot Musical Interaction
- **Venue:** Frontiers in Robotics and AI, 2024
- **Link:** [Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1461615/full)
- **Summary:** Theoretical framework for classifying musical gestures in human-robot interaction using Shimon, a robotic marimba player. Head movements significantly enhance temporal synchronization.

---

## Top Picks for Next Session

Papers that follow most naturally from FlueBricks + RealJam + Ghost in the Keys, and build on previously covered material (DDSP, AMT):

1. **Live Music Models (#1)** — the real-time generation frontier
2. **Symbiotic Virtuosity (#3)** — framing + a spectacular demo
3. **AI Harmonizer (#4)** — bridges your AMT session to live performance
