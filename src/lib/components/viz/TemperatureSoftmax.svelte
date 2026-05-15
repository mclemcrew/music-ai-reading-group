<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let tauLog = $state(-1); // log10(tau); range -2 (tau=0.01) to +0.7 (tau≈5)
	let tau = $derived(Math.pow(10, tauLog));

	const N = 8;
	const positiveIdx = 3;
	const similarities: number[] = [];
	for (let i = 0; i < N; i++) {
		const distFromPos = Math.abs(i - positiveIdx);
		const noise = (Math.sin(i * 1.7) + Math.cos(i * 0.9)) * 0.1;
		const sim = i === positiveIdx ? 0.88 : Math.max(-0.35, 0.78 - 0.16 * distFromPos + noise);
		similarities.push(sim);
	}

	function softmax(logits: number[]): number[] {
		const max = Math.max(...logits);
		const exps = logits.map((l) => Math.exp(l - max));
		const sum = exps.reduce((s, e) => s + e, 0);
		return exps.map((e) => e / sum);
	}

	let probs = $derived.by(() => {
		const scaled = similarities.map((s) => s / tau);
		return softmax(scaled);
	});

	let lossInfo = $derived.by(() => {
		const p = probs[positiveIdx];
		const loss = -Math.log(Math.max(p, 1e-12));
		const logN = Math.log(N);
		const miBound = Math.max(0, logN - loss);
		return { loss, logN, miBound, posProb: p };
	});

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';

		const pad = canvasPad(w, 32);
		const labelGap = 16;
		const simH = 50; // height for similarity row
		const arrowH = 22;
		const xAxisH = 28;
		const probTopY = labelGap + simH + arrowH;
		const probH = h - probTopY - xAxisH;
		const baselineY = probTopY + probH;
		const slotW = (w - pad * 2) / N;
		const barW = Math.min(48, slotW * 0.58);

		// === Top row: similarity inputs ===
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.fillText('input similarity   s = E_audio · E_text  ∈ [−1, 1]', pad, 12);

		// Sim row baseline (zero line)
		const simZeroY = labelGap + simH * 0.55;
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.6;
		ctx.beginPath();
		ctx.moveTo(pad, simZeroY);
		ctx.lineTo(w - pad, simZeroY);
		ctx.stroke();

		// Similarity bars (centered on zero, positive up, negative down)
		const simHalfH = simH * 0.4;
		for (let i = 0; i < N; i++) {
			const cx = pad + (i + 0.5) * slotW;
			const s = similarities[i];
			const isPos = i === positiveIdx;
			const barX = cx - barW / 2;
			const barT = s >= 0 ? simZeroY - s * simHalfH : simZeroY;
			const barBot = s >= 0 ? simZeroY : simZeroY - s * simHalfH;
			ctx.fillStyle = isPos
				? 'rgba(224,112,32,0.85)'
				: s >= 0
					? 'rgba(41,121,255,0.45)'
					: 'rgba(214,56,100,0.5)';
			ctx.fillRect(barX, barT, barW, barBot - barT);

			// Value label
			ctx.fillStyle = isPos ? '#c8611a' : CANVAS_LABEL;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'center';
			ctx.fillText(s.toFixed(2), cx, s >= 0 ? barT - 3 : barBot + 9);
		}

		// === Middle: divide by τ + softmax arrow ===
		ctx.fillStyle = 'var(--text-muted)';
		ctx.fillStyle = '#4a4640';
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		const arrowY = labelGap + simH + arrowH / 2 + 3;
		ctx.fillText(
			`↓  divide by τ = ${tau.toFixed(tau < 0.1 ? 3 : 2)},  then softmax  ↓`,
			w / 2,
			arrowY
		);

		// === Bottom row: probabilities (linear scale) ===
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.fillText('softmax probability   p_i = exp(s_i/τ) / Σ exp(s_j/τ)', pad, probTopY - 4);

		// Probability baseline
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.6;
		ctx.beginPath();
		ctx.moveTo(pad, baselineY);
		ctx.lineTo(w - pad, baselineY);
		ctx.stroke();

		const maxProb = Math.max(...probs);
		const probScale = Math.max(maxProb, 1 / N);
		const plotH = probH - 10;

		// Uniform reference (1/N)
		const uniformY = baselineY - (1 / N / probScale) * plotH;
		ctx.strokeStyle = 'rgba(124,77,255,0.4)';
		ctx.setLineDash([4, 3]);
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(pad, uniformY);
		ctx.lineTo(w - pad, uniformY);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = 'rgba(124,77,255,0.75)';
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'right';
		ctx.fillText(`uniform 1/N = ${(1 / N).toFixed(3)}`, w - pad - 4, uniformY - 3);

		// Probability bars
		for (let i = 0; i < N; i++) {
			const cx = pad + (i + 0.5) * slotW;
			const barX = cx - barW / 2;
			// Ensure a minimum visible height when prob > 1e-6 so all bars are seen
			const rawH = (probs[i] / probScale) * plotH;
			const minVisH = probs[i] > 1e-6 ? 1.5 : 0;
			const barH = Math.max(rawH, minVisH);
			const barY = baselineY - barH;
			const isPos = i === positiveIdx;

			ctx.fillStyle = isPos ? 'rgba(224,112,32,0.9)' : 'rgba(41,121,255,0.55)';
			ctx.beginPath();
			ctx.roundRect(barX, barY, barW, barH, [3, 3, 0, 0]);
			ctx.fill();

			// Candidate label below baseline
			ctx.fillStyle = isPos ? '#e07020' : CANVAS_LABEL;
			ctx.font = canvasFont(w, isPos ? 11 : 10, isPos ? '600' : '');
			ctx.textAlign = 'center';
			ctx.fillText(isPos ? 'pos' : String(i + 1), cx, baselineY + 14);

			// Probability value above bar
			if (probs[i] > 0.005) {
				ctx.fillStyle = isPos ? '#c8611a' : 'rgba(41,121,255,0.9)';
				ctx.font = canvasFont(w, 9);
				ctx.fillText(probs[i].toFixed(probs[i] < 0.1 ? 3 : 2), cx, Math.max(barY - 4, probTopY + 8));
			}
		}
	}

	function setTau(value: number) {
		tauLog = Math.log10(value);
	}

	$effect(() => {
		// re-draw whenever tau (and therefore probs) changes
		void probs;
		draw();
	});

	onMount(() => {
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => window.removeEventListener('resize', onResize);
	});
