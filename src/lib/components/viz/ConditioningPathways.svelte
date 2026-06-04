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

	const ORANGE = '#e07020'; // text / cross-attn
	const VIOLET = '#7c4dff'; // timestep + duration / AdaLN
	const TEAL = '#1a9e8f'; // inpaint mask / local-additive
	const GREY = '#9ca3af';

	let playing = $state(true);
	let t = 0;

	function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

	function head(ctx: CanvasRenderingContext2D, x: number, y: number, dir: string, color: string) {
		ctx.save();
		ctx.fillStyle = color;
		ctx.beginPath();
		if (dir === 'down') {
			ctx.moveTo(x - 4, y - 7); ctx.lineTo(x + 4, y - 7); ctx.lineTo(x, y);
		} else if (dir === 'up') {
			ctx.moveTo(x - 4, y + 7); ctx.lineTo(x + 4, y + 7); ctx.lineTo(x, y);
		} else if (dir === 'right') {
			ctx.moveTo(x - 7, y - 4); ctx.lineTo(x - 7, y + 4); ctx.lineTo(x, y);
		}
		ctx.closePath();
		ctx.fill();
		ctx.restore();
	}

	// a pulse dot travelling along a straight segment toward its target
	function pulse(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, color: string, phase: number) {
		const f = ((t * 0.7 + phase) % 1);
		const px = x0 + (x1 - x0) * f;
		const py = y0 + (y1 - y0) * f;
		ctx.save();
		ctx.globalAlpha = 0.9 * (1 - Math.abs(f - 0.5) * 0.7);
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.arc(px, py, 3, 0, Math.PI * 2);
		ctx.fill();
		ctx.restore();
	}

	function line(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, color: string, alpha = 0.5) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.moveTo(x0, y0);
		ctx.lineTo(x1, y1);
		ctx.stroke();
		ctx.restore();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 16);
		const blkW = Math.min(canvasPad(w, 300), w * 0.4);
		const blkX = (w - blkW) / 2;
		const cx = w / 2;
		const subs = [
			{ name: 'self-attention', tint: VIOLET },
			{ name: 'cross-attention', tint: ORANGE },
			{ name: 'feed-forward (SwiGLU)', tint: VIOLET }
		];
		const blkTop = canvasPad(w, 56);
		const blkBot = h - canvasPad(w, 56);
		const blkH = blkBot - blkTop;
		const subH = blkH / subs.length;

		// outer block
		ctx.save();
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 1.2;
		ctx.setLineDash([4, 3]);
		roundRectPath(ctx, blkX, blkTop, blkW, blkH, 6);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.restore();

		// sub-blocks
		const subMid: number[] = [];
		subs.forEach((sb, i) => {
			const y = blkTop + i * subH;
			const my = y + subH / 2;
			subMid.push(my);
			const ix = blkX + canvasPad(w, 10);
			const iy = y + canvasPad(w, 7);
			const iw = blkW - canvasPad(w, 20);
			const ih = subH - canvasPad(w, 14);
			ctx.save();
			ctx.globalAlpha = 0.07;
			ctx.fillStyle = sb.tint;
			roundRectPath(ctx, ix, iy, iw, ih, 5);
			ctx.fill();
			ctx.restore();
			ctx.strokeStyle = sb.tint === ORANGE ? ORANGE : GREY;
			ctx.lineWidth = sb.tint === ORANGE ? 1.3 : 1;
			ctx.globalAlpha = sb.tint === ORANGE ? 0.7 : 1;
			roundRectPath(ctx, ix, iy, iw, ih, 5);
			ctx.stroke();
			ctx.globalAlpha = 1;
			// AdaLN tick on the left edge of every sub-layer
			ctx.fillStyle = VIOLET;
			ctx.fillRect(ix, iy, canvasPad(w, 3), ih);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 11, '500');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(sb.name, cx, my);
		});

		// ---- top pathway: timestep + duration -> AdaLN ----
		const topLabelY = canvasPad(w, 16);
		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('timestep t + duration', cx, topLabelY);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('AdaLN: scale · shift · gate', cx, topLabelY + canvasPad(w, 12));
		line(ctx, cx, topLabelY + canvasPad(w, 18), cx, blkTop, VIOLET);
		head(ctx, cx, blkTop, 'down', VIOLET);
		pulse(ctx, cx, topLabelY + canvasPad(w, 18), cx, blkTop, VIOLET, 0);

		// ---- left pathway: text (T5Gemma) -> cross-attention ----
		const srcW = canvasPad(w, 92);
		const srcH = canvasPad(w, 34);
		const srcX = padX;
		const srcY = subMid[1] - srcH / 2;
		ctx.save();
		ctx.globalAlpha = 0.08;
		ctx.fillStyle = ORANGE;
		roundRectPath(ctx, srcX, srcY, srcW, srcH, 6);
		ctx.fill();
		ctx.restore();
		ctx.strokeStyle = ORANGE;
		ctx.lineWidth = 1.3;
		roundRectPath(ctx, srcX, srcY, srcW, srcH, 6);
		ctx.stroke();
		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('text prompt', srcX + srcW / 2, srcY + srcH / 2 - canvasPad(w, 6));
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('frozen T5Gemma', srcX + srcW / 2, srcY + srcH / 2 + canvasPad(w, 7));
		line(ctx, srcX + srcW, subMid[1], blkX, subMid[1], ORANGE);
		head(ctx, blkX, subMid[1], 'right', ORANGE);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('cross-attention', (srcX + srcW + blkX) / 2, subMid[1] - canvasPad(w, 7));
		pulse(ctx, srcX + srcW, subMid[1], blkX, subMid[1], ORANGE, 0.33);

		// ---- bottom pathway: masked input + mask -> local addition ----
		const botLabelY = h - canvasPad(w, 24);
		ctx.fillStyle = TEAL;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('masked input + mask', cx, botLabelY + canvasPad(w, 10));
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('added at every block (inpainting)', cx, botLabelY + canvasPad(w, 21));
		line(ctx, cx, botLabelY, cx, blkBot, TEAL);
		head(ctx, cx, blkBot, 'up', TEAL);
		pulse(ctx, cx, botLabelY, cx, blkBot, TEAL, 0.66);

		// ---- right side: AdaLN reaches every sub-layer ----
		const tagX = blkX + blkW + canvasPad(w, 10);
		subMid.forEach((my) => {
			ctx.fillStyle = VIOLET;
			ctx.font = canvasFont(w, 9, '600');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText('γ · σ · β', tagX, my);
		});
		// brace
		ctx.save();
		ctx.strokeStyle = VIOLET;
		ctx.globalAlpha = 0.4;
		ctx.lineWidth = 1;
		const braceX = tagX + canvasPad(w, 40);
		ctx.beginPath();
		ctx.moveTo(braceX, subMid[0]);
		ctx.lineTo(braceX, subMid[subMid.length - 1]);
		ctx.stroke();
		ctx.restore();
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText('every', braceX + canvasPad(w, 5), (subMid[0] + subMid[subMid.length - 1]) / 2 - canvasPad(w, 6));
		ctx.fillText('sub-layer', braceX + canvasPad(w, 5), (subMid[0] + subMid[subMid.length - 1]) / 2 + canvasPad(w, 6));
	}

	function tick() {
		if (running && playing) {
			t += 0.006;
			draw();
		}
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {
				running = true;
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
	<VizPanel title="Three Conditioning Pathways" titleColor="var(--violet)">
		{#snippet controls()}
			<VizButton color="var(--violet)" active={playing} onclick={() => (playing = !playing)}>
				{playing ? 'Pause' : 'Animate'}
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:300px"></canvas>
		{#snippet caption()}
			Conditioning reaches every DiT block through three different doors. The diffusion timestep and
			the requested duration modulate each sub-layer through adaptive layer norm (the scale, shift,
			and gate on the right). The text prompt, encoded by a frozen T5Gemma, comes in through
			cross-attention. And for editing, the masked reference audio and its binary mask are added to
			the hidden state at every block. (After SA3 Figures 4 and 8.)
		{/snippet}
	</VizPanel>
</div>
