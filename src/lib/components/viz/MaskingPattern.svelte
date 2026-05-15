<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	const N_FRAMES = 80;
	const SPAN_LENGTH = 10;
	let startingProb = $state(0.08); // HuBERT default 8%

	let starts: Set<number> = $state(new Set());
	let masked: Set<number> = $state(new Set());

	function randomize() {
		const newStarts = new Set<number>();
		const newMasked = new Set<number>();
		for (let i = 0; i < N_FRAMES; i++) {
			if (Math.random() < startingProb) {
				newStarts.add(i);
				for (let k = 0; k < SPAN_LENGTH; k++) {
					if (i + k < N_FRAMES) newMasked.add(i + k);
				}
			}
		}
		starts = newStarts;
		masked = newMasked;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const pad = canvasPad(w, 20);
		const topPad = 38;
		const botPad = 40;
		const stripH = h - topPad - botPad;
		const slotW = (w - pad * 2) / N_FRAMES;
		const frameW = Math.max(2, slotW * 0.92);

		// Frame strip
		for (let i = 0; i < N_FRAMES; i++) {
			const x = pad + i * slotW;
			const isMasked = masked.has(i);
			const isStart = starts.has(i);

			ctx.fillStyle = isMasked ? 'rgba(224,112,32,0.65)' : 'rgba(26,158,143,0.35)';
			ctx.fillRect(x, topPad, frameW, stripH);

			if (isStart) {
				// Diamond marker above the frame
				const cx = x + frameW / 2;
				const cy = topPad - 14;
				const sz = 5;
				ctx.fillStyle = '#7c4dff';
				ctx.beginPath();
				ctx.moveTo(cx, cy - sz);
				ctx.lineTo(cx + sz, cy);
				ctx.lineTo(cx, cy + sz);
				ctx.lineTo(cx - sz, cy);
				ctx.closePath();
				ctx.fill();
				// Vertical guide line
				ctx.strokeStyle = 'rgba(124,77,255,0.32)';
				ctx.lineWidth = 0.7;
				ctx.setLineDash([3, 2]);
				ctx.beginPath();
				ctx.moveTo(cx, topPad - 6);
				ctx.lineTo(cx, topPad + stripH);
				ctx.stroke();
				ctx.setLineDash([]);
			}
		}

		// Legend row (compact)
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.fillStyle = '#7c4dff';
		ctx.fillText('◆ start', pad, 16);
		ctx.fillStyle = '#e07020';
		ctx.fillText('■ masked 10-span', pad + 60, 16);
		ctx.fillStyle = '#1a9e8f';
		ctx.fillText('■ context', pad + 200, 16);

		// Stats
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'left';
		const pct = ((masked.size / N_FRAMES) * 100).toFixed(0);
		ctx.fillText(
			`${N_FRAMES} frames · ${starts.size} starts · ${masked.size} masked (${pct}%)`,
			pad,
			topPad + stripH + 24
		);

		// X-axis frame indices (every 10)
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		for (let i = 0; i <= N_FRAMES; i += 10) {
			const x = pad + i * slotW;
			ctx.fillText(String(i), x - 4, topPad + stripH + 40);
		}

		// Time axis label
		ctx.textAlign = 'right';
		ctx.fillText('frame index (75 Hz)', w - pad, topPad + stripH + 40);
	}

	$effect(() => {
		void starts;
		void masked;
		draw();
	});

	onMount(() => {
		randomize();
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => window.removeEventListener('resize', onResize);
	});
</script>

<VizPanel title="HuBERT-style masking on a frame strip" titleColor="var(--violet)">
	{#snippet controls()}
		<label class="slider-label">
			<span>start prob p</span>
			<input
				type="range"
				min="0.02"
				max="0.18"
				step="0.01"
				bind:value={startingProb}
				oninput={randomize}
			/>
			<span class="p-display">{(startingProb * 100).toFixed(0)}%</span>
		</label>
		<VizButton color="var(--orange)" onclick={randomize}>Re-sample</VizButton>
	{/snippet}
	<canvas bind:this={canvas} height="160" style="height: 160px;"></canvas>
	{#snippet caption()}
		Each frame has probability <code>p</code> of being chosen as a starting index (purple diamond). From each start, the next 10 frames are masked together. Overlapping spans merge — that's why the total masked fraction is well below <code>p × 10</code>. MERT (and HuBERT) default to <strong>p ≈ 8%</strong>, which yields roughly <strong>50% of frames masked</strong> in expectation. The model must reconstruct the orange frames using only the teal context.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		touch-action: none;
	}

	.slider-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.p-display {
		min-width: 2.6em;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--violet);
		text-align: right;
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 140px;
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		outline: none;
		padding: 10px 0;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--violet);
		cursor: pointer;
		box-shadow: 0 0 6px var(--violet-glow);
	}

	@media (max-width: 640px) {
		input[type='range'] {
			width: 100px;
		}
	}
</style>
