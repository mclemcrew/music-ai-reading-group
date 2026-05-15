<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let stepDisplay = $state('step 0');
	let lossDisplay = $state('loss: \u2014');

	const nSamples = 400;
	const targetAmps = [1.0, 0.5, 0.25, 0, 0, 0, 0, 0];
	let predAmps: number[] = [];
	let losses: number[] = [];
	let step = 0;
	let training = $state(false);
	let animId: number;

	function initPred() {
		predAmps = targetAmps.map(() => Math.random() * 0.8);
	}

	function synth(amps: number[]) {
		const out: number[] = [];
		for (let n = 0; n < nSamples; n++) {
			let v = 0;
			for (let k = 0; k < amps.length; k++) {
				v += amps[k] * Math.sin((2 * Math.PI * (k + 1) * 4 * n) / nSamples);
			}
			out.push(v);
		}
		return out;
	}

	function computeLoss(a: number[], b: number[]) {
		let sum = 0;
		for (let i = 0; i < a.length; i++) sum += Math.abs(a[i] - b[i]);
		return sum / a.length;
	}

	function trainStep() {
		const lr = 0.03;
		for (let k = 0; k < predAmps.length; k++) {
			const diff = targetAmps[k] - predAmps[k];
			predAmps[k] += lr * diff + (Math.random() - 0.5) * 0.01;
			predAmps[k] = Math.max(0, predAmps[k]);
		}
		step++;
		losses.push(computeLoss(synth(targetAmps), synth(predAmps)));
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';
		const waveH = h * 0.55;
		const lossH = h * 0.35;
		const gap = h * 0.1;

		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const targetWave = synth(targetAmps);
		const predWave = synth(predAmps);
		const wMid = waveH / 2;
		const wAmp = waveH * 0.4;

		// Target
		ctx.beginPath();
		ctx.strokeStyle = '#1a9e8f';
		ctx.lineWidth = 1.5;
		ctx.shadowColor = 'rgba(26,158,143,0.3)';
		ctx.shadowBlur = 4;
		for (let i = 0; i < nSamples; i++) {
			const x = (i / nSamples) * w;
			const y = wMid + (targetWave[i] * wAmp) / 1.75;
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();
		ctx.shadowBlur = 0;

		// Predicted
		ctx.beginPath();
		ctx.strokeStyle = '#e07020';
		ctx.lineWidth = 2;
		ctx.shadowColor = 'rgba(224,112,32,0.4)';
		ctx.shadowBlur = 6;
		for (let i = 0; i < nSamples; i++) {
			const x = (i / nSamples) * w;
			const y = wMid + (predWave[i] * wAmp) / 1.75;
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();
		ctx.shadowBlur = 0;

		// Labels
		ctx.font = canvasFont(w, 10);
		ctx.fillStyle = '#1a9e8f';
		ctx.fillText('target', 8, 16);
		ctx.fillStyle = '#e07020';
		ctx.fillText('predicted', 60, 16);

		// Separator
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		ctx.beginPath();
		ctx.moveTo(0, waveH + gap / 2);
		ctx.lineTo(w, waveH + gap / 2);
		ctx.stroke();

		// Loss curve
		if (losses.length > 1) {
			const lossTop = waveH + gap;
			const maxLoss = Math.max(...losses, 0.5);
			ctx.beginPath();
			ctx.strokeStyle = '#7c4dff';
			ctx.lineWidth = 2;
			ctx.shadowColor = 'rgba(124,77,255,0.3)';
			ctx.shadowBlur = 4;
			for (let i = 0; i < losses.length; i++) {
				const x = (i / Math.max(losses.length - 1, 1)) * w;
				const y = lossTop + lossH * (1 - losses[i] / maxLoss);
				i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
			}
			ctx.stroke();
			ctx.shadowBlur = 0;
			ctx.fillStyle = '#7c4dff';
			ctx.fillText('loss', 8, lossTop + 14);
		}
	}

	function trainLoop() {
		if (!training) return;
		trainStep();
		stepDisplay = 'step ' + step;
		lossDisplay = 'loss: ' + losses[losses.length - 1].toFixed(4);
		draw();
		if (step < 200) {
			animId = requestAnimationFrame(trainLoop);
		} else {
			training = false;
		}
	}

	function toggleTraining() {
		if (training) {
			training = false;
			cancelAnimationFrame(animId);
		} else {
			training = true;
			trainLoop();
		}
	}

	function resetTraining() {
		training = false;
		cancelAnimationFrame(animId);
		step = 0;
		losses = [];
		initPred();
		stepDisplay = 'step 0';
		lossDisplay = 'loss: \u2014';
		draw();
	}

	onMount(() => {
		initPred();
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			window.removeEventListener('resize', onResize);
			training = false;
			cancelAnimationFrame(animId);
		};
	});
</script>

<VizPanel title="Training Loop" titleColor="var(--violet)">
	{#snippet controls()}
		<span class="status">{stepDisplay}</span>
		<span class="status">{lossDisplay}</span>
		<VizButton active={training} onclick={toggleTraining}>
			{training ? 'Pause' : 'Train'}
		</VizButton>
		<VizButton onclick={resetTraining}>Reset</VizButton>
	{/snippet}
	<canvas bind:this={canvas} height="260"></canvas>
	{#snippet caption()}
		Watch gradient descent converge: orange waveform approaches the teal target.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
	}

	.status {
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}
</style>
