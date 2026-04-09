/**
 * Paper Constellation — data source of truth.
 *
 * To add a new paper: append an entry to `papers` with a stable `id`, the cluster it
 * belongs to, and a 2–3 sentence blurb. Layout recomputes automatically.
 *
 * To add a new cluster: append an entry to `clusters` with a stable `id`, a theme
 * color token, and an `order`. Cluster centers redistribute automatically, and the
 * scroll tour gains a new step.
 *
 * To add a cross-cluster edge: set `relatedTo: ['other-paper-id']` on either paper.
 */

export interface Cluster {
	/** Stable identifier used as foreign key by papers and layout. */
	id: string;
	/** Display label shown in tour steps and cluster hulls. */
	label: string;
	/** CSS custom property name from theme.css, e.g. '--orange'. */
	colorVar: string;
	/** One-line description shown in the scroll tour step for this cluster. */
	blurb: string;
	/** Ordering for tour sequence and auto-layout angle assignment. */
	order: number;
}

export interface Paper {
	/** Stable identifier, usually `${surname}-${year}` style. */
	id: string;
	title: string;
	/** Short authors string, e.g. 'Engel et al.' */
	authorsShort: string;
	year: number;
	/** Primary link (arxiv abstract or pdf). */
	link: string;
	/** Foreign key to Cluster.id */
	clusterId: string;
	/** Optional slug of a post under /posts/[slug] that discusses this paper. */
	postSlug?: string;
	/** Optional Excalidraw slides link. */
	excalidraw?: string;
	/** 2–3 sentence "why we picked it" description, academic-writer voice. */
	blurb: string;
	/** Optional explicit edges to other paper ids, drawn thicker than cluster edges. */
	relatedTo?: string[];
}

export const clusters: Cluster[] = [
	{
		id: 'signal-processing',
		label: 'Signal Processing & ML',
		colorVar: '--orange',
		blurb:
			'Classical DSP components expressed as differentiable modules, so networks only need to learn how to control synthesis, not reinvent it.',
		order: 0
	},
	{
		id: 'transcription',
		label: 'Music Transcription',
		colorVar: '--teal',
		blurb:
			'Recovering symbolic note events from audio. A decade of progress from dual-objective CNNs to sequence models to tiny deployable networks.',
		order: 1
	},
	{
		id: 'generation',
		label: 'Music Generation',
		colorVar: '--violet',
		blurb:
			'Producing new musical content from learned priors. Two poles of the design space: audio-domain masked modeling and symbolic anticipation.',
		order: 2
	}
];

