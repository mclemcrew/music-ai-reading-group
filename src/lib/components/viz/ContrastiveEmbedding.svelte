<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	const N = 8;
	let tau = $state(0.07);
	let lr = $state(0.18);
	let stepsPerSecond = $state(10);
	const HIGHLIGHT = 2;

	type Pt = { x: number; y: number };

	function seededInit(): { a: Pt[]; t: Pt[] } {
		const a: Pt[] = [];
		const t: Pt[] = [];
		for (let i = 0; i < N; i++) {
			const aAng = ((i * 137 + 41) % 360) * (Math.PI / 180);
			const tAng = ((i * 199 + 113) % 360) * (Math.PI / 180);
			a.push({ x: Math.cos(aAng), y: Math.sin(aAng) });
			t.push({ x: Math.cos(tAng), y: Math.sin(tAng) });
		}
		return { a, t };
	}

	const _initSeed = seededInit();
	let audio: Pt[] = $state(_initSeed.a);
	let text: Pt[] = $state(_initSeed.t);
	let step = $state(0);
	let lossHistory: number[] = $state([]);
	let running = $state(false);
	let canvas: HTMLCanvasElement;
	let raf = 0;
	let lastStepAt = 0;

	function dot(p: Pt, q: Pt): number {
		return p.x * q.x + p.y * q.y;
	}

	function softmaxRow(anchor: Pt, candidates: Pt[]): number[] {
		const logits = candidates.map((c) => dot(anchor, c) / tau);
		const max = Math.max(...logits);
		const exps = logits.map((l) => Math.exp(l - max));
		const sum = exps.reduce((s, e) => s + e, 0);
		return exps.map((e) => e / sum);
	}

	function infoNCELoss(): number {
		let total = 0;
		for (let i = 0; i < N; i++) {
			const probsAT = softmaxRow(audio[i], text);
			const probsTA = softmaxRow(text[i], audio);
			total += -Math.log(Math.max(probsAT[i], 1e-12));
			total += -Math.log(Math.max(probsTA[i], 1e-12));
		}
		return total / (2 * N);
	}

	function normalize(p: Pt): Pt {
		const r = Math.hypot(p.x, p.y) || 1;
		return { x: p.x / r, y: p.y / r };
	}

	function trainStep() {
		const newA: Pt[] = audio.map((p) => ({ x: p.x, y: p.y }));
		const newT: Pt[] = text.map((p) => ({ x: p.x, y: p.y }));

		// Update audio embeddings: gradient of -log P(text_i | audio_i)
		for (let i = 0; i < N; i++) {
			const probs = softmaxRow(audio[i], text);
			let gx = 0,
				gy = 0;
			for (let j = 0; j < N; j++) {
				const w = j === i ? 1 - probs[j] : -probs[j];
				gx += w * text[j].x;
				gy += w * text[j].y;
			}
			newA[i].x += lr * gx;
			newA[i].y += lr * gy;
		}

		// Update text embeddings symmetrically
		for (let i = 0; i < N; i++) {
			const probs = softmaxRow(text[i], audio);
			let gx = 0,
				gy = 0;
			for (let j = 0; j < N; j++) {
				const w = j === i ? 1 - probs[j] : -probs[j];
				gx += w * audio[j].x;
				gy += w * audio[j].y;
			}
			newT[i].x += lr * gx;
			newT[i].y += lr * gy;
		}

		audio = newA.map(normalize);
		text = newT.map(normalize);
		step += 1;
		lossHistory = [...lossHistory, infoNCELoss()];
		if (lossHistory.length > 200) lossHistory = lossHistory.slice(-200);
	}

	function reset() {
		stopRun();
		const seed = seededInit();
		audio = seed.a;
		text = seed.t;
		step = 0;
		lossHistory = [infoNCELoss()];
	}

	function runToggle() {
		if (running) stopRun();
		else startRun();
	}

	function startRun() {
		running = true;
		lastStepAt = performance.now();
		const tick = (now: number) => {
			if (!running) return;
			const interval = 1000 / stepsPerSecond;
			if (now - lastStepAt >= interval) {
				trainStep();
				lastStepAt = now;
			}
			raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
	}

	function stopRun() {
		running = false;
		cancelAnimationFrame(raf);
	}

	function draw() {
		if (!canvas) return;
		if (audio.length !== N || text.length !== N) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const pad = canvasPad(w, 18);
		const lossPanelW = Math.max(180, w * 0.32);
		const embPanelW = w - lossPanelW - pad * 2 - 12;
		const embCx = pad + embPanelW / 2;
		const embCy = h / 2 + 4;
		const R = Math.min(embPanelW, h - 60) / 2 - 6;

		// === Left: 2D embedding plane ===
		// Unit circle
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 1;
		ctx.setLineDash([3, 3]);
		ctx.beginPath();
		ctx.arc(embCx, embCy, R, 0, Math.PI * 2);
		ctx.stroke();
		ctx.setLineDash([]);

		// Title for left panel
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.fillText('embedding space (unit circle)', pad, 16);

		// Pair connection lines
		for (let i = 0; i < N; i++) {
			const ax = embCx + audio[i].x * R;
			const ay = embCy - audio[i].y * R;
			const tx = embCx + text[i].x * R;
			const ty = embCy - text[i].y * R;
			const isHighlight = i === HIGHLIGHT;
			ctx.strokeStyle = isHighlight ? 'rgba(124,77,255,0.75)' : 'rgba(155,155,155,0.35)';
			ctx.lineWidth = isHighlight ? 1.6 : 0.8;
			ctx.beginPath();
			ctx.moveTo(ax, ay);
			ctx.lineTo(tx, ty);
			ctx.stroke();
		}

		// Audio dots
		for (let i = 0; i < N; i++) {
			const x = embCx + audio[i].x * R;
			const y = embCy - audio[i].y * R;
			const isHighlight = i === HIGHLIGHT;
			ctx.beginPath();
			ctx.arc(x, y, isHighlight ? 7 : 5, 0, Math.PI * 2);
			ctx.fillStyle = isHighlight ? '#e07020' : 'rgba(224,112,32,0.65)';
			ctx.fill();
			ctx.strokeStyle = '#ffffff';
			ctx.lineWidth = 1.2;
			ctx.stroke();
			if (isHighlight) {
				ctx.fillStyle = '#c8611a';
				ctx.font = canvasFont(w, 9, '600');
				ctx.textAlign = 'center';
				ctx.fillText(`a${i + 1}`, x, y - 11);
			}
		}

		// Text dots
		for (let i = 0; i < N; i++) {
			const x = embCx + text[i].x * R;
			const y = embCy - text[i].y * R;
			const isHighlight = i === HIGHLIGHT;
			ctx.beginPath();
			ctx.arc(x, y, isHighlight ? 7 : 5, 0, Math.PI * 2);
			ctx.fillStyle = isHighlight ? '#2979ff' : 'rgba(41,121,255,0.65)';
			ctx.fill();
			ctx.strokeStyle = '#ffffff';
			ctx.lineWidth = 1.2;
			ctx.stroke();
			if (isHighlight) {
				ctx.fillStyle = '#2360cc';
				ctx.font = canvasFont(w, 9, '600');
				ctx.textAlign = 'center';
				ctx.fillText(`t${i + 1}`, x, y - 11);
			}
		}

		// Legend at bottom of left panel
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.fillStyle = '#e07020';
		ctx.beginPath();
		ctx.arc(pad + 6, h - 14, 4, 0, Math.PI * 2);
		ctx.fill();
		ctx.fillText('audio  E^a', pad + 14, h - 11);
		ctx.fillStyle = '#2979ff';
		ctx.beginPath();
		ctx.arc(pad + 84, h - 14, 4, 0, Math.PI * 2);
		ctx.fill();
		ctx.fillText('text  E^t', pad + 92, h - 11);
		ctx.strokeStyle = 'rgba(124,77,255,0.75)';
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.moveTo(pad + 152, h - 14);
		ctx.lineTo(pad + 168, h - 14);
		ctx.stroke();
		ctx.fillStyle = CANVAS_LABEL;
		ctx.fillText('highlighted pair', pad + 174, h - 11);

		// === Right: loss curve ===
		const lossX = pad + embPanelW + 12;
		const lossY = 28;
		const lossW = lossPanelW;
		const lossH = h - lossY - 56;

		// Panel title
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.fillText('InfoNCE loss', lossX, 16);

		// Frame
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.6;
		ctx.beginPath();
		ctx.moveTo(lossX, lossY);
		ctx.lineTo(lossX, lossY + lossH);
		ctx.lineTo(lossX + lossW, lossY + lossH);
		ctx.stroke();

		// log N reference line (max theoretical for a uniform softmax)
		const yMax = Math.max(Math.log(N) * 1.05, lossHistory[0] ?? 0.5);
		const yMin = 0;
		const ly = (v: number) => lossY + lossH - ((v - yMin) / (yMax - yMin)) * lossH;
		const logN = Math.log(N);
		const logNy = ly(logN);
		ctx.strokeStyle = 'rgba(124,77,255,0.5)';
		ctx.setLineDash([4, 3]);
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(lossX, logNy);
		ctx.lineTo(lossX + lossW, logNy);
		ctx.stroke();
		ctx.setLineDash([]);
		ctx.fillStyle = '#7c4dff';
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'right';
		ctx.fillText(`log N = ${logN.toFixed(2)}`, lossX + lossW - 4, logNy - 4);

		// Loss curve
		if (lossHistory.length > 1) {
			const totalSteps = Math.max(120, lossHistory.length);
			ctx.strokeStyle = '#e07020';
			ctx.lineWidth = 2;
			ctx.beginPath();
			for (let i = 0; i < lossHistory.length; i++) {
				const x = lossX + (i / totalSteps) * lossW;
				const y = ly(Math.min(Math.max(lossHistory[i], yMin), yMax));
				i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
			}
			ctx.stroke();

			// Current loss dot
			const lastIdx = lossHistory.length - 1;
			const cx = lossX + (lastIdx / totalSteps) * lossW;
			const cy = ly(Math.min(Math.max(lossHistory[lastIdx], yMin), yMax));
			ctx.beginPath();
			ctx.arc(cx, cy, 4, 0, Math.PI * 2);
			ctx.fillStyle = '#e07020';
			ctx.fill();
		}

		// y axis ticks
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'right';
		[0, logN].forEach((v) => {
			ctx.fillText(v.toFixed(2), lossX - 4, ly(v) + 3);
		});

		// x axis labels (auto-rescale to current trajectory length)
		const totalStepsLabel = Math.max(120, lossHistory.length);
		ctx.textAlign = 'left';
		ctx.fillText('step 0', lossX, lossY + lossH + 14);
		ctx.textAlign = 'right';
		ctx.fillText(String(totalStepsLabel), lossX + lossW, lossY + lossH + 14);

		// === Bottom: readout for highlighted pair ===
		const probs = softmaxRow(audio[HIGHLIGHT], text);
		const posProb = probs[HIGHLIGHT];
		const curLoss = lossHistory[lossHistory.length - 1] ?? infoNCELoss();
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'left';
		ctx.fillText(
			`step ${step} · L = ${curLoss.toFixed(3)} · P(t${HIGHLIGHT + 1}|a${HIGHLIGHT + 1}) = ${posProb.toFixed(3)} · MI bound = ${Math.max(0, logN - curLoss).toFixed(3)} nats`,
			lossX,
			h - 14
		);
	}

	$effect(() => {
		void audio;
		void text;
		void step;
		void lossHistory;
		draw();
	});

	onMount(() => {
		reset();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			window.removeEventListener('resize', onResize);
			cancelAnimationFrame(raf);
		};
	});
