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

	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 5200;
	let progress = $state(0);

	type TokKind = 'user-audio' | 'user-text' | 'cot' | 'gen-text' | 'gen-audio';

	interface Tok {
		kind: TokKind;
		label: string;
	}

	const tokenColor: Record<TokKind, string> = {
		'user-audio': ORANGE,
		'user-text': GREY,
		cot: VIOLET,
		'gen-text': BLUE,
		'gen-audio': TEAL
	};

	const tokenStyle: Record<TokKind, 'solid' | 'dashed'> = {
		'user-audio': 'solid',
		'user-text': 'solid',
		cot: 'dashed',
		'gen-text': 'solid',
		'gen-audio': 'solid'
	};

	const standardSeq: Tok[] = [
		{ kind: 'user-audio', label: '♪' },
		{ kind: 'user-audio', label: '♪' },
		{ kind: 'user-audio', label: '♪' },
		{ kind: 'user-audio', label: '♪' },
		{ kind: 'user-text', label: 'caption?' },
		{ kind: 'gen-text', label: 'A' },
		{ kind: 'gen-text', label: 'door' },
		{ kind: 'gen-text', label: 'creaks' },
		{ kind: 'gen-text', label: 'open' },
		{ kind: 'gen-text', label: '.' }
	];

	const transfusionSeq: Tok[] = [
		{ kind: 'user-text', label: 'tell a' },
		{ kind: 'user-text', label: 'castle' },
		{ kind: 'user-text', label: 'story' },
		{ kind: 'cot', label: '<plan>' },
		{ kind: 'cot', label: 'door' },
		{ kind: 'cot', label: 'first' },
		{ kind: 'cot', label: '</plan>' },
		{ kind: 'gen-audio', label: '♪' },
		{ kind: 'gen-audio', label: '♪' },
		{ kind: 'cot', label: '<plan>' },
		{ kind: 'cot', label: 'wind' },
		{ kind: 'cot', label: 'next' },
		{ kind: 'cot', label: '</plan>' },
		{ kind: 'gen-audio', label: '♪' },
		{ kind: 'gen-audio', label: '♪' },
		{ kind: 'gen-audio', label: '♪' }
	];

	function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

	function drawTok(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		tw: number,
		th: number,
		tok: Tok,
		alpha: number
	) {
		if (alpha < 0.02) return;
		const color = tokenColor[tok.kind];
		const dashed = tokenStyle[tok.kind] === 'dashed';
		ctx.save();
		ctx.globalAlpha = alpha * 0.06;
		ctx.fillStyle = color;
		roundRect(ctx, x, y, tw, th, 3);
		ctx.fill();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1;
		if (dashed) ctx.setLineDash([3, 2]);
		roundRect(ctx, x, y, tw, th, 3);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 9, '500');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(tok.label, x + tw / 2, y + th / 2);
		ctx.restore();
	}

	function drawArrowHead(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		color: string,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.moveTo(x, y - 4);
		ctx.lineTo(x + 7, y);
		ctx.lineTo(x, y + 4);
		ctx.closePath();
		ctx.fill();
		ctx.restore();
	}

	function drawSequence(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		laneW: number,
		seq: Tok[],
		title: string,
		titleColor: string,
		subtitle: string,
		boundaryIdx: number,
		boundaryLabel: string,
		visibleCount: number
	) {
		ctx.fillStyle = titleColor;
		ctx.font = canvasFont(w, 13, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText(title, x, y);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText(subtitle, x, y + 16);

		const laneY = y + 38;
		const laneH = 24;
		const gap = 3;
		const tw = (laneW - gap * (seq.length - 1)) / seq.length;

		seq.forEach((tok, i) => {
			const tx = x + i * (tw + gap);
			const fade = Math.max(0, Math.min(1, visibleCount - i));
			const alpha = 0.12 + 0.88 * fade;
			drawTok(ctx, w, tx, laneY, tw, laneH, tok, alpha);
		});

		const boundaryX = x + boundaryIdx * (tw + gap) - gap / 2;
		ctx.save();
		ctx.strokeStyle = 'rgba(0,0,0,0.18)';
		ctx.lineWidth = 1;
		ctx.setLineDash([3, 3]);
		ctx.beginPath();
		ctx.moveTo(boundaryX, laneY - 6);
		ctx.lineTo(boundaryX, laneY + laneH + 6);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(boundaryLabel, boundaryX, laneY + laneH + 8);
		ctx.restore();

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('input', x, laneY - 14);
		ctx.textAlign = 'right';
		ctx.fillText('generated', x + laneW, laneY - 14);

		const headIdx = Math.min(seq.length, Math.floor(visibleCount));
		if (headIdx > 0 && headIdx <= seq.length) {
			const headX = x + headIdx * (tw + gap) - gap;
			const headY = laneY + laneH / 2;
			if (headIdx > boundaryIdx) {
				drawArrowHead(ctx, headX + 2, headY, titleColor, 1);
			}
		}

		return { laneY, laneH, tw, gap };
	}

	function drawLegend(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number
	) {
		const items: Array<{ label: string; color: string; dashed?: boolean }> = [
			{ label: 'user audio', color: ORANGE },
			{ label: 'user text', color: GREY },
			{ label: 'CoT plan', color: VIOLET, dashed: true },
			{ label: 'gen text', color: BLUE },
			{ label: 'gen audio', color: TEAL }
		];
		ctx.font = canvasFont(w, 9, '500');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		let cx = x;
		items.forEach((it) => {
			ctx.save();
			if (it.dashed) ctx.setLineDash([3, 2]);
			ctx.strokeStyle = it.color;
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.roundRect(cx, y - 6, 14, 12, 2);
			ctx.stroke();
			ctx.setLineDash([]);
			ctx.restore();
			ctx.fillStyle = it.color;
			ctx.fillText(it.label, cx + 18, y);
			cx += 18 + ctx.measureText(it.label).width + 14;
		});
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 12);
		const laneW = w - padX * 2;

		const stdLen = standardSeq.length;
		const tfLen = transfusionSeq.length;
		const visStd = playing ? progress * stdLen : stdLen;
		const visTf = playing ? progress * tfLen : tfLen;

		drawSequence(
			ctx,
			w,
			padX,
			padY,
			laneW,
			standardSeq,
			'Standard audio-LM (LTU / LLark / Music Flamingo / AF-Next)',
			VIOLET,
			'audio prefix → text generation. one modality boundary, fixed direction.',
			5,
			'modality boundary',
			visStd
		);

		const midY = padY + 100;
		drawSequence(
			ctx,
			w,
			padX,
			midY,
			laneW,
			transfusionSeq,
			'Transfusion forcing (AudioChat)',
			ORANGE,
			'no modality boundary. CoT planning interleaved with audio generation, mid-utterance.',
			3,
			'first plan ↔ audio handoff',
			visTf
		);

		const legendY = midY + 110;
		drawLegend(ctx, w, padX, legendY);

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'middle';
		const headStd = Math.min(stdLen, Math.floor(visStd));
		const headTf = Math.min(tfLen, Math.floor(visTf));
		ctx.fillText(`${headStd} / ${stdLen} tokens`, padX + laneW, padY + 38 - 14);
		ctx.fillText(`${headTf} / ${tfLen} tokens`, padX + laneW, midY + 38 - 14);
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
			if (progress >= 1) {
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
		progress = 0;
		playStart = performance.now();
		playing = true;
	}

	function reset() {
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
				if (playing) playing = false;
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
	<VizPanel title="Transfusion Forcing vs. Soft-Prompt Audio LMs" titleColor="var(--orange)">
		{#snippet controls()}
			<VizButton color="var(--orange)" active={playing} onclick={togglePlay}>
				{playing ? 'Pause' : 'Play tokens'}
			</VizButton>
			<VizButton color="var(--orange)" onclick={reset}>Show all</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:300px"></canvas>
		{#snippet caption()}
			Top: every other paper in this post. Audio is a prefix; the LM only generates text.
			Bottom: AudioChat. Audio, text, and CoT planning interleave on the same sequence — the
			LM writes a plan, emits a couple of audio tokens, replans, emits more. The single
			next-token loss covers all of it.
		{/snippet}
	</VizPanel>
</div>
