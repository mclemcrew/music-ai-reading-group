<script lang="ts">
	import { onMount } from 'svelte';
	import { animate } from 'animejs';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	const nPoints = 10;
	let controlPoints: { x: number; y: number }[] = [];
	let draggingIdx = -1;
	let noiseData: number[] = [];

	function initPoints() {
		controlPoints = [];
		for (let i = 0; i < nPoints; i++) {
			controlPoints.push({ x: i / (nPoints - 1), y: 0.7 });
		}
	}

	function initNoise() {
		noiseData = [];
		for (let i = 0; i < 200; i++) {
			noiseData.push(0.3 + Math.random() * 0.4);
		}
	}

	function getFilterY(xNorm: number) {
		const pos = xNorm * (nPoints - 1);
		const i0 = Math.floor(pos);
		const i1 = Math.min(i0 + 1, nPoints - 1);
		const t = pos - i0;
		return controlPoints[i0].y * (1 - t) + controlPoints[i1].y * t;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';
		const padB = canvasPad(w, 30),
			padT = canvasPad(w, 10);
		const plotH = h - padB - padT;

		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		// Axis
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		ctx.beginPath();
		ctx.moveTo(0, h - padB);
		ctx.lineTo(w, h - padB);
		ctx.stroke();

		// Freq labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 12);
		const labels = ['0', '1k', '2k', '3k', '4k', '5k', '6k', '7k', '8k'];
		labels.forEach((l, i) => {
			ctx.fillText(l, (i / (labels.length - 1)) * w - 5, h - 16);
		});

		// White noise bars
		const barW = w / noiseData.length;
		for (let i = 0; i < noiseData.length; i++) {
			const x = i * barW;
			const barH = noiseData[i] * plotH;
			ctx.fillStyle = 'rgba(0,0,0,0.10)';
			ctx.fillRect(x, padT + plotH - barH, barW - 1, barH);
		}

		// Filtered noise bars
		for (let i = 0; i < noiseData.length; i++) {
			const xNorm = i / noiseData.length;
			const x = i * barW;
			const filterAmp = getFilterY(xNorm);
			const barH = noiseData[i] * filterAmp * plotH;
			ctx.fillStyle = 'rgba(124,77,255,0.30)';
			ctx.fillRect(x, padT + plotH - barH, barW - 1, barH);
		}

		// Filter curve
		ctx.beginPath();
		ctx.strokeStyle = '#7c4dff';
		ctx.lineWidth = 2.5;
		ctx.shadowColor = 'rgba(124,77,255,0.4)';
		ctx.shadowBlur = 6;
		for (let i = 0; i <= 100; i++) {
			const xNorm = i / 100;
			const x = xNorm * w;
			const y = padT + plotH * (1 - getFilterY(xNorm));
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();
		ctx.shadowBlur = 0;

		// Control points — larger on touch devices
		const pointR = 'ontouchstart' in window ? 12 : 7;
		controlPoints.forEach((p, i) => {
			const x = p.x * w;
			const y = padT + plotH * (1 - p.y);
			const active = draggingIdx === i;

			if (active) {
				ctx.beginPath();
				ctx.arc(x, y, pointR + 5, 0, Math.PI * 2);
				ctx.fillStyle = 'rgba(124,77,255,0.12)';
				ctx.fill();
			}

			ctx.beginPath();
			ctx.arc(x, y, pointR, 0, Math.PI * 2);
			ctx.fillStyle = active ? '#7c4dff' : '#ffffff';
			ctx.fill();
			ctx.strokeStyle = '#7c4dff';
			ctx.lineWidth = 2.5;
			ctx.stroke();
		});
	}

	function getCanvasPos(e: MouseEvent | TouchEvent) {
		const rect = canvas.getBoundingClientRect();
		const src = 'touches' in e ? e.touches[0] : e;
		return { x: src.clientX - rect.left, y: src.clientY - rect.top };
	}

	function findNearest(pos: { x: number; y: number }) {
		const rect = canvas.getBoundingClientRect();
		const padB = 30,
			padT = 10,
			plotH = rect.height - padB - padT;
		let best = -1,
			bestDist = 30;
		controlPoints.forEach((p, i) => {
			const px = p.x * rect.width;
			const py = padT + plotH * (1 - p.y);
			const d = Math.hypot(pos.x - px, pos.y - py);
			if (d < bestDist) {
				bestDist = d;
				best = i;
			}
		});
		return best;
	}

	function updateDrag(pos: { x: number; y: number }) {
		if (draggingIdx < 0) return;
		const rect = canvas.getBoundingClientRect();
		const padB = 30,
			padT = 10,
			plotH = rect.height - padB - padT;
		controlPoints[draggingIdx].y = Math.max(0, Math.min(1, 1 - (pos.y - padT) / plotH));
		draw();
	}

	function randomize() {
		const targets = controlPoints.map(() => 0.15 + Math.random() * 0.75);
		controlPoints.forEach((p, i) => {
			animate(p, {
				y: targets[i],
				duration: 500,
				ease: 'outExpo',
				onUpdate: () => draw()
			});
		});
	}

	onMount(() => {
		initPoints();
		initNoise();
		draw();

		const onResize = () => draw();
		window.addEventListener('resize', onResize);

		const onMouseUp = () => {
			draggingIdx = -1;
			draw();
		};
		window.addEventListener('mouseup', onMouseUp);

		return () => {
			window.removeEventListener('resize', onResize);
			window.removeEventListener('mouseup', onMouseUp);
		};
	});
</script>

<VizPanel title="Filtered Noise" titleColor="var(--violet)">
	{#snippet controls()}
		<VizButton color="var(--violet)" onclick={randomize}>Randomize</VizButton>
		<VizButton
			onclick={() => {
				initPoints();
				draw();
			}}>Reset</VizButton
		>
	{/snippet}
	<canvas
		bind:this={canvas}
		height="200"
		onmousedown={(e) => {
			draggingIdx = findNearest(getCanvasPos(e));
			draw();
		}}
		onmousemove={(e) => {
			if (draggingIdx < 0) return;
			updateDrag(getCanvasPos(e));
		}}
		ontouchstart={(e) => {
			e.preventDefault();
			draggingIdx = findNearest(getCanvasPos(e));
			draw();
		}}
		ontouchmove={(e) => {
			e.preventDefault();
			updateDrag(getCanvasPos(e));
		}}
		ontouchend={() => {
			draggingIdx = -1;
			draw();
		}}
	></canvas>
	{#snippet caption()}
		Drag control points to shape the noise filter. Grey = raw noise, purple = filtered output.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		touch-action: none;
	}
</style>
