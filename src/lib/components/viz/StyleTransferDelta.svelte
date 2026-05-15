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
	const BLUE = '#2979ff';
	const GREY = '#9ca3af';
	const ROSE = '#d62a70';

	type Pair = 'bright' | 'punchy' | 'warm';
	const PAIRS: Pair[] = ['bright', 'punchy', 'warm'];
	const PAIR_LABEL: Record<Pair, string> = {
		bright: 'reference is brighter',
		punchy: 'reference is punchier',
		warm: 'reference is warmer'
	};

	let pair = $state<Pair>('bright');
	let progress = $state(1);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 5000;

	const N_BINS = 56;

	// Each pair returns reference and target spectra over a log-frequency axis.
	// Values in arbitrary units, range ~ 0..1.
	function spectra(p: Pair): { ref: number[]; tgt: number[] } {
		const ref: number[] = [];
		const tgt: number[] = [];
		for (let i = 0; i < N_BINS; i++) {
			const t = i / (N_BINS - 1);
			let r = 0;
			let g = 0;
			if (p === 'bright') {
				// target rolls off in highs, reference has more energy on top
				const base = 0.65 - t * 0.4;
				r = base + 0.35 * Math.exp(-Math.pow((t - 0.78) / 0.18, 2));
				g = base + 0.05 * Math.exp(-Math.pow((t - 0.78) / 0.18, 2));
			} else if (p === 'punchy') {
				// reference has more low-shelf and tighter dynamics implied (we'll show as low boost)
				const lowBoost = 0.5 * Math.exp(-Math.pow((t - 0.06) / 0.1, 2));
				const lowBase = 0.5 - t * 0.25;
				r = lowBase + lowBoost + 0.06 * Math.cos(t * 12);
				g = lowBase + 0.1 * lowBoost + 0.06 * Math.cos(t * 12);
			} else {
				// warm: reference has mid-low body + softer top; target sounds more harsh
				r = 0.7 - 0.55 * t + 0.18 * Math.exp(-Math.pow((t - 0.18) / 0.13, 2));
				g = 0.5 - 0.1 * t + 0.18 * Math.exp(-Math.pow((t - 0.78) / 0.13, 2));
			}
			ref.push(Math.max(0.03, Math.min(1, r)));
			tgt.push(Math.max(0.03, Math.min(1, g)));
		}
		return { ref, tgt };
	}

	type ChainStep = {
		label: string;
		color: string;
		// Per-bin gain to apply to target (in arbitrary units, ~ -0.4 .. +0.4)
		curve: (t: number) => number;
	};

	function chainFor(p: Pair): ChainStep[] {
		if (p === 'bright')
			return [
				{
					label: 'set_eq(high_shelf, +4 dB)',
					color: BLUE,
					curve: (t) => 0.32 * Math.max(0, (t - 0.45) / 0.55)
				},
				{
					label: 'set_compressor(ratio=3:1)',
					color: TEAL,
					curve: (t) => -0.04
				}
			];
		if (p === 'punchy')
			return [
				{
					label: 'set_eq(low_shelf, +3.5 dB)',
					color: BLUE,
					curve: (t) => 0.32 * Math.max(0, 1 - t * 4)
				},
				{
					label: 'set_compressor(ratio=6:1, attack=5 ms)',
					color: TEAL,
					curve: (t) => -0.06 - 0.06 * Math.exp(-Math.pow((t - 0.5) / 0.3, 2))
				},
				{
					label: 'set_saturation(drive=0.4)',
					color: ROSE,
					curve: (t) => 0.05 * Math.cos(t * 6)
				}
			];
		// warm
		return [
			{
				label: 'set_eq(low_shelf, +2.5 dB)',
				color: BLUE,
				curve: (t) => 0.22 * Math.max(0, 1 - t * 4)
			},
			{
				label: 'set_eq(high_shelf, -3.5 dB)',
				color: BLUE,
				curve: (t) => -0.32 * Math.max(0, (t - 0.55) / 0.45)
			},
			{
				label: 'set_saturation(drive=0.55)',
				color: ROSE,
				curve: (t) => 0.04 * Math.cos(t * 6)
			}
		];
	}

	function setPair(p: Pair) {
		pair = p;
		progress = 0;
		playStart = performance.now();
		playing = true;
	}
	function play() {
		progress = 0;
		playStart = performance.now();
		playing = true;
	}
	function showAll() {
		playing = false;
		progress = 1;
		draw();
	}

	function freqToX(t: number, plotL: number, plotW: number): number {
		return plotL + t * plotW;
	}

	function magToY(m: number, plotT: number, plotH: number): number {
		// m in [0..1.2], pad a bit
		return plotT + plotH * (1 - Math.min(1, Math.max(0, m / 1.05)));
	}

	function drawSpectrum(
		ctx: CanvasRenderingContext2D,
		plotL: number,
		plotT: number,
		plotW: number,
		plotH: number,
		bins: number[],
		color: string,
		alpha: number,
		dashed = false,
		fill = false
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = dashed ? 1.4 : 1.6;
		if (dashed) ctx.setLineDash([4, 3]);
		ctx.beginPath();
		bins.forEach((m, i) => {
			const t = i / (bins.length - 1);
			const x = freqToX(t, plotL, plotW);
			const y = magToY(m, plotT, plotH);
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		});
		ctx.stroke();
		if (fill) {
			ctx.lineTo(plotL + plotW, plotT + plotH);
			ctx.lineTo(plotL, plotT + plotH);
			ctx.closePath();
			ctx.fillStyle = color;
			ctx.globalAlpha = alpha * 0.08;
			ctx.fill();
		}
		ctx.setLineDash([]);
		ctx.restore();
	}

	function drawDeltaShade(
		ctx: CanvasRenderingContext2D,
		plotL: number,
		plotT: number,
		plotW: number,
		plotH: number,
		ref: number[],
		tgt: number[],
		alpha: number
	) {
		ctx.save();
		ctx.fillStyle = ROSE;
		ctx.globalAlpha = alpha;
		ctx.beginPath();
		// Top edge: ref, bottom edge: tgt, only where ref > tgt
		// We close cleanly between matching bin pairs
		for (let i = 0; i < ref.length - 1; i++) {
			const t0 = i / (ref.length - 1);
			const t1 = (i + 1) / (ref.length - 1);
			const x0 = freqToX(t0, plotL, plotW);
			const x1 = freqToX(t1, plotL, plotW);
			ctx.moveTo(x0, magToY(ref[i], plotT, plotH));
			ctx.lineTo(x1, magToY(ref[i + 1], plotT, plotH));
			ctx.lineTo(x1, magToY(tgt[i + 1], plotT, plotH));
			ctx.lineTo(x0, magToY(tgt[i], plotT, plotH));
			ctx.closePath();
		}
		ctx.fill();
		ctx.restore();
	}

	function drawChainBox(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		chain: ChainStep[],
		visN: number
	) {
		// Outline
		ctx.save();
		ctx.strokeStyle = GREY;
		ctx.globalAlpha = 0.35;
		ctx.lineWidth = 0.8;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('FX chain (predicted by LLM2Fx-Tools)', x + 8, y + 6);

		const stepH = (hh - 26) / chain.length;
		chain.forEach((s, i) => {
			const sy = y + 22 + i * stepH;
			const isVis = i < visN;
			const isHead = Math.abs(visN - i - 0.5) < 0.5;
			const a = isVis ? 1 : isHead ? Math.max(0, visN - i) : 0;
			ctx.save();
			ctx.globalAlpha = a;
			ctx.fillStyle = s.color;
			ctx.globalAlpha = a * 0.07;
			ctx.beginPath();
			ctx.roundRect(x + 8, sy + 2, ww - 16, stepH - 4, 3);
			ctx.fill();
			ctx.globalAlpha = a;
			ctx.strokeStyle = s.color;
			ctx.lineWidth = isHead ? 1.5 : 1;
			ctx.beginPath();
			ctx.roundRect(x + 8, sy + 2, ww - 16, stepH - 4, 3);
			ctx.stroke();
			ctx.fillStyle = s.color;
			ctx.font = canvasFont(w, 10, '600');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText(s.label, x + 14, sy + stepH / 2);
			ctx.restore();
		});
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 18);

		const { ref, tgt } = spectra(pair);
		const chain = chainFor(pair);

		// Layout: spectrum chart on left ~70%, chain box on right
		const chartW = (w - padX * 2) * 0.7;
		const chartX = padX;
		const chartY = padY;
		const chartH = h - padY * 2 - 38;

		const chainX = chartX + chartW + 14;
		const chainW = w - chainX - padX;

		// Apply chain progressively to target → "current"
		const chainProgress = progress; // 0..1 across whole chain
		const stepProgress = chainProgress * chain.length; // 0..N
		const visStepCount = Math.floor(stepProgress);
		const fracInLast = stepProgress - visStepCount;

		const current: number[] = [...tgt];
		for (let i = 0; i < chain.length; i++) {
			const fully = i < visStepCount;
			const partial = i === visStepCount ? fracInLast : 0;
			const w_ = fully ? 1 : partial;
			if (w_ <= 0) continue;
			for (let b = 0; b < N_BINS; b++) {
				const t = b / (N_BINS - 1);
				current[b] += chain[i].curve(t) * w_;
			}
		}
		// Clamp
		for (let b = 0; b < N_BINS; b++) {
			current[b] = Math.max(0.03, Math.min(1.05, current[b]));
		}

		// Plot frame
		ctx.save();
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(chartX, chartY + chartH);
		ctx.lineTo(chartX + chartW, chartY + chartH);
		ctx.moveTo(chartX, chartY);
		ctx.lineTo(chartX, chartY + chartH);
		ctx.stroke();
		ctx.restore();

		// Light grid
		ctx.save();
		ctx.strokeStyle = 'rgba(0,0,0,0.04)';
		ctx.lineWidth = 1;
		for (let i = 1; i < 4; i++) {
			const yy = chartY + (chartH * i) / 4;
			ctx.beginPath();
			ctx.moveTo(chartX, yy);
			ctx.lineTo(chartX + chartW, yy);
			ctx.stroke();
		}
		ctx.restore();

		// Frequency axis labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('low', chartX, chartY + chartH + 4);
		ctx.textAlign = 'center';
		ctx.fillText('mid', chartX + chartW / 2, chartY + chartH + 4);
		ctx.textAlign = 'right';
		ctx.fillText('high', chartX + chartW, chartY + chartH + 4);

		// Y axis label
		ctx.save();
		ctx.translate(chartX - 10, chartY + chartH / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.fillText('energy', 0, 0);
		ctx.restore();

		// Delta shading: only when delta is between target-original and reference (the gap to close)
		drawDeltaShade(
			ctx,
			chartX,
			chartY,
			chartW,
			chartH,
			ref,
			tgt,
			0.16 * Math.max(0, 1 - chainProgress)
		);

		// Reference (dashed teal)
		drawSpectrum(ctx, chartX, chartY, chartW, chartH, ref, TEAL, 0.95, true, false);
		// Original target (light grey, fades as chain applies)
		drawSpectrum(
			ctx,
			chartX,
			chartY,
			chartW,
			chartH,
			tgt,
			GREY,
			0.4 + 0.3 * (1 - chainProgress),
			false,
			false
		);
		// Current (target after chain so far) — orange, full
		drawSpectrum(ctx, chartX, chartY, chartW, chartH, current, ORANGE, 1, false, true);

		// Legend
		const legX = chartX + 8;
		const legY = chartY + 6;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textBaseline = 'middle';

		const drawLegendDot = (lx: number, ly: number, color: string, dashed: boolean) => {
			ctx.save();
			ctx.strokeStyle = color;
			ctx.lineWidth = 2;
			if (dashed) ctx.setLineDash([4, 3]);
			ctx.beginPath();
			ctx.moveTo(lx, ly);
			ctx.lineTo(lx + 16, ly);
			ctx.stroke();
			ctx.setLineDash([]);
			ctx.restore();
		};

		drawLegendDot(legX, legY, TEAL, true);
		ctx.fillStyle = TEAL;
		ctx.textAlign = 'left';
		ctx.fillText('reference', legX + 22, legY);

		const legX2 = legX + 100;
		drawLegendDot(legX2, legY, GREY, false);
		ctx.fillStyle = GREY;
		ctx.fillText('target (start)', legX2 + 22, legY);

		const legX3 = legX2 + 110;
		drawLegendDot(legX3, legY, ORANGE, false);
		ctx.fillStyle = ORANGE;
		ctx.fillText('target (after chain)', legX3 + 22, legY);

		// Chain box on the right
		drawChainBox(
			ctx,
			w,
			chainX,
			chartY,
			chainW,
			chartH,
			chain,
			stepProgress
		);

		// Footer status
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		const status =
			chainProgress >= 1
				? 'gap closed — target now matches reference shape'
				: chainProgress < 0.02
					? 'gap to close (rose shading) — apply chain to morph target into reference'
					: `applying step ${visStepCount + 1}/${chain.length}`;
		ctx.fillText(status, chartX, h - padY + 4);
	}

	function tick(ts: number) {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		if (playing) {
			const elapsed = ts - playStart;
			progress = Math.min(1, elapsed / PLAY_MS);
			draw();
			if (progress >= 1) playing = false;
		}
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		progress = 0;
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
</script>

<div bind:this={container}>
	<VizPanel
		title="Style transfer: target → reference, one tool call at a time"
		titleColor="var(--orange)"
	>
		{#snippet controls()}
			{#each PAIRS as p}
				<VizButton color="var(--orange)" active={pair === p} onclick={() => setPair(p)}>
					{PAIR_LABEL[p]}
				</VizButton>
			{/each}
			<VizButton color="var(--orange)" active={playing} onclick={play}>Play chain</VizButton>
			<VizButton color="var(--orange)" onclick={showAll}>Show end</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:300px"></canvas>
		{#snippet caption()}
			The dashed teal line is what we want it to sound like (the reference). The grey line is
			the unprocessed target as it starts. The rose shading is the gap we need to close. The
			orange line is the target after each tool call lands — watch it morph step by step
			toward the reference. This is exactly the LLM2Fx-Tools style-transfer task: predict the
			chain that closes the gap, in the right order.
		{/snippet}
	</VizPanel>
</div>
