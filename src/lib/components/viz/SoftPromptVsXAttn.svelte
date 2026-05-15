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
	let visible = false;
	let running = true;
	let raf = 0;

	let gate = $state(0);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 3000;

	const ORANGE = '#e07020';
	const TEAL = '#1a9e8f';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const GREY = '#9ca3af';

	const N_AUDIO = 4;
	const M_TEXT = 6;
	const N_BLOCKS = 4;

	function roundRect(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		r: number
	) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

	function strokeBox(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		color: string,
		r = 4,
		lineWidth = 1,
		fillAlpha = 0.04,
		dashed = false
	) {
		ctx.save();
		// fill
		ctx.fillStyle = color;
		ctx.globalAlpha = fillAlpha;
		roundRect(ctx, x, y, w, h, r);
		ctx.fill();
		ctx.globalAlpha = 1;
		// stroke
		ctx.strokeStyle = color;
		ctx.lineWidth = lineWidth;
		if (dashed) ctx.setLineDash([4, 3]);
		roundRect(ctx, x, y, w, h, r);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.restore();
	}

	function arrow(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y1: number,
		x2: number,
		y2: number,
		color: string,
		lineWidth = 1,
		alpha = 1,
		dashed = false
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.fillStyle = color;
		ctx.lineWidth = lineWidth;
		if (dashed) ctx.setLineDash([4, 3]);
		ctx.beginPath();
		ctx.moveTo(x1, y1);
		ctx.lineTo(x2, y2);
		ctx.stroke();
		ctx.setLineDash([]);
		// arrowhead
		const ang = Math.atan2(y2 - y1, x2 - x1);
		const ah = 5;
		ctx.beginPath();
		ctx.moveTo(x2, y2);
		ctx.lineTo(x2 - ah * Math.cos(ang - Math.PI / 6), y2 - ah * Math.sin(ang - Math.PI / 6));
		ctx.lineTo(x2 - ah * Math.cos(ang + Math.PI / 6), y2 - ah * Math.sin(ang + Math.PI / 6));
		ctx.closePath();
		ctx.fill();
		ctx.restore();
	}

	function drawTokenRow(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		laneW: number,
		tokens: Array<{ color: string; label: string }>,
		tokH: number
	) {
		const n = tokens.length;
		const gap = 3;
		const tokW = (laneW - gap * (n - 1)) / n;
		tokens.forEach((tok, i) => {
			const tx = x + i * (tokW + gap);
			strokeBox(ctx, tx, y, tokW, tokH, tok.color, 3, 1, 0.06);
			ctx.fillStyle = tok.color;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(tok.label, tx + tokW / 2, y + tokH / 2);
		});
		return { tokW, gap };
	}

	function drawBlockStack(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		blockW: number,
		blockH: number,
		blockGap: number,
		color: string,
		labelPrefix: string
	) {
		for (let i = 0; i < N_BLOCKS; i++) {
			const by = y + i * (blockH + blockGap);
			strokeBox(ctx, x, by, blockW, blockH, color, 5, 1, 0.04);
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(`${labelPrefix} ${i + 1}`, x + blockW / 2, by + blockH / 2);

			// arrow between blocks
			if (i < N_BLOCKS - 1) {
				arrow(
					ctx,
					x + blockW / 2,
					by + blockH,
					x + blockW / 2,
					by + blockH + blockGap,
					color,
					1,
					0.5
				);
			}
		}
	}

	function drawLeftPanel(
		ctx: CanvasRenderingContext2D,
		w: number,
		h: number,
		px: number,
		py: number,
		panelX: number,
		panelW: number
	) {
		// Header
		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 13, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('Soft Prompt', panelX, py);

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('LLaVA / LTU / LLark / Audio Flamingo', panelX, py + 16);

		// Token lane: N audio (orange) + M text (grey)
		const laneY = py + 36;
		const laneH = 18;
		const laneX = panelX;
		const laneW = panelW;
		const tokens = [
			...Array.from({ length: N_AUDIO }, () => ({ color: ORANGE, label: 'audio' })),
			...Array.from({ length: M_TEXT }, () => ({ color: GREY, label: 'text' }))
		];
		drawTokenRow(ctx, w, laneX, laneY, laneW, tokens, laneH);

		// Lane bracket label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('single combined sequence', laneX, laneY + laneH + 4);

		// Block stack
		const blockStackY = laneY + laneH + 22;
		const availH = h - blockStackY - py - 10;
		const blockGap = 6;
		const blockH = (availH - blockGap * (N_BLOCKS - 1)) / N_BLOCKS;
		const blockW = Math.min(panelW * 0.55, 140);
		const blockX = panelX + (panelW - blockW) / 2 - panelW * 0.05;

		// Arrow from token lane down to first block
		arrow(
			ctx,
			blockX + blockW / 2,
			laneY + laneH + 14,
			blockX + blockW / 2,
			blockStackY - 2,
			VIOLET,
			1,
			0.5
		);

		drawBlockStack(ctx, w, blockX, blockStackY, blockW, blockH, blockGap, VIOLET, 'LM block');

		// Annotation on the right
		const annoX = blockX + blockW + 10;
		const annoW = panelX + panelW - annoX;
		if (annoW > 60) {
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'left';
			ctx.textBaseline = 'top';
			const lines = ['Audio is part of', 'the input sequence.', '', 'LM is unchanged.'];
			lines.forEach((line, i) => {
				ctx.fillText(line, annoX, blockStackY + 8 + i * 12);
			});
		}
	}

	function drawRightPanel(
		ctx: CanvasRenderingContext2D,
		w: number,
		h: number,
		px: number,
		py: number,
		panelX: number,
		panelW: number
	) {
		// Header
		ctx.fillStyle = BLUE;
		ctx.font = canvasFont(w, 13, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('Gated XAttn', panelX, py);

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('original DeepMind Flamingo', panelX, py + 16);

		// Text-only lane (no audio inline)
		const laneY = py + 36;
		const laneH = 18;
		// Reserve right side for resampler + xattn branches
		const branchW = Math.min(panelW * 0.35, 110);
		const laneX = panelX;
		const laneW = panelW - branchW - 8;
		const textTokens = Array.from({ length: M_TEXT }, () => ({ color: GREY, label: 'text' }));
		drawTokenRow(ctx, w, laneX, laneY, laneW, textTokens, laneH);

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('text-only sequence', laneX, laneY + laneH + 4);

		// Perceiver Resampler box on right
		const prX = laneX + laneW + 8;
		const prW = branchW;
		const prH = 38;
		const prY = laneY - 4;
		strokeBox(ctx, prX, prY, prW, prH, ORANGE, 4, 1, 0.05);
		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 9, 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('Perceiver', prX + prW / 2, prY + 11);
		ctx.fillText('Resampler', prX + prW / 2, prY + 23);

		// Mini audio token bar inside/below Perceiver
		const audioY = prY + prH + 4;
		const audioH = 10;
		const audioGap = 2;
		const audioTokW = (prW - audioGap * (N_AUDIO - 1)) / N_AUDIO;
		for (let i = 0; i < N_AUDIO; i++) {
			const ax = prX + i * (audioTokW + audioGap);
			strokeBox(ctx, ax, audioY, audioTokW, audioH, ORANGE, 2, 0.8, 0.08);
		}
		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 8);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(`${N_AUDIO} audio tokens`, prX + prW / 2, audioY + audioH + 2);

		// Block stack
		const blockStackY = laneY + laneH + 22;
		const availH = h - blockStackY - py - 24;
		const blockGap = 6;
		const blockH = (availH - blockGap * (N_BLOCKS - 1)) / N_BLOCKS;
		const blockW = Math.min(laneW * 0.7, 120);
		const blockX = laneX + (laneW - blockW) / 2;

		// Arrow from token lane down
		arrow(
			ctx,
			blockX + blockW / 2,
			laneY + laneH + 14,
			blockX + blockW / 2,
			blockStackY - 2,
			BLUE,
			1,
			0.5
		);

		// Draw blocks with optional xattn branches
		const branchAlpha = 0.05 + gate * 0.85;
		const branchLW = 0.6 + gate * 1.6;

		for (let i = 0; i < N_BLOCKS; i++) {
			const by = blockStackY + i * (blockH + blockGap);
			strokeBox(ctx, blockX, by, blockW, blockH, BLUE, 5, 1, 0.04);
			ctx.fillStyle = BLUE;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(`LM block ${i + 1}`, blockX + blockW / 2, by + blockH / 2);

			// Connect blocks
			if (i < N_BLOCKS - 1) {
				arrow(
					ctx,
					blockX + blockW / 2,
					by + blockH,
					blockX + blockW / 2,
					by + blockH + blockGap,
					BLUE,
					1,
					0.5
				);
			}

			// Gated xattn branch on every other block (i = 1, 3 → blocks 2 and 4)
			if (i === 1 || i === 3) {
				const xbW = Math.min(branchW - 6, 90);
				const xbH = Math.min(blockH * 0.7, 22);
				const xbX = prX + (prW - xbW) / 2;
				const xbY = by + (blockH - xbH) / 2;

				// dashed branch box
				ctx.save();
				ctx.globalAlpha = branchAlpha;
				strokeBox(ctx, xbX, xbY, xbW, xbH, TEAL, 3, branchLW, 0.05, true);
				ctx.fillStyle = TEAL;
				ctx.globalAlpha = branchAlpha;
				ctx.font = canvasFont(w, 8, 'bold');
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				ctx.fillText('tanh(α)·xattn', xbX + xbW / 2, xbY + xbH / 2);
				ctx.restore();

				// arrow from xattn box INTO the LM block
				arrow(
					ctx,
					xbX,
					xbY + xbH / 2,
					blockX + blockW + 1,
					by + blockH / 2,
					TEAL,
					branchLW,
					branchAlpha
				);

				// thin line from Perceiver Resampler box DOWN to this xattn box
				const fromX = prX + prW / 2;
				const fromY = audioY + audioH + 12;
				ctx.save();
				ctx.globalAlpha = branchAlpha * 0.7;
				ctx.strokeStyle = ORANGE;
				ctx.lineWidth = branchLW * 0.7;
				ctx.setLineDash([2, 2]);
				ctx.beginPath();
				ctx.moveTo(fromX, fromY);
				ctx.lineTo(fromX, xbY + xbH / 2);
				ctx.lineTo(xbX + xbW + 1, xbY + xbH / 2);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.restore();
			}
		}

		// Gate-state label
		const gateLabel =
			gate < 0.05
				? 'α≈0: LM = pretrained LM'
				: gate > 0.95
					? 'α=1: full audio influence'
					: `α=${gate.toFixed(2)}: partial`;
		ctx.fillStyle = gate < 0.05 ? CANVAS_LABEL : TEAL;
		ctx.font = canvasFont(w, 9, gate > 0.05 ? 'bold' : '');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		const labelY = blockStackY + N_BLOCKS * (blockH + blockGap) - blockGap + 4;
		ctx.fillText(gateLabel, panelX, labelY);

		// Formula below
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('y ← y + tanh(α) · xattn(y, audio)', panelX, labelY + 12);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const px = canvasPad(w, 14);
		const py = canvasPad(w, 12);

		const innerW = w - px * 2;
		const half = innerW / 2;
		const dividerX = px + half;
		const gutter = canvasPad(w, 10);

		// Vertical divider
		ctx.strokeStyle = 'rgba(0,0,0,0.12)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(dividerX, py);
		ctx.lineTo(dividerX, h - py);
		ctx.stroke();

		// Left panel
		drawLeftPanel(ctx, w, h, px, py, px, half - gutter / 2);

		// Right panel
		drawRightPanel(ctx, w, h, px, py, dividerX + gutter / 2, half - gutter / 2);
	}

	function tick(ts: number) {
		if (!running) return;
		if (playing) {
			const elapsed = ts - playStart;
			const t = Math.min(1, elapsed / PLAY_MS);
			gate = t;
			draw();
			if (t >= 1) {
				playing = false;
			}
		}
		raf = requestAnimationFrame(tick);
	}

	function togglePlay() {
		if (playing) {
			playing = false;
			return;
		}
		gate = 0;
		playStart = performance.now();
		playing = true;
	}

	function reset() {
		playing = false;
		gate = 0;
		draw();
	}

	function onSlider() {
		playing = false;
		draw();
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {
				visible = true;
				running = true;
				draw();
				raf = requestAnimationFrame(tick);
			},
			() => {
				visible = false;
				running = false;
				if (playing) playing = false;
				cancelAnimationFrame(raf);
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
	<VizPanel title="Soft Prompt vs. Gated Cross-Attention" titleColor="var(--blue)">
		{#snippet controls()}
			<VizButton color="var(--blue)" active={playing} onclick={togglePlay}>
				{playing ? 'Stop' : 'Play'}
			</VizButton>
			<VizButton color="var(--blue)" onclick={reset}>Reset</VizButton>
			<label class="slider">
				<span class="slider-label">α tanh-gate</span>
				<input
					type="range"
					min="0"
					max="1"
					step="0.01"
					bind:value={gate}
					oninput={onSlider}
				/>
				<span class="slider-value">{gate.toFixed(2)}</span>
			</label>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:360px"></canvas>
		{#snippet caption()}
			Audio Flamingo, Audio Flamingo 2/3/Next, and Music Flamingo all use the LEFT pattern despite
			the name. Only the original DeepMind Flamingo (and OpenFlamingo, IDEFICS) uses the RIGHT
			pattern with tanh-gated cross-attention initialized to α=0 so the LM stays bit-identical at
			step 0.
		{/snippet}
	</VizPanel>
</div>

<style>
	.slider {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-display);
		font-size: 0.7rem;
		color: var(--text-muted);
	}

	.slider-label {
		white-space: nowrap;
	}

	.slider-value {
		min-width: 2.4em;
		text-align: right;
		color: var(--blue);
		font-variant-numeric: tabular-nums;
	}

	input[type='range'] {
		-webkit-appearance: none;
		appearance: none;
		width: 90px;
		height: 4px;
		background: var(--border);
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--blue);
		border: 2px solid var(--surface);
		cursor: pointer;
		box-shadow: 0 0 0 1px var(--blue);
	}

	input[type='range']::-moz-range-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--blue);
		border: 2px solid var(--surface);
		cursor: pointer;
	}

	@container viz (max-width: 500px) {
		input[type='range'] {
			width: 70px;
		}
	}
</style>
