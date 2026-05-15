<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	type Source = 'c4' | 'cmajor' | 'octaves';

	const SOURCES: Record<Source, { label: string; fundamentals: number[]; description: string }> = {
		c4: {
			label: 'C4 alone',
			fundamentals: [261.63],
			description: 'Single note: C4 with overtones at 2x, 3x, 4x ... 8x its fundamental.'
		},
		cmajor: {
			label: 'C major chord',
			fundamentals: [261.63, 329.63, 392.0],
			description: 'C4 + E4 + G4 — three fundamentals, each with their own harmonic stack.'
		},
		octaves: {
			label: 'C octaves',
			fundamentals: [130.81, 261.63, 523.25],
			description: 'C3 + C4 + C5 — three octaves of the same pitch class, two semitones apart by powers of 2.'
		}
	};

	let source = $state<Source>('cmajor');
	let showAnnotations = $state(true);
	let melCanvas: HTMLCanvasElement;
	let cqtCanvas: HTMLCanvasElement;

	const NUM_HARMONICS = 8;
	const N_TIME = 40;
	const N_MEL = 64;
	const F_MAX = 4000;
	const MIDI_MIN = 36; // C2
	const MIDI_MAX = 96; // C7
	const N_CQT = MIDI_MAX - MIDI_MIN; // 60 semitone bins

	function hzToMel(hz: number): number {
		return 2595 * Math.log10(1 + hz / 700);
	}
	function melToHz(mel: number): number {
		return 700 * (Math.pow(10, mel / 2595) - 1);
	}
	function freqToMidi(f: number): number {
		return 12 * Math.log2(f / 440) + 69;
	}
	function midiToFreq(midi: number): number {
		return 440 * Math.pow(2, (midi - 69) / 12);
	}
	function midiToNoteName(midi: number): string {
		const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
		const oct = Math.floor(midi / 12) - 1;
		return names[midi % 12] + oct;
	}

	function getHarmonics(): Array<{ f: number; amp: number; fundIdx: number; k: number }> {
		const result: Array<{ f: number; amp: number; fundIdx: number; k: number }> = [];
		const funds = SOURCES[source].fundamentals;
		for (let fi = 0; fi < funds.length; fi++) {
			for (let k = 1; k <= NUM_HARMONICS; k++) {
				result.push({ f: k * funds[fi], amp: 1 / Math.pow(k, 0.7), fundIdx: fi, k });
			}
		}
		return result;
	}

	// Colors per fundamental, matching the site's accent palette
	const FUND_COLORS = ['#e07020', '#2979ff', '#1a9e8f'];

	// Build a static spectrum (the same across all time frames since the chord is sustained)
	function buildMelSpectrum(): number[] {
		const harmonics = getHarmonics();
		const melMax = hzToMel(F_MAX);
		const bins = new Array(N_MEL).fill(0);
		for (const { f, amp } of harmonics) {
			if (f > F_MAX) continue;
			const mel = hzToMel(f);
			const fracBin = (mel / melMax) * N_MEL;
			// Triangular spread across 1-2 neighboring bins (mimics mel filterbank smoothing)
			const i0 = Math.floor(fracBin);
			const frac = fracBin - i0;
			if (i0 >= 0 && i0 < N_MEL) bins[i0] += amp * (1 - frac);
			if (i0 + 1 < N_MEL) bins[i0 + 1] += amp * frac;
			// Also bleed into i0-1 to simulate filter width — mel bins get wider at higher freq
			if (i0 - 1 >= 0) bins[i0 - 1] += amp * 0.15;
		}
		return bins;
	}

	function buildCqtSpectrum(): number[] {
		const harmonics = getHarmonics();
		const bins = new Array(N_CQT).fill(0);
		for (const { f, amp } of harmonics) {
			const midi = freqToMidi(f);
			const bin = midi - MIDI_MIN;
			if (bin < 0 || bin >= N_CQT) continue;
			const i0 = Math.floor(bin);
			const frac = bin - i0;
			if (i0 >= 0 && i0 < N_CQT) bins[i0] += amp * (1 - frac);
			if (i0 + 1 < N_CQT) bins[i0 + 1] += amp * frac;
		}
		return bins;
	}

	function intensityColor(v: number, vmax: number): string {
		const t = Math.max(0, Math.min(1, v / vmax));
		// Cream → orange ramp
		const eased = Math.pow(t, 0.55);
		// Background cream is (250,250,246), target orange is (224,112,32)
		const r = Math.round(250 * (1 - eased) + 224 * eased);
		const g = Math.round(250 * (1 - eased) + 112 * eased);
		const b = Math.round(246 * (1 - eased) + 32 * eased);
		return `rgb(${r},${g},${b})`;
	}

	function drawHeatmap(
		canvas: HTMLCanvasElement,
		spectrum: number[],
		title: string,
		titleColor: string,
		opts: {
			yTickFreqs: number[];
			yTickLabels: string[];
			yPositionFn: (freq: number) => number;
			semitoneGrid?: boolean;
			harmonicAnnotations?: { f: number; fundIdx: number; k: number; label: string }[];
		}
	) {
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const padL = 44;
		const padR = showAnnotations && opts.harmonicAnnotations ? 60 : 14;
		const padT = 22;
		const padB = 22;
		const plotW = w - padL - padR;
		const plotH = h - padT - padB;
		const cellW = plotW / N_TIME;
		const numBins = spectrum.length;
		const cellH = plotH / numBins;

		// vmax for normalization
		const vmax = Math.max(...spectrum, 1e-6);

		// Heatmap cells — bottom = low freq, top = high freq
		for (let i = 0; i < numBins; i++) {
			const y = padT + plotH - (i + 1) * cellH;
			ctx.fillStyle = intensityColor(spectrum[i], vmax);
			for (let t = 0; t < N_TIME; t++) {
				const x = padL + t * cellW;
				ctx.fillRect(x, y, Math.ceil(cellW) + 1, Math.ceil(cellH) + 1);
			}
		}

		// Frame
		ctx.strokeStyle = 'rgba(31,29,27,0.32)';
		ctx.lineWidth = 1;
		ctx.strokeRect(padL, padT, plotW, plotH);

		// Semitone grid on CQT (every C note)
		if (opts.semitoneGrid) {
			ctx.strokeStyle = 'rgba(124,77,255,0.18)';
			ctx.lineWidth = 0.6;
			ctx.setLineDash([2, 2]);
			for (let midi = MIDI_MIN; midi <= MIDI_MAX; midi += 12) {
				const bin = midi - MIDI_MIN;
				const y = padT + plotH - (bin / N_CQT) * plotH;
				ctx.beginPath();
				ctx.moveTo(padL, y);
				ctx.lineTo(padL + plotW, y);
				ctx.stroke();
			}
			ctx.setLineDash([]);
		}

		// Y-axis labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'right';
		for (let i = 0; i < opts.yTickLabels.length; i++) {
			const y = opts.yPositionFn(opts.yTickFreqs[i]);
			ctx.fillText(opts.yTickLabels[i], padL - 5, y + 3);
		}

		// Title
		ctx.fillStyle = titleColor;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'left';
		ctx.fillText(title, padL, 13);

		// X-axis label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.fillText('time →', padL + plotW / 2, h - 6);

		// Per-fundamental harmonic stack annotations: colored dot + label per harmonic
		if (showAnnotations && opts.harmonicAnnotations) {
			// Limit to first MAX_K harmonics per fundamental so labels don't crowd
			const MAX_K = SOURCES[source].fundamentals.length > 1 ? 4 : 8;
			// Track label positions per fundamental to dodge collisions
			const usedY: Record<number, number[]> = {};
			for (const h of opts.harmonicAnnotations) {
				if (h.k > MAX_K) continue;
				const y = opts.yPositionFn(h.f);
				if (y < padT - 4 || y > padT + plotH + 4) continue;
				const color = FUND_COLORS[h.fundIdx % FUND_COLORS.length];
				// Dot at the right edge of the heatmap
				const dotX = padL + plotW + 6;
				ctx.fillStyle = color;
				ctx.beginPath();
				ctx.arc(dotX, y, 3.4, 0, Math.PI * 2);
				ctx.fill();
				// Label to the right of the dot
				// Dodge labels stacked vertically by fundamental
				const fundKey = h.fundIdx;
				if (!usedY[fundKey]) usedY[fundKey] = [];
				let labelY = y + 3;
				for (const prev of usedY[fundKey]) {
					if (Math.abs(labelY - prev) < 10) {
						labelY = prev - 11;
					}
				}
				usedY[fundKey].push(labelY);
				ctx.fillStyle = color;
				ctx.font = canvasFont(w, 9, h.k === 1 ? '600' : '400');
				ctx.textAlign = 'left';
				ctx.fillText(h.label, dotX + 6, labelY);
			}
		}
	}

	function draw() {
		if (!melCanvas || !cqtCanvas) return;
		const melSpec = buildMelSpectrum();
		const cqtSpec = buildCqtSpectrum();
		const harmonics = getHarmonics();

		// Mel labels: a few Hz markers
		const melTicks = [200, 500, 1000, 2000, 4000];
		drawHeatmap(melCanvas, melSpec, 'Mel-spectrogram (perceptual)', '#2979ff', {
			yTickFreqs: melTicks,
			yTickLabels: melTicks.map((f) => (f >= 1000 ? `${f / 1000}k Hz` : `${f} Hz`)),
			yPositionFn: (freq: number) => {
				const padT = 22;
				const plotH = (melCanvas.getBoundingClientRect().height || 240) - padT - 22;
				const melMax = hzToMel(F_MAX);
				const fracBin = hzToMel(freq) / melMax;
				return padT + plotH - fracBin * plotH;
			},
			harmonicAnnotations: harmonics
				.filter((h) => h.f < F_MAX)
				.map((h) => ({
					f: h.f,
					fundIdx: h.fundIdx,
					k: h.k,
					label: h.f >= 1000 ? `${(h.f / 1000).toFixed(1)}k` : `${Math.round(h.f)}`
				}))
		});

		// CQT labels: C notes at every octave
		const cqtMidis: number[] = [];
		for (let m = MIDI_MIN; m <= MIDI_MAX; m += 12) cqtMidis.push(m);
		drawHeatmap(cqtCanvas, cqtSpec, 'CQT (1 bin / semitone)', '#7c4dff', {
			yTickFreqs: cqtMidis.map(midiToFreq),
			yTickLabels: cqtMidis.map(midiToNoteName),
			yPositionFn: (freq: number) => {
				const padT = 22;
				const plotH = (cqtCanvas.getBoundingClientRect().height || 240) - padT - 22;
				const midi = freqToMidi(freq);
				const bin = midi - MIDI_MIN;
				return padT + plotH - (bin / N_CQT) * plotH;
			},
			semitoneGrid: true,
			harmonicAnnotations: harmonics
				.filter((h) => freqToMidi(h.f) >= MIDI_MIN && freqToMidi(h.f) <= MIDI_MAX)
				.map((h) => ({
					f: h.f,
					fundIdx: h.fundIdx,
					k: h.k,
					label: midiToNoteName(Math.round(freqToMidi(h.f)))
				}))
		});
	}

	$effect(() => {
		void source;
		void showAnnotations;
		draw();
	});

	onMount(() => {
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => window.removeEventListener('resize', onResize);
	});