</script>

<VizPanel title="Temperature τ shapes the softmax" titleColor="var(--orange)">
	{#snippet controls()}
		<label class="slider-label">
			<span>τ =</span>
			<input
				type="range"
				min="-2"
				max="0.7"
				step="0.01"
				bind:value={tauLog}
			/>
			<span class="tau-display">{tau.toFixed(tau < 0.1 ? 3 : tau < 1 ? 2 : 2)}</span>
		</label>
		<VizButton color="var(--rose)" onclick={() => setTau(0.01)}>τ → 0</VizButton>
		<VizButton color="var(--orange)" onclick={() => setTau(0.07)}>0.07 (CLAP init)</VizButton>
		<VizButton color="var(--violet)" onclick={() => setTau(5)}>τ → ∞</VizButton>
	{/snippet}
	<canvas bind:this={canvas} height="280" style="height: 280px;"></canvas>
	{#snippet caption()}
		<strong>τ → 0:</strong> softmax becomes argmax — all probability on the positive (or the wrong negative if the positive isn't already closest). <strong>τ → ∞:</strong> uniform — every candidate gets 1/N = {(1 / N).toFixed(3)}.
		Current loss <code>−log P(pos)</code> = <strong>{lossInfo.loss.toFixed(3)}</strong> · MI lower bound <code>log N − L</code> = <strong>{lossInfo.miBound.toFixed(3)}</strong> nats (max log N = {lossInfo.logN.toFixed(3)}).
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		touch-action: none;
	}

	.slider-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.tau-display {
		min-width: 3.5em;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--orange);
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 160px;
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		outline: none;
		padding: 10px 0;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--orange);
		cursor: pointer;
		box-shadow: 0 0 6px var(--orange-glow);
	}

	@media (max-width: 640px) {
		input[type='range'] {
			width: 110px;
		}
	}
</style>
