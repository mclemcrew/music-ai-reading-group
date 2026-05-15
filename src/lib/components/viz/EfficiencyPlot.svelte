<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let hoveredIdx = $state(-1);
	let mousePos = { x: 0, y: 0 };
	let running = true;

	// Models: log10(params), F-score (onset+offset, %), color, description
	// NOTE: each F-score is from that model's own benchmark — they are NOT directly comparable
	const models = [
		{
			name: 'NMP (Bittner 2022)',
			log10p: Math.log10(16_782),
			f: 71,
			color: '#e07020',
			note: '16K params · GuitarSet (real multi-inst) · SOTA'
		},
		{
			name: 'MI-AMT baseline',
			log10p: Math.log10(17_000_000),
			f: 39,
			color: '#9ca3af',
			note: '17M params · instrument-agnostic · low accuracy'
		},
		{
			name: 'Onsets & Frames (*)',
			log10p: Math.log10(18_000_000),
			f: 95,
			color: '#1a9e8f',
			note: '18M params · MAPS (piano, mostly synthetic) · (*) easiest benchmark'
		},
		{
			name: 'MT3 (Gardner 2022)',
			log10p: Math.log10(60_000_000),
			f: 92,
			color: '#2979ff',
			note: '60M params · MAESTRO (piano) · 6 datasets'
		},
		{
			name: 'Vocano (vocals)',
			log10p: Math.log10(25_000_000),
			f: 64,
			color: '#7c4dff',
			note: '~25M params · Molina dataset · vocals specialist'
		}
	];

	// Pareto-efficient frontier: NMP → O&F
	const paretoIdxs = [0, 2]; // NMP and O&F

	// Canvas-space point positions, computed per draw
	let ptPx: Array<{ x: number; y: number }> = [];

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 44);
		const padY = canvasPad(w, 14);
		const padBottom = canvasPad(w, 34);
		const padRight = canvasPad(w, 12);
		const innerW = w - padX - padRight;
		const innerH = h - padY - padBottom;

		// Axis ranges
		const xMin = 3.8; // log10(6300) ≈ 3.8
		const xMax = 8.2; // log10(~160M)
		const yMin = 25;
		const yMax = 100;

		function toCanvasX(v: number) {
			return padX + ((v - xMin) / (xMax - xMin)) * innerW;
		}
		function toCanvasY(v: number) {
			return padY + ((yMax - v) / (yMax - yMin)) * innerH;
		}

		// Grid lines
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;

		// Vertical gridlines at log10 param marks
		for (const p of [4, 5, 6, 7, 8]) {
			const x = toCanvasX(p);
			ctx.beginPath();
			ctx.moveTo(x, padY);
			ctx.lineTo(x, padY + innerH);
			ctx.stroke();
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'alphabetic';
			const labels: Record<number, string> = { 4: '10K', 5: '100K', 6: '1M', 7: '10M', 8: '100M' };
			ctx.fillText(labels[p], x, padY + innerH + 14);
		}

		// Horizontal gridlines
		for (const f of [30, 40, 50, 60, 70, 80, 90, 100]) {
			const y = toCanvasY(f);
			ctx.beginPath();
			ctx.moveTo(padX, y);
			ctx.lineTo(padX + innerW, y);
			ctx.stroke();
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'right';
			ctx.textBaseline = 'middle';
			ctx.fillText(f + '%', padX - 5, y);
		}

		// Axis labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('parameters (log scale)', padX + innerW / 2, h - 4);

		ctx.save();
		ctx.translate(10, padY + innerH / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.fillText('F-score onset+offset (%)', 0, 0);
		ctx.restore();

		// Pareto frontier (dashed teal line)
		const paretoPoints = paretoIdxs.map((i) => models[i]);
		ctx.strokeStyle = 'rgba(26,158,143,0.35)';
		ctx.lineWidth = 1.5;
		ctx.setLineDash([5, 4]);
		ctx.beginPath();
		paretoPoints.forEach((m, i) => {
			const x = toCanvasX(m.log10p);
			const y = toCanvasY(m.f);
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		});
		ctx.stroke();
		ctx.setLineDash([]);
		// "efficiency frontier" label
		const mx = (toCanvasX(models[0].log10p) + toCanvasX(models[2].log10p)) / 2;
		const my = (toCanvasY(models[0].f) + toCanvasY(models[2].f)) / 2 - 10;
		ctx.fillStyle = 'rgba(26,158,143,0.45)';
		ctx.font = '7.5px "Quicksand", system-ui, sans-serif';
		ctx.textAlign = 'center';
		ctx.fillText('efficiency frontier', mx, my);

		// Compute & store canvas-space positions
		ptPx = models.map((m) => ({
			x: toCanvasX(m.log10p),
			y: toCanvasY(m.f)
		}));

		// Draw points
		models.forEach((m, i) => {
			const { x, y } = ptPx[i];
			const isHovered = i === hoveredIdx;
			const r = isHovered ? 9 : 6;

			ctx.fillStyle = m.color;
			if (isHovered) {
				ctx.shadowColor = m.color;
				ctx.shadowBlur = 12;
			}
			ctx.beginPath();
			ctx.arc(x, y, r, 0, Math.PI * 2);
			ctx.fill();
			ctx.shadowBlur = 0;

			// Border ring
			ctx.strokeStyle = m.color;
			ctx.lineWidth = isHovered ? 2 : 1;
			ctx.globalAlpha = isHovered ? 1 : 0.5;
			ctx.beginPath();
			ctx.arc(x, y, r + 3, 0, Math.PI * 2);
			ctx.stroke();
			ctx.globalAlpha = 1;
		});

		// Hover tooltip
		if (hoveredIdx >= 0) {
			const m = models[hoveredIdx];
			const { x, y } = ptPx[hoveredIdx];
			const boxW = 170;
			const boxH = 46;
			const bx = Math.min(x - boxW / 2, w - boxW - 8);
			const by = y - boxH - 14;

			ctx.fillStyle = '#ffffff';
			ctx.shadowColor = 'rgba(0,0,0,0.12)';
			ctx.shadowBlur = 8;
			ctx.beginPath();
			ctx.roundRect(Math.max(8, bx), Math.max(4, by), boxW, boxH, 6);
			ctx.fill();
			ctx.shadowBlur = 0;

			ctx.strokeStyle = m.color;
			ctx.lineWidth = 1.5;
			ctx.beginPath();
			ctx.roundRect(Math.max(8, bx), Math.max(4, by), boxW, boxH, 6);
			ctx.stroke();

			const tx = Math.max(8, bx) + 10;
			const ty = Math.max(4, by) + 16;
			ctx.fillStyle = m.color;
			ctx.font = canvasFont(w, 11, 'bold');
			ctx.textAlign = 'left';
			ctx.fillText(m.name, tx, ty);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.fillText(m.note, tx, ty + 14);
			ctx.fillText(
				m.f + '% F  ·  ' + (m.log10p < 5 ? Math.round(10 ** m.log10p).toLocaleString() : (10 ** m.log10p / 1e6).toFixed(0) + 'M') + ' params',
				tx,
				ty + 25
			);
		}
	}

	function findHovered(px: number, py: number): number {
		let best = -1;
		let bestDist = 18;
		ptPx.forEach((pt, i) => {
			const d = Math.hypot(pt.x - px, pt.y - py);
			if (d < bestDist) {
				bestDist = d;
				best = i;
			}
		});
		return best;
	}

	function getPos(e: MouseEvent | TouchEvent) {
		const rect = canvas.getBoundingClientRect();
		const src = 'touches' in e ? e.touches[0] : e;
		const dpr = window.devicePixelRatio || 1;
		// ptPx is in logical (CSS) pixels, so no DPR scaling needed here
		return {
			x: (src.clientX - rect.left),
			y: (src.clientY - rect.top)
		};
	}

	onMount(() => {
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			running = false;
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<VizPanel title="Efficiency Frontier" titleColor="var(--orange)">
	<canvas
		bind:this={canvas}
		height="250"
		onmousemove={(e) => {
			const pos = getPos(e);
			const idx = findHovered(pos.x, pos.y);
			if (idx !== hoveredIdx) {
				hoveredIdx = idx;
				draw();
			}
		}}
		onmouseleave={() => {
			if (hoveredIdx !== -1) {
				hoveredIdx = -1;
				draw();
			}
		}}
		ontouchstart={(e) => {
			e.preventDefault();
			const pos = getPos(e);
			hoveredIdx = findHovered(pos.x, pos.y);
			draw();
		}}
		ontouchmove={(e) => {
			e.preventDefault();
			const pos = getPos(e);
			const idx = findHovered(pos.x, pos.y);
			if (idx !== hoveredIdx) {
				hoveredIdx = idx;
				draw();
			}
		}}
		ontouchend={() => {
			hoveredIdx = -1;
			draw();
		}}
	></canvas>
	{#snippet caption()}
		F-scores from each model's own benchmark — different datasets, different difficulty. NMP→GuitarSet (real multi-instrument), O&F(*)→MAPS (piano, mostly synthetic), MT3→MAESTRO, Vocano→Molina. Cross-model comparisons are approximate. Tap or hover a point for details.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		cursor: crosshair;
		touch-action: none;
	}
</style>
