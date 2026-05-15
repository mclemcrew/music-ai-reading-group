<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import {
		setupCanvas,
		CANVAS_BG,
		CANVAS_LABEL,
		observeVisibility,
		canvasFont,
		canvasPad
	} from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;
	let raf = 0;

	const ORANGE = '#e07020';
	const TEAL = '#1a9e8f';
	const VIOLET = '#7c4dff';
	const GREY = '#9ca3af';

	type Preset = 'flat' | 'warm' | 'bright' | 'punchy';
	const PRESETS: Preset[] = ['flat', 'warm', 'bright', 'punchy'];

	const PRESET_LABEL: Record<Preset, string> = {
		flat: 'flat (no FX)',
		warm: 'warm vintage tape',
		bright: 'airy + present',
		punchy: 'punchy modern drums'
	};

	// EQ params: low shelf gain (dB), mid bell freq (kHz), mid bell gain (dB), high shelf gain (dB)
	type EQ = {
		lowGain: number; // -12..+12 dB at 80 Hz
		midFreq: number; // 0.4..6 kHz log scale parameter [0..1]
		midGain: number;
		highGain: number;
	};

	const PRESET_EQ: Record<Preset, EQ> = {
		flat: { lowGain: 0, midFreq: 0.5, midGain: 0, highGain: 0 },
		warm: { lowGain: 2.5, midFreq: 0.4, midGain: 1.0, highGain: -3.5 },
		bright: { lowGain: -1.5, midFreq: 0.6, midGain: -1, highGain: 4.5 },
		punchy: { lowGain: 3.5, midFreq: 0.45, midGain: -2, highGain: 2 }
	};

	let preset = $state<Preset>('flat');
	let eq = $state<EQ>({ ...PRESET_EQ.flat });
	let target = $state<EQ>({ ...PRESET_EQ.flat });

	function applyPreset(p: Preset) {
		preset = p;
		target = { ...PRESET_EQ[p] };
	}

	function setLow(v: number) {
		eq = { ...eq, lowGain: v };
		target = { ...target, lowGain: v };
		preset = matchPreset(eq);
	}
	function setMidFreq(v: number) {
		eq = { ...eq, midFreq: v };
		target = { ...target, midFreq: v };
		preset = matchPreset(eq);
	}
	function setMidGain(v: number) {
		eq = { ...eq, midGain: v };
		target = { ...target, midGain: v };
		preset = matchPreset(eq);
	}
	function setHighGain(v: number) {
		eq = { ...eq, highGain: v };
		target = { ...target, highGain: v };
		preset = matchPreset(eq);
	}

	function matchPreset(e: EQ): Preset {
		// If close to a preset's values, return it; otherwise stay where we are
		for (const p of PRESETS) {
			const d = PRESET_EQ[p];
			if (
				Math.abs(d.lowGain - e.lowGain) < 0.3 &&
				Math.abs(d.midFreq - e.midFreq) < 0.05 &&
				Math.abs(d.midGain - e.midGain) < 0.3 &&
				Math.abs(d.highGain - e.highGain) < 0.3
			)
				return p;
		}
		return preset;
	}

	// Convert mid-freq slider [0..1] to a Hz value (logarithmic over 400Hz..6kHz)
	function midFreqHz(v: number): number {
		const lo = Math.log10(400);
		const hi = Math.log10(6000);
		return Math.pow(10, lo + v * (hi - lo));
	}

	// Compute filter response at a given frequency (Hz). Returns gain in dB.
	function response(f: number, e: EQ): number {
		// Low shelf at 80 Hz
		const fl = 80;
		const sl = 1 / (1 + Math.pow(f / fl, 2));
		const low = e.lowGain * sl;
		// Mid bell
		const fm = midFreqHz(e.midFreq);
		const Q = 1.0;
		const x = (f - fm) / (fm / Q);
		const bell = e.midGain / (1 + x * x);
		// High shelf at 6 kHz
		const fh = 6000;
		const sh = 1 / (1 + Math.pow(fh / f, 2));
		const high = e.highGain * sh;
		return low + bell + high;
	}

	// Frequency range: 30 Hz – 18 kHz
	const F_LO = 30;
	const F_HI = 18000;

	function freqToX(f: number, plotL: number, plotW: number): number {
		const lo = Math.log10(F_LO);
		const hi = Math.log10(F_HI);
		return plotL + ((Math.log10(f) - lo) / (hi - lo)) * plotW;
	}

	function dbToY(db: number, plotT: number, plotH: number): number {
		// db range: -12 .. +12
		return plotT + plotH * (1 - (db + 12) / 24);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = canvasPad(w, 38);
		const padR = canvasPad(w, 14);
		const padT = canvasPad(w, 14);
		const padB = canvasPad(w, 28);
		const plotL = padL;
		const plotR = w - padR;
		const plotT = padT;
		const plotB = h - padB;
		const plotW = plotR - plotL;
		const plotH = plotB - plotT;

		// Grid
		ctx.strokeStyle = 'rgba(0,0,0,0.06)';
		ctx.lineWidth = 1;
		// Frequency grid at decade lines
		[100, 1000, 10000].forEach((f) => {
			const x = freqToX(f, plotL, plotW);
			ctx.beginPath();
			ctx.moveTo(x, plotT);
			ctx.lineTo(x, plotB);
			ctx.stroke();
		});
		// dB grid every 6 dB
		for (let db = -12; db <= 12; db += 6) {
			const y = dbToY(db, plotT, plotH);
			ctx.beginPath();
			ctx.moveTo(plotL, y);
			ctx.lineTo(plotR, y);
			ctx.stroke();
		}

		// Zero-dB line emphasized
		ctx.strokeStyle = 'rgba(0,0,0,0.18)';
		ctx.lineWidth = 1;
		const zeroY = dbToY(0, plotT, plotH);
		ctx.beginPath();
		ctx.moveTo(plotL, zeroY);
		ctx.lineTo(plotR, zeroY);
		ctx.stroke();

		// Axis labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		[
			{ f: 100, l: '100 Hz' },
			{ f: 1000, l: '1 kHz' },
			{ f: 10000, l: '10 kHz' }
		].forEach(({ f, l }) => {
			ctx.fillText(l, freqToX(f, plotL, plotW), plotB + 4);
		});

		ctx.textAlign = 'right';
		ctx.textBaseline = 'middle';
		[-12, -6, 0, 6, 12].forEach((db) => {
			ctx.fillText(`${db > 0 ? '+' : ''}${db} dB`, plotL - 4, dbToY(db, plotT, plotH));
		});

		// Axis title
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'right';
		ctx.textBaseline = 'top';
		ctx.fillText('frequency (log)', plotR, plotB + 16);

		// Compute and draw the EQ response curve
		ctx.strokeStyle = ORANGE;
		ctx.lineWidth = 2;
		ctx.beginPath();
		const N = 240;
		for (let i = 0; i <= N; i++) {
			const t = i / N;
			const f = Math.pow(10, Math.log10(F_LO) + t * (Math.log10(F_HI) - Math.log10(F_LO)));
			const db = response(f, eq);
			const x = freqToX(f, plotL, plotW);
			const y = dbToY(Math.max(-12, Math.min(12, db)), plotT, plotH);
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Soft fill under curve (above zero) and above (below zero) for clarity
		ctx.save();
		ctx.fillStyle = ORANGE;
		ctx.globalAlpha = 0.07;
		ctx.beginPath();
		for (let i = 0; i <= N; i++) {
			const t = i / N;
			const f = Math.pow(10, Math.log10(F_LO) + t * (Math.log10(F_HI) - Math.log10(F_LO)));
			const db = response(f, eq);
			const x = freqToX(f, plotL, plotW);
			const y = dbToY(Math.max(-12, Math.min(12, db)), plotT, plotH);
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.lineTo(plotR, zeroY);
		ctx.lineTo(plotL, zeroY);
		ctx.closePath();
		ctx.fill();
		ctx.restore();

		// Mark the three knob "anchor" frequencies
		const anchors: Array<{ f: number; label: string; color: string; gain: number }> = [
			{ f: 80, label: 'low shelf', color: TEAL, gain: eq.lowGain },
			{ f: midFreqHz(eq.midFreq), label: 'mid bell', color: VIOLET, gain: eq.midGain },
			{ f: 6000, label: 'high shelf', color: ORANGE, gain: eq.highGain }
		];
		anchors.forEach((a) => {
			const x = freqToX(a.f, plotL, plotW);
			const y = dbToY(Math.max(-12, Math.min(12, a.gain)), plotT, plotH);
			// Marker
			ctx.save();
			ctx.fillStyle = a.color;
			ctx.globalAlpha = 0.25;
			ctx.beginPath();
			ctx.arc(x, y, 9, 0, Math.PI * 2);
			ctx.fill();
			ctx.globalAlpha = 1;
			ctx.strokeStyle = a.color;
			ctx.lineWidth = 1.6;
			ctx.beginPath();
			ctx.arc(x, y, 5, 0, Math.PI * 2);
			ctx.stroke();
			ctx.restore();

			// Stack name + frequency on the same side of the marker, both clear of the halo.
			const placeBelow = y < plotT + 32;
			const fLabel =
				a.f >= 1000 ? `${(a.f / 1000).toFixed(a.f >= 5000 ? 0 : 1)} kHz` : `${a.f.toFixed(0)} Hz`;
			ctx.textAlign = 'center';
			if (placeBelow) {
				ctx.textBaseline = 'top';
				ctx.fillStyle = a.color;
				ctx.font = canvasFont(w, 9, '600');
				ctx.fillText(a.label, x, y + 14);
				ctx.fillStyle = CANVAS_LABEL;
				ctx.font = canvasFont(w, 9);
				ctx.fillText(fLabel, x, y + 25);
			} else {
				ctx.textBaseline = 'bottom';
				ctx.fillStyle = a.color;
				ctx.font = canvasFont(w, 9, '600');
				ctx.fillText(a.label, x, y - 25);
				ctx.fillStyle = CANVAS_LABEL;
				ctx.font = canvasFont(w, 9);
				ctx.fillText(fLabel, x, y - 14);
			}
		});

		// Top-right summary text
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'right';
		ctx.textBaseline = 'top';
		ctx.fillText(`preset: ${PRESET_LABEL[preset]}`, plotR, plotT + 4);
	}

	function tick() {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		// Lerp eq toward target for smooth transitions on preset change.
		// $effect picks up the change to eq and redraws.
		(['lowGain', 'midFreq', 'midGain', 'highGain'] as Array<keyof EQ>).forEach((k) => {
			const dx = target[k] - eq[k];
			if (Math.abs(dx) > 0.01) {
				eq = { ...eq, [k]: eq[k] + dx * 0.18 };
			}
		});
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {
				running = true;
				draw();
			},
			() => {
				running = false;
			}
		);
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		raf = requestAnimationFrame(tick);
		return () => {
			running = false;
			cancelAnimationFrame(raf);
			obs.disconnect();
			window.removeEventListener('resize', onResize);
		};
	});

	$effect(() => {
		eq.lowGain;
		eq.midFreq;
		eq.midGain;
		eq.highGain;
		draw();
	});
