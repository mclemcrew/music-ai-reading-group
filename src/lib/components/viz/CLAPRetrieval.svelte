<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';

	const DIMS = ['rhythmic', 'harmonic', 'bright', 'natural', 'speech', 'sustained'];

	type Clip = {
		id: string;
		label: string;
		tags: string[];
		vec: number[]; // 6-D embedding
		synth: (ctx: AudioContext, master: GainNode, t0: number, duration: number) => void;
	};

	function clamp01(v: number): number {
		return Math.max(0, Math.min(1, v));
	}

	// === Synth helpers ===
	function envelope(
		gain: GainNode,
		ctx: AudioContext,
		t0: number,
		attack: number,
		hold: number,
		release: number,
		peak = 0.5
	) {
		gain.gain.setValueAtTime(0, t0);
		gain.gain.linearRampToValueAtTime(peak, t0 + attack);
		gain.gain.setValueAtTime(peak, t0 + attack + hold);
		gain.gain.linearRampToValueAtTime(0, t0 + attack + hold + release);
	}

	function tone(
		ctx: AudioContext,
		master: GainNode,
		f: number,
		t0: number,
		dur: number,
		type: OscillatorType = 'sine',
		amp = 0.18
	) {
		const osc = ctx.createOscillator();
		osc.type = type;
		osc.frequency.value = f;
		const g = ctx.createGain();
		envelope(g, ctx, t0, 0.02, dur - 0.08, 0.06, amp);
		osc.connect(g).connect(master);
		osc.start(t0);
		osc.stop(t0 + dur + 0.05);
	}

	function noiseBurst(
		ctx: AudioContext,
		master: GainNode,
		t0: number,
		dur: number,
		lowF: number,
		highF: number,
		amp = 0.18
	) {
		const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
		const data = buf.getChannelData(0);
		for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
		const src = ctx.createBufferSource();
		src.buffer = buf;
		const bp = ctx.createBiquadFilter();
		bp.type = 'bandpass';
		bp.frequency.value = (lowF + highF) / 2;
		bp.Q.value = Math.max(0.4, (lowF + highF) / (highF - lowF));
		const g = ctx.createGain();
		envelope(g, ctx, t0, 0.005, dur * 0.4, dur * 0.5, amp);
		src.connect(bp).connect(g).connect(master);
		src.start(t0);
		src.stop(t0 + dur + 0.05);
	}

	const CLIPS: Clip[] = [
		{
			id: 'jazz',
			label: 'jazz piano chord',
			tags: ['music', 'harmonic', 'piano', 'jazz', 'chord', 'sustained'],
			vec: [0.1, 0.95, 0.5, 0.2, 0.0, 0.9],
			synth(ctx, master, t0, dur) {
				// Cmaj7: C4 E4 G4 B4
				const fs = [261.63, 329.63, 392.0, 493.88];
				for (const f of fs) {
					tone(ctx, master, f, t0, dur, 'triangle', 0.12);
					tone(ctx, master, f * 2, t0, dur, 'sine', 0.04);
					tone(ctx, master, f * 3, t0, dur, 'sine', 0.02);
				}
			}
		},
		{
			id: 'drums',
			label: 'drum loop',
			tags: ['rhythmic', 'percussion', 'beat', 'drums', 'fast'],
			vec: [0.95, 0.15, 0.4, 0.3, 0.0, 0.0],
			synth(ctx, master, t0, dur) {
				const beatDur = 0.18;
				const beats = Math.floor(dur / beatDur);
				for (let b = 0; b < beats; b++) {
					const tb = t0 + b * beatDur;
					if (b % 2 === 0) {
						// Kick
						const osc = ctx.createOscillator();
						osc.type = 'sine';
						osc.frequency.setValueAtTime(120, tb);
						osc.frequency.exponentialRampToValueAtTime(40, tb + 0.08);
						const g = ctx.createGain();
						envelope(g, ctx, tb, 0.001, 0.04, 0.08, 0.35);
						osc.connect(g).connect(master);
						osc.start(tb);
						osc.stop(tb + 0.18);
					} else {
						// Snare
						noiseBurst(ctx, master, tb, 0.1, 1200, 5000, 0.25);
					}
					// Hat
					noiseBurst(ctx, master, tb + beatDur / 2, 0.04, 6000, 12000, 0.08);
				}
			}
		},
		{
			id: 'bird',
			label: 'bird chirp',
			tags: ['bird', 'high', 'bright', 'natural', 'outdoor', 'chirp'],
			vec: [0.45, 0.35, 0.95, 0.92, 0.05, 0.2],
			synth(ctx, master, t0, dur) {
				const numChirps = 4;
				for (let i = 0; i < numChirps; i++) {
					const tc = t0 + 0.05 + i * (dur / numChirps);
					const osc = ctx.createOscillator();
					osc.type = 'sine';
					osc.frequency.setValueAtTime(2800 + i * 200, tc);
					osc.frequency.exponentialRampToValueAtTime(4200 + i * 150, tc + 0.08);
					osc.frequency.exponentialRampToValueAtTime(3500, tc + 0.16);
					const g = ctx.createGain();
					envelope(g, ctx, tc, 0.01, 0.08, 0.06, 0.2);
					osc.connect(g).connect(master);
					osc.start(tc);
					osc.stop(tc + 0.2);
				}
			}
		},
		{
			id: 'bass',
			label: 'bass riff',
			tags: ['bass', 'low', 'rhythmic', 'music', 'groove'],
			vec: [0.65, 0.75, 0.0, 0.1, 0.0, 0.5],
			synth(ctx, master, t0, dur) {
				// 4 notes: G2, A2, C3, A2
				const notes = [98, 110, 130.81, 110];
				const noteDur = dur / notes.length;
				for (let i = 0; i < notes.length; i++) {
					const tn = t0 + i * noteDur;
					tone(ctx, master, notes[i], tn, noteDur * 0.9, 'sawtooth', 0.18);
					tone(ctx, master, notes[i] * 2, tn, noteDur * 0.9, 'sine', 0.05);
				}
			}
		},
		{
			id: 'rain',
			label: 'rain ambience',
			tags: ['rain', 'nature', 'ambient', 'natural', 'outdoor', 'noise', 'sustained'],
			vec: [0.3, 0.0, 0.25, 0.95, 0.0, 0.92],
			synth(ctx, master, t0, dur) {
				const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
				const data = buf.getChannelData(0);
				for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * 0.7;
				const src = ctx.createBufferSource();
				src.buffer = buf;
				const lp = ctx.createBiquadFilter();
				lp.type = 'lowpass';
				lp.frequency.value = 4000;
				lp.Q.value = 0.5;
				const g = ctx.createGain();
				envelope(g, ctx, t0, 0.1, dur - 0.3, 0.2, 0.25);
				src.connect(lp).connect(g).connect(master);
				src.start(t0);
				src.stop(t0 + dur + 0.05);
			}
		},
		{
			id: 'violin',
			label: 'violin note',
			tags: ['violin', 'music', 'sustained', 'harmonic', 'string', 'melodic'],
			vec: [0.05, 0.9, 0.55, 0.3, 0.0, 0.95],
			synth(ctx, master, t0, dur) {
				const f0 = 440; // A4
				const osc = ctx.createOscillator();
				osc.type = 'sawtooth';
				osc.frequency.value = f0;
				// Vibrato
				const lfo = ctx.createOscillator();
				lfo.frequency.value = 5;
				const lfoGain = ctx.createGain();
				lfoGain.gain.value = 4;
				lfo.connect(lfoGain).connect(osc.frequency);
				const filt = ctx.createBiquadFilter();
				filt.type = 'lowpass';
				filt.frequency.value = 2400;
				filt.Q.value = 2;
				const g = ctx.createGain();
				envelope(g, ctx, t0, 0.08, dur - 0.3, 0.22, 0.18);
				osc.connect(filt).connect(g).connect(master);
				osc.start(t0);
				osc.stop(t0 + dur + 0.05);
				lfo.start(t0);
				lfo.stop(t0 + dur + 0.05);
			}
		}
	];

	// Keyword → dimension contributions
	const KEYWORD_MAP: Record<string, number[]> = {
		// rhythmic
		rhythmic: [1, 0, 0, 0, 0, 0],
		rhythm: [0.9, 0, 0, 0, 0, 0],
		beat: [0.85, 0, 0, 0, 0, 0],
		drum: [0.95, -0.1, 0, 0, 0, -0.2],
		drums: [0.95, -0.1, 0, 0, 0, -0.2],
		percussion: [0.9, 0, 0, 0, 0, -0.2],
		fast: [0.7, 0, 0.1, 0, 0, -0.3],
		groove: [0.7, 0.2, 0, 0, 0, 0],
		// harmonic
		music: [0, 0.7, 0, 0, 0, 0.2],
		musical: [0, 0.8, 0, 0, 0, 0.2],
		chord: [0, 0.95, 0, 0, 0, 0.5],
		harmonic: [0, 0.95, 0, 0, 0, 0.3],
		jazz: [0.2, 0.85, 0.2, 0, 0, 0.4],
		piano: [0, 0.9, 0.3, 0, 0, 0.5],
		melodic: [0, 0.85, 0.2, 0, 0, 0.4],
		string: [0, 0.85, 0.4, 0, 0, 0.6],
		violin: [0, 0.85, 0.5, 0, 0, 0.7],
		bass: [0.4, 0.7, -0.4, 0, 0, 0.3],
		// bright
		bright: [0, 0, 1, 0, 0, 0],
		high: [0, 0, 0.85, 0, 0, 0],
		treble: [0, 0, 0.85, 0, 0, 0],
		shrill: [0, 0, 0.9, 0, 0, 0],
		// natural
		natural: [0, 0, 0, 1, 0, 0],
		nature: [0, 0, 0, 0.95, 0, 0],
		outdoor: [0, 0, 0, 0.95, 0, 0],
		outside: [0, 0, 0, 0.9, 0, 0],
		rain: [0.2, 0, 0, 0.95, 0, 0.7],
		bird: [0.3, 0, 0.8, 0.9, 0, 0],
		birds: [0.3, 0, 0.8, 0.9, 0, 0],
		chirp: [0.4, 0, 0.9, 0.9, 0, 0],
		ambient: [0, 0, 0, 0.6, 0, 0.9],
		ambience: [0, 0, 0, 0.6, 0, 0.9],
		// speech
		speech: [0, 0, 0, 0, 1, 0],
		voice: [0, 0, 0, 0, 0.9, 0],
		talking: [0, 0, 0, 0, 0.9, 0],
		vocal: [0, 0.3, 0, 0, 0.7, 0],
		// sustained
		sustained: [0, 0, 0, 0, 0, 1],
		long: [0, 0, 0, 0, 0, 0.7],
		drone: [0, 0.2, 0, 0, 0, 0.95],
		note: [0, 0.4, 0, 0, 0, 0.7],
		pad: [0, 0.4, 0, 0, 0, 0.9],
		// negative ones
		low: [0, 0, -0.7, 0, 0, 0]
	};

	function embedQuery(text: string): number[] {
		const vec = new Array(6).fill(0);
		const words = text.toLowerCase().match(/[a-z]+/g) || [];
		let n = 0;
		for (const w of words) {
			const v = KEYWORD_MAP[w];
			if (v) {
				for (let i = 0; i < 6; i++) vec[i] += v[i];
				n += 1;
			}
		}
		if (n === 0) return vec; // all zeros
		// Average, clamp
		for (let i = 0; i < 6; i++) vec[i] = clamp01(vec[i] / Math.max(1, n * 0.6));
		return vec;
	}

	function cosine(a: number[], b: number[]): number {
		let dot = 0,
			na = 0,
			nb = 0;
		for (let i = 0; i < a.length; i++) {
			dot += a[i] * b[i];
			na += a[i] * a[i];
			nb += b[i] * b[i];
		}
		const denom = Math.sqrt(na) * Math.sqrt(nb);
		return denom < 1e-9 ? 0 : dot / denom;
	}

	let query = $state('rhythmic percussion');
	let queryVec = $derived(embedQuery(query));
	let ranked = $derived.by(() => {
		const scored = CLIPS.map((c) => ({ clip: c, sim: cosine(queryVec, c.vec) }));
		scored.sort((a, b) => b.sim - a.sim);
		return scored;
	});

	let audioCtx: AudioContext | null = null;
	let playingId = $state<string | null>(null);

	function playClip(clip: Clip) {
		if (!audioCtx) audioCtx = new AudioContext();
		if (audioCtx.state === 'suspended') audioCtx.resume();
		const master = audioCtx.createGain();
		master.gain.value = 0.7;
		master.connect(audioCtx.destination);
		const t0 = audioCtx.currentTime + 0.02;
		const dur = 1.8;
		clip.synth(audioCtx, master, t0, dur);
		playingId = clip.id;
		setTimeout(() => {
			if (playingId === clip.id) playingId = null;
		}, dur * 1000 + 200);
	}

	const PRESETS = ['rhythmic percussion', 'jazz chord', 'high bird sounds', 'rain ambience', 'sustained drone'];
