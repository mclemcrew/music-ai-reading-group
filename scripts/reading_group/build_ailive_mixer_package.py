#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SKILL_SCRIPTS = Path("/Users/mclemens/.codex/skills/excalidraw-diagrams/scripts")
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from ailive_mixer_content import (
    CITATIONS_MARKDOWN,
    DISCUSSION_QUESTIONS_MARKDOWN,
    MATH_WALKTHROUGH_MARKDOWN,
    OUTPUT_SLUG,
    PAPER_PATHS,
    PDF_PAGE_ASSETS,
    PRESENTER,
    READING_GROUP_DATE,
    SUMMARY_MARKDOWN,
)
from excalidraw_generator import BoxStyle, DiagramStyle, SlideDeck
from excalidraw_image_helper import (
    add_arrow_label,
    add_highlight_box,
    add_image,
    add_text,
)


OUTPUT_DIR = PROJECT_ROOT / "reading-group" / OUTPUT_SLUG
SLIDES_DIR = OUTPUT_DIR / "slides"
ASSETS_DIR = SLIDES_DIR / "assets"
MATH_DIR = OUTPUT_DIR / "math"
DECK_PATH = SLIDES_DIR / "ailive-mixer-reading-group.excalidraw"


def ensure_directories() -> None:
    for path in (OUTPUT_DIR, SLIDES_DIR, ASSETS_DIR, MATH_DIR):
        path.mkdir(parents=True, exist_ok=True)


def render_pdf_pages() -> dict[str, Path]:
    rendered_paths: dict[str, Path] = {}
    for asset in PDF_PAGE_ASSETS:
        prefix = ASSETS_DIR / asset["key"]
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "140",
                "-f",
                str(asset["page"]),
                "-l",
                str(asset["page"]),
                str(PAPER_PATHS[asset["pdf_key"]]),
                str(prefix),
            ],
            check=True,
        )
        rendered_path = ASSETS_DIR / f"{asset['key']}-{asset['page']}.png"
        rendered_paths[asset["key"]] = rendered_path
    return rendered_paths


def write_markdown_outputs() -> None:
    (OUTPUT_DIR / "summary.md").write_text(SUMMARY_MARKDOWN)
    (OUTPUT_DIR / "discussion-questions.md").write_text(DISCUSSION_QUESTIONS_MARKDOWN)
    (OUTPUT_DIR / "citations.md").write_text(CITATIONS_MARKDOWN)
    (MATH_DIR / "math_walkthrough.md").write_text(MATH_WALKTHROUGH_MARKDOWN)


