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

	const ORANGE = '#e07020'; // input embeddings (x)
	const VIOLET = '#7c4dff'; // learnable query embeddings (q)
	const TEAL = '#1a9e8f'; // extracted downsampled output (y)
	const GREY = '#9ca3af';

	// 4 phases: 0 inputs, 1 interleave queries, 2 process (transformer), 3 extract
	let playing = $state(false);
	let progress = $state(1); // 0..1 over the whole 4-phase animation
	let playStart = 0;
	const PLAY_MS = 5600;

	const N_IN = 8; // input embeddings x0..x7
	const STRIDE = 2; // S=2 → 2× downsampling

	function box(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		s: number,
		color: string,
		label: string,
		w: number,
		alpha: number,
		dashed = false
	) {
		if (alpha < 0.02) return;
		ctx.save();
		ctx.globalAlpha = alpha * 0.09;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.roundRect(x, y, s, s, 3);
		ctx.fill();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		if (dashed) ctx.setLineDash([3, 2]);
		ctx.beginPath();
		ctx.roundRect(x, y, s, s, 3);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 9, '500');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, x + s / 2, y + s / 2 + 1);
		ctx.restore();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 18);
		const s = Math.min(30, (w - padX * 2) / 13);
		const p = playing ? progress : 1;
		// phase fractions
		const ph1 = Math.min(1, p / 0.25); // interleave queries appear
		const ph2 = Math.min(1, Math.max(0, (p - 0.3) / 0.25)); // transformer process
		const ph3 = Math.min(1, Math.max(0, (p - 0.62) / 0.3)); // extract y

		const topY = canvasPad(w, 26);
		const procY = h / 2 - s / 2;
		const outY = h - canvasPad(w, 30) - s;

		// ---- top lane: interleaved sequence (x x q | x x q | ...) ----
		const nSeg = N_IN / STRIDE;
		const totalSlots = N_IN + nSeg; // each segment gains one query
		const gap = canvasPad(w, 4);
		const segGap = canvasPad(w, 12);
		const laneW = totalSlots * s + (totalSlots - nSeg) * gap + (nSeg - 1) * segGap;
		let x = (w - laneW) / 2;

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'bottom';
		ctx.fillText('audio patch embeddings, grouped into segments of 2 + a learnable query', padX, topY - canvasPad(w, 6));

		const queryX: number[] = [];
		for (let seg = 0; seg < nSeg; seg++) {
			for (let k = 0; k < STRIDE; k++) {
				const idx = seg * STRIDE + k;
				box(ctx, x, topY, s, ORANGE, `x${idx}`, w, 1);
				x += s + gap;
			}
			// learnable query, fades in during phase 1
			queryX.push(x);
			box(ctx, x, topY, s, VIOLET, 'q', w, ph1, true);
			x += s + segGap;
		}

		// ---- middle: transformer stack ----
		const boxW = laneW * 0.62;
		const boxX = (w - boxW) / 2;
		const tH = s * 1.1;
		const tY = procY - tH / 2 + s / 2;
		const pulse = ph2 > 0 && ph2 < 1 ? 0.5 + 0.5 * Math.sin(ph2 * Math.PI) : ph2 >= 1 ? 1 : 0.25;
		ctx.save();
		ctx.globalAlpha = 0.3 + 0.7 * Math.min(1, ph1);
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 1.2;
		ctx.setLineDash([4, 3]);
		ctx.beginPath();
		ctx.roundRect(boxX, tY, boxW, tH, 5);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = `rgba(124,77,255,${0.06 * pulse})`;
		ctx.fill();
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('D transformer layers  (queries attend over their segment)', w / 2, tY + tH / 2);
		ctx.restore();

		// connectors from top lane into the transformer
		ctx.save();
		ctx.globalAlpha = 0.25 * Math.min(1, ph1);
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 0.8;
		ctx.beginPath();
		ctx.moveTo(w / 2, topY + s);
		ctx.lineTo(w / 2, tY);
		ctx.stroke();
		ctx.restore();

		// ---- bottom: extracted y embeddings (the downsampled output) ----
		const outW = nSeg * s + (nSeg - 1) * segGap;
		let ox = (w - outW) / 2;
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('keep the query outputs, discard the rest → 2× downsampled', padX, outY + s + canvasPad(w, 6));

		for (let seg = 0; seg < nSeg; seg++) {
			box(ctx, ox, outY, s, TEAL, `y${seg}`, w, ph3);
			// rising arrow from transformer to y
			if (ph3 > 0.02) {
				ctx.save();
				ctx.globalAlpha = 0.3 * ph3;
				ctx.strokeStyle = TEAL;
				ctx.lineWidth = 0.9;
				ctx.beginPath();
				ctx.moveTo(ox + s / 2, tY + tH);
				ctx.lineTo(ox + s / 2, outY);
				ctx.stroke();
				ctx.restore();
			}
			ox += s + segGap;
		}
	}

	function tick(ts: number) {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		if (playing) {
			progress = Math.min(1, (ts - playStart) / PLAY_MS);
			draw();
			if (progress >= 1) playing = false;
		}
		raf = requestAnimationFrame(tick);
	}

	function play() {
		if (playing) {
			playing = false;
			return;
		}
		progress = 0;
		playStart = performance.now();
		playing = true;
	}

	function showAll() {
		playing = false;
		progress = 1;
		draw();
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
				playing = false;
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
	<VizPanel title="Transformer Resampling Block (TRB)" titleColor="var(--violet)">
		{#snippet controls()}
			<VizButton color="var(--violet)" active={playing} onclick={play}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--violet)" onclick={showAll}>Show all</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:300px"></canvas>
		{#snippet caption()}
			SAME downsamples with attention instead of strided convolution. The sequence is split into
			segments; a learnable <em>query</em> embedding is appended to each, the whole interleaved
			sequence is run through transformer layers, and only the query outputs are kept. Stride 2
			here halves the length; SAME stacks this to a 16× TRB stage, which on top of 256× patching
			gives the full 4096× compression. (After SAME Figures 1–2.)
		{/snippet}
	</VizPanel>
</div>