</script>

<VizPanel title="Same chord, two representations" titleColor="var(--violet)">
	{#snippet controls()}
		<div class="picker">
			{#each Object.entries(SOURCES) as [k, info]}
				<VizButton
					color="var(--violet)"
					active={source === k}
					onclick={() => (source = k as Source)}>{info.label}</VizButton>
			{/each}
		</div>
		<VizButton
			color="var(--teal)"
			active={showAnnotations}
			onclick={() => (showAnnotations = !showAnnotations)}>
			{showAnnotations ? '◉' : '○'} label harmonics
		</VizButton>
	{/snippet}
	<div class="grid">
		<canvas bind:this={melCanvas} height="240" style="height: 240px;"></canvas>
		<canvas bind:this={cqtCanvas} height="240" style="height: 240px;"></canvas>
	</div>
	{#snippet caption()}
		{SOURCES[source].description} The colored dots in the right margin label each fundamental's harmonic stack &mdash; <span style="color:#e07020;font-weight:600;">orange</span> for the lowest fundamental, <span style="color:#2979ff;font-weight:600;">blue</span> for the next, <span style="color:#1a9e8f;font-weight:600;">teal</span> for the highest (in chord/octaves mode). <strong>The key contrast:</strong> in <strong>CQT</strong>, the colored stacks are translation-invariant &mdash; each fundamental's harmonics sit at the same <em>relative</em> semitone offsets (0, +12, +19, +24, ...), so you can read the stacks as identical patterns just shifted in pitch. In <strong>mel</strong>, the same harmonic stack <em>changes shape</em> depending on where you start: the spacing between harmonics 1&rarr;2 versus 2&rarr;3 looks different at C4 than at G4. That translation invariance is exactly what MERT exploits by using CQT as its musical teacher.
	{/snippet}
</VizPanel>

<style>
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1px;
		background: var(--border);
	}

	canvas {
		display: block;
		width: 100%;
		touch-action: none;
		background: var(--surface);
	}

	.picker {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	@media (max-width: 720px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
