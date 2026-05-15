<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let tau = $state(0.3);

	// Dataset training hours (approximate, from MT3 paper)
	const datasets = [
		{ name: 'MAESTRO', hours: 200, highResource: true },
		{ name: 'Slakh2100', hours: 100, highResource: true },
		{ name: 'Cerberus4', hours: 22, highResource: true },
		{ name: 'MusicNet', hours: 34, highResource: false },
		{ name: 'GuitarSet', hours: 3, highResource: false },
		{ name: 'URMP', hours: 1.3, highResource: false }
	];

	// Current animated bar heights (probability), lerped toward target
	let currentProbs: number[] = datasets.map(() => 0);
	let running = true;
	let raf = 0;

	function computeProbs(t: number): number[] {
		const total = datasets.reduce((s, d) => s + d.hours, 0);
		const raw = datasets.map((d) => Math.pow(d.hours / total, t));
		const sum = raw.reduce((a, b) => a + b, 0);
		return raw.map((v) => v / sum);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 44);
		const padY = canvasPad(w, 12);
		const padBottom = canvasPad(w, 42);
		const innerW = w - padX - 12;
		const innerH = h - padY - padBottom;
		const n = datasets.length;
		const barSlot = innerW / n;
		const barW = Math.min(barSlot * 0.55, 38);
		const maxBarH = innerH - 18; // leave room for % label above bar

		// Y-axis label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 12);
		ctx.save();
		ctx.translate(10, padY + innerH / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.fillText('sampling probability', 0, 0);
		ctx.restore();

		// Compute dynamic y-axis ceiling based on current bar values
		const maxProb = Math.max(...currentProbs, 0.1);
		const yMax = Math.ceil(maxProb * 10 + 1) / 10; // round up to next 10%
		const yStep = yMax <= 0.3 ? 0.05 : 0.1;

		// Horizontal gridlines
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		for (let pct = yStep; pct <= yMax + 0.001; pct += yStep) {
			const y = padY + innerH - (pct / yMax) * maxBarH;
			ctx.beginPath();
			ctx.moveTo(padX, y);
			ctx.lineTo(padX + innerW, y);
			ctx.stroke();
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 11);
			ctx.textAlign = 'right';
			ctx.fillText(Math.round(pct * 100) + '%', padX - 3, y + 3);
		}

		// Draw bars
		datasets.forEach((ds, i) => {
			const prob = currentProbs[i];
			const cx = padX + (i + 0.5) * barSlot;
			const barH = (prob / yMax) * maxBarH;
			const x = cx - barW / 2;
			const y = padY + innerH - barH;
			const color = ds.highResource ? '#1a9e8f' : '#e07020';
			const alpha = 0.55 + 0.35 * prob;

			// Bar
			ctx.fillStyle = `rgba(${ds.highResource ? '26,158,143' : '224,112,32'},${alpha})`;
			ctx.beginPath();
			ctx.roundRect(x, y, barW, barH, [3, 3, 0, 0]);
			ctx.fill();

			// Percentage label above bar
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 12);
			ctx.textAlign = 'center';
			ctx.fillText(Math.round(prob * 100) + '%', cx, y - 4);

			// Dataset name label below
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 11);
			ctx.textAlign = 'center';
			ctx.fillText(ds.name, cx, padY + innerH + 14);

			// Hours label
			ctx.fillStyle = ds.highResource ? 'rgba(20,124,112,0.85)' : 'rgba(192,93,22,0.85)';
			ctx.font = canvasFont(w, 11);
			ctx.fillText(ds.hours + 'h', cx, padY + innerH + 24);
		});

		// τ annotation
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 12);
		ctx.textAlign = 'right';
		ctx.fillText('τ = ' + tau.toFixed(2), w - 10, padY + 10);
	}

	let animRaf = 0;
	function animateBars() {
		const target = computeProbs(tau);
		let needsUpdate = false;
		for (let i = 0; i < currentProbs.length; i++) {
			const diff = target[i] - currentProbs[i];
			if (Math.abs(diff) > 0.0005) {
				currentProbs[i] += diff * 0.15;
				needsUpdate = true;
			} else {
				currentProbs[i] = target[i];
			}
		}
		draw();
		if (needsUpdate) {
			animRaf = requestAnimationFrame(animateBars);
		}
	}

	function onTauInput() {
		cancelAnimationFrame(animRaf);
		animateBars();
	}

	onMount(() => {
		currentProbs = computeProbs(tau);
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			running = false;
			cancelAnimationFrame(animRaf);
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<VizPanel title="Temperature-Weighted Mixture Sampling" titleColor="var(--orange)">
	{#snippet controls()}
		<label class="slider-label">
			<span>τ</span>
			<input type="range" min="0.05" max="1.0" step="0.01" bind:value={tau} oninput={onTauInput} />
			<span class="val">{tau.toFixed(2)}</span>
		</label>
		<div class="legend">
			<span class="dot hi"></span><span>high-resource</span>
			<span class="dot lo"></span><span>low-resource</span>
		</div>
	{/snippet}
	<canvas bind:this={canvas} height="150"></canvas>
	{#snippet caption()}
		τ = 1.0 samples in direct proportion to dataset size, so tiny datasets nearly disappear. τ = 0.3 (MT3's setting) compresses the range, giving URMP's 1.3 h roughly the same representation as MAESTRO's 200 h.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
	}

	.slider-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.val {
		min-width: 3em;
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 120px;
		height: 4px;
		background: var(--border);
		border-radius: 2px;
		outline: none;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--orange);
		cursor: pointer;
		box-shadow: 0 0 8px var(--orange-glow);
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-display);
		font-size: 0.65rem;
		color: var(--text-muted);
	}

	.dot {
		display: inline-block;
		width: 7px;
		height: 7px;
		border-radius: 1px;
		flex-shrink: 0;
	}

	.dot.hi {
		background: #1a9e8f;
	}

	.dot.lo {
		background: #e07020;
	}

	@media (max-width: 640px) {
		input[type='range'] {
			width: 90px;
		}
		.legend {
			display: none;
		}
	}
</style>