</script>

<div bind:this={container}>
	<VizPanel title="What an EQ actually does — try the knobs" titleColor="var(--orange)">
		{#snippet controls()}
			{#each PRESETS as p}
				<VizButton color="var(--orange)" active={preset === p} onclick={() => applyPreset(p)}>
					{p}
				</VizButton>
			{/each}
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:280px"></canvas>
		<div class="knobs">
			<label class="knob">
				<span class="knob-label">low shelf gain</span>
				<input
					type="range"
					min="-12"
					max="12"
					step="0.5"
					value={eq.lowGain}
					oninput={(e) => setLow(parseFloat(e.currentTarget.value))}
				/>
				<span class="knob-value">{eq.lowGain.toFixed(1)} dB</span>
			</label>
			<label class="knob">
				<span class="knob-label">mid bell freq</span>
				<input
					type="range"
					min="0"
					max="1"
					step="0.01"
					value={eq.midFreq}
					oninput={(e) => setMidFreq(parseFloat(e.currentTarget.value))}
				/>
				<span class="knob-value">{midFreqHz(eq.midFreq).toFixed(0)} Hz</span>
			</label>
			<label class="knob">
				<span class="knob-label">mid bell gain</span>
				<input
					type="range"
					min="-12"
					max="12"
					step="0.5"
					value={eq.midGain}
					oninput={(e) => setMidGain(parseFloat(e.currentTarget.value))}
				/>
				<span class="knob-value">{eq.midGain.toFixed(1)} dB</span>
			</label>
			<label class="knob">
				<span class="knob-label">high shelf gain</span>
				<input
					type="range"
					min="-12"
					max="12"
					step="0.5"
					value={eq.highGain}
					oninput={(e) => setHighGain(parseFloat(e.currentTarget.value))}
				/>
				<span class="knob-value">{eq.highGain.toFixed(1)} dB</span>
			</label>
		</div>
		{#snippet caption()}
			A 4-knob EQ. Each knob has a name a producer would actually use, and the curve responds
			intuitively — boost low-shelf and you raise the bottom; cut high-shelf and you take air
			off the top. This is the whole reason LLMs are competitive at this task: the action
			space is tiny, the labels mean what they say, and tutorials all over the internet have
			already trained the language model on which knob does what.
		{/snippet}
	</VizPanel>
</div>

<style>
	.knobs {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.5rem 1rem;
		padding: 0.75rem 0.75rem 0;
	}
	.knob {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.knob-label {
		flex: 0 0 110px;
	}
	.knob input[type='range'] {
		flex: 1;
		min-width: 0;
		-webkit-appearance: none;
		appearance: none;
		height: 3px;
		background: var(--border);
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}
	.knob input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--orange);
		border: 2px solid var(--surface);
		cursor: pointer;
		box-shadow: 0 0 0 1px var(--orange);
	}
	.knob input[type='range']::-moz-range-thumb {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--orange);
		border: 2px solid var(--surface);
		cursor: pointer;
	}
	.knob-value {
		flex: 0 0 60px;
		text-align: right;
		color: var(--orange);
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}

	@media (max-width: 640px) {
		.knobs {
			grid-template-columns: 1fr;
		}
	}
</style>
