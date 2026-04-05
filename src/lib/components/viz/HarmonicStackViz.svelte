<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let running = true;
	let stackT = $state(0); // 0 = raw CQT, 1 = fully stacked
	let animating = $state(false);
	let animDir = 1;
	let raf = 0;

	// Fundamental position (normalized 0–1 within the plot area)
	const FUND_X = 0.22;

	// Each harmonic channel: k is the frequency multiple,
	// raw position in the CQT is log-spaced from the fundamental.
	const harmonics = [
		{ k: 0.5, label: 'f/2', color: '#9ca3af', hz: '131' },
		{ k: 1,   label: 'f',   color: '#1a9e8f', hz: '262' },
		{ k: 2,   label: '2f',  color: '#2979ff', hz: '523' },
		{ k: 3,   label: '3f',  color: '#7c4dff', hz: '785' },
		{ k: 4,   label: '4f',  color: '#e07020', hz: '1047' },
		{ k: 5,   label: '5f',  color: '#e07020', hz: '1308' },
		{ k: 6,   label: '6f',  color: '#e07020', hz: '1569' },
		{ k: 7,   label: '7f',  color: '#e07020', hz: '1831' }
	];

	// CQT is log-frequency: each octave spans the same number of bins.
	// Position = FUND_X + log2(k) × spread_per_octave
	function rawXNorm(k: number): number {
		return FUND_X + Math.log2(k) * 0.18;
	}

	function lerp(a: number, b: number, t: number) {
		return a + (b - a) * t;
	}

	// Draw a Gaussian peak (filled + stroked) at position cx on baseline baseY
	function drawPeak(
		ctx: CanvasRenderingContext2D,
		cx: number, baseY: number,
		amplitude: number, sigma: number,
		color: string, alpha: number
	) {
		const nPts = 30;
		const extent = sigma * 3;

		// Fill under curve
		ctx.beginPath();
		ctx.moveTo(cx - extent, baseY);
		for (let i = 0; i <= nPts; i++) {
			const dx = (i / nPts * 2 - 1) * extent;
			const y = amplitude * Math.exp(-0.5 * (dx / sigma) ** 2);
			ctx.lineTo(cx + dx, baseY - y);
		}
		ctx.lineTo(cx + extent, baseY);
		ctx.closePath();
		ctx.globalAlpha = alpha * 0.18;
		ctx.fillStyle = color;
		ctx.fill();
		ctx.globalAlpha = 1;

		// Stroke
		ctx.beginPath();
		for (let i = 0; i <= nPts; i++) {
			const dx = (i / nPts * 2 - 1) * extent;
			const y = amplitude * Math.exp(-0.5 * (dx / sigma) ** 2);
			if (i === 0) ctx.moveTo(cx + dx, baseY - y);
			else ctx.lineTo(cx + dx, baseY - y);
		}
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.5;
		ctx.stroke();
		ctx.globalAlpha = 1;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const n = harmonics.length;
		const padX = canvasPad(w, 44);
		const padY = canvasPad(w, 10);
		const padBottom = canvasPad(w, 40);
		const innerW = w - padX - 14;
		const innerH = h - padY - padBottom;
		const rowH = innerH / n;

		// Vertical gridlines (frequency axis)
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		for (let i = 0; i <= 10; i++) {
			const x = padX + (i / 10) * innerW;
			ctx.beginPath();
			ctx.moveTo(x, padY);
			ctx.lineTo(x, padY + innerH);
			ctx.stroke();
		}

		// Row separators
		for (let r = 0; r <= n; r++) {
			const y = padY + r * rowH;
			ctx.beginPath();
			ctx.moveTo(padX, y);
			ctx.lineTo(padX + innerW, y);
			ctx.stroke();
		}

		// Fundamental alignment reference (dashed vertical line at fund position)
		const fundPx = padX + FUND_X * innerW;
		ctx.strokeStyle = 'rgba(26,158,143,0.2)';
		ctx.lineWidth = 1;
		ctx.setLineDash([2, 4]);
		ctx.beginPath();
		ctx.moveTo(fundPx, padY);
		ctx.lineTo(fundPx, padY + innerH);
		ctx.stroke();
		ctx.setLineDash([]);

		// Peak rendering
		const sigma = Math.max(10, innerW * 0.02);
		const peakAmp = rowH * 0.5;

		harmonics.forEach((harm, i) => {
			const rowY = padY + i * rowH;
			const rawX = padX + rawXNorm(harm.k) * innerW;
			const alignedX = fundPx;
			const peakX = lerp(rawX, alignedX, stackT);
			const baselineY = rowY + rowH * 0.8;
			const alpha = 0.6 + 0.4 * (i === 1 ? 1 : stackT);

			// Glow when stacked
			if (stackT > 0.9) {
				ctx.shadowColor = harm.color;
				ctx.shadowBlur = 6;
			}

			drawPeak(ctx, peakX, baselineY, peakAmp, sigma, harm.color, alpha);
			ctx.shadowBlur = 0;

			// Row label (left side)
			ctx.fillStyle = i === 1 ? '#1a9e8f' : CANVAS_LABEL;
			ctx.font = canvasFont(w, 12);
			ctx.textAlign = 'right';
			ctx.textBaseline = 'middle';
			ctx.fillText(harm.label, padX - 6, rowY + rowH / 2);

			// Hz label above peak (fades out as stacking progresses)
			if (stackT < 0.4) {
				const labelAlpha = 1 - stackT / 0.4;
				ctx.globalAlpha = labelAlpha * 0.8;
				ctx.fillStyle = harm.color;
				ctx.font = canvasFont(w, 10);
				ctx.textAlign = 'center';
				ctx.fillText(harm.hz + ' Hz', rawX, rowY + 10);
				ctx.globalAlpha = 1;
			}
		});

		// Kernel strip (appears during/after stacking)
		if (stackT > 0.3) {
			const alpha = Math.min(1, (stackT - 0.3) / 0.4);
			const kernW = sigma * 5;
			const kernX = fundPx - kernW / 2;

			ctx.strokeStyle = `rgba(224,112,32,${alpha * 0.6})`;
			ctx.lineWidth = 2;
			ctx.setLineDash([5, 4]);
			ctx.strokeRect(kernX, padY + 2, kernW, innerH - 4);
			ctx.setLineDash([]);

			// Kernel label
			if (stackT > 0.7) {
				const labelAlpha = (stackT - 0.7) / 0.3;
				ctx.fillStyle = `rgba(224,112,32,${labelAlpha * 0.8})`;
				ctx.font = canvasFont(w, 11);
				ctx.textAlign = 'center';
				ctx.fillText('3×3 kernel', fundPx, padY + innerH + 16);
			}
		}

		// Frequency axis label (visible when unstacked)
		if (stackT < 0.2) {
			const axAlpha = 1 - stackT / 0.2;
			ctx.globalAlpha = axAlpha * 0.5;
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'center';
			ctx.fillText('← frequency (CQT, log scale) →', padX + innerW / 2, padY + innerH + 16);
			ctx.globalAlpha = 1;
		}

		// State description at bottom
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		const stateLabel =
			stackT < 0.05
				? 'raw CQT: harmonics of C4 spread across 131–1831 Hz'
				: stackT > 0.95
					? 'stacked: all peaks at f, captured by one small kernel'
					: 'shifting each channel to align its harmonic with f…';
		ctx.fillText(stateLabel, padX + innerW / 2, h - 8);

		// Param count (when fully stacked)
		if (stackT > 0.95) {
			const a = (stackT - 0.95) / 0.05;
			ctx.fillStyle = `rgba(224,112,32,${a * 0.85})`;
			ctx.font = canvasFont(w, 11);
			ctx.textAlign = 'right';
			ctx.fillText('16,782 params total', padX + innerW - 4, padY + 16);
		}
	}

	function animate() {
		if (!running) return;
		const speed = 0.03;
		stackT = Math.max(0, Math.min(1, stackT + animDir * speed));
		draw();
		if ((animDir > 0 && stackT < 1) || (animDir < 0 && stackT > 0)) {
			raf = requestAnimationFrame(animate);
		} else {
			animating = false;
		}
	}

	function toggleStack() {
		if (animating) return;
		animating = true;
		animDir = stackT < 0.5 ? 1 : -1;
		animate();
	}

	onMount(() => {
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			running = false;
			cancelAnimationFrame(raf);
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<VizPanel title="Harmonic Stacking" titleColor="var(--blue)">
	{#snippet controls()}
		<VizButton color="var(--blue)" active={stackT > 0.5} onclick={toggleStack}>
			{stackT > 0.5 ? 'Unstack' : 'Stack'}
		</VizButton>
	{/snippet}
	<canvas bind:this={canvas} height="240"></canvas>
	{#snippet caption()}
		A note at C4 (262 Hz) produces harmonics at 2f, 3f, … 7f, spread across 3.8 octaves of the CQT. In the raw spectrogram, detecting all harmonics requires a kernel spanning hundreds of bins. <code>harmonic_stack()</code> shifts each channel by <code>log2(k) × bins_per_semitone × 12</code>, aligning every harmonic at the fundamental's bin position. A 3×3 kernel now captures the full harmonic series.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
	}
</style>
