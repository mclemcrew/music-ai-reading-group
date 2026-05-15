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

	type Step = {
		thought: string;
		tool: string;
		args: string;
		color: string;
	};

	const STEPS: Step[] = [
		{
			thought: 'reference is brighter and tighter than target.',
			tool: 'set_eq',
			args: 'high_shelf=4 kHz, +3 dB',
			color: BLUE
		},
		{
			thought: 'low end of target is loose; bring it down a touch.',
			tool: 'set_eq',
			args: 'low_shelf=80 Hz, -2 dB',
			color: BLUE
		},
		{
			thought: 'reference has more dynamic control. add comp.',
			tool: 'set_compressor',
			args: 'ratio=3:1, attack=15 ms',
			color: TEAL
		},
		{
			thought: 'reference is wetter; small plate to glue it.',
			tool: 'set_reverb',
			args: 'plate, mix=0.18, decay=1.4 s',
			color: ORANGE
		}
	];

	let progress = $state(0);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 6000;

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

	function drawAudioCard(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		title: string,
		subtitle: string,
		color: string,
		seed: number
	) {
		ctx.save();
		ctx.fillStyle = color;
		ctx.globalAlpha = 0.06;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText(title, x + 8, y + 6);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText(subtitle, x + 8, y + 22);

		// little mock waveform
		ctx.save();
		ctx.strokeStyle = color;
		ctx.globalAlpha = 0.7;
		ctx.lineWidth = 1;
		ctx.beginPath();
		const wfX = x + 8;
		const wfY = y + hh - 18;
		const wfW = ww - 16;
		for (let i = 0; i < wfW; i += 2) {
			const phase = (i + seed * 7) * 0.18;
			const yy =
				wfY +
				Math.sin(phase) * 6 +
				Math.sin(phase * 2.3) * 3 +
				Math.cos(phase * 0.7 + seed) * 2;
			if (i === 0) ctx.moveTo(wfX + i, yy);
			else ctx.lineTo(wfX + i, yy);
		}
		ctx.stroke();
		ctx.restore();
	}

	function drawLM(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		listening: boolean
	) {
		ctx.save();
		ctx.fillStyle = VIOLET;
		ctx.globalAlpha = 0.06;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 6);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = VIOLET;
		ctx.lineWidth = 1.6;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 6);
		ctx.stroke();
		ctx.restore();
		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 12, 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('multimodal LLM', x + ww / 2, y + 22);
		ctx.font = canvasFont(w, 9);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.fillText('CoT planning', x + ww / 2, y + 36);
		ctx.fillText(
			listening ? 'listening to ref + target' : 'planning chain',
			x + ww / 2,
			y + hh - 14
		);
	}

	function drawCoTBubble(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		text: string,
		alpha: number
	) {
		if (alpha < 0.02) return;
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.fillStyle = '#fff';
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.fill();
		ctx.strokeStyle = VIOLET;
		ctx.setLineDash([3, 2]);
		ctx.lineWidth = 0.9;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 9, '500');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		// Wrap text
		const lines = wrap(ctx, text, ww - 12);
		lines.forEach((line, i) => {
			ctx.fillText(line, x + 6, y + 6 + i * 12);
		});
		ctx.restore();
	}

	function drawToolCall(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		tool: string,
		args: string,
		color: string,
		alpha: number,
		highlighted: boolean
	) {
		if (alpha < 0.02) return;
		ctx.save();
		ctx.globalAlpha = alpha * 0.08;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.fill();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = highlighted ? 1.8 : 1.2;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText(tool, x + 8, y + 6);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		const lines = wrap(ctx, args, ww - 14);
		lines.forEach((line, i) => {
			ctx.fillText(line, x + 8, y + 22 + i * 11);
		});
		ctx.restore();
	}

	function wrap(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
		const words = text.split(/\s+/);
		const lines: string[] = [];
		let cur = '';
		for (const wd of words) {
			const trial = cur ? cur + ' ' + wd : wd;
			if (ctx.measureText(trial).width > maxW && cur) {
				lines.push(cur);
				cur = wd;
			} else {
				cur = trial;
			}
		}
		if (cur) lines.push(cur);
		return lines;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 14);

		// Left column: reference + target audio
		const leftW = Math.min(150, w * 0.22);
		const leftX = padX;
		const cardH = 60;
		const cardGap = 8;
		drawAudioCard(
			ctx,
			w,
			leftX,
			padY,
			leftW,
			cardH,
			'reference',
			'how it should sound',
			TEAL,
			3
		);
		drawAudioCard(
			ctx,
			w,
			leftX,
			padY + cardH + cardGap,
			leftW,
			cardH,
			'target',
			'unprocessed source',
			GREY,
			11
		);

		// Center: LLM
		const lmW = Math.min(140, w * 0.18);
		const lmX = leftX + leftW + 24;
		const lmY = padY;
		const lmH = cardH * 2 + cardGap;
		const listening = progress < 0.15;
		drawLM(ctx, w, lmX, lmY, lmW, lmH, listening);

		// Connect ref/target → LM
		const arrAlpha = 1;
		ctx.save();
		ctx.strokeStyle = GREY;
		ctx.globalAlpha = arrAlpha * 0.45;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(leftX + leftW + 2, padY + cardH / 2);
		ctx.lineTo(lmX - 4, padY + cardH / 2);
		ctx.moveTo(leftX + leftW + 2, padY + cardH + cardGap + cardH / 2);
		ctx.lineTo(lmX - 4, padY + cardH + cardGap + cardH / 2);
		ctx.stroke();
		ctx.restore();

		// Right: chain of tool calls + thoughts
		const rightX = lmX + lmW + 24;
		const rightW = w - rightX - padX;
		const rowH = (lmH + 30) / Math.max(1, STEPS.length);
		const callY0 = padY;
		const callH = 38;
		const tCallW = Math.min(180, rightW * 0.55);
		const tCallX = rightX;

		// Connect LM → chain (single arrow group)
		ctx.save();
		ctx.globalAlpha = 0.55;
		ctx.strokeStyle = VIOLET;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(lmX + lmW + 2, padY + lmH / 2);
		ctx.lineTo(rightX - 6, padY + lmH / 2);
		ctx.stroke();
		ctx.restore();

		// Steps stacked
		const totalH = h - padY * 2 - 4;
		const stepH = totalH / STEPS.length;
		STEPS.forEach((s, i) => {
			const sy = padY + i * stepH;
			const stepProgress = Math.max(0, Math.min(1, progress * STEPS.length - i));
			const cotAlpha = Math.min(1, stepProgress * 1.5);
			const callAlpha = Math.min(1, Math.max(0, stepProgress * 1.5 - 0.5));
			const isHead =
				progress < 1 &&
				stepProgress > 0 &&
				stepProgress < 1;

			// CoT bubble
			const cotW = rightW - tCallW - 14;
			const cotH = Math.min(stepH - 8, 36);
			drawCoTBubble(ctx, w, rightX, sy + 4, cotW, cotH, s.thought, cotAlpha);

			// Tool call
			drawToolCall(
				ctx,
				w,
				rightX + cotW + 14,
				sy + 4,
				tCallW,
				cotH,
				s.tool,
				s.args,
				s.color,
				callAlpha,
				isHead
			);

			// Connect CoT → tool call
			if (callAlpha > 0.05) {
				ctx.save();
				ctx.globalAlpha = callAlpha * 0.55;
				ctx.strokeStyle = s.color;
				ctx.lineWidth = 1;
				ctx.beginPath();
				ctx.moveTo(rightX + cotW + 2, sy + 4 + cotH / 2);
				ctx.lineTo(rightX + cotW + 12, sy + 4 + cotH / 2);
				ctx.stroke();
				ctx.restore();
			}

			// Connect to next step's CoT
			if (i < STEPS.length - 1 && callAlpha > 0.5) {
				ctx.save();
				ctx.globalAlpha = (callAlpha - 0.5) * 1.4;
				ctx.strokeStyle = VIOLET;
				ctx.setLineDash([2, 3]);
				ctx.lineWidth = 0.9;
				ctx.beginPath();
				ctx.moveTo(rightX + cotW / 2, sy + 4 + cotH);
				ctx.lineTo(rightX + cotW / 2, sy + stepH + 4);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.restore();
			}
		});

		// Top header
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('input', padX, 2);
		ctx.fillText('LLM', lmX, 2);
		ctx.fillText('CoT  ↪  tool call', rightX, 2);
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
		progress = 1;
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
	<VizPanel title="LLM2Fx-Tools: tool calling for style transfer" titleColor="var(--orange)">
		{#snippet controls()}
			<VizButton color="var(--orange)" active={playing} onclick={play}>
				Play chain
			</VizButton>
			<VizButton color="var(--orange)" onclick={showAll}>Show full chain</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		{#snippet caption()}
			Reference + target audio go in. The multimodal LLM listens, plans the chain, and emits
			tool calls one at a time, with chain-of-thought reasoning between them. The order is
			learned: EQ before compressor before reverb is a chain decision, not a hardcoded
			pipeline. Each call is structured JSON, executable end-to-end.
		{/snippet}
	</VizPanel>
</div>
