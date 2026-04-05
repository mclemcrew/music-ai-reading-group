<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, observeVisibility, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let visible = false;
	let running = true;
	let activeLevels = $state(1);
	let currentLevels = 1; // smoothly lerps toward activeLevels
	let raf = 0;

	// Audio state
	let playingOriginal = $state(false);
	let playingRecon = $state(false);
	let originalAudio: HTMLAudioElement | null = null;
	let reconAudio: HTMLAudioElement | null = null;
	let loadedReconLevel = 0;

	const NUM_CODEBOOKS = 9;
	const TIME_STEPS = 12;

	// Color per codebook level tier
	const tierColor = (i: number): string => {
		if (i === 0) return '#e07020';
		if (i <= 3) return '#1a9e8f';
		if (i <= 6) return '#7c4dff';
		return '#2979ff';
	};

	// Pre-generate deterministic token "values" for visual variety
	const tokenSeeds: number[][] = [];
	for (let r = 0; r < NUM_CODEBOOKS; r++) {
		tokenSeeds[r] = [];
		for (let c = 0; c < TIME_STEPS; c++) {
			tokenSeeds[r][c] = ((r * 17 + c * 31 + 7) % 100) / 100;
		}
	}

	function lerp(a: number, b: number, t: number): number {
		return a + (b - a) * t;
	}

	function rowActivation(row: number): number {
		return Math.max(0, Math.min(1, currentLevels - row));
	}

	function lerpColor(hex1: string, hex2: string, t: number): string {
		const r1 = parseInt(hex1.slice(1, 3), 16);
		const g1 = parseInt(hex1.slice(3, 5), 16);
		const b1 = parseInt(hex1.slice(5, 7), 16);
		const r2 = parseInt(hex2.slice(1, 3), 16);
		const g2 = parseInt(hex2.slice(3, 5), 16);
		const b2 = parseInt(hex2.slice(5, 7), 16);
		const r = Math.round(lerp(r1, r2, t));
		const g = Math.round(lerp(g1, g2, t));
		const b = Math.round(lerp(b1, b2, t));
		return `rgb(${r},${g},${b})`;
	}

	// --- Audio controls ---
	function reconSrc(level: number): string {
		const n = String(level).padStart(2, '0');
		return `${base}/audio/dac_codec_${n}.wav`;
	}

	function toggleOriginal() {
		if (!originalAudio) return;
		if (playingOriginal) {
			originalAudio.pause();
			playingOriginal = false;
		} else {
			// Stop reconstructed if playing
			if (reconAudio && playingRecon) {
				reconAudio.pause();
				playingRecon = false;
			}
			originalAudio.currentTime = 0;
			originalAudio.play();
			playingOriginal = true;
		}
	}

	function toggleRecon() {
		// Load correct file for current level
		const level = activeLevels;
		if (!reconAudio) return;

		if (playingRecon && loadedReconLevel === level) {
			reconAudio.pause();
			playingRecon = false;
			return;
		}

		// Stop original if playing
		if (originalAudio && playingOriginal) {
			originalAudio.pause();
			playingOriginal = false;
		}

		// Switch source if level changed
		if (loadedReconLevel !== level) {
			reconAudio.src = reconSrc(level);
			loadedReconLevel = level;
		}

		reconAudio.currentTime = 0;
		reconAudio.play();
		playingRecon = true;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = canvasPad(w, 10);
		const padR = canvasPad(w, 10);
		const padT = canvasPad(w, 8);
		const padB = canvasPad(w, 24);

		// === Layout regions ===
		const waveW = 70;
		const gridL = padL + waveW + 20;
		const gridR = w - padR - waveW - 20;
		const gridW = gridR - gridL;
		const gridT = padT;
		const gridH = h - padT - padB;
		const recoL = gridR + 20;

		// === Input waveform (left) ===
		ctx.strokeStyle = playingOriginal ? '#1a9e8f' : '#9ca3af';
		ctx.lineWidth = playingOriginal ? 2 : 1.5;
		ctx.beginPath();
		const wCx = padL + waveW / 2;
		const wCy = padT + gridH / 2;
		const wAmp = gridH * 0.35;
		for (let i = 0; i <= 60; i++) {
			const t = i / 60;
			const x = padL + t * waveW;
			const y = wCy + Math.sin(t * Math.PI * 6) * wAmp * (1 - 0.3 * Math.sin(t * Math.PI * 2));
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		ctx.fillText('input', wCx, h - 6);

		// === Arrow: input → grid ===
		const arrowY = wCy;
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.moveTo(padL + waveW + 4, arrowY);
		ctx.lineTo(gridL - 6, arrowY);
		ctx.stroke();
		ctx.fillStyle = '#dde0e6';
		ctx.beginPath();
		ctx.moveTo(gridL - 6, arrowY - 3);
		ctx.lineTo(gridL - 1, arrowY);
		ctx.lineTo(gridL - 6, arrowY + 3);
		ctx.fill();

		// === Codebook grid (center) ===
		const rowH = gridH / NUM_CODEBOOKS;
		const cellW = gridW / TIME_STEPS;
		const cellPad = 1.5;
		const inactiveStroke = '#e5e7eb';

		for (let r = 0; r < NUM_CODEBOOKS; r++) {
			const y = gridT + r * rowH;
			const activation = rowActivation(r);
			const color = tierColor(r);

			ctx.fillStyle = lerpColor('#d1d5db', color, activation);
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'right';
			ctx.fillText(`c${r}`, gridL - 4, y + rowH / 2 + 3);

			for (let c = 0; c < TIME_STEPS; c++) {
				const cx = gridL + c * cellW + cellPad;
				const cy = y + cellPad;
				const cw = cellW - cellPad * 2;
				const ch = rowH - cellPad * 2;
				const radius = 2;

				const inactiveAlpha = 1 - activation;
				if (inactiveAlpha > 0.01) {
					ctx.globalAlpha = inactiveAlpha;
					ctx.strokeStyle = inactiveStroke;
					ctx.lineWidth = 0.8;
					ctx.setLineDash([2, 2]);
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.stroke();
					ctx.setLineDash([]);
					ctx.globalAlpha = 1;
				}

				if (activation > 0.01) {
					const seed = tokenSeeds[r][c];
					const shade = 0.3 + seed * 0.5;

					ctx.globalAlpha = shade * activation;
					ctx.fillStyle = color;
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.fill();

					ctx.globalAlpha = activation;
					ctx.strokeStyle = color;
					ctx.lineWidth = 1;
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.stroke();
					ctx.globalAlpha = 1;
				}
			}

			if (r < NUM_CODEBOOKS - 1) {
				const nextActivation = rowActivation(r + 1);
				const plusAlpha = Math.min(activation, nextActivation);
				if (plusAlpha > 0.05) {
					ctx.globalAlpha = plusAlpha;
					ctx.fillStyle = CANVAS_LABEL;
					ctx.font = canvasFont(w, 10);
					ctx.textAlign = 'center';
					ctx.fillText('+', gridL + gridW + 8, y + rowH + 2);
					ctx.globalAlpha = 1;
				}
			}
		}

		// === Arrow: grid → output ===
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.moveTo(gridR + 4, arrowY);
		ctx.lineTo(recoL - 6, arrowY);
		ctx.stroke();
		ctx.fillStyle = '#dde0e6';
		ctx.beginPath();
		ctx.moveTo(recoL - 6, arrowY - 3);
		ctx.lineTo(recoL - 1, arrowY);
		ctx.lineTo(recoL - 6, arrowY + 3);
		ctx.fill();

		// === Reconstructed waveform (right) ===
		const nHarmonics = Math.max(1, Math.floor(currentLevels * 1.5));
		const recoW = waveW;
		const recoColor = tierColor(Math.min(Math.floor(Math.max(currentLevels - 1, 0)), 8));
		ctx.strokeStyle = playingRecon ? recoColor : recoColor;
		ctx.lineWidth = playingRecon ? 2 : 1.5;
		ctx.beginPath();
		const rCx = recoL + recoW / 2;
		for (let i = 0; i <= 60; i++) {
			const t = i / 60;
			const x = recoL + t * recoW;
			let y = 0;
			for (let k = 1; k <= nHarmonics; k++) {
				y += (1 / k) * Math.sin(t * Math.PI * 6 * k);
			}
			y = wCy + y * wAmp * 0.6 * (1 - 0.3 * Math.sin(t * Math.PI * 2));
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		ctx.fillText('output', rCx, h - 6);

		// Level count label
		const displayLevels = Math.round(currentLevels);
		ctx.fillStyle = tierColor(Math.min(displayLevels - 1, 8));
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'center';
		ctx.fillText(`${displayLevels} / ${NUM_CODEBOOKS} codebooks`, gridL + gridW / 2, h - 6);
	}

	function tick() {
		if (!running) return;
		const target = activeLevels;
		const diff = target - currentLevels;
		if (Math.abs(diff) > 0.01) {
			currentLevels += diff * 0.12;
			draw();
		}
		raf = requestAnimationFrame(tick);
	}

	function addLevel() {
		if (activeLevels < NUM_CODEBOOKS) activeLevels++;
	}

	function removeLevel() {
		if (activeLevels > 1) activeLevels--;
	}

	onMount(() => {
		// Create audio elements
		originalAudio = new Audio(`${base}/audio/dac_codec_target.wav`);
		reconAudio = new Audio(reconSrc(activeLevels));
		loadedReconLevel = activeLevels;

		originalAudio.addEventListener('ended', () => { playingOriginal = false; });
		reconAudio.addEventListener('ended', () => { playingRecon = false; });

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
				cancelAnimationFrame(raf);
				// Pause audio when scrolled away
				if (originalAudio && playingOriginal) {
					originalAudio.pause();
					playingOriginal = false;
				}
				if (reconAudio && playingRecon) {
					reconAudio.pause();
					playingRecon = false;
				}
			}
		);

		draw();
		raf = requestAnimationFrame(tick);

		const onResize = () => draw();
		window.addEventListener('resize', onResize);

		return () => {
			running = false;
			cancelAnimationFrame(raf);
			obs.disconnect();
			window.removeEventListener('resize', onResize);
			if (originalAudio) { originalAudio.pause(); originalAudio = null; }
			if (reconAudio) { reconAudio.pause(); reconAudio = null; }
		};
	});
