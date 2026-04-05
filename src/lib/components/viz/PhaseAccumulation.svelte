<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, canvasFont, canvasPad, observeVisibility } from '$lib/utils/canvas';

	let naiveEl: HTMLCanvasElement;
	let accumEl: HTMLCanvasElement;

	let freq1 = 3;
	let freq2 = 7;
	let changePoint = 0.5;
	let startTime = 0;
	let freqChanged = $state(false);
	let changeTime = Infinity;
	let visible = false;
	let running = true;

	function draw() {
		if (!running || !naiveEl || !accumEl) return;
		const { ctx: ctx1, w: w1, h: h1 } = setupCanvas(naiveEl);
		const { ctx: ctx2, w: w2, h: h2 } = setupCanvas(accumEl);

		[ctx1, ctx2].forEach((ctx) => {
			ctx.lineCap = 'round';
			ctx.lineJoin = 'round';
		});

		const now = (performance.now() - startTime) / 1000;
		const totalSamples = 400;
		const midY1 = h1 / 2;
		const midY2 = h2 / 2;
		const amp = h1 * 0.35;

		[ctx1, ctx2].forEach((ctx, i) => {
			const w = i === 0 ? w1 : w2;
			const h = i === 0 ? h1 : h2;
			ctx.fillStyle = CANVAS_BG;
			ctx.fillRect(0, 0, w, h);

			ctx.strokeStyle = CANVAS_GRID;
			ctx.lineWidth = 0.5;
			ctx.beginPath();
			ctx.moveTo(0, h / 2);
			ctx.lineTo(w, h / 2);
			ctx.stroke();

			if (freqChanged) {
				const cx = w * changePoint;
				ctx.strokeStyle = 'rgba(255,80,80,0.4)';
				ctx.setLineDash([4, 4]);
				ctx.beginPath();
				ctx.moveTo(cx, 0);
				ctx.lineTo(cx, h);
				ctx.stroke();
				ctx.setLineDash([]);
			}
		});

		// Naive phase
		ctx1.beginPath();
		ctx1.strokeStyle = '#ff5050';
		ctx1.lineWidth = 2;
		ctx1.shadowColor = 'rgba(255,80,80,0.4)';
		ctx1.shadowBlur = 6;
		for (let i = 0; i < totalSamples; i++) {
			const t = i / totalSamples;
			const x = t * w1;
			const f = t < changePoint || !freqChanged ? freq1 : freq2;
			const phi = 2 * Math.PI * f * (t + now * 0.3);
			const y = midY1 + amp * Math.sin(phi);
			i === 0 ? ctx1.moveTo(x, y) : ctx1.lineTo(x, y);
		}
		ctx1.stroke();
		ctx1.shadowBlur = 0;

		// Accumulated phase
		ctx2.beginPath();
		ctx2.strokeStyle = '#1a9e8f';
		ctx2.lineWidth = 2;
		ctx2.shadowColor = 'rgba(26,158,143,0.4)';
		ctx2.shadowBlur = 6;
		let phase = 0;
		const dt = 1 / totalSamples;
		for (let i = 0; i < totalSamples; i++) {
			const t = i / totalSamples;
			const x = t * w2;
			const f = t < changePoint || !freqChanged ? freq1 : freq2;
			phase += 2 * Math.PI * f * dt;
			const y = midY2 + amp * Math.sin(phase + now * 0.3 * 2 * Math.PI * freq1);
			i === 0 ? ctx2.moveTo(x, y) : ctx2.lineTo(x, y);
		}
		ctx2.stroke();
		ctx2.shadowBlur = 0;

		if (visible) requestAnimationFrame(draw);
	}

	function triggerChange() {
		freqChanged = true;
		changeTime = performance.now();
	}

	function reset() {
		freqChanged = false;
		startTime = performance.now();
	}

	onMount(() => {
		startTime = performance.now();
		const obs = observeVisibility(
			naiveEl.closest('.viz-panel')!,
			() => {
				visible = true;
				draw();
			},
			() => {
				visible = false;
			}
		);
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			obs.disconnect();
			window.removeEventListener('resize', onResize);
			running = false;
		};
	});
</script>

<VizPanel title="Phase Accumulation" titleColor="var(--teal)">
	{#snippet controls()}
		<VizButton color="var(--orange)" active={freqChanged} onclick={triggerChange}>
			Change freq
		</VizButton>
		<VizButton onclick={reset}>Reset</VizButton>
	{/snippet}
	<div class="split-canvas">
		<div class="canvas-col">
			<div class="canvas-label naive">Naive: <code>sin(2&pi;ft)</code></div>
			<canvas bind:this={naiveEl} height="120"></canvas>
		</div>
		<div class="canvas-col">
			<div class="canvas-label accum">Accumulated: <code>sin(cumsum(&Delta;&phi;))</code></div>
			<canvas bind:this={accumEl} height="120"></canvas>
		</div>
	</div>
	{#snippet caption()}
		Click "Change freq" to jump from {freq1} Hz to {freq2} Hz. Notice the phase discontinuity in the naive approach.
	{/snippet}
</VizPanel>

<style>
	.split-canvas {
		display: flex;
		gap: 1px;
		background: var(--border);
	}

	.canvas-col {
		flex: 1;
		background: var(--surface);
		position: relative;
	}

	.canvas-label {
		position: absolute;
		top: 8px;
		left: 12px;
		font-family: var(--font-mono);
		font-size: 0.7rem;
		z-index: 1;
		pointer-events: none;
	}

	.canvas-label.naive {
		color: #ff5050;
	}

	.canvas-label.accum {
		color: var(--teal);
	}

	canvas {
		display: block;
		width: 100%;
	}

	@media (max-width: 640px) {
		.split-canvas {
			flex-direction: column;
		}
	}
</style>
