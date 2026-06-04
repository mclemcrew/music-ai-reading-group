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

	// false = fixed-length (always allocate Lmax), true = variable-length (L ∝ duration)
	let variable = $state(false);
	// animation progress between the two modes, 0 = fixed, 1 = variable
	let morph = $state(0);
	let target = 0;

	// requested durations (seconds), and the model's max
	const DURATIONS = [9, 35, 100, 120];
	const LMAX = 120;

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 18);
		const padTop = canvasPad(w, 30);
		const labelW = canvasPad(w, 44);
		const trackX = padX + labelW;
		const trackW = w - trackX - padX;
		const rowH = (h - padTop - canvasPad(w, 34)) / DURATIONS.length;
		const barH = Math.min(26, rowH * 0.52);

		// header
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText('request', padX, padTop - canvasPad(w, 14));
		ctx.textAlign = 'right';
		const headColor = morph > 0.5 ? TEAL : ORANGE;
		ctx.fillStyle = headColor;
		ctx.fillText(
			morph > 0.5 ? 'variable: allocate L ∝ duration' : 'fixed: always allocate Lmax',
			trackX + trackW,
			padTop - canvasPad(w, 14)
		);

		DURATIONS.forEach((d, i) => {
			const cy = padTop + rowH * i + rowH / 2;
			// row label
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10, '500');
			ctx.textAlign = 'right';
			ctx.textBaseline = 'middle';
			ctx.fillText(`${d}s`, trackX - canvasPad(w, 8), cy);

			const audioFrac = d / LMAX;
			// in fixed mode the allocated compute is always full width;
			// in variable mode it shrinks to the audio fraction.
			const allocFrac = 1 - morph * (1 - audioFrac);
			const allocW = trackW * allocFrac;
			const audioW = trackW * audioFrac;

			// allocated-but-silent region (the wasted compute) — hatched, only visible in fixed mode
			const padFrac = Math.max(0, allocFrac - audioFrac);
			if (padFrac > 0.001) {
				const sx = trackX + audioW;
				const sw = allocW - audioW;
				ctx.save();
				ctx.globalAlpha = 0.5 * (1 - morph);
				// hatch
				ctx.strokeStyle = GREY;
				ctx.lineWidth = 0.6;
				ctx.beginPath();
				ctx.rect(sx, cy - barH / 2, sw, barH);
				ctx.clip();
				for (let x = sx - barH; x < sx + sw; x += 5) {
					ctx.moveTo(x, cy + barH / 2);
					ctx.lineTo(x + barH, cy - barH / 2);
				}
				ctx.stroke();
				ctx.restore();
				ctx.save();
				ctx.globalAlpha = 0.55 * (1 - morph);
				ctx.strokeStyle = GREY;
				ctx.lineWidth = 1;
				ctx.strokeRect(sx, cy - barH / 2, sw, barH);
				ctx.restore();
			}

			// audio (real content) region
			const col = morph > 0.5 ? TEAL : ORANGE;
			ctx.save();
			ctx.globalAlpha = 0.08;
			ctx.fillStyle = col;
			ctx.fillRect(trackX, cy - barH / 2, audioW, barH);
			ctx.globalAlpha = 1;
			ctx.strokeStyle = col;
			ctx.lineWidth = 1.4;
			ctx.strokeRect(trackX, cy - barH / 2, audioW, barH);
			ctx.restore();
		});

		// caption strip
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'bottom';
		const wasted = Math.round((1 - DURATIONS.reduce((a, d) => a + d / LMAX, 0) / DURATIONS.length) * 100);
		ctx.fillText(
			morph > 0.5
				? 'latent length tracks the request — short clips cost short compute'
				: `~${wasted}% of compute spent denoising zero-padded silence (hatched)`,
			padX,
			h - canvasPad(w, 6)
		);
	}

	function tick() {
		if (running) {
			if (Math.abs(morph - target) > 0.001) {
				morph += (target - morph) * 0.12;
				draw();
			}
		}
		raf = requestAnimationFrame(tick);
	}

	function toggle() {
		variable = !variable;
		target = variable ? 1 : 0;
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
	<VizPanel title="Fixed- vs Variable-Length Generation" titleColor="var(--teal)">
		{#snippet controls()}
			<VizButton color="var(--teal)" active={variable} onclick={toggle}>
				{variable ? 'Variable-length' : 'Fixed-length'}
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:240px"></canvas>
		{#snippet caption()}
			Diffusion models normally denoise a fixed-size tensor, so a 9-second clip from a model
			that can do 120s still pays to denoise 120s of mostly silence. Stable Audio 3 allocates a
			latent sequence whose length is proportional to the requested duration, so short outputs
			cost short compute. Toggle to compare. (After SA3 Figure 2.)
		{/snippet}
	</VizPanel>
</div>
