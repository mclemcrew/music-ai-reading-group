<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, observeVisibility, canvasFont, canvasPad } from '$lib/utils/canvas';

	let leftEl: HTMLCanvasElement;
	let rightEl: HTMLCanvasElement;
	let visible = false;
	let running = true;
	let startTime = 0;
	let gatingEnabled = $state(true);

	// Synthetic piano roll: 8 pitch rows, time 0–1 normalized
	const notes = [
		{ pitch: 6, start: 0.04, dur: 0.20 },
		{ pitch: 2, start: 0.09, dur: 0.22 },
		{ pitch: 4, start: 0.28, dur: 0.17 },
		{ pitch: 1, start: 0.33, dur: 0.24 },
		{ pitch: 7, start: 0.50, dur: 0.15 },
		{ pitch: 3, start: 0.56, dur: 0.21 },
		{ pitch: 5, start: 0.70, dur: 0.18 },
		{ pitch: 0, start: 0.77, dur: 0.21 }
	];

	// Notes whose frame detector keeps firing after the note ends (ghost tails)
	const ghostSet = new Set([1, 3, 5]);
	const GHOST_EXT = 0.13;

	// Pitch labels top→bottom (pitch 7 = top row, pitch 0 = bottom row)
	const pitchLabels = ['B5', 'G5', 'E5', 'C5', 'A4', 'F4', 'D4', 'B3'];

	function drawPanel(canvas: HTMLCanvasElement, showGhosts: boolean, t: number) {
		const { ctx, w, h } = setupCanvas(canvas);
		const nPitches = 8;
		const padX = canvasPad(w, 38);
		const padY = canvasPad(w, 10);
		const innerW = w - padX - 8;
		const innerH = h - padY * 2;
		const rowH = innerH / nPitches;

		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		// Pitch labels on the left
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'middle';
		for (let p = 0; p < nPitches; p++) {
			const rowIdx = p; // row 0 = top = pitch 7 = B5
			const cy = padY + rowIdx * rowH + rowH / 2;
			ctx.fillStyle = CANVAS_LABEL;
			ctx.fillText(pitchLabels[rowIdx], padX - 4, cy);
		}

		// Horizontal row separators
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		for (let p = 0; p <= nPitches; p++) {
			const y = padY + p * rowH;
			ctx.beginPath();
			ctx.moveTo(padX, y);
			ctx.lineTo(padX + innerW, y);
			ctx.stroke();
		}
		// Vertical quarter-time markers
		for (const frac of [0.25, 0.5, 0.75]) {
			const x = padX + frac * innerW;
			ctx.beginPath();
			ctx.moveTo(x, padY);
			ctx.lineTo(x, padY + innerH);
			ctx.stroke();
		}

		notes.forEach((note, i) => {
			const x = padX + note.start * innerW;
			const nw = note.dur * innerW;
			const y = padY + (nPitches - 1 - note.pitch) * rowH + 2;
			const nh = rowH - 4;

			// Ghost tail: energy-decay fade — strong at note-end, fades to transparent
			if (showGhosts && ghostSet.has(i)) {
				const baseAlpha = 0.22 + 0.08 * Math.sin(t * 2.2 + i * 1.3);
				const gw = GHOST_EXT * innerW;
				const grad = ctx.createLinearGradient(x + nw, 0, x + nw + gw, 0);
				grad.addColorStop(0, `rgba(220,60,60,${baseAlpha})`);
				grad.addColorStop(1, 'rgba(220,60,60,0)');
				ctx.fillStyle = grad;
				ctx.fillRect(x + nw, y, gw, nh);
			}

			// Real note rectangle
			ctx.fillStyle = 'rgba(26,158,143,0.70)';
			ctx.fillRect(x, y, nw, nh);
			ctx.strokeStyle = '#1a9e8f';
			ctx.lineWidth = 1;
			ctx.strokeRect(x, y, nw, nh);
		});

		// Panel label
		ctx.font = canvasFont(w, 12);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		if (showGhosts) {
			ctx.fillStyle = 'rgba(220,60,60,0.55)';
			ctx.fillText('frame detector only', padX + 4, padY + innerH - 5);
		} else {
			ctx.fillStyle = gatingEnabled ? '#1a9e8f' : 'rgba(220,60,60,0.55)';
			ctx.fillText(gatingEnabled ? 'onset-gated ✓' : 'frame detector only', padX + 4, padY + innerH - 5);
		}
	}

	let raf = 0;
	function draw() {
		if (!running || !leftEl || !rightEl) return;
		const t = (performance.now() - startTime) / 1000;
		drawPanel(leftEl, true, t);
		drawPanel(rightEl, !gatingEnabled, t);
		if (visible) raf = requestAnimationFrame(draw);
	}

	onMount(() => {
		startTime = performance.now();
		const panel = leftEl.closest('.viz-panel')!;
		const obs = observeVisibility(
			panel,
			() => {
				visible = true;
				draw();
			},
			() => {
				visible = false;
			}
		);
		draw();
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

<VizPanel title="Onset Gating" titleColor="var(--teal)">
	{#snippet controls()}
		<VizButton
			color="var(--teal)"
			active={gatingEnabled}
			onclick={() => {
				gatingEnabled = !gatingEnabled;
				if (!visible) draw();
			}}
		>
			{gatingEnabled ? 'Gating: on' : 'Gating: off'}
		</VizButton>
	{/snippet}
	<div class="split-canvas">
		<div class="canvas-col">
			<div class="canvas-label ghost-label">frame only</div>
			<canvas bind:this={leftEl} height="160"></canvas>
		</div>
		<div class="canvas-col">
			<div class="canvas-label gated-label">{gatingEnabled ? 'onset gated' : 'frame only'}</div>
			<canvas bind:this={rightEl} height="160"></canvas>
		</div>
	</div>
	{#snippet caption()}
		Left: frame detector fires ghost tails (red fade) after the note ends — acoustic decay keeps the frame posterior high. Right: onset gating eliminates them — a frame pitch only activates if the onset detector also fired. Ghost tails shown on three arbitrary notes for illustration; in practice any note with sufficient decay can produce them.
	{/snippet}
</VizPanel>

<style>
	.split-canvas {
		display: flex;
		gap: 1px;
		background: var(--border);
	}

	.canvas-col {
		flex: 1;
		background: var(--surface);
		position: relative;
	}

	.canvas-label {
		position: absolute;
		top: 8px;
		left: 10px;
		font-family: var(--font-display);
		font-size: 0.68rem;
		z-index: 1;
		pointer-events: none;
	}

	.ghost-label {
		color: rgba(220, 60, 60, 0.6);
	}

	.gated-label {
		color: var(--teal);
	}

	canvas {
		display: block;
		width: 100%;
	}

	@media (max-width: 640px) {
		.split-canvas {
			flex-direction: column;
		}
	}
</style>
