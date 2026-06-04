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
	let activeStage = $state(-1);
	let playing = $state(false);
	let startTime = 0;
	let inputMode = $state<'text' | 'voice' | 'hum'>('text');

	const STAGE_MS = 1100;
	const NUM_STAGES = 6;

	const TEAL = '#1a9e8f';
	const ORANGE = '#e07020';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const GREY = '#9ca3af';

	const REQUEST_BY_MODE: Record<typeof inputMode, string> = {
		text: '"warm the vocals"',
		voice: '🎙  "warm the vocals"',
		hum: '♪  hummed riff'
	};

	const TOOL_BY_MODE: Record<typeof inputMode, { name: string; color: string; detail: string }> = {
		text: { name: 'fx_param', color: TEAL, detail: 'low_shelf +2 dB → slider 0.62' },
		voice: { name: 'fx_param', color: TEAL, detail: 'low_shelf +2 dB → slider 0.62' },
		hum: { name: 'BasicPitch', color: ORANGE, detail: 'WAV → MIDI → new track' }
	};

	const SCRIPT_BY_MODE: Record<typeof inputMode, string> = {
		text: 'reaper.TrackFX_SetParam(t,0,5,0.62)',
		voice: 'reaper.TrackFX_SetParam(t,0,5,0.62)',
		hum: 'reaper.InsertTrackAtIndex(-1, true)'
	};

	function roundedRect(
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

	function drawBlock(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		color: string,
		label: string,
		sublabel: string,
		active: boolean,
		canvasW: number
	) {
		const a = active ? 1 : 0.55;
		if (active) {
			ctx.shadowColor = color;
			ctx.shadowBlur = 12;
		}
		ctx.fillStyle = color + (active ? '14' : '08');
		roundedRect(ctx, x, y, w, h, 8);
		ctx.fill();
		ctx.strokeStyle = color;
		ctx.globalAlpha = a;
		ctx.lineWidth = active ? 1.8 : 1;
		roundedRect(ctx, x, y, w, h, 8);
		ctx.stroke();
		ctx.globalAlpha = 1;
		ctx.shadowBlur = 0;

		ctx.fillStyle = active ? color : color + 'aa';
		ctx.font = canvasFont(canvasW, 13, active ? 'bold' : 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, x + w / 2, y + h / 2 - 7);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(canvasW, 11);
		ctx.fillText(sublabel, x + w / 2, y + h / 2 + 10);
	}

	function drawArrow(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y: number,
		x2: number,
		active: boolean
	) {
		ctx.strokeStyle = active ? '#333' : 'rgba(0,0,0,0.22)';
		ctx.lineWidth = active ? 1.4 : 1;
		ctx.beginPath();
		ctx.moveTo(x1, y);
		ctx.lineTo(x2 - 5, y);
		ctx.stroke();
		ctx.beginPath();
		ctx.moveTo(x2, y);
		ctx.lineTo(x2 - 6, y - 3);
		ctx.lineTo(x2 - 6, y + 3);
		ctx.closePath();
		ctx.fillStyle = active ? '#333' : 'rgba(0,0,0,0.22)';
		ctx.fill();
	}

	function drawUndoCurl(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		active: boolean,
		canvasW: number
	) {
		ctx.strokeStyle = active ? VIOLET : VIOLET + '66';
		ctx.lineWidth = active ? 1.4 : 1;
		ctx.beginPath();
		ctx.arc(x, y, 10, Math.PI * 0.25, Math.PI * 1.6);
		ctx.stroke();
		// arrowhead
		const ax = x + 10 * Math.cos(Math.PI * 1.6);
		const ay = y + 10 * Math.sin(Math.PI * 1.6);
		ctx.beginPath();
		ctx.moveTo(ax, ay);
		ctx.lineTo(ax - 4, ay - 1);
		ctx.lineTo(ax - 2, ay + 4);
		ctx.closePath();
		ctx.fillStyle = active ? VIOLET : VIOLET + '66';
		ctx.fill();
		ctx.fillStyle = active ? VIOLET : VIOLET + '99';
		ctx.font = canvasFont(canvasW, 11, active ? 'bold' : 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('undo', x, y + 16);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 18);

		// Three layer bands (subtle backgrounds)
		const bandH = (h - padY * 2) / 3;
		const bandLabels = ['User Interaction', 'Processing', 'Execution'];
		const bandColors = [TEAL, ORANGE, BLUE];
		for (let i = 0; i < 3; i++) {
			const y = padY + i * bandH;
			ctx.fillStyle = bandColors[i] + '06';
			ctx.fillRect(padX, y, w - padX * 2, bandH - 4);
			ctx.fillStyle = bandColors[i];
			ctx.font = canvasFont(w, 13, 'bold');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'top';
			ctx.fillText(bandLabels[i], padX + 8, y + 6);
		}

		const blockW = (w - padX * 2) * 0.24;
		const blockH = 52;

		// Stage 0: Input pill (top band)
		const topY = padY + bandH / 2;
		const inputX = padX + (w - padX * 2) * 0.15 - blockW / 2;
		const inputLabel =
			inputMode === 'text' ? 'Text' : inputMode === 'voice' ? 'Whisper' : 'BasicPitch';
		const inputSub = REQUEST_BY_MODE[inputMode];
		drawBlock(
			ctx,
			inputX,
			topY - blockH / 2,
			blockW,
			blockH,
			TEAL,
			inputLabel,
			inputSub,
			activeStage === 0,
			w
		);

		// Stage 1: Electron gateway (top band, right)
		const gatewayX = padX + (w - padX * 2) * 0.6 - blockW / 2;
		drawBlock(
			ctx,
			gatewayX,
			topY - blockH / 2,
			blockW,
			blockH,
			TEAL,
			'Electron Gateway',
			'route to LLM',
			activeStage === 1,
			w
		);

		// Arrow stage 0 → 1
		drawArrow(ctx, inputX + blockW + 4, topY, gatewayX - 4, activeStage >= 1);

		// Stage 2: LLM (middle band)
		const midY = padY + bandH + bandH / 2;
		const llmX = padX + (w - padX * 2) * 0.15 - blockW / 2;
		drawBlock(
			ctx,
			llmX,
			midY - blockH / 2,
			blockW,
			blockH,
			ORANGE,
			'GPT-5',
			'plan + tool call',
			activeStage === 2,
			w
		);

		// Arrow stage 1 → 2 (down + left)
		if (activeStage >= 2) {
			ctx.strokeStyle = '#333';
			ctx.lineWidth = 1.4;
			ctx.beginPath();
			ctx.moveTo(gatewayX + blockW / 2, topY + blockH / 2);
			ctx.lineTo(gatewayX + blockW / 2, midY - blockH / 2 - 6);
			ctx.lineTo(llmX + blockW / 2 + 6, midY - blockH / 2 - 6);
			ctx.stroke();
			drawArrow(ctx, llmX + blockW / 2 + 6, midY - blockH / 2 - 4, llmX + blockW / 2, true);
		}

		// Stage 3: MCP tool block (middle band, right)
		const toolX = padX + (w - padX * 2) * 0.6 - blockW / 2;
		const tool = TOOL_BY_MODE[inputMode];
		drawBlock(
			ctx,
			toolX,
			midY - blockH / 2,
			blockW,
			blockH,
			tool.color,
			tool.name,
			tool.detail,
			activeStage === 3,
			w
		);

		// Arrow stage 2 → 3
		drawArrow(ctx, llmX + blockW + 4, midY, toolX - 4, activeStage >= 3);

		// Stage 4: ReaScript pill (bottom band)
		const botY = padY + bandH * 2 + bandH / 2;
		const scriptX = padX + (w - padX * 2) * 0.15 - blockW / 2;
		drawBlock(
			ctx,
			scriptX,
			botY - blockH / 2,
			blockW,
			blockH,
			BLUE,
			'ReaScript',
			SCRIPT_BY_MODE[inputMode],
			activeStage === 4,
			w
		);

		// Arrow stage 3 → 4 (down)
		if (activeStage >= 4) {
			ctx.strokeStyle = '#333';
			ctx.lineWidth = 1.4;
			ctx.beginPath();
			ctx.moveTo(toolX + blockW / 2, midY + blockH / 2);
			ctx.lineTo(toolX + blockW / 2, botY - blockH / 2 - 6);
			ctx.lineTo(scriptX + blockW / 2 + 6, botY - blockH / 2 - 6);
			ctx.stroke();
			drawArrow(ctx, scriptX + blockW / 2 + 6, botY - blockH / 2 - 4, scriptX + blockW / 2, true);
		}

		// Stage 5: REAPER state (bottom band, right)
		const reaperX = padX + (w - padX * 2) * 0.6 - blockW / 2;
		drawBlock(
			ctx,
			reaperX,
			botY - blockH / 2,
			blockW,
			blockH,
			BLUE,
			'REAPER',
			'project state',
			activeStage === 5,
			w
		);

		// Arrow stage 4 → 5
		drawArrow(ctx, scriptX + blockW + 4, botY, reaperX - 4, activeStage >= 5);

		// Undo curl above REAPER (always faintly visible, glows at stage 5)
		drawUndoCurl(ctx, reaperX + blockW + 18, botY - 4, activeStage >= 5, w);
	}

	function tick() {
		if (!running) return;
		if (playing) {
			const elapsed = performance.now() - startTime;
			const newStage = Math.floor(elapsed / STAGE_MS);
			if (newStage >= NUM_STAGES) {
				activeStage = NUM_STAGES - 1;
				playing = false;
				draw();
				return;
			}
			activeStage = newStage;
			draw();
			raf = requestAnimationFrame(tick);
		}
	}

	function togglePlay() {
		if (playing) {
			playing = false;
			cancelAnimationFrame(raf);
			draw();
		} else {
			if (activeStage >= NUM_STAGES - 1) activeStage = -1;
			startTime = performance.now() - Math.max(0, activeStage) * STAGE_MS;
			playing = true;
			tick();
		}
	}

	function reset() {
		playing = false;
		activeStage = -1;
		cancelAnimationFrame(raf);
		draw();
	}

	function setMode(m: typeof inputMode) {
		inputMode = m;
		draw();
	}

	$effect(() => {
		// keep canvas in sync when activeStage updates outside tick (mode toggle)
		void inputMode;
		void activeStage;
		draw();
	});

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {},
			() => {
				if (playing) {
					playing = false;
					cancelAnimationFrame(raf);
				}
			}
		);
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			obs.disconnect();
			window.removeEventListener('resize', onResize);
			running = false;
			cancelAnimationFrame(raf);
		};
	});
