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

	type Mix = 'text' | 'text+audio' | 'text+param' | 'all-three';
	const MIXES: Mix[] = ['text', 'text+audio', 'text+param', 'all-three'];

	const PROMPTS = [
		'warm vintage tape',
		'punchy modern drums',
		'airy and intimate vocals',
		'dark cathedral reverb'
	];

	let promptIdx = $state(0);
	let mix = $state<Mix>('all-three');
	let progress = $state(0);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 3500;

	type Knob = { label: string; value: number };

	// Target knob settings per (mix, prompt). Higher value = more activation.
	function targetKnobs(p: number, m: Mix): Knob[] {
		const base: Knob[][] = [
			// warm vintage tape
			[
				{ label: 'low shelf', value: 0.7 },
				{ label: 'high cut', value: 0.55 },
				{ label: 'sat drive', value: 0.65 },
				{ label: 'comp ratio', value: 0.45 },
				{ label: 'reverb mix', value: 0.25 }
			],
			// punchy modern drums
			[
				{ label: 'low shelf', value: 0.55 },
				{ label: 'high cut', value: 0.2 },
				{ label: 'sat drive', value: 0.35 },
				{ label: 'comp ratio', value: 0.85 },
				{ label: 'reverb mix', value: 0.2 }
			],
			// airy intimate vocals
			[
				{ label: 'low shelf', value: 0.3 },
				{ label: 'high cut', value: 0.15 },
				{ label: 'sat drive', value: 0.25 },
				{ label: 'comp ratio', value: 0.55 },
				{ label: 'reverb mix', value: 0.5 }
			],
			// cathedral reverb
			[
				{ label: 'low shelf', value: 0.35 },
				{ label: 'high cut', value: 0.4 },
				{ label: 'sat drive', value: 0.2 },
				{ label: 'comp ratio', value: 0.3 },
				{ label: 'reverb mix', value: 0.92 }
			]
		];
		const noisy = base[p].map((k) => ({ ...k }));
		// "text only" produces a noisier estimate
		if (m === 'text') {
			return noisy.map((k, i) => ({
				...k,
				value: Math.min(1, Math.max(0, k.value + (((i * 17) % 30) - 15) / 100))
			}));
		}
		if (m === 'text+audio') {
			return noisy.map((k, i) => ({
				...k,
				value: Math.min(1, Math.max(0, k.value + (((i * 11) % 20) - 10) / 100))
			}));
		}
		if (m === 'text+param') {
			return noisy.map((k, i) => ({
				...k,
				value: Math.min(1, Math.max(0, k.value + (((i * 7) % 14) - 7) / 100))
			}));
		}
		return noisy; // all-three: cleanest
	}

	let knobValues = [0.5, 0.5, 0.5, 0.5, 0.5];

	function updateTargets() {
		const target = targetKnobs(promptIdx, mix);
		// Lerp slowly toward target — handled in tick.
		(window as any).__fxKnobTarget = target.map((k) => k.value);
	}

	function setPrompt(i: number) {
		promptIdx = i;
		updateTargets();
	}

	function setMix(m: Mix) {
		mix = m;
		updateTargets();
	}

	function play() {
		progress = 0;
		playStart = performance.now();
		playing = true;
	}

	function drawTokenLine(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		laneW: number,
		text: string,
		color: string
	) {
		// Render text token-by-token in a soft box
		const words = text.split(' ');
		const gap = 6;
		const tokH = 22;
		ctx.font = canvasFont(w, 11, '500');
		const widths = words.map((wd) => ctx.measureText(wd).width + 16);
		const totalW = widths.reduce((a, b) => a + b, 0) + gap * (words.length - 1);
		const scale = Math.min(1, laneW / totalW);
		let cx = x;
		words.forEach((wd, i) => {
			const tw = widths[i] * scale;
			ctx.save();
			ctx.globalAlpha = 0.08;
			ctx.fillStyle = color;
			ctx.beginPath();
			ctx.roundRect(cx, y, tw, tokH, 3);
			ctx.fill();
			ctx.globalAlpha = 1;
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.roundRect(cx, y, tw, tokH, 3);
			ctx.stroke();
			ctx.restore();
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 11, '500');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(wd, cx + tw / 2, y + tokH / 2);
			cx += tw + gap * scale;
		});
	}

	function drawICEPanel(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		title: string,
		color: string,
		active: boolean,
		drawIcon: (cx: number, cy: number) => void
	) {
		ctx.save();
		ctx.globalAlpha = active ? 1 : 0.35;
		ctx.fillStyle = color;
		ctx.globalAlpha = active ? 0.06 : 0.02;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.fill();
		ctx.globalAlpha = active ? 1 : 0.4;
		ctx.strokeStyle = color;
		ctx.lineWidth = active ? 1.4 : 1;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(title, x + 10, y + hh / 2);
		drawIcon(x + ww / 2, y + hh / 2);
		ctx.restore();
	}

	function drawKnob(
		ctx: CanvasRenderingContext2D,
		w: number,
		cx: number,
		cy: number,
		r: number,
		value: number,
		label: string,
		active: boolean
	) {
		// Outer ring
		ctx.save();
		ctx.strokeStyle = active ? ORANGE : GREY;
		ctx.globalAlpha = active ? 0.4 : 0.25;
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.arc(cx, cy, r, Math.PI * 0.75, Math.PI * 2.25);
		ctx.stroke();
		// Active arc
		ctx.globalAlpha = 1;
		ctx.strokeStyle = active ? ORANGE : VIOLET;
		ctx.lineWidth = 2.4;
		const start = Math.PI * 0.75;
		const end = start + value * Math.PI * 1.5;
		ctx.beginPath();
		ctx.arc(cx, cy, r, start, end);
		ctx.stroke();
		// Indicator from centre out to 85% radius. Sweeps the upper 270° only.
		const angle = end;
		ctx.beginPath();
		ctx.moveTo(cx, cy);
		ctx.lineTo(cx + Math.cos(angle) * r * 0.85, cy + Math.sin(angle) * r * 0.85);
		ctx.lineWidth = 1.6;
		ctx.stroke();
		ctx.restore();
		// Value reading sits in the open bottom-inside of the knob, where the arc + indicator don't reach.
		ctx.fillStyle = active ? ORANGE : GREY;
		ctx.font = canvasFont(w, 13, '700');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(value.toFixed(2), cx, cy + r * 0.42);
		// Param label below the knob.
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textBaseline = 'top';
		ctx.fillText(label, cx, cy + r + 6);
	}

	function drawArrow(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y1: number,
		x2: number,
		y2: number,
		color: string,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.fillStyle = color;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.moveTo(x1, y1);
		ctx.lineTo(x2, y2);
		ctx.stroke();
		const ang = Math.atan2(y2 - y1, x2 - x1);
		ctx.beginPath();
		ctx.moveTo(x2, y2);
		ctx.lineTo(x2 - 6 * Math.cos(ang - Math.PI / 6), y2 - 6 * Math.sin(ang - Math.PI / 6));
		ctx.lineTo(x2 - 6 * Math.cos(ang + Math.PI / 6), y2 - 6 * Math.sin(ang + Math.PI / 6));
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

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 14);

		// Top: prompt
		const promptY = padY;
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('prompt', padX, promptY);
		drawTokenLine(ctx, w, padX, promptY + 14, w - padX * 2, PROMPTS[promptIdx], BLUE);

		// Middle: in-context example bank (3 panels stacked vertically) + LLM box on the right.
		const midY = promptY + 50;
		const panelH = 90;
		const lmY = midY;
		const lmW = 130;
		const lmX = w - padX - lmW;

		const iceX0 = padX;
		const iceW = lmX - padX - 18; // full width minus gap to LLM box
		const iceGap = 4;
		const iceH = (panelH - iceGap * 2) / 3;
		const iceUsed = {
			text: mix === 'text' || mix === 'text+audio' || mix === 'text+param' || mix === 'all-three',
			audio: mix === 'text+audio' || mix === 'all-three',
			param: mix === 'text+param' || mix === 'all-three'
		};

		const iceY0 = lmY;
		const iceY1 = lmY + iceH + iceGap;
		const iceY2 = lmY + (iceH + iceGap) * 2;

		drawICEPanel(
			ctx,
			w,
			iceX0,
			iceY0,
			iceW,
			iceH,
			'textual',
			BLUE,
			iceUsed.text,
			(cx, cy) => {
				ctx.fillStyle = BLUE;
				ctx.font = canvasFont(w, 10);
				ctx.textAlign = 'left';
				ctx.textBaseline = 'middle';
				ctx.fillText('"warm" → +low shelf, "airy" → +high shelf', iceX0 + 70, cy);
			}
		);
		drawICEPanel(
			ctx,
			w,
			iceX0,
			iceY1,
			iceW,
			iceH,
			'audio',
			TEAL,
			iceUsed.audio,
			(cx, cy) => {
				// Inline waveform aligned to the right of the title
				ctx.save();
				ctx.strokeStyle = TEAL;
				ctx.lineWidth = 1;
				ctx.globalAlpha = 0.85;
				ctx.beginPath();
				const wfX = iceX0 + 70;
				const wfW = iceW - 90;
				for (let i = 0; i < wfW; i += 1) {
					const t = (i / wfW) * 2 - 1;
					const y = cy + Math.sin(i * 0.4) * 5 * Math.exp(-Math.abs(t) * 1.2);
					if (i === 0) ctx.moveTo(wfX + i, y);
					else ctx.lineTo(wfX + i, y);
				}
				ctx.stroke();
				ctx.restore();
			}
		);
		drawICEPanel(
			ctx,
			w,
			iceX0,
			iceY2,
			iceW,
			iceH,
			'parametric',
			ORANGE,
			iceUsed.param,
			(cx, cy) => {
				ctx.fillStyle = ORANGE;
				ctx.font = canvasFont(w, 10);
				ctx.textAlign = 'left';
				ctx.textBaseline = 'middle';
				ctx.fillText('ratio: 3:1, shelf: +2 dB, decay: 1.4 s', iceX0 + 70, cy);
			}
		);

		// LLM box (full height of the ICE stack)
		ctx.save();
		ctx.fillStyle = VIOLET;
		ctx.globalAlpha = 0.06;
		ctx.beginPath();
		ctx.roundRect(lmX, lmY, lmW, panelH, 6);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = VIOLET;
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.roundRect(lmX, lmY, lmW, panelH, 6);
		ctx.stroke();
		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 13, 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText('frozen LLM', lmX + lmW / 2, lmY + panelH / 2 - 8);
		ctx.font = canvasFont(w, 10);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.fillText('one forward pass', lmX + lmW / 2, lmY + panelH / 2 + 12);
		ctx.restore();

		// Arrows from each ICE row → LLM left edge, at that row's vertical centre.
		const arrowAlpha = Math.max(0.25, progress);
		const iceRows = [
			{ used: iceUsed.text, y: iceY0 + iceH / 2, color: BLUE },
			{ used: iceUsed.audio, y: iceY1 + iceH / 2, color: TEAL },
			{ used: iceUsed.param, y: iceY2 + iceH / 2, color: ORANGE }
		];
		iceRows.forEach((row) => {
			if (!row.used) return;
			drawArrow(ctx, iceX0 + iceW + 2, row.y, lmX - 4, row.y, row.color, arrowAlpha * 0.6);
		});

		// Arrow from prompt down into LLM
		drawArrow(
			ctx,
			lmX + lmW / 2,
			promptY + 36,
			lmX + lmW / 2,
			lmY,
			BLUE,
			arrowAlpha * 0.75
		);

		// Bottom: knob row
		const knobY = lmY + panelH + 60;
		const knobR = Math.min(28, (w - padX * 2) / 14);
		const labels = ['low shelf', 'high cut', 'sat drive', 'comp ratio', 'reverb mix'];
		const slotW = (w - padX * 2) / labels.length;
		labels.forEach((lab, i) => {
			const cx = padX + slotW * (i + 0.5);
			const v = knobValues[i];
			const active = playing ? progress > i * 0.18 : true;
			drawKnob(ctx, w, cx, knobY, knobR, v, lab, active);
		});

		// Output arrow from LLM down to knobs
		drawArrow(
			ctx,
			lmX + lmW / 2,
			lmY + panelH + 2,
			lmX + lmW / 2,
			knobY - knobR - 6,
			VIOLET,
			arrowAlpha * 0.6
		);

		// Output label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('predicted parameters', w / 2, knobY + knobR + 22);
	}

	function tick(ts: number) {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		const target = (window as any).__fxKnobTarget as number[] | undefined;
		if (target) {
			let needs = false;
			for (let i = 0; i < knobValues.length; i++) {
				const dx = target[i] - knobValues[i];
				if (Math.abs(dx) > 0.003) {
					knobValues[i] += dx * 0.12;
					needs = true;
				}
			}
			if (needs) draw();
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
		updateTargets();
		// Snap initial values
		const target = (window as any).__fxKnobTarget as number[];
		for (let i = 0; i < knobValues.length; i++) knobValues[i] = target[i];
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

	$effect(() => {
		promptIdx;
		mix;
		updateTargets();
	});
</script>

<div bind:this={container}>
	<VizPanel title="LLM2Fx: prompt → parameters with in-context examples" titleColor="var(--orange)">
		{#snippet controls()}
			{#each PROMPTS as p, i}
				<VizButton color="var(--blue)" active={promptIdx === i} onclick={() => setPrompt(i)}>
					{p}
				</VizButton>
			{/each}
			<VizButton color="var(--orange)" onclick={play}>Play</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		<div class="mix-row">
			<span class="mix-label">in-context bank:</span>
			{#each MIXES as m}
				<VizButton color="var(--orange)" active={mix === m} onclick={() => setMix(m)}>
					{m}
				</VizButton>
			{/each}
		</div>
		{#snippet caption()}
			A frozen LLM emits a parameter vector from a text prompt. Each of the three in-context
			banks contributes a different prior — textual examples teach descriptor → param mappings,
			audio examples ground descriptors in acoustic features, parametric examples calibrate
			numerical scale. The combined "all-three" setup is what closes the gap to optimization
			baselines.
		{/snippet}
	</VizPanel>
</div>

<style>
	.mix-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.75rem 0;
	}
	.mix-label {
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--text-muted);
		font-weight: 600;
	}
</style>