export const papers: Paper[] = [
	// ────────────────────────────────────────────────────────────
	// Cluster: Signal Processing & ML
	// ────────────────────────────────────────────────────────────
	{
		id: 'ddsp-2020',
		title: 'DDSP: Differentiable Digital Signal Processing',
		authorsShort: 'Engel et al.',
		year: 2020,
		link: 'https://arxiv.org/abs/2001.04643',
		clusterId: 'signal-processing',
		postSlug: 'ddsp-from-scratch',
		excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/7mA11Gu7KXU',
		blurb:
			'We examine how classical synthesis components, in particular oscillator banks, time-varying filters, and convolutional reverb, can be expressed as differentiable modules so that gradients flow from audio output back through the entire synthesis pipeline. The inductive bias appears to be the salient contribution: by encoding the physics of sound directly into the architecture, DDSP reaches fidelity comparable to WaveNet at roughly 300x fewer parameters.'
	},
	{
		id: 'hayes-2024',
		title: 'A Review of Differentiable Digital Signal Processing for Music and Speech Synthesis',
		authorsShort: 'Hayes et al.',
		year: 2024,
		link: 'https://arxiv.org/abs/2308.15422',
		clusterId: 'signal-processing',
		blurb:
			'A survey of the DDSP field four years on, organized around the design choices that recur across applications (e.g., which DSP primitives to keep differentiable, how to parameterize time-varying filters, how to handle phase). We read it to ground our understanding of where DDSP has gone since the original paper and which open problems remain.',
		relatedTo: ['ddsp-2020']
	},

	// ────────────────────────────────────────────────────────────
	// Cluster: Music Transcription
	// ────────────────────────────────────────────────────────────
	{
		id: 'onsets-frames-2017',
		title: 'Onsets and Frames: Dual-Objective Piano Transcription',
		authorsShort: 'Hawthorne et al.',
		year: 2017,
		link: 'https://arxiv.org/pdf/1710.11153',
		clusterId: 'transcription',
		postSlug: 'music-transcription',
		blurb:
			'We examine the observation that note onsets are acoustically distinctive whereas sustain frames are ambiguous, which motivates training two specialized detectors jointly and using the onset predictions to gate the frame predictions at inference. The architecture is a CNN frontend feeding two bidirectional LSTM heads, and the gating rule is a deliberate algorithmic choice that removes spurious sustained notes, the most common failure mode of single-model approaches.'
	},
	{
		id: 'mt3-2021',
		title: 'MT3: Multi-Task Multitrack Music Transcription',
		authorsShort: 'Gardner et al.',
		year: 2021,
		link: 'https://arxiv.org/pdf/2111.03017',
		clusterId: 'transcription',
		postSlug: 'music-transcription',
		blurb:
			'We examine whether a general-purpose sequence-to-sequence Transformer can handle transcription across all instruments and datasets at once, using a carefully designed token vocabulary (instrument, time, pitch, on/off) rather than a transcription-specific architecture. Temperature-weighted mixture training appears to be the salient ingredient, allowing small datasets (e.g., GuitarSet, URMP) to contribute meaningful gradient signal alongside the much larger MAESTRO.',
		relatedTo: ['onsets-frames-2017']
	},
	{
		id: 'nmp-2022',
		title:
			'A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation',
		authorsShort: 'Bittner et al.',
		year: 2022,
		link: 'https://arxiv.org/pdf/2203.09893',
		clusterId: 'transcription',
		postSlug: 'music-transcription',
		blurb:
			'We examine how encoding harmonic structure in the input representation, via 8 harmonically shifted copies of a Constant-Q Transform, allows a 16,782-parameter CNN to perform competitive multi-instrument transcription. The tradeoff is explicit: some accuracy on any single instrument in exchange for a single deployable model that generalizes, which is the direct precursor to Spotify\'s open-source Basic Pitch tool.',
		relatedTo: ['mt3-2021', 'onsets-frames-2017']
	},

	// ────────────────────────────────────────────────────────────
	// Cluster: Music Generation
	// ────────────────────────────────────────────────────────────
	{
		id: 'vampnet-2023',
		title: 'VampNet: Music Generation via Masked Acoustic Token Modeling',
		authorsShort: 'Garcia et al.',
		year: 2023,
		link: 'https://arxiv.org/abs/2307.04686',
		clusterId: 'generation',
		postSlug: 'music-generation',
		excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/6vP3sw0sD6C',
		blurb:
			'We examine a non-autoregressive approach to audio generation that operates on discrete tokens from the Descript Audio Codec and uses a bidirectional masked transformer with iterative parallel decoding. The same model handles vamping, inpainting, and prompt continuation by varying only the mask pattern, which we posit is the most generalizable aspect of the design.'
	},
	{
		id: 'amt-2023',
		title: 'Anticipatory Music Transformer',
		authorsShort: 'Thickstun et al.',
		year: 2023,
		link: 'https://arxiv.org/abs/2306.08620',
		clusterId: 'generation',
		postSlug: 'music-generation',
		excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/1IR71UHPGmr',
		blurb:
			'We examine a symbolic-domain alternative to VampNet that models MIDI as a temporal point process and introduces an interleaving strategy where control tokens are placed a fixed interval before the events they condition. This anticipation mechanism preserves locality while defining valid stopping times for autoregressive sampling, which in turn enables controllable infilling without task-specific fine-tuning.',
		relatedTo: ['vampnet-2023']
	},

	// ────────────────────────────────────────────────────────────
	// Cluster: Music Generation — Real-Time Interaction
	// ────────────────────────────────────────────────────────────
	{
		id: 'aria-duet-2025',
		title: 'The Ghost in the Keys: A Disklavier Demo for Human-AI Musical Co-Creativity',
		authorsShort: 'Bradshaw et al.',
		year: 2025,
		link: 'https://arxiv.org/pdf/2511.01663',
		clusterId: 'generation',
		postSlug: 'real-time-ai-music',
		blurb:
			'We examine how continuous KV-cache prefill eliminates the 1–2 second latency bottleneck that blocks real-time human-AI piano duets. The system uses a Yamaha Disklavier as a shared physical interface: the human plays, signals a handover via the left pedal, and the Aria model generates a continuation performed acoustically on the same piano. The musicological evaluation across six styles demonstrates vocabulary consistency, prosodic response, and coherent phrasal dialogue.',
		relatedTo: ['realjam-2025', 'amt-2023']
	},
	{
		id: 'realjam-2025',
		title: 'ReaLJam: Real-Time Human-AI Music Jamming with Reinforcement Learning-Tuned Transformers',
		authorsShort: 'Scarlatos et al.',
		year: 2025,
		link: 'https://arxiv.org/pdf/2502.21267',
		clusterId: 'generation',
		postSlug: 'real-time-ai-music',
		blurb:
			'We examine how a commitment protocol and waterfall display can mask server round-trip latency rather than eliminate it, enabling live human-AI chord accompaniment via a web interface. The RL-tuned online Transformer learns to produce chords that anticipate the user\'s melody despite seeing only the past — analogous to process-reward RLHF. The user study reveals a surprisal–control paradox: musicians who felt more in control rated sessions lower.',
		relatedTo: ['aria-duet-2025', 'vampnet-2023']
	}
];
