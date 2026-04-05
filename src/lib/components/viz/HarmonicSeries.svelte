<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_GRID, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let f0 = $state(440);
	let playing = $state(false);
	const nHarmonics = 8;
	let amps: number[] = [];
	let draggingK = -1;

	// Web Audio
	let audioCtx: AudioContext | null = null;
	let oscillators: { osc: OscillatorNode; gain: GainNode }[] = [];
	let masterGain: GainNode | null = null;

	let _layout: any = {};

	function initAmps() {
		amps = [];
		for (let k = 1; k <= nHarmonics; k++) amps.push(1 / k);
	}
	initAmps();

	function startAudio() {
		if (!audioCtx) audioCtx = new AudioContext();
		if (audioCtx.state === 'suspended') audioCtx.resume();

		masterGain = audioCtx.createGain();
		masterGain.gain.value = 0.15;
		masterGain.connect(audioCtx.destination);

		oscillators = [];
		for (let k = 1; k <= nHarmonics; k++) {
			const osc = audioCtx.createOscillator();
			const gain = audioCtx.createGain();
			osc.type = 'sine';
			osc.frequency.value = k * f0;
			gain.gain.value = amps[k - 1];
			osc.connect(gain);
			gain.connect(masterGain);
			osc.start();
			oscillators.push({ osc, gain });
		}
		playing = true;
	}

	function stopAudio() {
		if (masterGain && audioCtx) {
			masterGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.05);
			setTimeout(() => {
				oscillators.forEach((o) => o.osc.stop());
				oscillators = [];
				masterGain?.disconnect();
				masterGain = null;
			}, 100);
		}
		playing = false;
	}

	function updateAudio() {
		if (!playing || !audioCtx) return;
		const t = audioCtx.currentTime;
		oscillators.forEach((o, i) => {
			o.osc.frequency.setTargetAtTime((i + 1) * f0, t, 0.02);
			o.gain.gain.setTargetAtTime(amps[i], t, 0.02);
		});
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const barRegionH = h * 0.55;
		const waveRegionY = h * 0.62;
		const waveRegionH = h * 0.32;
		const pad = canvasPad(w, 20);
		const barAreaW = w - pad * 2;
		const slotW = barAreaW / nHarmonics;
		const barW = Math.min(36, slotW * 0.55);
		const maxBarH = barRegionH - 30;

		_layout = { barRegionH, waveRegionY, waveRegionH, pad, barAreaW, slotW, barW, maxBarH, w, h };

		// Separator
		ctx.strokeStyle = CANVAS_GRID;
		ctx.lineWidth = 0.5;
		ctx.beginPath();
		ctx.moveTo(pad, waveRegionY - 6);
		ctx.lineTo(w - pad, waveRegionY - 6);
		ctx.stroke();

		// Harmonic bars
		for (let k = 1; k <= nHarmonics; k++) {
			const freq = k * f0;
			const amp = amps[k - 1];
			const cx = pad + (k - 0.5) * slotW;
			const barH = amp * maxBarH;
			const barX = cx - barW / 2;
			const barY = barRegionH - barH;
			const alpha = 0.35 + 0.65 * amp;
			const isActive = draggingK === k;

			if (isActive) {
				ctx.fillStyle = 'rgba(224,112,32,0.06)';
				ctx.fillRect(barX - 4, 0, barW + 8, barRegionH);
			}

			ctx.fillStyle = 'rgba(224,112,32,' + alpha + ')';
			ctx.beginPath();
			ctx.roundRect(barX, barY, barW, barH, [3, 3, 0, 0]);
			ctx.fill();

			// Drag handle — larger on touch
			const handleR = 'ontouchstart' in window ? 8 : 4;
			ctx.beginPath();
			ctx.arc(cx, barY, handleR, 0, Math.PI * 2);
			ctx.fillStyle = isActive ? '#e07020' : 'rgba(224,112,32,0.5)';
			ctx.fill();

			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 12);
			ctx.textAlign = 'center';
			ctx.fillText(
				freq >= 1000 ? (freq / 1000).toFixed(1) + 'k' : String(freq),
				cx,
				Math.min(barY - 8, barRegionH - maxBarH - 2)
			);
			ctx.fillStyle = k === 1 ? '#e07020' : CANVAS_LABEL;
			ctx.fillText('k=' + k, cx, barRegionH + 14);
			ctx.textAlign = 'left';
		}

		// Waveform preview
		const waveMid = waveRegionY + waveRegionH / 2;
		const waveAmp = waveRegionH * 0.4;
		const nSamp = 300;
		const cycles = 3;

		let maxV = 0;
		const vals: number[] = [];
		for (let i = 0; i < nSamp; i++) {
			const t = i / nSamp;
			let v = 0;
			for (let k = 1; k <= nHarmonics; k++) {
				v += amps[k - 1] * Math.sin(2 * Math.PI * k * cycles * t);
			}
			vals.push(v);
			if (Math.abs(v) > maxV) maxV = Math.abs(v);
		}
		const norm = maxV > 0 ? 1 / maxV : 1;

		ctx.beginPath();
		ctx.strokeStyle = '#e07020';
		ctx.lineWidth = 1.8;
		for (let i = 0; i < nSamp; i++) {
			const x = pad + (i / nSamp) * barAreaW;
			const y = waveMid - vals[i] * norm * waveAmp;
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = '12px "DM Mono", monospace';
		ctx.fillText('summed waveform \u2014 drag bars to reshape', pad, waveRegionY + 4);
	}

	function getCanvasPos(e: MouseEvent | TouchEvent) {
		const rect = canvas.getBoundingClientRect();
		const src = 'touches' in e ? e.touches[0] : e;
		return { x: src.clientX - rect.left, y: src.clientY - rect.top };
	}

	function findBar(pos: { x: number; y: number }) {
		const { pad, slotW, barRegionH } = _layout;
		for (let k = 1; k <= nHarmonics; k++) {
			const cx = pad + (k - 0.5) * slotW;
			if (Math.abs(pos.x - cx) < slotW / 2 && pos.y < barRegionH + 5) return k;
		}
		return -1;
	}

	function updateAmp(pos: { x: number; y: number }) {
		if (draggingK < 1) return;
		const { barRegionH, maxBarH } = _layout;
		amps[draggingK - 1] = Math.max(0, Math.min(1, (barRegionH - pos.y) / maxBarH));
		draw();
		updateAudio();
	}

	function onSliderInput() {
		draw();
		updateAudio();
	}

	function resetAll() {
		initAmps();
		f0 = 440;
		draw();
		updateAudio();
	}

	onMount(() => {
		draw();

		const onResize = () => draw();
		window.addEventListener('resize', onResize);

		const onMouseUp = () => {
			draggingK = -1;
			draw();
		};
		window.addEventListener('mouseup', onMouseUp);

		return () => {
			window.removeEventListener('resize', onResize);
			window.removeEventListener('mouseup', onMouseUp);
			if (playing) stopAudio();
		};
	});
