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
	const BLUE = '#2979ff';
	const GREY = '#9ca3af';

	let playing = $state(true);
	let t = 0;

	// the three conditioning signals, each highlighting a different injection site
	const PATHWAYS = [
		{ key: 'adaln', label: 't + duration', via: 'AdaLN: gate · scale · shift', color: VIOLET },
		{ key: 'xattn', label: 'text (T5Gemma) + duration', via: 'cross-attention', color: ORANGE },
		{ key: 'local', label: 'masked input + binary mask', via: 'local addition (every block)', color: TEAL }
	];

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 16);
		// central transformer block column
		const blkW = Math.min(canvasPad(w, 200), w * 0.34);
		const blkX = (w - blkW) / 2;
		const subs = ['self-attention', 'cross-attention', 'feed-forward (SwiGLU)'];
		const top = canvasPad(w, 44);
		const bottom = h - canvasPad(w, 30);
		const blkTop = top + canvasPad(w, 6);
		const blkH = bottom - blkTop;
		const subH = blkH / subs.length;

		// outer block outline
		ctx.save();
		ctx.strokeStyle = GREY;
		ctx.lineWidth = 1.2;
		ctx.setLineDash([4, 3]);
		ctx.beginPath();
		ctx.roundRect(blkX, blkTop, blkW, blkH, 6);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.restore();

		// block identity is conveyed by the panel title + sub-block names + caption;
		// the top-centre space is reserved for the AdaLN source label so they don't collide.

		// sub-blocks
		subs.forEach((name, i) => {
			const y = blkTop + i * subH;
			ctx.save();
			ctx.globalAlpha = 0.06;
			ctx.fillStyle = i === 1 ? ORANGE : VIOLET;
			ctx.beginPath();
			ctx.roundRect(blkX + canvasPad(w, 8), y + canvasPad(w, 6), blkW - canvasPad(w, 16), subH - canvasPad(w, 12), 4);
			ctx.fill();
			ctx.restore();
			ctx.strokeStyle = GREY;
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.roundRect(blkX + canvasPad(w, 8), y + canvasPad(w, 6), blkW - canvasPad(w, 16), subH - canvasPad(w, 12), 4);
			ctx.stroke();
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10, '500');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(name, w / 2, y + subH / 2);
		});

		// helper to animate dots along a path
		const phase = (t % 1);
		function flow(pts: number[][], color: string, idx: number) {
			ctx.save();
			ctx.strokeStyle = color;
			ctx.globalAlpha = 0.5;
			ctx.lineWidth = 1.2;
			ctx.beginPath();
			pts.forEach((pt, i) => (i === 0 ? ctx.moveTo(pt[0], pt[1]) : ctx.lineTo(pt[0], pt[1])));
			ctx.stroke();
			ctx.restore();
			// moving dot
			const seg = (phase + idx * 0.33) % 1;
			// piecewise length param along polyline
			let total = 0;
			const segLens = [];
			for (let i = 1; i < pts.length; i++) {
				const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
				segLens.push(d);
				total += d;
			}
			let want = seg * total;
			let px = pts[0][0],
				py = pts[0][1];
			for (let i = 0; i < segLens.length; i++) {
				if (want <= segLens[i]) {
					const f = segLens[i] === 0 ? 0 : want / segLens[i];
					px = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f;
					py = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f;
					break;
				}
				want -= segLens[i];
			}
			ctx.save();
			ctx.fillStyle = color;
			ctx.beginPath();
			ctx.arc(px, py, 3, 0, Math.PI * 2);
			ctx.fill();
			ctx.restore();
		}

		// --- AdaLN: from top, splits to every sub-block edge (modulation) ---
		const adalnSrcX = blkX + blkW * 0.5;
		flow(
			[
				[adalnSrcX, top - canvasPad(w, 2)],
				[adalnSrcX, blkTop]
			],
			VIOLET,
			0
		);
		// little gate marks on the right edge of each sub-block
		subs.forEach((_, i) => {
			const y = blkTop + i * subH + subH / 2;
			ctx.save();
			ctx.globalAlpha = 0.7;
			ctx.fillStyle = VIOLET;
			ctx.font = canvasFont(w, 8, '600');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText('γ·σ·β', blkX + blkW + canvasPad(w, 6), y);
			ctx.restore();
		});

		// --- cross-attention: from left into the middle sub-block ---
		const xY = blkTop + 1 * subH + subH / 2;
		flow(
			[
				[padX + canvasPad(w, 4), xY],
				[blkX, xY]
			],
			ORANGE,
			1
		);

		// --- local-additive: from bottom, adds into every block ---
		const localX = blkX + blkW * 0.5;
		flow(
			[
				[localX, bottom + canvasPad(w, 2)],
				[localX, bottom]
			],
			TEAL,
			2
		);

		// source labels
		ctx.textBaseline = 'middle';
		ctx.font = canvasFont(w, 9, '600');
		// top (AdaLN)
		ctx.fillStyle = VIOLET;
		ctx.textAlign = 'center';
		ctx.fillText('timestep t + duration', adalnSrcX, top - canvasPad(w, 28));
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.fillText('AdaLN modulation', adalnSrcX, top - canvasPad(w, 16));
		// left (cross-attn)
		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.fillText('text', padX, xY - canvasPad(w, 12));
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.fillText('T5Gemma → cross-attn', padX, xY - canvasPad(w, 2));
		// bottom (local-additive)
		ctx.fillStyle = TEAL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'center';
		ctx.fillText('masked input + mask', localX, bottom + canvasPad(w, 12));
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.fillText('local addition (inpainting)', localX, bottom + canvasPad(w, 22));
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
		<canvas bind:this={canvas} style="width:100%;height:280px"></canvas>
		{#snippet caption()}
			Conditioning enters every DiT block by three different doors. The diffusion timestep and the
			requested duration modulate each sub-layer through adaptive layer norm (gate, scale, shift).
			The text prompt — encoded by a frozen T5Gemma — enters through cross-attention. And for
			editing, the masked reference audio plus its binary mask are projected and <em>added</em> to
			the hidden state at every block. (After SA3 Figures 4 &amp; 8.)
		{/snippet}
	</VizPanel>
</div>
