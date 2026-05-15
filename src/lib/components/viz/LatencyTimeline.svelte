<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import {
		setupCanvas,
		CANVAS_BG,
		CANVAS_LABEL,
		observeVisibility,
		canvasFont,
		canvasPad
	} from '$lib/utils/canvas';
	import { resumeAudio, playNote, midiToFreq } from '$lib/utils/synth';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;
	let raf = 0;

	// Mode toggle: standard cold-start vs. continuous prefill
	let prefillMode = $state(false);

	// Animation & audio state
	let t = $state(0);
	let playing = $state(false);
	let muted = $state(true);
	let lastTs = 0;

	// Audio scheduling: track which notes have already been triggered
	let lastHumanNote = -1;
	let lastAiNote = -1;

	// Timeline constants (in ms of simulated time)
	const HUMAN_PLAY_MS = 3000;
	const COLD_START_MS = 1800;
	const PREFILL_CHUNK_MS = 400;
	const PREFILL_CHUNKS = 7;
	const SPECULATIVE_MS = 150;
	const GENERATION_MS = 2400;
	const TOTAL_COLD = HUMAN_PLAY_MS + COLD_START_MS + GENERATION_MS;
	const TOTAL_PREFILL = HUMAN_PLAY_MS + SPECULATIVE_MS + GENERATION_MS;
	const CYCLE_MS = Math.max(TOTAL_COLD, TOTAL_PREFILL) + 800;

	const SPEED = 0.5;

	// Note sequences (MIDI numbers)
	// Human ascending phrase: C4 E4 G4 C5 E5 G5
	const HUMAN_NOTES = [60, 64, 67, 72, 76, 79];
	const HUMAN_NOTE_INTERVAL = HUMAN_PLAY_MS / HUMAN_NOTES.length;
	// AI responding phrase: G5 E5 C5 G4 E4 C4 (descending answer)
	const AI_NOTES = [79, 76, 72, 67, 64, 60];
	const AI_NOTE_INTERVAL = GENERATION_MS / AI_NOTES.length;

	function scheduleAudio() {
		if (muted || !playing) return;

		// Human notes during play phase
		const humanIdx = Math.floor(t / HUMAN_NOTE_INTERVAL);
		if (humanIdx >= 0 && humanIdx < HUMAN_NOTES.length && humanIdx !== lastHumanNote) {
			lastHumanNote = humanIdx;
			playNote({ midi: HUMAN_NOTES[humanIdx], duration: 0.35, gain: 0.14, type: 'triangle' });
		}

		// AI notes during generation phase
		const aiStart = prefillMode
			? HUMAN_PLAY_MS + SPECULATIVE_MS
			: HUMAN_PLAY_MS + COLD_START_MS;
		const aiIdx = Math.floor((t - aiStart) / AI_NOTE_INTERVAL);
		if (t >= aiStart && aiIdx >= 0 && aiIdx < AI_NOTES.length && aiIdx !== lastAiNote) {
			lastAiNote = aiIdx;
			playNote({ midi: AI_NOTES[aiIdx], duration: 0.35, gain: 0.14, type: 'sine' });
		}
	}

	function reset() {
		playing = false;
		t = 0;
		lastHumanNote = -1;
		lastAiNote = -1;
	}

	function togglePlay() {
		playing = !playing;
		if (playing && t >= CYCLE_MS) {
			t = 0;
			lastHumanNote = -1;
			lastAiNote = -1;
		}
		if (playing && !muted) resumeAudio();
		lastTs = performance.now();
	}

	function toggleMode() {
		prefillMode = !prefillMode;
		reset();
	}

	function toggleMute() {
		muted = !muted;
		if (!muted) resumeAudio();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		// ── Increased left padding so "Human" / "AI" labels fit ──
		const padL = canvasPad(w, 52);
		const padR = canvasPad(w, 14);
		const padT = canvasPad(w, 36);
		const padB = canvasPad(w, 48);

		const timelineW = w - padL - padR;
		const rowH = canvasPad(w, 38);
		const trackGap = canvasPad(w, 14);

		const rowY0 = padT;
		const rowY1 = padT + rowH + trackGap;

		const simDuration = prefillMode ? TOTAL_PREFILL : TOTAL_COLD;
		const px = timelineW / (simDuration + 200);
		const now = Math.min(t, simDuration + 200);

		function segment(
			startMs: number, endMs: number,
			row: number, color: string, alpha = 1
		) {
			const x0 = padL + startMs * px;
			const x1 = padL + Math.min(endMs, now) * px;
			if (x1 <= x0) return;
			const y = row === 0 ? rowY0 : rowY1;
			ctx.globalAlpha = alpha;
			ctx.fillStyle = color;
			ctx.beginPath();
			ctx.roundRect(x0, y, x1 - x0, rowH, 4);
			ctx.fill();
			ctx.globalAlpha = 1;
		}

		function progressBar(startMs: number, endMs: number, row: number, color: string) {
			const frac = Math.max(0, Math.min(1, (now - startMs) / (endMs - startMs)));
			if (frac <= 0) return;
			segment(startMs, startMs + (endMs - startMs) * frac, row, color);
		}

		// ── Row labels ───────────────────────────────────────────
		ctx.fillStyle = '#374151';
		ctx.font = canvasFont(w, 12);
		ctx.textAlign = 'right';
		const labelX = padL - 8;
		ctx.fillText('Human', labelX, rowY0 + rowH / 2 + 4);
		ctx.fillText('AI', labelX, rowY1 + rowH / 2 + 4);

		// ── Row backgrounds ──────────────────────────────────────
		[rowY0, rowY1].forEach((ry) => {
			ctx.fillStyle = '#f3f4f6';
			ctx.beginPath();
			ctx.roundRect(padL, ry, timelineW, rowH, 4);
			ctx.fill();
			ctx.strokeStyle = '#e5e7eb';
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.roundRect(padL, ry, timelineW, rowH, 4);
			ctx.stroke();
		});

		if (!prefillMode) {
			// ── STANDARD (cold-start) mode ──────────────────────────
			progressBar(0, HUMAN_PLAY_MS, 0, '#1a9e8f');
			progressBar(HUMAN_PLAY_MS, HUMAN_PLAY_MS + COLD_START_MS, 1, '#e03131');
			progressBar(HUMAN_PLAY_MS + COLD_START_MS, TOTAL_COLD, 1, '#3498DB');

			// Handover marker
			const handoverX = padL + HUMAN_PLAY_MS * px;
			if (now >= HUMAN_PLAY_MS) {
				ctx.strokeStyle = '#374151';
				ctx.lineWidth = 1.5;
				ctx.setLineDash([4, 3]);
				ctx.beginPath();
				ctx.moveTo(handoverX, rowY0 - 8);
				ctx.lineTo(handoverX, rowY1 + rowH + 8);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.fillStyle = '#374151';
				ctx.font = canvasFont(w, 10);
				ctx.textAlign = 'center';
				ctx.fillText('handover', handoverX, rowY0 - 12);
			}

			// Gap label
			if (now >= HUMAN_PLAY_MS + COLD_START_MS * 0.5) {
				const gapMidX = padL + (HUMAN_PLAY_MS + COLD_START_MS / 2) * px;
				ctx.fillStyle = '#ffffff';
				ctx.font = canvasFont(w, 11);
				ctx.textAlign = 'center';
				ctx.fillText('KV cache cold start', gapMidX, rowY1 + rowH / 2 + 4);
			}

			// Latency annotation — positioned below the tick marks
			if (now >= HUMAN_PLAY_MS + COLD_START_MS) {
				const x0 = padL + HUMAN_PLAY_MS * px;
				const x1 = padL + (HUMAN_PLAY_MS + COLD_START_MS) * px;
				const annY = rowY1 + rowH + 28;
				ctx.strokeStyle = '#e03131';
				ctx.lineWidth = 1.2;
				ctx.beginPath();
				ctx.moveTo(x0, annY);
				ctx.lineTo(x1, annY);
				ctx.stroke();
				[x0, x1].forEach((cx) => {
					ctx.beginPath();
					ctx.moveTo(cx, annY - 4);
					ctx.lineTo(cx, annY + 4);
					ctx.stroke();
				});
				ctx.fillStyle = '#e03131';
				ctx.font = canvasFont(w, 11);
				ctx.textAlign = 'center';
				ctx.fillText(`${(COLD_START_MS / 1000).toFixed(1)}s gap`, (x0 + x1) / 2, annY + 16);
			}
		} else {
			// ── PREFILL mode ────────────────────────────────────────
			progressBar(0, HUMAN_PLAY_MS, 0, '#1a9e8f');

			for (let i = 0; i < PREFILL_CHUNKS; i++) {
				const chunkStart = i * PREFILL_CHUNK_MS;
				const chunkEnd = chunkStart + PREFILL_CHUNK_MS * 0.7;
				const chunkEndCapped = Math.min(chunkEnd, HUMAN_PLAY_MS);
				progressBar(chunkStart, chunkEndCapped, 1, '#FF9500');
			}

			progressBar(HUMAN_PLAY_MS, HUMAN_PLAY_MS + SPECULATIVE_MS, 1, '#9B59B6');
			progressBar(HUMAN_PLAY_MS + SPECULATIVE_MS, TOTAL_PREFILL, 1, '#3498DB');

			const handoverX = padL + HUMAN_PLAY_MS * px;
			if (now >= HUMAN_PLAY_MS) {
				ctx.strokeStyle = '#374151';
				ctx.lineWidth = 1.5;
				ctx.setLineDash([4, 3]);
				ctx.beginPath();
				ctx.moveTo(handoverX, rowY0 - 8);
				ctx.lineTo(handoverX, rowY1 + rowH + 8);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.fillStyle = '#374151';
				ctx.font = canvasFont(w, 10);
				ctx.textAlign = 'center';
				ctx.fillText('handover', handoverX, rowY0 - 12);
			}

			if (now >= PREFILL_CHUNK_MS * 0.5) {
				ctx.fillStyle = '#ffffff';
				ctx.font = canvasFont(w, 9);
				ctx.textAlign = 'center';
				const visChunks = Math.min(PREFILL_CHUNKS, Math.floor(now / PREFILL_CHUNK_MS) + 1);
				for (let i = 0; i < visChunks; i++) {
					const cx = padL + (i * PREFILL_CHUNK_MS + PREFILL_CHUNK_MS * 0.35) * px;
					if (cx < handoverX - 5) {
						ctx.fillText(`c${i + 1}`, cx, rowY1 + rowH / 2 + 3);
					}
				}
			}

			if (now >= HUMAN_PLAY_MS + SPECULATIVE_MS * 0.5) {
				const specMidX = padL + (HUMAN_PLAY_MS + SPECULATIVE_MS / 2) * px;
				ctx.fillStyle = '#ffffff';
				ctx.font = canvasFont(w, 9);
				ctx.textAlign = 'center';
				ctx.fillText('spec.', specMidX, rowY1 + rowH / 2 + 3);
			}

			if (now >= HUMAN_PLAY_MS + SPECULATIVE_MS) {
				const x0 = padL + HUMAN_PLAY_MS * px;
				const x1 = padL + (HUMAN_PLAY_MS + SPECULATIVE_MS) * px;
				const annY = rowY1 + rowH + 28;
				ctx.strokeStyle = '#9B59B6';
				ctx.lineWidth = 1.2;
				ctx.beginPath();
				ctx.moveTo(x0, annY);
				ctx.lineTo(x1, annY);
				ctx.stroke();
				[x0, x1].forEach((cx) => {
					ctx.beginPath();
					ctx.moveTo(cx, annY - 4);
					ctx.lineTo(cx, annY + 4);
					ctx.stroke();
				});
				ctx.fillStyle = '#9B59B6';
				ctx.font = canvasFont(w, 11);
				ctx.textAlign = 'center';
				ctx.fillText(`${SPECULATIVE_MS}ms`, (x0 + x1) / 2, annY + 16);
			}
		}

		// ── Timeline tick marks ──────────────────────────────────
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		const tickInterval = 500;
		const ticks = Math.ceil(simDuration / tickInterval);
		for (let i = 0; i <= ticks; i++) {
			const ms = i * tickInterval;
			const tx = padL + ms * px;
			if (tx > w - padR) break;
			ctx.strokeStyle = '#d1d5db';
			ctx.lineWidth = 0.8;
			ctx.beginPath();
			ctx.moveTo(tx, rowY1 + rowH + 4);
			ctx.lineTo(tx, rowY1 + rowH + 9);
			ctx.stroke();
			if (i % 2 === 0) {
				ctx.fillText(`${(ms / 1000).toFixed(1)}s`, tx, rowY1 + rowH + 22);
			}
		}

		// ── Current time cursor ──────────────────────────────────
		if (now > 0 && now < simDuration + 100) {
			const curX = padL + now * px;
			ctx.strokeStyle = '#374151';
			ctx.lineWidth = 1;
			ctx.setLineDash([3, 3]);
			ctx.beginPath();
			ctx.moveTo(curX, rowY0 - 4);
			ctx.lineTo(curX, rowY1 + rowH + 4);
			ctx.stroke();
			ctx.setLineDash([]);
		}

		// ── Mode label ────────────────────────────────────────────
		ctx.fillStyle = prefillMode ? '#1a9e8f' : '#e03131';
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'left';
		ctx.fillText(
			prefillMode ? 'Continuous Prefill' : 'Standard (Cold Start)',
			padL,
			h - 10
		);

		// ── Legend ────────────────────────────────────────────────
		const legend = prefillMode
			? [
					{ color: '#1a9e8f', label: 'human plays' },
					{ color: '#FF9500', label: 'prefill chunks' },
					{ color: '#9B59B6', label: 'spec. re-eval' },
					{ color: '#3498DB', label: 'AI generates' }
				]
			: [
					{ color: '#1a9e8f', label: 'human plays' },
					{ color: '#e03131', label: 'cold KV start' },
					{ color: '#3498DB', label: 'AI generates' }
				];

		let legendX = w * 0.38;
		legend.forEach(({ color, label }) => {
			ctx.fillStyle = color;
			ctx.fillRect(legendX, h - 17, 10, 10);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'left';
			ctx.fillText(label, legendX + 14, h - 8);
			legendX += ctx.measureText(label).width + 30;
		});
	}

	function tick(ts: number) {
		if (!running) return;
		if (playing) {
			const dt = ts - lastTs;
			lastTs = ts;
			t = t + dt * SPEED;
			scheduleAudio();
			if (t >= CYCLE_MS) {
				t = CYCLE_MS;
				playing = false;
			}
			draw();
		}
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		const obs = observeVisibility(
			container,
			() => {
				running = true;
				draw();
				raf = requestAnimationFrame(tick);
			},
			() => {
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
	<VizPanel title="Latency Timeline" titleColor="var(--teal)">
		{#snippet controls()}
			<VizButton color="var(--teal)" onclick={toggleMute}>
				{muted ? '🔇 Unmute' : '🔊 Mute'}
			</VizButton>
			<VizButton color="var(--teal)" onclick={toggleMode}>
				{prefillMode ? 'Standard Mode' : 'Prefill Mode'}
			</VizButton>
			<VizButton color="var(--teal)" onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--teal)" onclick={reset}>
				Reset
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:200px"></canvas>
		{#snippet caption()}
			<b>Standard mode:</b> cold KV-cache computation creates a 1.8-second gap at handover — you hear the silence.
			<b>Prefill mode:</b> cache is updated in chunks while the human plays — the AI responds almost immediately. Toggle to compare. Unmute to hear the difference.
		{/snippet}
	</VizPanel>
</div>
