<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad, observeVisibility } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let visible = false;
	let running = true;
	let raf = 0;

	type Mode = 'autoregressive' | 'seq2seq' | 'sort' | 'anticipation';
	const MODES: Mode[] = ['autoregressive', 'seq2seq', 'sort', 'anticipation'];
	const MODE_LABELS: Record<Mode, string> = {
		autoregressive: 'Autoregressive',
		seq2seq: 'Seq2Seq',
		sort: 'Sort by time',
		anticipation: 'Anticipation'
	};

	let mode = $state<Mode>('autoregressive');
	let delta = $state(5);

	// Smooth blend weights — active mode lerps to 1, others to 0
	let weights: Record<Mode, number> = { autoregressive: 1, seq2seq: 0, sort: 0, anticipation: 0 };

	const TOTAL_TIME = 20;

	const controls = [
		{ label: 'C4', time: 5 },
		{ label: 'E4', time: 8 },
		{ label: 'G4', time: 11 },
		{ label: 'A4', time: 14 },
		{ label: 'C5', time: 17 }
	];

	const events = [
		{ label: 'E3', time: 5.2 },
		{ label: 'G3', time: 7.5 },
		{ label: 'B3', time: 9.8 },
		{ label: 'C3', time: 12.1 },
		{ label: 'E3', time: 14.5 },
		{ label: 'G3', time: 16.8 }
	];

	function lerp(a: number, b: number, t: number): number {
		return a + (b - a) * t;
	}

	let _canvasW = 900;

	function setMode(m: Mode) {
		mode = m;
	}

	function drawToken(
		ctx: CanvasRenderingContext2D,
		x: number, y: number, w: number, h: number,
		label: string, color: string, alpha: number
	) {
		const r = 4;
		if (alpha < 0.02) return;

		// Fill
		ctx.globalAlpha = alpha * 0.3;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.roundRect(x - w / 2, y, w, h, r);
		ctx.fill();

		// Stroke
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.roundRect(x - w / 2, y, w, h, r);
		ctx.stroke();

		// Label
		ctx.fillStyle = color;
		ctx.font = canvasFont(_canvasW, 11);
		ctx.textAlign = 'center';
		ctx.fillText(label, x, y + h / 2 + 4);
		ctx.globalAlpha = 1;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		_canvasW = w;
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = canvasPad(w, 14);
		const padR = canvasPad(w, 14);
		const padT = canvasPad(w, 14);
		const padB = canvasPad(w, 28);
		const timelineY = padT + (h - padT - padB) / 2;
		const plotL = padL;
		const plotR = w - padR;
		const plotW = plotR - plotL;

		const timeToX = (sec: number) => plotL + (sec / TOTAL_TIME) * plotW;

		const wAR = weights.autoregressive;
		const wS2S = weights.seq2seq;
		const wSort = weights.sort;
		const wAnt = weights.anticipation;

		// === Timeline axis ===
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.moveTo(plotL, timelineY);
		ctx.lineTo(plotR, timelineY);
		ctx.stroke();

		// Arrow
		ctx.fillStyle = '#dde0e6';
		ctx.beginPath();
		ctx.moveTo(plotR, timelineY - 3);
		ctx.lineTo(plotR + 5, timelineY);
		ctx.lineTo(plotR, timelineY + 3);
		ctx.fill();

		// Time ticks
		ctx.fillStyle = 'rgba(31,29,27,0.78)';
		ctx.font = canvasFont(w, 11, '500');
		ctx.textAlign = 'center';
		for (let s = 0; s <= TOTAL_TIME; s += 5) {
			const x = timeToX(s);
			ctx.strokeStyle = '#dde0e6';
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(x, timelineY - 3);
			ctx.lineTo(x, timelineY + 3);
			ctx.stroke();
			ctx.fillText(`${s}s`, x, timelineY + 14);
		}

		// === Token layout ===
		const tokW = Math.min(38, plotW / 14);
		const tokH = 22;
		const controlBaseY = timelineY - 18 - tokH;
		const eventBaseY = timelineY + 18;

		// Seq2seq positions: controls packed left, events packed right
		const s2sGap = tokW * 1.5; // gap between control block and event block
		const nCtrl = controls.length;
		const nEvt = events.length;
		const s2sTotalW = nCtrl * (tokW + 5) + s2sGap + nEvt * (tokW + 5);
		const s2sStartX = plotL + (plotW - s2sTotalW) / 2 + tokW / 2;
		const s2sEvtStartX = s2sStartX + nCtrl * (tokW + 5) + s2sGap;

		const controlAlpha = 1 - wAR;

		// === Draw controls ===
		for (let i = 0; i < nCtrl; i++) {
			const ctrl = controls[i];

			const xS2S = s2sStartX + i * (tokW + 5);
			const xSort = timeToX(ctrl.time);
			const xAnt = timeToX(Math.max(0, ctrl.time - delta));
			const xAR = xSort; // parked at time position when faded

			const x = xAR * wAR + xS2S * wS2S + xSort * wSort + xAnt * wAnt;

			drawToken(ctx, x, controlBaseY, tokW, tokH, ctrl.label, '#e07020', controlAlpha);

			// Connection lines from control to its target time on the event row
			const connAlpha = wAnt * 0.4 + wSort * 0.25;
			if (connAlpha > 0.02) {
				const targetX = timeToX(ctrl.time);
				ctx.globalAlpha = connAlpha;
				ctx.strokeStyle = '#e07020';
				ctx.lineWidth = 1;
				ctx.setLineDash([3, 3]);
				ctx.beginPath();
				ctx.moveTo(x, controlBaseY + tokH);
				ctx.quadraticCurveTo(
					(x + targetX) / 2, timelineY - 2,
					targetX, timelineY - 2
				);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.globalAlpha = 1;
			}
		}

		// === Draw events ===
		for (let i = 0; i < nEvt; i++) {
			const evt = events[i];

			// Events also move in Seq2Seq mode — pushed to right block
			const xS2S = s2sEvtStartX + i * (tokW + 5);
			const xTime = timeToX(evt.time);

			const x = xTime * (wAR + wSort + wAnt) + xS2S * wS2S;

			drawToken(ctx, x, eventBaseY, tokW, tokH, evt.label, '#1a9e8f', 1);
		}

		// === Seq2seq: long-range dependency arrow ===
		if (wS2S > 0.05) {
			const lastCtrlX = s2sStartX + (nCtrl - 1) * (tokW + 5);
			const firstEvtX = s2sEvtStartX;
			const labelY = eventBaseY + tokH + 22;

			// Curve that goes BELOW the event tokens
			ctx.globalAlpha = wS2S * 0.6;
			ctx.strokeStyle = '#6b7280';
			ctx.lineWidth = 1.5;
			ctx.setLineDash([5, 4]);
			ctx.beginPath();
			ctx.moveTo(lastCtrlX + tokW / 2 + 2, controlBaseY + tokH);
			ctx.bezierCurveTo(
				lastCtrlX + tokW * 2, labelY + 4,
				firstEvtX - tokW * 2, labelY + 4,
				firstEvtX - tokW / 2 - 2, eventBaseY + tokH
			);
			ctx.stroke();
			ctx.setLineDash([]);

			// Label below everything
			ctx.fillStyle = 'rgba(31,29,27,0.85)';
			ctx.font = canvasFont(w, 13, '600');
			ctx.textAlign = 'center';
			ctx.globalAlpha = wS2S;
			ctx.fillText('long-range dependency', (lastCtrlX + firstEvtX) / 2, labelY + 6);
			ctx.globalAlpha = 1;
		}

		// === Sort: warning annotation ===
		if (wSort > 0.3) {
			ctx.globalAlpha = Math.min(1, (wSort - 0.3) / 0.4) * 0.85;
			ctx.fillStyle = '#e07020';
			ctx.font = canvasFont(w, 13);
			ctx.textAlign = 'center';
			ctx.fillText('not a stopping time \u2014 can\'t sample autoregressively', plotL + plotW / 2, controlBaseY - 8);
			ctx.globalAlpha = 1;
		}

		// === Anticipation: delta bracket ===
		if (wAnt > 0.2) {
			const ctrl = controls[2];
			const antX = timeToX(Math.max(0, ctrl.time - delta));
			const targetX = timeToX(ctrl.time);
			const bracketY = controlBaseY - 18;

			ctx.globalAlpha = Math.min(1, (wAnt - 0.2) / 0.3);
			ctx.strokeStyle = '#2979ff';
			ctx.lineWidth = 1.2;

			ctx.beginPath();
			ctx.moveTo(antX, bracketY + 6);
			ctx.lineTo(antX, bracketY);
			ctx.lineTo(targetX, bracketY);
			ctx.lineTo(targetX, bracketY + 6);
			ctx.stroke();

			ctx.fillStyle = '#2979ff';
			ctx.font = canvasFont(w, 13);
			ctx.textAlign = 'center';
			ctx.fillText(`\u03B4 = ${delta}s`, (antX + targetX) / 2, bracketY - 6);
			ctx.globalAlpha = 1;
		}

		// === Autoregressive: label in place of controls ===
		if (wAR > 0.3) {
			ctx.globalAlpha = Math.min(1, (wAR - 0.3) / 0.4);
			ctx.fillStyle = 'rgba(31,29,27,0.85)';
			ctx.font = canvasFont(w, 13, '600');
			ctx.textAlign = 'center';
			ctx.fillText('no controls \u2014 unconditional generation', plotL + plotW / 2, controlBaseY + tokH / 2 + 5);
			ctx.globalAlpha = 1;
		}

		// === Legend ===
		ctx.font = canvasFont(w, 12, '600');
		ctx.textAlign = 'left';
		ctx.fillStyle = '#c05d16';
		ctx.globalAlpha = Math.max(0.65, controlAlpha);
		ctx.fillText('controls (melody)', plotL, h - 8);
		ctx.globalAlpha = 1;
		ctx.fillStyle = '#147c70';
		ctx.textAlign = 'right';
		ctx.fillText('events (accompaniment)', plotR, h - 8);
	}

	function tick() {
		if (!running) return;
		let needsDraw = false;
		for (const m of MODES) {
			const target = m === mode ? 1 : 0;
			const diff = target - weights[m];
			if (Math.abs(diff) > 0.005) {
				weights[m] += diff * 0.1;
				needsDraw = true;
			}
		}
		if (needsDraw) draw();
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
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

	$effect(() => {
		delta;
		draw();
	});
</script>

<div bind:this={container}>
	<VizPanel title="Anticipatory Interleaving" titleColor="var(--blue)">
		{#snippet controls()}
			{#each MODES as m}
				<VizButton color="var(--blue)" active={mode === m} onclick={() => setMode(m)}>
					{MODE_LABELS[m]}
				</VizButton>
			{/each}
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:260px"></canvas>
		{#if mode === 'anticipation'}
			<div class="delta-row">
				<label class="delta-label">
					<span class="delta-symbol">&delta;</span>
					<input
						type="range"
						min="1"
						max="10"
						step="1"
						bind:value={delta}
						class="delta-slider"
					/>
					<span class="delta-value">{delta}s</span>
				</label>
			</div>
		{/if}
		{#snippet caption()}
			{#if mode === 'autoregressive'}
				Unconditional generation: the model produces events left-to-right with no control input. No conditioning, no infilling.
			{:else if mode === 'seq2seq'}
				All controls are prepended before events. The model can condition on them, but controls are far from the events they influence.
			{:else if mode === 'sort'}
				Controls placed at their actual time, interleaved with events by timestamp. Preserves locality but violates stopping-time constraints — the model can't tell during generation when to insert the next control.
			{:else}
				Controls placed &delta; seconds before their target events. Preserves locality AND is a valid stopping time for autoregressive sampling. Drag the slider to see how &delta; affects placement.
			{/if}
		{/snippet}
	</VizPanel>
</div>

<style>
	.delta-row {
		display: flex;
		justify-content: center;
		padding: 0.4rem 0.75rem 0;
	}

	.delta-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.delta-symbol {
		color: var(--blue);
		font-size: 0.9rem;
	}

	.delta-slider {
		width: 140px;
		accent-color: var(--blue);
		cursor: pointer;
	}

	.delta-value {
		color: var(--blue);
		min-width: 2.5ch;
		text-align: right;
	}
</style>