</script>

<VizPanel title="CLAP-style retrieval (illustrative)" titleColor="var(--blue)">
	<div class="query-row">
		<input
			type="text"
			bind:value={query}
			placeholder="describe a sound..."
			class="query-input"
		/>
		<div class="presets">
			{#each PRESETS as p}
				<button class="preset" onclick={() => (query = p)}>{p}</button>
			{/each}
		</div>
	</div>

	<div class="embed-row">
		<div class="embed-block">
			<div class="embed-label">query "{query || '—'}" → embedding</div>
			<div class="vec-bars">
				{#each queryVec as v, i}
					<div class="vec-bar">
						<div class="vec-bar-fill" style="height: {Math.max(2, v * 100)}%;"></div>
						<div class="vec-dim">{DIMS[i]}</div>
					</div>
				{/each}
			</div>
		</div>
	</div>

	<div class="results">
		{#each ranked as { clip, sim }, idx}
			<div class="result-row" class:top={idx === 0}>
				<div class="rank">{idx + 1}</div>
				<button
					class="play-btn"
					class:playing={playingId === clip.id}
					onclick={() => playClip(clip)}
					aria-label="Play {clip.label}"
				>
					{playingId === clip.id ? '◼' : '▶'}
				</button>
				<div class="clip-info">
					<div class="clip-label">{clip.label}</div>
					<div class="clip-tags">{clip.tags.slice(0, 4).join(' · ')}</div>
				</div>
				<div class="mini-vec">
					{#each clip.vec as v}
						<div class="mini-bar" style="height: {Math.max(3, v * 24)}px;"></div>
					{/each}
				</div>
				<div class="sim-bar-wrap">
					<div class="sim-bar" style="width: {Math.max(2, sim * 100)}%;"></div>
					<span class="sim-val">{sim.toFixed(2)}</span>
				</div>
			</div>
		{/each}
	</div>

	{#snippet caption()}
		<strong>Illustrative — not real CLAP.</strong> Real CLAP encodes audio and text into a learned 512-dim space (~150M parameters per encoder) trained on millions of pairs. Here we use a hand-designed 6-D semantic space so you can see the mechanism: the query gets embedded, every clip is already embedded, and cosine similarity ranks the clips. Same recipe, vastly simpler geometry. Notice how queries that name musical structure (chords, key, instrumentation) work well because the space has axes for them — but a query like <em>"in the key of G minor"</em> would fail here, exactly as it tends to fail in real CLAP, because the training distribution rarely captions that.
	{/snippet}
</VizPanel>

<style>
	.query-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.85rem 1.5rem 0.5rem;
		border-bottom: 1px solid var(--border);
	}

	.query-input {
		font-family: var(--font-body);
		font-size: 0.95rem;
		padding: 0.55rem 0.85rem;
		border: 1px solid var(--border);
		border-radius: 7px;
		background: var(--surface);
		color: var(--text);
		outline: none;
		transition: border-color 0.15s;
	}

	.query-input:focus {
		border-color: var(--blue);
	}

	.presets {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}

	.preset {
		font-family: var(--font-display);
		font-size: 0.72rem;
		padding: 0.25rem 0.6rem;
		border-radius: 12px;
		border: 1px solid var(--border);
		background: var(--surface-2);
		color: var(--text-muted);
		cursor: pointer;
		transition: all 0.15s;
	}

	.preset:hover {
		border-color: var(--blue);
		color: var(--blue);
	}

	.embed-row {
		padding: 0.85rem 1.5rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
	}

	.embed-label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		color: var(--text-muted);
		margin-bottom: 0.4rem;
	}

	.vec-bars {
		display: flex;
		gap: 0.5rem;
		align-items: flex-end;
		height: 56px;
	}

	.vec-bar {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-end;
		min-width: 40px;
		height: 100%;
	}

	.vec-bar-fill {
		width: 80%;
		background: linear-gradient(to top, var(--blue), rgba(41, 121, 255, 0.4));
		border-radius: 2px 2px 0 0;
	}

	.vec-dim {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		color: var(--text-muted);
		margin-top: 4px;
	}

	.results {
		display: flex;
		flex-direction: column;
	}

	.result-row {
		display: grid;
		grid-template-columns: 28px 36px 1fr 64px 1fr;
		gap: 0.7rem;
		align-items: center;
		padding: 0.55rem 1.5rem;
		border-bottom: 1px solid var(--surface-3);
		transition: background 0.15s;
	}

	.result-row:hover {
		background: var(--surface-2);
	}

	.result-row.top {
		background: rgba(224, 112, 32, 0.05);
	}

	.rank {
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--text-muted);
		text-align: center;
	}

	.play-btn {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		cursor: pointer;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}

	.play-btn:hover {
		border-color: var(--orange);
		color: var(--orange);
	}

	.play-btn.playing {
		background: var(--orange);
		color: white;
		border-color: var(--orange);
	}

	.clip-info {
		min-width: 0;
	}

	.clip-label {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.88rem;
		color: var(--text);
	}

	.clip-tags {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--text-muted);
	}

	.mini-vec {
		display: flex;
		gap: 2px;
		align-items: flex-end;
		height: 26px;
	}

	.mini-bar {
		width: 6px;
		background: rgba(41, 121, 255, 0.55);
		border-radius: 1px 1px 0 0;
	}

	.sim-bar-wrap {
		position: relative;
		height: 14px;
		background: var(--surface-2);
		border-radius: 7px;
		overflow: hidden;
		display: flex;
		align-items: center;
	}

	.sim-bar {
		height: 100%;
		background: linear-gradient(to right, rgba(224, 112, 32, 0.5), var(--orange));
		border-radius: 7px;
	}

	.sim-val {
		position: absolute;
		right: 8px;
		top: 50%;
		transform: translateY(-50%);
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--text);
		font-weight: 600;
	}

	@media (max-width: 640px) {
		.result-row {
			grid-template-columns: 20px 28px 1fr;
			grid-template-rows: auto auto;
			padding: 0.5rem 1rem;
		}

		.mini-vec,
		.sim-bar-wrap {
			grid-column: 3 / 4;
		}

		.embed-row,
		.query-row {
			padding: 0.65rem 1rem;
		}
	}
</style>