def build_deck() -> tuple[SlideDeck, dict[str, object]]:
    deck = SlideDeck(
        slide_width=1200,
        slide_height=680,
        gap=400,
        diagram_style=DiagramStyle(roughness=1),
        box_style=BoxStyle(font_family="hand", font_size=18),
    )
    slides: dict[str, object] = {}

    s1 = deck.slide("Title")
    slides["title"] = s1
    s1.title("AILIVE MIXER")
    s1.text(
        "A deep learning automatic mixer for live performance\n"
        "Zurale, Lorente, Lester, Mitchell - arXiv:2603.15995v1\n"
        "Shure Incorporated - March 16, 2026",
        40,
        86,
        font_size=18,
    )
    s1.text(f"Presenter: {PRESENTER}\nReading Group | {READING_GROUP_DATE}", 40, 180, font_size=15)
    b11 = s1.box(700, 90, "Live multitrack\nmixing", width=180, height=70, role="input")
    b12 = s1.box(920, 90, "Bleed-aware\ninputs", width=180, height=70, role="process")
    b13 = s1.box(810, 220, "Zero-latency\ngain output", width=210, height=70, role="output")
    s1.arrow_between(b11, b13)
    s1.arrow_between(b12, b13)
    s1.note(
        "Context papers:\n"
        "- Steinmetz et al. 2020: DMC baseline\n"
        "- Tsiros and Palladini 2020: workflow / trust framing",
        700,
        340,
        font_size=14,
    )
    s1.footer("Main claim: offline automatic mixing assumptions break when the stage introduces bleed and latency constraints.")

    s2 = deck.slide("Why Live Mixing Is Different")
    slides["live_problem"] = s2
    s2.title("Live Mixing Is Not Offline Mixing")
    p21 = s2.box(40, 120, "Acoustic bleed\nbetween microphones", width=220, height=80, role="input")
    p22 = s2.box(300, 120, "Audio-visual sync\nleaves no reaction time", width=250, height=80, role="error")
    p23 = s2.box(590, 120, "No clean objective metric\nfor perceptual mix quality", width=260, height=80, role="neutral")
    p24 = s2.box(890, 120, "Engineers still need\ncontrol and override", width=240, height=80, role="param")
    for source in (p21, p22, p23):
        s2.arrow_between(source, p24, color="gray")
    goal = s2.box(420, 330, "Deployment target:\nhelpful live gain control", width=320, height=90, role="output")
    s2.arrow_between(p21, goal)
    s2.arrow_between(p22, goal)
    s2.arrow_between(p23, goal)
    s2.arrow_between(p24, goal)
    s2.note(
        "AILIVE focuses on the first two constraints.\n"
        "Channel-AI is useful because it keeps the fourth constraint visible.",
        780,
        350,
        font_size=14,
    )

    s3 = deck.slide("Landscape")
    slides["landscape"] = s3
    s3.title("Where AILIVE Sits")
    l1 = s3.box(40, 170, "Rule-based / classic\nautomatic mixing", width=180, height=70, role="neutral")
    l2 = s3.box(300, 170, "DMC 2020\nparametric offline\nmixing console", width=190, height=90, role="process")
    l3 = s3.box(580, 170, "Channel-AI 2020\nconsole-integrated\nhuman-centered assist", width=210, height=90, role="param")
    l4 = s3.box(880, 170, "AILIVE 2026\nbleed-aware live\ngain prediction", width=210, height=90, role="output")
    s3.arrow_between(l1, l2, "automation")
    s3.arrow_between(l2, l4, "architecture")
    s3.arrow_between(l3, l4, "workflow lens")
    s3.text("Technical lineage", 80, 120, font_size=16)
    s3.text("Deployment lens", 620, 120, font_size=16)
    s3.note(
        "AILIVE is not a broad survey contribution.\n"
        "It is a systems adaptation of DMC under live-console constraints.",
        820,
        360,
        font_size=14,
    )

    s4 = deck.slide("DMC Baseline")
    slides["dmc"] = s4
    s4.title("DMC Is the Direct Technical Baseline")
    d1 = s4.box(40, 160, "Input stems", width=120, height=55, role="input")
    d2 = s4.box(220, 160, "Encoder +\ncontext", width=150, height=70, role="process")
    d3 = s4.box(430, 160, "Differentiable\nconsole", width=170, height=70, role="process")
    d4 = s4.box(660, 160, "Human-readable\nparameters", width=180, height=70, role="output")
    d5 = s4.box(900, 160, "Stereo mix", width=120, height=55, role="output")
    s4.arrow_between(d1, d2)
    s4.arrow_between(d2, d3)
    s4.arrow_between(d3, d4)
    s4.arrow_between(d4, d5)
    s4.note(
        "What DMC gives AILIVE:\n"
        "- strong mixing-console inductive bias\n"
        "- parameter prediction, not opaque waveform output\n"
        "- stereo sum / difference loss\n"
        "\n"
        "What DMC does not solve:\n"
        "- live bleed corruption\n"
        "- 50 ms control updates\n"
        "- zero-latency deployment",
        60,
        300,
        font_size=14,
    )
    s4.footer("AILIVE keeps the parametric philosophy but drops to mono gain and rebuilds the timing model.")

    s5 = deck.slide("AILIVE Overview")
    slides["ailive_overview"] = s5
    s5.title("AILIVE Rebuilds the Stack for Stage Constraints")
    a1 = s5.box(40, 140, "Per-channel\nwaveform", width=120, height=60, role="input")
    a2 = s5.box(200, 140, "VGGish\nembedding", width=120, height=60, role="process")
    a3 = s5.box(360, 140, "Transformer\n(channel context)", width=180, height=70, role="process")
    a4 = s5.box(600, 140, "RMS\nconditioning", width=140, height=60, role="param")
    a5 = s5.box(790, 140, "GRU\n(time context)", width=140, height=60, role="process")
    a6 = s5.box(980, 140, "Gain MLP", width=120, height=60, role="output")
    a7 = s5.box(980, 300, "Apply gain\n+ sum mono", width=140, height=70, role="output")
    s5.arrow_between(a1, a2)
    s5.arrow_between(a2, a3)
    s5.arrow_between(a3, a4)
    s5.arrow_between(a4, a5)
    s5.arrow_between(a5, a6)
    s5.arrow_between(a6, a7)
    s5.note(
        "Architectural deltas vs. DMC:\n"
        "- RMS restores loudness information lost by embeddings\n"
        "- transformers model inter-channel dependence at multiple stages\n"
        "- GRU stabilizes the gain trajectory over time\n"
        "- output scope is only mono gain",
        60,
        330,
        font_size=14,
    )

    s6 = deck.slide("Multi-Rate Control")
    slides["multirate"] = s6
    s6.title("The Key Trick: Predict One Frame Ahead")
    c1 = s6.box(50, 150, "Long context\nF1 = 975 ms", width=180, height=70, role="process")
    c2 = s6.box(300, 150, "Short control frames\nF2 = 50 ms", width=200, height=70, role="param")
    c3 = s6.box(570, 150, "At time t:\nextract features", width=170, height=70, role="process")
    c4 = s6.box(800, 150, "Predict gain\nfor frame t+1", width=180, height=70, role="output")
    c5 = s6.box(800, 320, "Immediate use on\nupcoming audio", width=190, height=70, role="output")
    s6.arrow_between(c1, c2, "split rates")
    s6.arrow_between(c2, c3)
    s6.arrow_between(c3, c4, "one-step lookahead")
    s6.arrow_between(c4, c5)
    s6.math("g_hat[t+1] <- f(phi(x_t))", 80, 330)
    s6.math("mix_hat[t+1] <- g_hat[t+1] * x[t+1]", 80, 370)
    s6.note(
        "Why MR should help:\n"
        "- semantic context still comes from ~1 s audio\n"
        "- control only has to look 50 ms ahead\n"
        "- SR must look 975 ms ahead, which is slower and blurrier",
        60,
        440,
        font_size=14,
    )

    s7 = deck.slide("Training Data")
    slides["training"] = s7
    s7.title("Training Without a Real Live-Bleed Dataset")
    t1 = s7.box(40, 150, "MedleyDB isolated\nmultitracks", width=180, height=70, role="input")
    t2 = s7.box(300, 150, "Parametric room\nbleed simulator", width=200, height=70, role="process")
    t3 = s7.box(580, 150, "Bleed-corrupted\ntraining inputs", width=190, height=70, role="process")
    t4 = s7.box(860, 150, "Original human mix\nas target", width=180, height=70, role="output")
    s7.arrow_between(t1, t2)
    s7.arrow_between(t2, t3)
    s7.arrow_between(t3, t4)
    s7.note(
        "Reported training details:\n"
        "- 43 songs total, 35 train / 8 val, <= 8 raw tracks\n"
        "- randomize bleed parameters and input levels on the fly\n"
        "- MR-STFT loss at 440 / 884 / 3528 samples\n"
        "- freeze VGGish for 100 epochs, then finetune",
        70,
        330,
        font_size=14,
    )
    s7.footer("The key compromise: the supervision target still comes from an offline mix of isolated stems.")

    s8 = deck.slide("Evaluation")
    slides["evaluation"] = s8
    s8.title("Evaluation Is Subjective by Necessity")
    e1 = s8.box(60, 140, "8 live-performance\nsong segments", width=170, height=70, role="input")
    e2 = s8.box(310, 140, "15 critical listeners\nAPE web tool", width=180, height=70, role="process")
    e3 = s8.box(580, 140, "Models:\nALM-MR / ALM-SR /\nDMC-B-0L / DMC-OG / RAW", width=260, height=95, role="neutral")
    e4 = s8.box(930, 140, "Absolute + normalized\nratings", width=190, height=70, role="output")
    s8.arrow_between(e1, e2)
    s8.arrow_between(e2, e3)
    s8.arrow_between(e3, e4)
    s8.note(
        "Inference setup matters:\n"
        "- all mixes generated at 0 latency\n"
        "- no normalization applied at inference\n"
        "- raw tracks intentionally poorly gain-staged to mimic a novice live user",
        70,
        330,
        font_size=14,
    )

    s9 = deck.slide("Results")
    slides["results"] = s9
    s9.title("Result: ALM-MR Wins on Consistency")
    r1 = s9.box(80, 150, "ALM-MR", width=180, height=55, role="output")
    r2 = s9.box(80, 230, "ALM-SR", width=180, height=55, role="process")
    r3 = s9.box(80, 310, "DMC-B-0L", width=180, height=55, role="neutral")
    r4 = s9.box(80, 390, "DMC-OG", width=180, height=55, role="neutral")
    r5 = s9.box(80, 470, "RAW", width=180, height=55, role="error")
    s9.text("best", 285, 165, font_size=16)
    s9.text("worse", 285, 485, font_size=16)
    s9.note(
        "Paper's summary:\n"
        "ALM-MR > ALM-SR > DMC-B-0L > DMC-OG > RAW\n"
        "\n"
        "Statistics reported:\n"
        "- Kruskal-Wallis H = 156.485\n"
        "- p = 8.293 x 10^-33\n"
        "- both ALM variants separate from the rest\n"
        "- no strong evidence ALM-MR > ALM-SR statistically",
        420,
        170,
        font_size=15,
    )
    s9.footer("The supplement shows the original violin plots and where the paper's ranking comes from.")

    s10 = deck.slide("What MR Buys")
    slides["mr_benefits"] = s10
    s10.title("What the Multi-Rate Model Seems To Buy")
    m1 = s10.box(60, 180, "Fewer abrupt\ngain jumps", width=180, height=80, role="output")
    m2 = s10.box(330, 180, "Less clipping\nin live use", width=180, height=80, role="output")
    m3 = s10.box(600, 180, "Better transient /\npercussive handling", width=200, height=80, role="output")
    m4 = s10.box(900, 180, "Same semantic context,\nfaster control loop", width=220, height=80, role="process")
    s10.note(
        "Important nuance:\n"
        "these are the authors' qualitative interpretations of the listening study,\n"
        "not a fully instrumented gain-trajectory ablation.",
        70,
        360,
        font_size=14,
    )
    s10.footer("The paper's systems argument is basically: control rate matters.")

    s11 = deck.slide("Human-Centered Lens")
    slides["human_centered"] = s11
    s11.title("Zero Latency Is Necessary, Not Sufficient")
    h1 = s11.box(80, 140, "No\nautomation", width=130, height=55, role="neutral")
    h2 = s11.box(250, 140, "Assistance", width=130, height=55, role="process")
    h3 = s11.box(420, 140, "Partial\nautomation", width=150, height=55, role="param")
    h4 = s11.box(620, 140, "Conditional\nautomation", width=160, height=55, role="output")
    h5 = s11.box(840, 140, "High\nautomation", width=130, height=55, role="error")
    s11.arrow_between(h1, h2)
    s11.arrow_between(h2, h3)
    s11.arrow_between(h3, h4)
    s11.arrow_between(h4, h5)
    s11.note(
        "Channel-AI's warning for reading AILIVE:\n"
        "- live engineers are conservative because the cost of failure is high\n"
        "- user-invoked assistance is easier to trust than opaque full automation\n"
        "- AILIVE's parametric gain output is a deployable strength, not a weakness",
        80,
        290,
        font_size=14,
    )

    s12 = deck.slide("Comparison")
    slides["comparison"] = s12
    s12.title("Three-Paper Comparison")
    s12.box(230, 100, "DMC 2020", width=170, height=45, role="process")
    s12.box(500, 100, "AILIVE 2026", width=170, height=45, role="output")
    s12.box(770, 100, "Channel-AI 2020", width=190, height=45, role="param")
    rows = [
        ("Primary goal", "learn mix params", "live gain prediction", "console assistance"),
        ("Latency assumption", "offline", "0-latency target", "user-invoked"),
        ("Output", "gain / pan / FX", "mono gain", "suggested settings"),
        ("Evaluation", "perceptual mix study", "live listening study", "expert interviews"),
        ("Main risk", "offline realism", "workflow realism", "technical depth"),
    ]
    y = 180
    for label, dmc, ailive, channel_ai in rows:
        s12.text(label, 40, y + 10, font_size=15)
        s12.box(220, y, dmc, width=190, height=38, role="neutral", font_size=14)
        s12.box(490, y, ailive, width=190, height=38, role="output", font_size=14)
        s12.box(760, y, channel_ai, width=210, height=38, role="param", font_size=14)
        y += 66

    s13 = deck.slide("Discussion Questions")
    slides["discussion"] = s13
    s13.title("Discussion Questions")
    s13.text("1. How robust is simulated bleed as a stand-in for real live contamination?", 40, 100, font_size=16)
    s13.text("2. What breaks the one-frame-ahead zero-latency assumption?", 40, 165, font_size=16)
    s13.text("3. Is mono gain the right deployable scope, or too narrow to matter?", 40, 230, font_size=16)
    s13.text("4. Would you trust this more as parametric assistive control than as end-to-end audio?", 40, 295, font_size=16)
    s13.text("5. What missing experiment would most change your confidence in the paper?", 40, 360, font_size=16)
    s13.note("See `discussion-questions.md` for the longer list.", 40, 470, font_size=14)

    s14 = deck.slide("Open Questions")
    slides["open_questions"] = s14
    s14.title("Open Questions and Next Reads")
    s14.text("- Can the same control loop extend to EQ, dynamics, or spatialization?", 40, 100, font_size=16)
    s14.text("- What would a trustworthy console workflow around ALM actually look like?", 40, 155, font_size=16)
    s14.text("- Which diagnostics correlate with 'smooth but not sluggish' gain behavior?", 40, 210, font_size=16)
    s14.text("- How much of the win is architecture, and how much is 50 ms control?", 40, 265, font_size=16)
    s14.text("- What is the right baseline in 2026 for live automatic mixing?", 40, 320, font_size=16)
    n1 = s14.box(740, 120, "Read next:\nDMC 2020", width=180, height=70, role="process")
    n2 = s14.box(950, 120, "Read next:\nChannel-AI 2020", width=180, height=70, role="param")
    s14.note("This deck is AILIVE-first, but the supplements keep the broader landscape visible.", 740, 250, font_size=14)

    sd = deck.supplement("Supplement: DMC Original Figures", below_slide=4, height=980)
    slides["supp_dmc"] = sd
    sd.title("DMC Original Figures")
    sd.note(
        "Why keep this page:\n"
        "- it shows the original DMC block diagram\n"
        "- it makes the console inductive bias concrete\n"
        "- it reminds us that AILIVE is an adaptation, not a clean-sheet method",
        820,
        110,
        font_size=14,
    )

    sa = deck.supplement("Supplement: AILIVE Original Figures", below_slide=5, height=980)
    slides["supp_ailive_system"] = sa
    sa.title("AILIVE Original Figures")
    sa.note(
        "This page contains both Fig. 1 and Fig. 2.\n"
        "Use it when the redraw feels too schematic and the group wants the paper's exact framing.",
        820,
        110,
        font_size=14,
    )

    sm = deck.supplement("Supplement: Math and Control Loop", below_slide=6, height=900)
    slides["supp_math"] = sm
    sm.title("Math and Control Loop")
    sm.math("y_sum = y_left + y_right", 60, 120)
    sm.math("y_diff = y_left - y_right", 60, 160)
    sm.math("L_stereo = L_MR(y_hat_sum, y_sum) + L_MR(y_hat_diff, y_diff)", 60, 220)
    sm.math("g_hat[t+1] <- f(phi(x_t))", 60, 340)
    sm.math("mix_hat[t+1] <- g_hat[t+1] * x[t+1]", 60, 390)
    sm.note(
        "DMC's equation solves a representation problem.\n"
        "AILIVE's frame shift solves a deployment-timing problem.\n"
        "That is the key conceptual bridge across the papers.",
        60,
        500,
        font_size=15,
    )

    sr = deck.supplement("Supplement: AILIVE Result Plots", below_slide=9, height=980)
    slides["supp_ailive_results"] = sr
    sr.title("AILIVE Result Plots")
    sr.note(
        "What to point out on this page:\n"
        "- ALM-MR is the tightest high-rating cluster\n"
        "- ALM-SR is better than DMC but more spread out\n"
        "- the paper itself summarizes the rank order explicitly",
        820,
        110,
        font_size=14,
    )

    sh = deck.supplement("Supplement: Channel-AI Design Frame", below_slide=11, height=980)
    slides["supp_channel_ai"] = sh
    sh.title("Channel-AI Design Frame")
    sh.note(
        "This is the deployment reality check.\n"
        "The table and interface screenshot explain why 'good model output'\n"
        "is not the same as 'good console integration.'",
        820,
        110,
        font_size=14,
    )

    return deck, slides


