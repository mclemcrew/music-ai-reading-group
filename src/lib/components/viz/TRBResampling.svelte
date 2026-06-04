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

	let playing = $state(false);
	let progress = $state(1); // 0..1 over the whole animation
	let playStart = 0;
	const PLAY_MS = 5200;

	const N_IN = 8; // x0..x7
	const STRIDE = 2; // S=2 -> 2x downsampling
	const N_SEG = N_IN / STRIDE;

	function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

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
		ctx.globalAlpha = alpha * 0.1;
		ctx.fillStyle = color;
		roundRectPath(ctx, x, y, s, s, 4);
		ctx.fill();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.4;
		if (dashed) ctx.setLineDash([3, 2]);
		roundRectPath(ctx, x, y, s, s, 4);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, x + s / 2, y + s / 2 + 1);
		ctx.restore();
	}

	function arrow(
		ctx: CanvasRenderingContext2D,
		x0: number,
		y0: number,
		x1: number,
		y1: number,
		color: string,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.moveTo(x0, y0);
		ctx.lineTo(x1, y1);
		ctx.stroke();
		// head
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.moveTo(x1 - 3.2, y1 - 6);
		ctx.lineTo(x1 + 3.2, y1 - 6);
		ctx.lineTo(x1, y1);
		ctx.closePath();
		ctx.fill();
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
		const p = playing ? progress : 1;
		const ph1 = Math.min(1, p / 0.28); // queries appear
		const ph2 = Math.min(1, Math.max(0, (p - 0.3) / 0.34)); // attention over segment
		const ph3 = Math.min(1, Math.max(0, (p - 0.66) / 0.34)); // extract to y

		// geometry: one interleaved lane up top, a transformer band, an output lane
		const slots = N_IN + N_SEG; // each segment adds one query
		const gap = canvasPad(w, 5);
		const segGap = canvasPad(w, 16);
		const avail = w - padX * 2;
		const s = Math.min(
			34,
			(avail - (slots - N_SEG) * gap - (N_SEG - 1) * segGap) / slots
		);
		const laneW = slots * s + (slots - N_SEG) * gap + (N_SEG - 1) * segGap;
		const laneX = (w - laneW) / 2;

		const topY = canvasPad(w, 40);
		const barY = canvasPad(w, 132);
		const barH = canvasPad(w, 30);
		const outY = h - canvasPad(w, 58);

		// section labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('1 · interleave a learnable query into each segment of two patches', padX, topY - canvasPad(w, 12));

		// per-segment translucent backgrounds + boxes + attention arcs
		const qCenters: number[] = [];
		const xCenters: number[][] = [];
		let x = laneX;
		for (let seg = 0; seg < N_SEG; seg++) {
			const segStart = x;
			const xs: number[] = [];
			for (let k = 0; k < STRIDE; k++) {
				const idx = seg * STRIDE + k;
				box(ctx, x, topY, s, ORANGE, `x${idx}`, w, 1);
				xs.push(x + s / 2);
				x += s + gap;
			}
			const qx = x;
			qCenters.push(qx + s / 2);
			xCenters.push(xs);
			box(ctx, qx, topY, s, VIOLET, 'q', w, ph1, true);
			const segEnd = qx + s;
			// segment background
			ctx.save();
			ctx.globalAlpha = 0.05 + 0.04 * ph2;
			ctx.fillStyle = VIOLET;
			roundRectPath(ctx, segStart - gap * 0.6, topY - canvasPad(w, 4), segEnd - segStart + gap * 1.2, s + canvasPad(w, 8), 5);
			ctx.fill();
			ctx.restore();
			x += s + segGap;
		}

		// 2 · attention: each query reads the two patches in its segment (arcs above)
		if (ph2 > 0.01) {
			ctx.fillStyle = VIOLET;
			ctx.font = canvasFont(w, 10, '600');
			ctx.textAlign = 'left';
			ctx.fillText('2 · each query attends over its segment', padX, topY + s + canvasPad(w, 22));
			qCenters.forEach((qx, seg) => {
				xCenters[seg].forEach((xc) => {
					const midX = (qx + xc) / 2;
					const lift = topY - canvasPad(w, 12);
					ctx.save();
					ctx.globalAlpha = 0.25 + 0.5 * ph2 * (0.6 + 0.4 * Math.sin(p * Math.PI * 2 + seg));
					ctx.strokeStyle = VIOLET;
					ctx.lineWidth = 1;
					ctx.beginPath();
					ctx.moveTo(xc, topY);
					ctx.quadraticCurveTo(midX, lift, qx, topY);
					ctx.stroke();
					ctx.restore();
				});
			});
		}

		// transformer band
		ctx.save();
		ctx.globalAlpha = 0.35 + 0.65 * Math.min(1, ph1);
		const pulse = ph2 > 0 && ph2 < 1 ? 0.5 + 0.5 * Math.sin(ph2 * Math.PI) : ph2 >= 1 ? 0.9 : 0.2;
		ctx.fillStyle = `rgba(124,77,255,${0.05 + 0.05 * pulse})`;
		roundRectPath(ctx, laneX, barY, laneW, barH, 6);
		ctx.fill();
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 1.2;
		ctx.setLineDash([4, 3]);
		roundRectPath(ctx, laneX, barY, laneW, barH, 6);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('D transformer layers', w / 2, barY + barH / 2);
		ctx.restore();

		// feed every slot into the band
		ctx.save();
		ctx.globalAlpha = 0.18 * Math.min(1, ph1);
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 0.8;
		[...xCenters.flat(), ...qCenters].forEach((cx) => {
			ctx.beginPath();
			ctx.moveTo(cx, topY + s);
			ctx.lineTo(cx, barY);
			ctx.stroke();
		});
		ctx.restore();

		// 3 · keep the query outputs as the downsampled sequence
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('3 · keep only the query outputs  ·  2× shorter', padX, outY + s + canvasPad(w, 20));

		qCenters.forEach((qx, seg) => {
			const ox = qx - s / 2;
			if (ph3 > 0.02) arrow(ctx, qx, barY + barH, qx, outY, TEAL, 0.35 * ph3);
			box(ctx, ox, outY, s, TEAL, `y${seg}`, w, ph3);
		});
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
		} else {
			// keep the attention arcs gently shimmering when fully shown
			draw();
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
			SAME downsamples with attention instead of strided convolution. It splits the sequence into
			segments, drops a learnable query into each, runs the whole interleaved sequence through the
			transformer so every query reads its own segment, then keeps only the query outputs. Stride 2
			halves the length here. SAME stacks this into a 16× stage, which on top of 256× patching gives
			the full 4096× compression.
		{/snippet}
	</VizPanel>
</div>