</script>

<VizPanel title="Contrastive training in 2D embedding space" titleColor="var(--blue)">
	{#snippet controls()}
		<VizButton color="var(--orange)" active={running} onclick={runToggle}>
			{running ? '⏸ Pause' : '▶ Train'}
		</VizButton>
		<VizButton onclick={() => trainStep()}>+1 step</VizButton>
		<VizButton onclick={reset}>Reset</VizButton>
	{/snippet}
	<div class="param-row">
		<label class="param">
			<span class="param-name">τ</span>
			<input type="range" min="0.02" max="1" step="0.01" bind:value={tau} />
			<span class="param-val">{tau.toFixed(2)}</span>
		</label>
		<label class="param">
			<span class="param-name">lr</span>
			<input type="range" min="0.02" max="0.5" step="0.01" bind:value={lr} />
			<span class="param-val">{lr.toFixed(2)}</span>
		</label>
		<label class="param">
			<span class="param-name">speed</span>
			<input type="range" min="1" max="60" step="1" bind:value={stepsPerSecond} />
			<span class="param-val">{stepsPerSecond}/s</span>
		</label>
	</div>
	<canvas bind:this={canvas} height="320" style="height: 320px;"></canvas>
	{#snippet caption()}
		Each audio embedding (orange) and text embedding (blue) lives on the unit circle (the L2-normalization constraint). Pressing <strong>▶ Train</strong> runs gradient steps on the symmetric InfoNCE loss: paired (a<sub>i</sub>, t<sub>i</sub>) get pulled together, all other pairs get pushed apart. Drag <strong>τ</strong> to see the temperature/sharpness trade-off, <strong>lr</strong> to see step size effects (push it past 0.3 and watch it overshoot), <strong>speed</strong> to watch single steps. Pause anytime to inspect the state.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		touch-action: none;
	}

	.param-row {
		display: flex;
		gap: 1.2rem;
		flex-wrap: wrap;
		padding: 0.65rem 1.5rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
	}

	.param {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.param-name {
		min-width: 2.6em;
		font-family: var(--font-mono);
		color: var(--text);
		font-weight: 600;
	}

	.param-val {
		min-width: 3em;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--blue);
		text-align: right;
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 110px;
		height: 5px;
		background: var(--border);
		border-radius: 3px;
		outline: none;
		padding: 8px 0;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: var(--blue);
		cursor: pointer;
		box-shadow: 0 0 4px var(--blue-glow);
	}

	@media (max-width: 640px) {
		.param-row {
			padding: 0.5rem 1rem;
			gap: 0.75rem;
		}
		input[type='range'] {
			width: 80px;
		}
	}
</style>
