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
	const GREY = '#9ca3af';

	const PROMPTS = ['warm vintage tape', 'punchy modern drums', 'airy intimate vocals'];
	let promptIdx = $state(0);

	let progress = $state(0);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 4500;

	type Mode = 'regression' | 'free-gen' | 'tool-call';
	const MODES: Mode[] = ['regression', 'free-gen', 'tool-call'];

	const MODE_LABEL: Record<Mode, string> = {
		regression: 'Regression head',
		'free-gen': 'Free generation',
		'tool-call': 'Tool calling'
	};

	const MODE_COLOR: Record<Mode, string> = {
		regression: GREY,
		'free-gen': VIOLET,
		'tool-call': ORANGE
	};

	const MODE_ABOUT: Record<Mode, string> = {
		regression:
			'A learned head emits a parameter vector directly. Fast and machine-readable, but every effect needs its own training and the LLM has to be modified.',
		'free-gen':
			'The frozen LLM emits text like "EQ: 80 Hz +2 dB". You parse it. Easy to set up, but the parser is brittle and the model can drift off-format.',
		'tool-call':
			'Structured JSON conforming to a registered tool schema. Type-safe, composable across many tools, supports chain-of-thought between calls. The LLM2Fx-Tools pivot.'
	};

	// Output strings for each (prompt, mode) combination
	function outputFor(mode: Mode, p: number): string[] {
		if (p === 0) {
			// warm vintage tape
			if (mode === 'regression') return ['[2.5, 0.4, 1.0, -3.5, 0.45, 0.25]'];
			if (mode === 'free-gen')
				return [
					'EQ:',
					'  low shelf 80 Hz +2.5 dB',
					'  high shelf 6 kHz -3.5 dB',
					'Saturation: drive 0.65',
					'Reverb: mix 0.25, plate'
				];
			return [
				'set_eq({',
				'  band: "low_shelf", freq: 80,',
				'  gain: 2.5',
				'})',
				'set_saturation({ drive: 0.65 })',
				'set_reverb({ mix: 0.25 })'
			];
		}
		if (p === 1) {
			// punchy modern drums
			if (mode === 'regression') return ['[3.5, 0.45, -2.0, 2.0, 0.85, 0.20]'];
			if (mode === 'free-gen')
				return [
					'EQ:',
					'  low shelf 80 Hz +3.5 dB',
					'  high shelf 6 kHz +2 dB',
					'Compressor:',
					'  ratio 6:1, attack 5 ms'
				];
			return [
				'set_eq({',
				'  band: "low_shelf", gain: 3.5',
				'})',
				'set_compressor({',
				'  ratio: 6.0, attack_ms: 5',
				'})'
			];
		}
		// airy intimate vocals
		if (mode === 'regression') return ['[-1.5, 0.6, -1.0, 4.5, 0.55, 0.50]'];
		if (mode === 'free-gen')
			return [
				'EQ:',
				'  high shelf 6 kHz +4.5 dB',
				'  low shelf 80 Hz -1.5 dB',
				'Compressor: ratio 3:1',
				'Reverb: plate, mix 0.50'
			];
		return [
			'set_eq({',
			'  band: "high_shelf", gain: 4.5',
			'})',
			'set_compressor({ ratio: 3.0 })',
			'set_reverb({ type: "plate" })'
		];
	}

	function MODE_PROBLEM(mode: Mode): string {
		if (mode === 'regression') return 'tied to a fixed effect set; no CoT';
		if (mode === 'free-gen') return 'string parsing fails on edge cases';
		return 'requires schema design up front';
	}

	function MODE_WIN(mode: Mode): string {
		if (mode === 'regression') return 'fast, machine-readable';
		if (mode === 'free-gen') return 'no fine-tuning needed';
		return 'composable, type-safe, scales';
	}

	function setPrompt(i: number) {
		promptIdx = i;
		progress = 0;
		playStart = performance.now();
		playing = true;
	}

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

	function drawColumn(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		colW: number,
		colH: number,
		mode: Mode,
		p: number,
		visibleChars: number
	) {
		const color = MODE_COLOR[mode];

		// Header
		ctx.save();
		ctx.fillStyle = color;
		ctx.globalAlpha = 0.06;
		ctx.beginPath();
		ctx.roundRect(x, y, colW, colH, 6);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.roundRect(x, y, colW, colH, 6);
		ctx.stroke();
		ctx.restore();

		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 12, '700');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(MODE_LABEL[mode], x + colW / 2, y + 8);

		// What it emits (subtitle)
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText(
			mode === 'regression'
				? 'parameter vector'
				: mode === 'free-gen'
					? 'parseable text'
					: 'JSON tool calls',
			x + colW / 2,
			y + 24
		);

		// Output area
		const outX = x + 10;
		const outY = y + 44;
		const outW = colW - 20;

		const lines = outputFor(mode, p);
		const fullText = lines.join('\n');
		const numChars = Math.floor(visibleChars * fullText.length);
		const visibleText = fullText.slice(0, numChars);
		const visibleLines = visibleText.split('\n');

		// Background "code box"
		ctx.save();
		ctx.fillStyle = '#fff';
		ctx.globalAlpha = 0.6;
		const boxH = colH - 90;
		ctx.beginPath();
		ctx.roundRect(outX, outY, outW, boxH, 4);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = color;
		ctx.globalAlpha = 0.3;
		ctx.lineWidth = 0.8;
		ctx.beginPath();
		ctx.roundRect(outX, outY, outW, boxH, 4);
		ctx.stroke();
		ctx.restore();

		// Body text in a darker color for readability; column color reserved for header + border.
		const bodySize = Math.max(11, Math.round(11 * Math.max(0.85, Math.min(1.15, w / 900))));
		ctx.fillStyle = '#1f1d1b';
		ctx.font = `500 ${bodySize}px ui-monospace, "SF Mono", "Menlo", monospace`;
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		const lineH = bodySize + 4;
		visibleLines.forEach((line, i) => {
			if (outY + 8 + i * lineH < outY + boxH - 4) {
				ctx.fillText(line, outX + 8, outY + 8 + i * lineH);
			}
		});

		// Cursor when streaming
		if (visibleChars < 1 && visibleChars > 0) {
			const lastLine = visibleLines[visibleLines.length - 1] || '';
			const lastY = outY + 8 + (visibleLines.length - 1) * lineH;
			const cursorX = outX + 8 + ctx.measureText(lastLine).width + 1;
			ctx.save();
			ctx.fillStyle = color;
			ctx.globalAlpha = (Math.sin(progress * 30) + 1) / 2;
			ctx.fillRect(cursorX, lastY, 5, lineH - 2);
			ctx.restore();
		}

		// Win/cost footer
		const footerY = y + colH - 32;
		ctx.fillStyle = TEAL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('+ ' + MODE_WIN(mode), outX, footerY);
		ctx.fillStyle = '#c05d16';
		ctx.fillText('− ' + MODE_PROBLEM(mode), outX, footerY + 13);
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

		// Top: prompt
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('same prompt:', padX, padY);

		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 13, '700');
		ctx.fillText(`"${PROMPTS[promptIdx]}"`, padX + 84, padY - 2);

		// Three columns
		const topY = padY + 30;
		const colH = h - topY - padY;
		const gap = 10;
		const colW = (w - padX * 2 - gap * 2) / 3;

		MODES.forEach((m, i) => {
			drawColumn(ctx, w, padX + i * (colW + gap), topY, colW, colH, m, promptIdx, progress);
		});
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
	<VizPanel
		title="Three ways to commit to FX parameters"
		titleColor="var(--orange)"
	>
		{#snippet controls()}
			{#each PROMPTS as p, i}
				<VizButton
					color={ORANGE}
					active={promptIdx === i}
					onclick={() => setPrompt(i)}
				>
					{p}
				</VizButton>
			{/each}
			<VizButton color={ORANGE} active={playing} onclick={play}>Stream</VizButton>
			<VizButton color={ORANGE} onclick={showAll}>Show all</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		<div class="about">
			{#each MODES as m}
				<div class="about-row" style="border-left-color: {MODE_COLOR[m]}">
					<strong style="color: {MODE_COLOR[m]}">{MODE_LABEL[m]}.</strong>
					{MODE_ABOUT[m]}
				</div>
			{/each}
		</div>
		{#snippet caption()}
			Same prompt, three different ways the model could commit to FX parameters. Regression
			needs a learned head and is tied to a fixed effect set. Free generation works with a
			frozen LLM but you have to parse the text. Tool calling is structured by construction —
			and that's the architectural pivot between LLM2Fx (free-generation-style) and
			LLM2Fx-Tools.
		{/snippet}
	</VizPanel>
</div>

<style>
	.about {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.4rem;
		padding: 0.5rem 0.75rem 0;
	}
	.about-row {
		font-size: 0.82rem;
		line-height: 1.45;
		border-left: 2px solid;
		padding-left: 0.6rem;
		color: var(--text);
	}
</style>