</script>

<div bind:this={container}>
	<VizPanel title="DAWZY Pipeline · End-to-End" titleColor="var(--teal)">
		{#snippet controls()}
			<div class="mode-row">
				<VizButton color="var(--teal)" active={inputMode === 'text'} onclick={() => setMode('text')}>
					Text
				</VizButton>
				<VizButton color="var(--teal)" active={inputMode === 'voice'} onclick={() => setMode('voice')}>
					Voice
				</VizButton>
				<VizButton color="var(--teal)" active={inputMode === 'hum'} onclick={() => setMode('hum')}>
					Hum
				</VizButton>
			</div>
			<VizButton color="var(--orange)" active={playing} onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--orange)" onclick={reset}>Reset</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:360px"></canvas>
		{#snippet caption()}
			Switch the input modality and replay. Notice that the user's intent travels through
			<em>two</em> deterministic boundaries (Whisper or BasicPitch on the way in,
			ReaScript on the way out) and only one probabilistic one (the LLM). The reversible
			undo curl is the safety net for that single probabilistic hop.
		{/snippet}
	</VizPanel>
</div>

<style>
	.mode-row {
		display: flex;
		gap: 0.4rem;
		padding-right: 0.5rem;
		border-right: 1px solid var(--border);
		margin-right: 0.25rem;
	}
</style>
