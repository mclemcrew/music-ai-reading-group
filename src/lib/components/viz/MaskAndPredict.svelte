<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, observeVisibility } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let visible = false;
	let running = true;
	let raf = 0;

	let pass = $state(0);
	let playing = $state(false);
	let lastStepTime = 0;

	const COLS = 16;
	const ROWS = 4;
	const MAX_PASS = 12;
	const STEP_MS = 350;

	// Row colors (c0-c3)
	const ROW_COLORS = ['#e07020', '#1a9e8f', '#7c4dff', '#2979ff'];
	const ROW_LABELS = ['c0', 'c1', 'c2', 'c3'];

	// Cell state: 0 = masked, 1 = just-predicted, 2 = settled
	type CellState = 0 | 1 | 2;
	let cells: CellState[][] = [];

	// Pre-compute reveal order: coarse rows first, then fine
	// Each pass reveals a batch of cells
	interface RevealBatch {
		positions: Array<[number, number]>; // [row, col]
	}
	let revealBatches: RevealBatch[] = [];

	function initCells() {
		cells = [];
		for (let r = 0; r < ROWS; r++) {
			cells[r] = [];
			for (let c = 0; c < COLS; c++) {
				cells[r][c] = 0;
			}
		}
	}

	function buildRevealOrder() {
		// Deterministic pseudo-random order: coarse rows revealed earlier
		const allPositions: Array<[number, number, number]> = []; // [row, col, priority]
		for (let r = 0; r < ROWS; r++) {
			for (let c = 0; c < COLS; c++) {
				// Priority: lower row index → earlier. Within row, pseudo-random order.
				const priority = r * 100 + ((c * 7 + r * 13 + 3) % COLS);
				allPositions.push([r, c, priority]);
			}
		}
		allPositions.sort((a, b) => a[2] - b[2]);

		const totalCells = ROWS * COLS;
		const batchSize = Math.ceil(totalCells / MAX_PASS);

		revealBatches = [];
		for (let i = 0; i < MAX_PASS; i++) {
			const start = i * batchSize;
			const end = Math.min(start + batchSize, totalCells);
			const positions: Array<[number, number]> = [];
			for (let j = start; j < end; j++) {
				positions.push([allPositions[j][0], allPositions[j][1]]);
			}
			revealBatches.push({ positions });
		}
	}

	function reset() {
		playing = false;
		pass = 0;
		initCells();
	}

	function step() {
		if (pass >= MAX_PASS) return;

		// Settle previous "just-predicted" cells
		for (let r = 0; r < ROWS; r++) {
			for (let c = 0; c < COLS; c++) {
				if (cells[r][c] === 1) cells[r][c] = 2;
			}
		}

		// Reveal new batch
		const batch = revealBatches[pass];
		if (batch) {
			for (const [r, c] of batch.positions) {
				cells[r][c] = 1;
			}
		}
		pass++;
	}

	function togglePlay() {
		playing = !playing;
		if (playing && pass >= MAX_PASS) {
			reset();
			playing = true;
		}
		lastStepTime = performance.now();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = 28;
		const padR = 10;
		const padT = 8;
		const padB = 32;

		const gridW = w - padL - padR;
		const gridH = h - padT - padB;
		const cellW = gridW / COLS;
		const cellH = gridH / ROWS;
		const cellPad = 2;

		// Draw grid cells
		for (let r = 0; r < ROWS; r++) {
			const baseY = padT + r * cellH;

			// Row label
			ctx.fillStyle = ROW_COLORS[r];
			ctx.font = '10px "DM Mono", monospace';
			ctx.textAlign = 'right';
			ctx.fillText(ROW_LABELS[r], padL - 5, baseY + cellH / 2 + 3);

			for (let c = 0; c < COLS; c++) {
				const cx = padL + c * cellW + cellPad;
				const cy = baseY + cellPad;
				const cw = cellW - cellPad * 2;
				const ch = cellH - cellPad * 2;
				const radius = 3;
				const state = cells[r]?.[c] ?? 0;

				if (state === 0) {
					// Masked
					ctx.fillStyle = '#f3f4f6';
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.fill();
					ctx.strokeStyle = '#d1d5db';
					ctx.lineWidth = 1;
					ctx.setLineDash([2, 2]);
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.stroke();
					ctx.setLineDash([]);

					// "?" text
					ctx.fillStyle = '#9ca3af';
					ctx.font = `${Math.min(ch * 0.55, 12)}px "DM Mono", monospace`;
					ctx.textAlign = 'center';
					ctx.textBaseline = 'middle';
					ctx.fillText('?', cx + cw / 2, cy + ch / 2);
					ctx.textBaseline = 'alphabetic';
				} else {
					const color = ROW_COLORS[r];

					if (state === 1) {
						// Just-predicted — glow
						ctx.shadowColor = color;
						ctx.shadowBlur = 8;
					}

					// Token seed for shade
					const seed = ((r * 17 + c * 31 + 7) % 100) / 100;
					const shade = 0.4 + seed * 0.45;

					ctx.globalAlpha = shade;
					ctx.fillStyle = color;
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.fill();
					ctx.globalAlpha = 1;

					ctx.strokeStyle = color;
					ctx.lineWidth = state === 1 ? 1.5 : 0.8;
					ctx.beginPath();
					ctx.roundRect(cx, cy, cw, ch, radius);
					ctx.stroke();

					ctx.shadowColor = 'transparent';
					ctx.shadowBlur = 0;
				}
			}
		}

		// Progress info
		const totalCells = ROWS * COLS;
		let revealedCount = 0;
		for (let r = 0; r < ROWS; r++) {
			for (let c = 0; c < COLS; c++) {
				if (cells[r]?.[c]) revealedCount++;
			}
		}
		const pct = Math.round((revealedCount / totalCells) * 100);

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = '11px "DM Mono", monospace';
		ctx.textAlign = 'left';
		ctx.fillText(`pass ${pass} / ${MAX_PASS}`, padL, h - 10);
		ctx.textAlign = 'right';
		ctx.fillText(`${pct}% revealed`, w - padR, h - 10);

		// Progress bar
		const barY = h - 22;
		const barH = 3;
		const barW = gridW * 0.4;
		const barL = padL + (gridW - barW) / 2;
		ctx.fillStyle = '#e5e7eb';
		ctx.beginPath();
		ctx.roundRect(barL, barY, barW, barH, 1.5);
		ctx.fill();
		ctx.fillStyle = '#7c4dff';
		ctx.beginPath();
		ctx.roundRect(barL, barY, barW * (pass / MAX_PASS), barH, 1.5);
		ctx.fill();
	}

	function tick(ts: number) {
		if (!running) return;

		if (playing && pass < MAX_PASS) {
			if (ts - lastStepTime >= STEP_MS) {
				step();
				lastStepTime = ts;
				draw();
			}
			if (pass >= MAX_PASS) {
				playing = false;
			}
		}

		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		initCells();
		buildRevealOrder();

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
		};
	});
</script>

<div bind:this={container}>
	<VizPanel title="Iterative Parallel Decoding" titleColor="var(--violet)">
		{#snippet controls()}
			<VizButton color="var(--violet)" onclick={step}>
				Step
			</VizButton>
			<VizButton color="var(--violet)" onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--violet)" onclick={reset}>
				Reset
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:220px"></canvas>
		{#snippet caption()}
			VampNet decodes in ~36 parallel passes (compressed to 12 here). Each pass predicts a batch of masked tokens simultaneously — coarse codebook levels (c0) are filled first, then finer levels. Click Step or Play to watch.
		{/snippet}
	</VizPanel>
</div>