</script>

<VizPanel title="Harmonic Series" titleColor="var(--orange)">
	{#snippet controls()}
		<label class="slider-label">
			<span class="mono">f0</span>
			<input
				type="range"
				min="100"
				max="1000"
				step="1"
				bind:value={f0}
				oninput={onSliderInput}
			/>
			<span class="mono freq-display">{f0} Hz</span>
		</label>
		<VizButton active={playing} onclick={() => (playing ? stopAudio() : startAudio())}>
			{playing ? 'Stop' : 'Play'}
		</VizButton>
		<VizButton onclick={resetAll}>Reset</VizButton>
	{/snippet}
	<canvas
		bind:this={canvas}
		height="280"
		onmousedown={(e) => {
			draggingK = findBar(getCanvasPos(e));
			if (draggingK > 0) updateAmp(getCanvasPos(e));
		}}
		onmousemove={(e) => {
			if (draggingK < 1) {
				const k = findBar(getCanvasPos(e));
				canvas.style.cursor = k > 0 ? 'ns-resize' : 'default';
				return;
			}
			updateAmp(getCanvasPos(e));
		}}
		ontouchstart={(e) => {
			e.preventDefault();
			draggingK = findBar(getCanvasPos(e));
			if (draggingK > 0) updateAmp(getCanvasPos(e));
		}}
		ontouchmove={(e) => {
			e.preventDefault();
			updateAmp(getCanvasPos(e));
		}}
		ontouchend={() => {
			draggingK = -1;
			draw();
		}}
	></canvas>
	{#snippet caption()}
		Drag the harmonic bars to reshape the timbre. Toggle "Play" to hear the result.
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
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.freq-display {
		min-width: 4.5em;
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 140px;
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		outline: none;
		padding: 10px 0;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--orange);
		cursor: pointer;
		box-shadow: 0 0 8px var(--orange-glow);
	}

	@media (max-width: 640px) {
		input[type='range'] {
			width: 100px;
		}
	}
</style>