</script>

<div bind:this={container}>
	<VizPanel title="Residual Vector Quantization" titleColor="var(--orange)">
		{#snippet controls()}
			<VizButton color="var(--orange)" onclick={removeLevel}>
				- Level
			</VizButton>
			<VizButton color="var(--orange)" onclick={addLevel}>
				+ Level
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:200px"></canvas>
		<div class="audio-row">
			<button class="play-btn original" class:active={playingOriginal} onclick={toggleOriginal}>
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					{#if playingOriginal}
						<rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
					{:else}
						<polygon points="5 3 19 12 5 21 5 3" />
					{/if}
				</svg>
				Original
			</button>
			<button class="play-btn recon" class:active={playingRecon} style="--recon-color: {tierColor(activeLevels - 1)}" onclick={toggleRecon}>
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					{#if playingRecon}
						<rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
					{:else}
						<polygon points="5 3 19 12 5 21 5 3" />
					{/if}
				</svg>
				{activeLevels} codebook{activeLevels > 1 ? 's' : ''}
			</button>
		</div>
		{#snippet caption()}
			DAC encodes audio into 9 codebook levels via residual vector quantization. Each level captures finer detail — c0 is coarse structure, c8 is fine texture. Use +/- to change levels, then listen to the difference.
		{/snippet}
	</VizPanel>
</div>

<style>
	.audio-row {
		display: flex;
		gap: 0.6rem;
		padding: 0.5rem 0.75rem 0;
		justify-content: center;
	}

	.play-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-mono);
		font-size: 0.75rem;
		padding: 0.35rem 0.85rem;
		border-radius: 5px;
		border: 1px solid var(--border);
		background: var(--surface-2);
		color: var(--text);
		cursor: pointer;
		transition: all 0.15s ease;
		min-height: 36px;
	}

	.play-btn:hover {
		border-color: var(--teal);
		color: var(--teal);
	}

	.play-btn.original:hover,
	.play-btn.original.active {
		border-color: var(--teal);
		color: var(--teal);
	}

	.play-btn.original.active {
		background: var(--teal);
		color: white;
	}

	.play-btn.recon:hover {
		border-color: var(--recon-color);
		color: var(--recon-color);
	}

	.play-btn.recon.active {
		background: var(--recon-color);
		color: white;
		border-color: var(--recon-color);
	}
</style>
