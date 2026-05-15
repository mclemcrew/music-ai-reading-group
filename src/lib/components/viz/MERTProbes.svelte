<script lang="ts">
	import VizPanel from '$lib/components/ui/VizPanel.svelte';

	const PITCH_CLASS_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
	const INSTRUMENT_NAMES = ['Strings', 'Keys', 'Bass', 'Percussion', 'Ambient'];
	const GENRE_NAMES = ['Jazz', 'Rock', 'Electronic', 'Classical', 'Ambient'];

	type Probe = {
		pitchClass: number[]; // 12-D, sums to ~1
		instrument: number[]; // 5-D, sums to ~1
		genre: number[]; // 5-D, sums to ~1
	};

	type Clip = {
		id: string;
		label: string;
		hint: string;
		probe: Probe;
		synth: (ctx: AudioContext, master: GainNode, t0: number, duration: number) => void;
	};

	// === Synth helpers (mirrors CLAPRetrieval; small audio sketches) ===
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
			label: 'Jazz piano chord',
			hint: 'Cmaj7 (C–E–G–B) on a piano-like synth',
			probe: {
				pitchClass: [0.32, 0.02, 0.02, 0.02, 0.22, 0.02, 0.02, 0.18, 0.02, 0.02, 0.02, 0.12],
				instrument: [0.05, 0.78, 0.08, 0.04, 0.05],
				genre: [0.78, 0.05, 0.03, 0.12, 0.02]
			},
			synth(ctx, master, t0, dur) {
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
			label: 'Drum loop',
			hint: 'Programmed kick/snare/hat pattern',
			probe: {
				pitchClass: [0.13, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.11, 0.08, 0.08, 0.08, 0.04],
				instrument: [0.02, 0.02, 0.02, 0.92, 0.02],
				genre: [0.12, 0.45, 0.32, 0.04, 0.07]
			},
			synth(ctx, master, t0, dur) {
				const beatDur = 0.18;
				const beats = Math.floor(dur / beatDur);
				for (let b = 0; b < beats; b++) {
					const tb = t0 + b * beatDur;
					if (b % 2 === 0) {
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
						noiseBurst(ctx, master, tb, 0.1, 1200, 5000, 0.25);
					}
					noiseBurst(ctx, master, tb + beatDur / 2, 0.04, 6000, 12000, 0.08);
				}
			}
		},
		{
			id: 'bird',
			label: 'Bird chirp',
			hint: 'High-frequency swept tones',
			probe: {
				pitchClass: [0.09, 0.07, 0.07, 0.07, 0.09, 0.13, 0.09, 0.07, 0.07, 0.07, 0.07, 0.11],
				instrument: [0.05, 0.05, 0.05, 0.3, 0.55],
				genre: [0.05, 0.05, 0.05, 0.05, 0.8]
			},
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
			label: 'Bass riff',
			hint: 'G–A–C–A on a sawtooth bass',
			probe: {
				pitchClass: [0.1, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.34, 0.02, 0.32, 0.02, 0.08],
				instrument: [0.03, 0.05, 0.85, 0.05, 0.02],
				genre: [0.32, 0.5, 0.1, 0.06, 0.02]
			},
			synth(ctx, master, t0, dur) {
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
			label: 'Rain ambience',
			hint: 'Low-passed white noise',
			probe: {
				pitchClass: [0.083, 0.083, 0.084, 0.083, 0.083, 0.084, 0.083, 0.083, 0.084, 0.083, 0.083, 0.084],
				instrument: [0.015, 0.015, 0.015, 0.015, 0.94],
				genre: [0.02, 0.02, 0.02, 0.02, 0.92]
			},
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
			label: 'Violin note',
			hint: 'Sustained A4 with vibrato',
			probe: {
				pitchClass: [0.02, 0.02, 0.02, 0.02, 0.04, 0.02, 0.02, 0.02, 0.02, 0.72, 0.02, 0.08],
				instrument: [0.88, 0.06, 0.02, 0.02, 0.02],
				genre: [0.08, 0.02, 0.02, 0.85, 0.03]
			},
			synth(ctx, master, t0, dur) {
				const f0 = 440;
				const osc = ctx.createOscillator();
				osc.type = 'sawtooth';
				osc.frequency.value = f0;
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

	let selectedId = $state<string>('jazz');
	let selected = $derived(CLIPS.find((c) => c.id === selectedId)!);
	let playingId = $state<string | null>(null);
	let audioCtx: AudioContext | null = null;

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

	function selectClip(clip: Clip) {
		selectedId = clip.id;
		playClip(clip);
	}

	function argmax(arr: number[]): number {
		let best = 0;
		for (let i = 1; i < arr.length; i++) if (arr[i] > arr[best]) best = i;
		return best;
	}

	function topPrediction(arr: number[], names: string[]): { label: string; prob: number } {
		const i = argmax(arr);
		return { label: names[i], prob: arr[i] };
	}
</script>

<VizPanel title="MERT probes: one encoder, many tasks" titleColor="var(--orange)">
	<div class="clip-row">
		{#each CLIPS as clip}
			<button
				class="clip-card"
				class:selected={selectedId === clip.id}
				class:playing={playingId === clip.id}
				onclick={() => selectClip(clip)}
			>
				<div class="play-glyph">{playingId === clip.id ? '◼' : '▶'}</div>
				<div class="clip-name">{clip.label}</div>
				<div class="clip-hint">{clip.hint}</div>
			</button>
		{/each}
	</div>

	<div class="probes">
		<div class="probe">
			<div class="probe-header">
				<span class="probe-name">Pitch class probe</span>
				<span class="probe-top">
					top: <strong>{topPrediction(selected.probe.pitchClass, PITCH_CLASS_NAMES).label}</strong>
					({(topPrediction(selected.probe.pitchClass, PITCH_CLASS_NAMES).prob * 100).toFixed(0)}%)
				</span>
			</div>
			<div class="bars pitch-bars">
				{#each selected.probe.pitchClass as v, i}
					{@const isTop = i === argmax(selected.probe.pitchClass)}
					<div class="bar-cell">
						<div
							class="bar-fill pitch"
							class:top={isTop}
							style="height: {Math.max(2, v * 100)}%;"
						></div>
						<div class="bar-tick" class:top={isTop}>{PITCH_CLASS_NAMES[i]}</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="probe-row">
			<div class="probe">
				<div class="probe-header">
					<span class="probe-name">Instrument family probe</span>
					<span class="probe-top">
						top: <strong>{topPrediction(selected.probe.instrument, INSTRUMENT_NAMES).label}</strong>
						({(topPrediction(selected.probe.instrument, INSTRUMENT_NAMES).prob * 100).toFixed(0)}%)
					</span>
				</div>
				<div class="hbars">
					{#each selected.probe.instrument as v, i}
						{@const isTop = i === argmax(selected.probe.instrument)}
						<div class="hbar-row">
							<div class="hbar-label" class:top={isTop}>{INSTRUMENT_NAMES[i]}</div>
							<div class="hbar-track">
								<div
									class="hbar-fill"
									class:top={isTop}
									style="width: {Math.max(2, v * 100)}%;"
								></div>
							</div>
							<div class="hbar-val">{(v * 100).toFixed(0)}%</div>
						</div>
					{/each}
				</div>
			</div>

			<div class="probe">
				<div class="probe-header">
					<span class="probe-name">Genre probe</span>
					<span class="probe-top">
						top: <strong>{topPrediction(selected.probe.genre, GENRE_NAMES).label}</strong>
						({(topPrediction(selected.probe.genre, GENRE_NAMES).prob * 100).toFixed(0)}%)
					</span>
				</div>
				<div class="hbars">
					{#each selected.probe.genre as v, i}
						{@const isTop = i === argmax(selected.probe.genre)}
						<div class="hbar-row">
							<div class="hbar-label" class:top={isTop}>{GENRE_NAMES[i]}</div>
							<div class="hbar-track">
								<div
									class="hbar-fill"
									class:top={isTop}
									style="width: {Math.max(2, v * 100)}%;"
								></div>
							</div>
							<div class="hbar-val">{(v * 100).toFixed(0)}%</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>

	{#snippet caption()}
		<strong>Illustrative — not real MERT outputs.</strong> Real MERT-330M produces a 1024-dim feature vector per frame; each downstream task trains its own MLP probe on top of those frozen features. The three probes here simulate that pipeline: <strong>pitch class</strong> shows where the harmonic content is concentrated, <strong>instrument family</strong> shows what's making the sound, and <strong>genre</strong> shows a higher-level musical category. Click a clip and notice that the <em>same representation</em> would feed all three probes — this is what "one encoder, many tasks" means in practice. Notice also where the probes get confused: drum loop has high entropy on pitch class (no clear tonal center); bird chirps and rain confuse genre because they're not music; jazz piano gets E and G in addition to C because those are in the Cmaj7 chord.
	{/snippet}
</VizPanel>

<style>
	.clip-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.5rem;
		padding: 0.85rem 1.5rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
	}

	.clip-card {
		text-align: left;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.55rem 0.7rem;
		cursor: pointer;
		transition: all 0.15s;
		display: grid;
		grid-template-columns: auto 1fr;
		grid-template-rows: auto auto;
		gap: 0.05rem 0.55rem;
	}

	.clip-card:hover {
		border-color: var(--orange);
	}

	.clip-card.selected {
		border-color: var(--orange);
		background: rgba(224, 112, 32, 0.08);
	}

	.clip-card.playing {
		box-shadow: 0 0 0 2px var(--orange-glow);
	}

	.play-glyph {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--orange);
		grid-row: 1 / 3;
		align-self: center;
		width: 18px;
	}

	.clip-name {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.82rem;
		color: var(--text);
	}

	.clip-hint {
		font-size: 0.7rem;
		color: var(--text-muted);
		line-height: 1.3;
	}

	.probes {
		padding: 1rem 1.5rem 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.probe {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.7rem 0.9rem 0.5rem;
	}

	.probe-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}

	.probe-header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}

	.probe-name {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.78rem;
		color: var(--orange);
	}

	.probe-top {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--text-muted);
	}

	.probe-top strong {
		color: var(--text);
	}

	.pitch-bars {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		gap: 4px;
		align-items: end;
		height: 84px;
	}

	.bar-cell {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-end;
		height: 100%;
	}

	.bar-fill {
		width: 80%;
		background: rgba(224, 112, 32, 0.35);
		border-radius: 2px 2px 0 0;
		min-height: 2px;
	}

	.bar-fill.top {
		background: var(--orange);
	}

	.bar-tick {
		font-family: var(--font-mono);
		font-size: 0.62rem;
		color: var(--text-muted);
		margin-top: 3px;
	}

	.bar-tick.top {
		color: var(--orange);
		font-weight: 700;
	}

	.hbars {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.hbar-row {
		display: grid;
		grid-template-columns: 72px 1fr 36px;
		gap: 0.5rem;
		align-items: center;
	}

	.hbar-label {
		font-family: var(--font-display);
		font-size: 0.74rem;
		color: var(--text-muted);
	}

	.hbar-label.top {
		color: var(--orange);
		font-weight: 600;
	}

	.hbar-track {
		height: 10px;
		background: var(--surface-2);
		border-radius: 5px;
		overflow: hidden;
	}

	.hbar-fill {
		height: 100%;
		background: rgba(224, 112, 32, 0.35);
		border-radius: 5px;
	}

	.hbar-fill.top {
		background: var(--orange);
	}

	.hbar-val {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--text-muted);
		text-align: right;
	}

	@media (max-width: 640px) {
		.clip-row {
			padding: 0.65rem 1rem;
		}

		.probes {
			padding: 0.75rem 1rem;
		}

		.probe-row {
			grid-template-columns: 1fr;
		}

		.pitch-bars {
			height: 64px;
		}

		.hbar-row {
			grid-template-columns: 60px 1fr 32px;
		}
	}
</style>
