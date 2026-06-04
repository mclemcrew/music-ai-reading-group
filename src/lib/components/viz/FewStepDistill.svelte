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
	const GREY = '#9ca3af';

	let playing = $state(false);
	let progress = $state(1);
	let playStart = 0;
	const PLAY_MS = 4200;

	// two tracks: a many-step teacher and the distilled few-step student
	const TRACKS = [
		{ label: 'flow-matching teacher', steps: 50, color: GREY, y: 0 },
		{ label: 'SA3 distilled + adversarial', steps: 8, color: TEAL, y: 1 }
	];

	// deterministic pseudo-noise so the "noisy" end looks like noise without Math.random
	function noiseAt(i: number): number {
		const s = Math.sin(i * 12.9898) * 43758.5453;
		return (s - Math.floor(s)) * 2 - 1;
	}

	function drawWave(
		ctx: CanvasRenderingContext2D,
		x0: number,
		x1: number,
		cy: number,
		amp: number,
		cleanliness: number,
		color: string,
		alpha: number
	) {
		// cleanliness 0 = pure noise, 1 = smooth tone
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.1;
		ctx.beginPath();
		const N = 48;
		for (let i = 0; i <= N; i++) {
			const t = i / N;
			const x = x0 + (x1 - x0) * t;
			const tone = Math.sin(t * Math.PI * 6) * amp;
			const noise = noiseAt(i + cy) * amp;
			const y = cy + tone * cleanliness + noise * (1 - cleanliness);
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
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

		const padX = canvasPad(w, 18);
		const trackX0 = padX + canvasPad(w, 70);
		const trackX1 = w - padX - canvasPad(w, 56);
		const trackW = trackX1 - trackX0;
		const p = playing ? progress : 1;

		// end labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '500');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillText('noise', trackX0, canvasPad(w, 18));
		ctx.fillText('audio', trackX1, canvasPad(w, 18));

		TRACKS.forEach((tr, ti) => {
			const cy = canvasPad(w, 52) + ti * (h - canvasPad(w, 78)) / 1;
			const cyc = ti === 0 ? canvasPad(w, 60) : h - canvasPad(w, 50);

			// label
			ctx.fillStyle = tr.color === GREY ? CANVAS_LABEL : tr.color;
			ctx.font = canvasFont(w, 10, '600');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText(tr.label, padX, cyc - canvasPad(w, 22));

			// step dots
			const marker = p; // 0..1 along the track
			for (let s = 0; s <= tr.steps; s++) {
				const t = s / tr.steps;
				const x = trackX0 + trackW * t;
				const reached = t <= marker + 1e-6;
				ctx.save();
				ctx.globalAlpha = reached ? 0.9 : 0.25;
				ctx.fillStyle = tr.color;
				ctx.beginPath();
				ctx.arc(x, cyc, tr.steps > 20 ? 1.5 : 3, 0, Math.PI * 2);
				ctx.fill();
				ctx.restore();
			}
			// connecting line
			ctx.save();
			ctx.globalAlpha = 0.3;
			ctx.strokeStyle = tr.color;
			ctx.lineWidth = 0.8;
			ctx.beginPath();
			ctx.moveTo(trackX0, cyc);
			ctx.lineTo(trackX1, cyc);
			ctx.stroke();
			ctx.restore();

			// small waveform thumbnail at the current denoise state
			const cleanliness = marker;
			drawWave(ctx, trackX1 + canvasPad(w, 8), w - padX, cyc, canvasPad(w, 7), cleanliness, tr.color, 0.9);

			// step count badge
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'right';
			ctx.textBaseline = 'middle';
			ctx.fillText(`${tr.steps} steps`, trackX0 - canvasPad(w, 8), cyc);
		});

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillText(
			'both arrive at clean audio — the distilled student takes far fewer network evaluations',
			w / 2,
			h - canvasPad(w, 5)
		);
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
	<VizPanel title="Few-Step Generation" titleColor="var(--teal)">
		{#snippet controls()}
			<VizButton color="var(--teal)" active={playing} onclick={play}>
				{playing ? 'Pause' : 'Denoise'}
			</VizButton>
			<VizButton color="var(--teal)" onclick={showAll}>Show all</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:220px"></canvas>
		{#snippet caption()}
			Diffusion normally needs dozens to hundreds of network passes to walk from noise to a clean
			sample. Stable Audio 3 uses ODE warmup distillation followed by adversarial post-training
			(ARC) so a student model reaches comparable quality in 8 steps — the difference between a
			minutes-long render and under two seconds for six minutes of audio.
		{/snippet}
	</VizPanel>
</div>
