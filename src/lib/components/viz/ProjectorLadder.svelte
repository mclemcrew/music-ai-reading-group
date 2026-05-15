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

	type Variant = 'linear' | 'mlp' | 'qformer' | 'perceiver';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;

	let variant: Variant = $state('linear');

	const COLORS: Record<Variant, string> = {
		linear: '#e07020',
		mlp: '#1a9e8f',
		qformer: '#7c4dff',
		perceiver: '#2979ff'
	};

	const TITLES: Record<Variant, string> = {
		linear: 'Linear Projector',
		mlp: 'MLP Projector',
		qformer: 'Q-Former',
		perceiver: 'Perceiver Resampler'
	};

	const CAPTIONS: Record<Variant, string> = {
		linear: 'Single matrix. Dimension change only. ~10M params. Used by LTU and LLark.',
		mlp: 'Two-layer MLP with one nonlinearity. Used by Music Flamingo and Audio Flamingo Next.',
		qformer:
			'Q-Former: K learned query vectors cross-attend to all encoder frames. Compresses arbitrary T into fixed N. Used by BLIP-2.',
		perceiver:
			'Perceiver Resampler: stacked cross-attention with learned latents. Original DeepMind Flamingo. Fixed N=64 regardless of input length.'
	};

	const T = 24; // input audio frames

	function setVariant(v: Variant) {
		variant = v;
		draw();
	}

	function withAlpha(hex: string, alpha: number): string {
		const r = parseInt(hex.slice(1, 3), 16);
		const g = parseInt(hex.slice(3, 5), 16);
		const b = parseInt(hex.slice(5, 7), 16);
		return `rgba(${r},${g},${b},${alpha})`;
	}

	function drawBar(
		ctx: CanvasRenderingContext2D,
		x: number,
		yTop: number,
		barW: number,
		barH: number,
		count: number,
		color: string,
		showEllipsis = false
	) {
		const gap = 1;
		const cellH = (barH - gap * (count - 1)) / count;
		ctx.lineWidth = 1;
		ctx.fillStyle = withAlpha(color, 0.04);
		ctx.strokeStyle = withAlpha(color, 0.7);
		for (let i = 0; i < count; i++) {
			const y = yTop + i * (cellH + gap);
			ctx.fillRect(x, y, barW, cellH);
			ctx.strokeRect(x + 0.5, y + 0.5, barW - 1, cellH - 1);
		}
		if (showEllipsis) {
			ctx.fillStyle = withAlpha(color, 0.5);
			const cx = x + barW / 2;
			const ey = yTop + barH + 8;
			for (let i = 0; i < 3; i++) {
				ctx.beginPath();
				ctx.arc(cx + (i - 1) * 5, ey, 1.2, 0, Math.PI * 2);
				ctx.fill();
			}
		}
	}

	function getBarRowYs(yTop: number, barH: number, count: number): number[] {
		const gap = 1;
		const cellH = (barH - gap * (count - 1)) / count;
		const ys: number[] = [];
		for (let i = 0; i < count; i++) {
			ys.push(yTop + i * (cellH + gap) + cellH / 2);
		}
		return ys;
	}

	function drawLabelBelow(
		ctx: CanvasRenderingContext2D,
		text: string,
		cx: number,
		y: number,
		w: number
	) {
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(text, cx, y);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const color = COLORS[variant];
		const padX = canvasPad(w, 22);
		const padTop = canvasPad(w, 28);
		const padBottom = canvasPad(w, 26);

		// Header
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 12, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText(TITLES[variant], padX, 8);

		// Faintness scaling for narrow viewports
		const lineAlpha = w < 500 ? 0.1 : 0.18;

		// Bar geometry
		const barW = Math.max(10, Math.min(18, w * 0.025));
		const barH = h - padTop - padBottom;
		const leftBarX = padX;
		const yTop = padTop;

		// Determine right side count
		let rightCount = T;
		let rightShowEllipsis = false;
		let rightLabel = 'N LLM tokens';
		if (variant === 'qformer') {
			rightCount = 8;
			rightShowEllipsis = true;
			rightLabel = 'N=32 LLM tokens';
		} else if (variant === 'perceiver') {
			rightCount = 8;
			rightShowEllipsis = true;
			rightLabel = 'N=64 LLM tokens';
		}

		const rightBarX = w - padX - barW;

		// Left bar
		drawBar(ctx, leftBarX, yTop, barW, barH, T, color, false);
		drawLabelBelow(ctx, 'T=24 audio frames', leftBarX + barW / 2, yTop + barH + 8, w);

		// Right bar
		drawBar(ctx, rightBarX, yTop, barW, barH, rightCount, color, rightShowEllipsis);
		drawLabelBelow(
			ctx,
			rightLabel,
			rightBarX + barW / 2,
			yTop + barH + (rightShowEllipsis ? 18 : 8),
			w
		);

		const leftYs = getBarRowYs(yTop, barH, T);
		const rightYs = getBarRowYs(yTop, barH, rightCount);

		const midLeft = leftBarX + barW;
		const midRight = rightBarX;
		const midW = midRight - midLeft;
		const midCx = midLeft + midW / 2;

		ctx.lineWidth = 1;

		if (variant === 'linear') {
			// Single thin vertical rectangle in middle
			const boxW = Math.min(70, midW * 0.35);
			const boxH = barH * 0.55;
			const boxX = midCx - boxW / 2;
			const boxY = yTop + (barH - boxH) / 2;

			// Faint connecting lines first
			ctx.strokeStyle = withAlpha(color, lineAlpha);
			ctx.lineWidth = 1;
			for (let i = 0; i < T; i++) {
				ctx.beginPath();
				ctx.moveTo(midLeft, leftYs[i]);
				ctx.lineTo(midRight, rightYs[i]);
				ctx.stroke();
			}

			// Box
			ctx.fillStyle = withAlpha(color, 0.04);
			ctx.fillRect(boxX, boxY, boxW, boxH);
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			ctx.strokeRect(boxX + 0.5, boxY + 0.5, boxW - 1, boxH - 1);

			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 10, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText('Linear', midCx, boxY + boxH / 2 - 7);
			ctx.font = canvasFont(w, 9);
			ctx.fillText('W ∈ ℝ^(d_a × d_l)', midCx, boxY + boxH / 2 + 8);
		} else if (variant === 'mlp') {
			// Two stacked thin vertical rectangles
			const boxW = Math.min(60, midW * 0.28);
			const boxH = barH * 0.55;
			const gap = 14;
			const totalW = boxW * 2 + gap;
			const box1X = midCx - totalW / 2;
			const box2X = box1X + boxW + gap;
			const boxY = yTop + (barH - boxH) / 2;

			// Faint lines
			ctx.strokeStyle = withAlpha(color, lineAlpha);
			ctx.lineWidth = 1;
			for (let i = 0; i < T; i++) {
				ctx.beginPath();
				ctx.moveTo(midLeft, leftYs[i]);
				ctx.lineTo(midRight, rightYs[i]);
				ctx.stroke();
			}

			// Box 1
			ctx.fillStyle = withAlpha(color, 0.04);
			ctx.fillRect(box1X, boxY, boxW, boxH);
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			ctx.strokeRect(box1X + 0.5, boxY + 0.5, boxW - 1, boxH - 1);

			// Box 2
			ctx.fillStyle = withAlpha(color, 0.04);
			ctx.fillRect(box2X, boxY, boxW, boxH);
			ctx.strokeRect(box2X + 0.5, boxY + 0.5, boxW - 1, boxH - 1);

			// Arrow between boxes (GeLU)
			ctx.strokeStyle = color;
			ctx.lineWidth = 1.2;
			ctx.beginPath();
			ctx.moveTo(box1X + boxW, boxY + boxH / 2);
			ctx.lineTo(box2X, boxY + boxH / 2);
			ctx.stroke();
			// arrowhead
			ctx.beginPath();
			ctx.moveTo(box2X, boxY + boxH / 2);
			ctx.lineTo(box2X - 4, boxY + boxH / 2 - 3);
			ctx.lineTo(box2X - 4, boxY + boxH / 2 + 3);
			ctx.closePath();
			ctx.fillStyle = color;
			ctx.fill();

			// Labels
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 10, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText('Linear', box1X + boxW / 2, boxY + boxH / 2);
			ctx.fillText('Linear', box2X + boxW / 2, boxY + boxH / 2);
			ctx.font = canvasFont(w, 9);
			ctx.fillText('GeLU', (box1X + boxW + box2X) / 2, boxY - 8);
		} else if (variant === 'qformer') {
			// K learned queries (8 circles) in middle
			const K = 8;
			const queryR = Math.max(5, Math.min(9, midW * 0.025));
			const queryX = midCx;
			const queryColH = barH * 0.7;
			const queryYTop = yTop + (barH - queryColH) / 2;
			const queryYs: number[] = [];
			for (let i = 0; i < K; i++) {
				queryYs.push(queryYTop + (i + 0.5) * (queryColH / K));
			}

			// Cross-attention: every left cell to every query (faint)
			ctx.strokeStyle = withAlpha(color, lineAlpha);
			ctx.lineWidth = 0.6;
			for (let i = 0; i < T; i++) {
				for (let k = 0; k < K; k++) {
					ctx.beginPath();
					ctx.moveTo(midLeft, leftYs[i]);
					ctx.lineTo(queryX - queryR, queryYs[k]);
					ctx.stroke();
				}
			}

			// Query → output (one to one)
			ctx.strokeStyle = withAlpha(color, 0.5);
			ctx.lineWidth = 1;
			for (let k = 0; k < K; k++) {
				ctx.beginPath();
				ctx.moveTo(queryX + queryR, queryYs[k]);
				ctx.lineTo(midRight, rightYs[k]);
				ctx.stroke();
			}

			// Query circles
			for (let k = 0; k < K; k++) {
				ctx.fillStyle = withAlpha(color, 0.08);
				ctx.beginPath();
				ctx.arc(queryX, queryYs[k], queryR, 0, Math.PI * 2);
				ctx.fill();
				ctx.strokeStyle = color;
				ctx.lineWidth = 1;
				ctx.beginPath();
				ctx.arc(queryX, queryYs[k], queryR, 0, Math.PI * 2);
				ctx.stroke();
			}

			// Label
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 10, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			ctx.fillText('learned queries', queryX, queryYTop + queryColH + 6);
			ctx.font = canvasFont(w, 9);
			ctx.fillText('K=8 (× cross-attn)', queryX, queryYTop + queryColH + 19);
		} else if (variant === 'perceiver') {
			// Two stacked query columns connected by arrows
			const K = 8;
			const queryR = Math.max(4, Math.min(7, midW * 0.02));
			const colGap = Math.min(70, midW * 0.3);
			const col1X = midCx - colGap / 2;
			const col2X = midCx + colGap / 2;
			const queryColH = barH * 0.7;
			const queryYTop = yTop + (barH - queryColH) / 2;
			const queryYs: number[] = [];
			for (let i = 0; i < K; i++) {
				queryYs.push(queryYTop + (i + 0.5) * (queryColH / K));
			}

			// Encoder → col1 cross-attn (faint, full)
			ctx.strokeStyle = withAlpha(color, lineAlpha);
			ctx.lineWidth = 0.5;
			for (let i = 0; i < T; i++) {
				for (let k = 0; k < K; k++) {
					ctx.beginPath();
					ctx.moveTo(midLeft, leftYs[i]);
					ctx.lineTo(col1X - queryR, queryYs[k]);
					ctx.stroke();
				}
			}

			// Encoder → col2 cross-attn (faint)
			ctx.strokeStyle = withAlpha(color, lineAlpha * 0.7);
			for (let i = 0; i < T; i++) {
				for (let k = 0; k < K; k++) {
					ctx.beginPath();
					ctx.moveTo(midLeft, leftYs[i]);
					ctx.lineTo(col2X - queryR, queryYs[k]);
					ctx.stroke();
				}
			}

			// Vertical arrows: col1[k] → col2[k] (cross-attn layer connector)
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			for (let k = 0; k < K; k++) {
				ctx.beginPath();
				ctx.moveTo(col1X + queryR, queryYs[k]);
				ctx.lineTo(col2X - queryR - 2, queryYs[k]);
				ctx.stroke();
				// small arrowhead
				ctx.beginPath();
				ctx.moveTo(col2X - queryR - 2, queryYs[k]);
				ctx.lineTo(col2X - queryR - 5, queryYs[k] - 2);
				ctx.lineTo(col2X - queryR - 5, queryYs[k] + 2);
				ctx.closePath();
				ctx.fillStyle = color;
				ctx.fill();
			}

			// Col2 → output bar
			ctx.strokeStyle = withAlpha(color, 0.5);
			ctx.lineWidth = 1;
			for (let k = 0; k < K; k++) {
				ctx.beginPath();
				ctx.moveTo(col2X + queryR, queryYs[k]);
				ctx.lineTo(midRight, rightYs[k]);
				ctx.stroke();
			}

			// Draw both columns of circles
			for (const colX of [col1X, col2X]) {
				for (let k = 0; k < K; k++) {
					ctx.fillStyle = withAlpha(color, 0.08);
					ctx.beginPath();
					ctx.arc(colX, queryYs[k], queryR, 0, Math.PI * 2);
					ctx.fill();
					ctx.strokeStyle = color;
					ctx.lineWidth = 1;
					ctx.beginPath();
					ctx.arc(colX, queryYs[k], queryR, 0, Math.PI * 2);
					ctx.stroke();
				}
			}

			// Label
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 10, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			ctx.fillText('Perceiver Resampler', midCx, queryYTop + queryColH + 6);
			ctx.font = canvasFont(w, 9);
			ctx.fillText('stacked cross-attn', midCx, queryYTop + queryColH + 19);
		}
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => draw(),
			() => {}
		);
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			running = false;
			obs.disconnect();
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<div bind:this={container}>
	<VizPanel title="The Projector Ladder" titleColor="var(--violet)">
		{#snippet controls()}
			<VizButton
				color="var(--orange)"
				active={variant === 'linear'}
				onclick={() => setVariant('linear')}
			>
				Linear
			</VizButton>
			<VizButton color="var(--teal)" active={variant === 'mlp'} onclick={() => setVariant('mlp')}>
				MLP
			</VizButton>
			<VizButton
				color="var(--violet)"
				active={variant === 'qformer'}
				onclick={() => setVariant('qformer')}
			>
				Q-Former
			</VizButton>
			<VizButton
				color="var(--blue)"
				active={variant === 'perceiver'}
				onclick={() => setVariant('perceiver')}
			>
				Perceiver
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:260px"></canvas>
		{#snippet caption()}
			{CAPTIONS[variant]}
		{/snippet}
	</VizPanel>
</div>

<style>
	canvas {
		display: block;
		width: 100%;
	}
</style>