def add_supplement_images(slides: dict[str, object], rendered_paths: dict[str, Path]) -> None:
    scene = json.loads(DECK_PATH.read_text())

    def place_page(slide_key: str, asset_key: str) -> tuple[float, float, str]:
        slide = slides[slide_key]
        add_image(
            scene,
            rendered_paths[asset_key],
            slide._x + 40,
            slide._y + 110,
            width=730,
            frame_id=slide._frame_id,
        )
        return slide._x, slide._y, slide._frame_id

    x, y, frame_id = place_page("supp_dmc", "dmc_architecture")
    add_highlight_box(scene, x + 105, y + 148, 610, 175, color="orange", frame_id=frame_id)
    add_highlight_box(scene, x + 485, y + 362, 240, 220, color="blue", frame_id=frame_id)
    add_text(scene, "main system graph", x + 820, y + 195, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 860, y + 225, x + 700, y + 230, frame_id=frame_id)
    add_text(scene, "TCN block", x + 820, y + 430, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 850, y + 455, x + 650, y + 460, frame_id=frame_id)

    x, y, frame_id = place_page("supp_ailive_system", "ailive_system")
    add_highlight_box(scene, x + 120, y + 135, 615, 190, color="orange", frame_id=frame_id)
    add_highlight_box(scene, x + 470, y + 380, 230, 150, color="blue", frame_id=frame_id)
    add_text(scene, "Fig. 1: ALM stack", x + 810, y + 195, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 860, y + 225, x + 730, y + 220, frame_id=frame_id)
    add_text(scene, "Fig. 2: multi-rate path", x + 810, y + 430, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 870, y + 460, x + 700, y + 450, frame_id=frame_id)
    add_text(
        scene,
        "Blue blocks run on the long frame.\nOrange blocks run on the short control frame.",
        x + 800,
        y + 270,
        font_size=13,
        frame_id=frame_id,
    )

    x, y, frame_id = place_page("supp_ailive_results", "ailive_results")
    add_highlight_box(scene, x + 120, y + 135, 220, 120, color="orange", frame_id=frame_id)
    add_highlight_box(scene, x + 420, y + 135, 220, 120, color="orange", frame_id=frame_id)
    add_highlight_box(scene, x + 82, y + 500, 590, 250, color="blue", frame_id=frame_id)
    add_text(scene, "absolute ratings", x + 820, y + 205, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 860, y + 235, x + 335, y + 220, frame_id=frame_id)
    add_text(scene, "normalized ratings", x + 820, y + 165, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 900, y + 190, x + 635, y + 185, frame_id=frame_id)
    add_text(scene, "ranking and statistics", x + 860, y + 560, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 960, y + 585, x + 670, y + 610, frame_id=frame_id)

    x, y, frame_id = place_page("supp_channel_ai", "channel_ai_framework")
    add_highlight_box(scene, x + 90, y + 170, 620, 135, color="orange", frame_id=frame_id)
    add_highlight_box(scene, x + 130, y + 380, 455, 295, color="blue", frame_id=frame_id)
    add_text(scene, "automation ladder", x + 820, y + 180, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 860, y + 210, x + 710, y + 220, frame_id=frame_id)
    add_text(scene, "interface + design guidelines", x + 790, y + 500, font_size=13, frame_id=frame_id)
    add_arrow_label(scene, x + 940, y + 525, x + 580, y + 520, frame_id=frame_id)
    add_text(
        scene,
        "Use this frame to discuss trust calibration,\n"
        "user invocation, and why full automation is not the only goal.",
        x + 790,
        y + 280,
        font_size=13,
        frame_id=frame_id,
    )

    DECK_PATH.write_text(json.dumps(scene, indent=2))


def main() -> None:
    ensure_directories()
    rendered_paths = render_pdf_pages()
    write_markdown_outputs()
    deck, slides = build_deck()
    deck.save(DECK_PATH)
    add_supplement_images(slides, rendered_paths)
    print(f"Wrote package to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
