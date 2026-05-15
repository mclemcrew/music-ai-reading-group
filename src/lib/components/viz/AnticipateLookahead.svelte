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
	import { resumeAudio, playNote, playChord, chordToMidis, midiToFreq } from '$lib/utils/synth';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;
	let raf = 0;

	let lookaheadOn = $state(true);
	let playing = $state(false);
	let muted = $state(true);
	let phase = $state(0);
	let barCount = $state(0);
	let lastTs = 0;

	// Audio tracking
	let lastChordBar = -1;
	let lastMelodyBeat = -1;

	const BARS_TO_SHOW = 8;
	const LOOKAHEAD_BARS = 2;
	const BEATS_PER_BAR = 4;
	const BAR_MS = 2000;
	const SPEED = 0.8;

	const CHORDS = ['C', 'Am', 'F', 'G', 'Em', 'Am', 'Dm', 'G'];
	const CHORD_COLORS = {
		committed: '#3498DB',
		uncommitted: '#9B59B6',
		playing: '#FF9500',
		human: '#e07020'
	};

	// Human melody: semitones above C4 per beat per bar
	const MELODY = [
		[0, 4, 7, 12],
		[9, 7, 4, 0],
		[5, 7, 9, 10],
		[7, 5, 4, 2],
		[4, 5, 7, 9],
		[9, 7, 5, 4],
		[2, 4, 5, 7],
		[7, 9, 10, 12]
	];

	const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B'];

	function scheduleAudio() {
		if (muted || !playing) return;

		const currentBar = barCount;
		const currentBeat = Math.floor(phase * BEATS_PER_BAR);

		// Chord: play on bar change
		if (currentBar !== lastChordBar) {
			lastChordBar = currentBar;
			const chordIdx = currentBar % CHORDS.length;
			const midis = chordToMidis(CHORDS[chordIdx], 3);
			playChord(midis, { duration: 0.6, gain: 0.14, type: 'sine' });
		}

		// Melody: play on beat change
		const beatId = currentBar * BEATS_PER_BAR + currentBeat;
		if (beatId !== lastMelodyBeat) {
			lastMelodyBeat = beatId;
			const melIdx = currentBar % MELODY.length;
			const semi = MELODY[melIdx][currentBeat];
			playNote({ midi: 60 + semi, duration: 0.2, gain: 0.12, type: 'triangle' });
		}
	}

	function reset() {
		playing = false;
		phase = 0;
		barCount = 0;
		lastChordBar = -1;
		lastMelodyBeat = -1;
	}

	function togglePlay() {
		playing = !playing;
		if (playing && !muted) resumeAudio();
		lastTs = performance.now();
	}

	function toggleLookahead() {
		lookaheadOn = !lookaheadOn;
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

		const padL = canvasPad(w, 14);
		const padR = canvasPad(w, 14);
		const padT = canvasPad(w, 18);
		const padB = canvasPad(w, 38);

		const gridW = w - padL - padR;
		const gridH = h - padT - padB;

		// Layout: chord waterfall (top 50%), melody row (bottom 40%), gap between
		const waterfallH = gridH * 0.50;
		const gapH = gridH * 0.06;
		const melodyH = gridH * 0.38;
		const melodyY = padT + waterfallH + gapH;

		const barW = gridW / BARS_TO_SHOW;
		const currentBar = barCount;

		// ── Section labels — positioned clearly ──────────────────
		ctx.fillStyle = '#374151';
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'left';
		ctx.fillText('AI chords', padL, padT - 4);
		ctx.fillText('Human melody', padL, melodyY - 4);

		// ── Background grid lines ────────────────────────────────
		ctx.strokeStyle = '#e5e7eb';
		ctx.lineWidth = 0.6;
		for (let b = 0; b <= BARS_TO_SHOW; b++) {
			const bx = padL + b * barW;
			ctx.beginPath();
			ctx.moveTo(bx, padT);
			ctx.lineTo(bx, padT + waterfallH);
			ctx.stroke();
		}

		// ── "Now" playhead — drawn early so label is under section header ──
		const pastBars = 1;
		const playheadX = padL + pastBars * barW;

		// Playhead line
		ctx.strokeStyle = '#374151';
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.moveTo(playheadX, padT);
		ctx.lineTo(playheadX, melodyY + melodyH);
		ctx.stroke();

		// Playhead label — right-aligned just to the left of the line
		ctx.fillStyle = '#374151';
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'right';
		ctx.fillText('now', playheadX - 5, padT - 4);

		// Playhead triangle at top
		ctx.fillStyle = '#374151';
		ctx.beginPath();
		ctx.moveTo(playheadX - 5, padT);
		ctx.lineTo(playheadX + 5, padT);
		ctx.lineTo(playheadX, padT + 7);
		ctx.fill();

		// ── Draw chord cells (waterfall) ─────────────────────────
		for (let col = 0; col < BARS_TO_SHOW; col++) {
			const absBar = currentBar - pastBars + col;
			if (absBar < 0) continue;

			const chordIdx = absBar % CHORDS.length;
			const chord = CHORDS[chordIdx];
			const barsAhead = absBar - currentBar;

			const cellX = padL + (col - phase) * barW;
			if (cellX + barW < padL || cellX > padL + gridW) continue;

			const cellH = waterfallH * 0.82;
			const cellY = padT + (waterfallH - cellH) / 2;
			const cellPad = 3;

			let fillColor: string;
			let alpha: number;

			if (barsAhead < 0) {
				fillColor = '#1a9e8f';
				alpha = 0.2;
			} else if (barsAhead === 0) {
				fillColor = CHORD_COLORS.playing;
				alpha = 1;
			} else if (lookaheadOn && barsAhead <= LOOKAHEAD_BARS) {
				fillColor = CHORD_COLORS.committed;
				alpha = 0.65 - barsAhead * 0.12;
			} else if (lookaheadOn && barsAhead <= LOOKAHEAD_BARS + 1) {
				fillColor = CHORD_COLORS.uncommitted;
				alpha = 0.3;
			} else if (!lookaheadOn && barsAhead > 0) {
				fillColor = '#9ca3af';
				alpha = 0.15;
			} else {
				continue;
			}

			// Fill
			ctx.globalAlpha = alpha;
			ctx.fillStyle = fillColor;
			ctx.beginPath();
			ctx.roundRect(cellX + cellPad, cellY, barW - cellPad * 2, cellH, 4);
			ctx.fill();
			ctx.globalAlpha = 1;

			// Stroke
			if (barsAhead === 0) {
				ctx.strokeStyle = CHORD_COLORS.playing;
				ctx.lineWidth = 2;
			} else if (barsAhead < 0) {
				ctx.strokeStyle = '#1a9e8f';
				ctx.lineWidth = 0.8;
			} else if (lookaheadOn && barsAhead <= LOOKAHEAD_BARS) {
				ctx.strokeStyle = CHORD_COLORS.committed;
				ctx.lineWidth = 1;
			} else {
				ctx.strokeStyle = '#9ca3af';
				ctx.lineWidth = 0.6;
			}
			ctx.beginPath();
			ctx.roundRect(cellX + cellPad, cellY, barW - cellPad * 2, cellH, 4);
			ctx.stroke();

			// Chord label
			const showLabel =
				barsAhead >= -1 && barsAhead <= (lookaheadOn ? LOOKAHEAD_BARS + 1 : 1);
			if (showLabel) {
				const isNow = barsAhead === 0;
				ctx.globalAlpha = isNow ? 1 : Math.max(0.4, alpha);
				ctx.fillStyle = isNow ? '#ffffff' : '#374151';
				ctx.font = canvasFont(w, isNow ? 16 : 14);
				ctx.textAlign = 'center';
				ctx.fillText(chord, cellX + barW / 2, cellY + cellH / 2 + 5);
				ctx.globalAlpha = 1;

				// Status label below chord name
				if (!isNow && barsAhead > 0 && lookaheadOn) {
					ctx.fillStyle = barsAhead <= LOOKAHEAD_BARS ? CHORD_COLORS.committed : CHORD_COLORS.uncommitted;
					ctx.font = canvasFont(w, 8);
					ctx.fillText(
						barsAhead <= LOOKAHEAD_BARS ? 'committed' : 'flexible',
						cellX + barW / 2,
						cellY + cellH / 2 + 20
					);
				}
			}
		}

		// ── Commitment boundary ──────────────────────────────────
		if (lookaheadOn) {
			const commitX = padL + (pastBars + LOOKAHEAD_BARS) * barW;
			if (commitX < padL + gridW) {
				ctx.strokeStyle = CHORD_COLORS.committed;
				ctx.lineWidth = 1.2;
				ctx.setLineDash([5, 4]);
				ctx.beginPath();
				ctx.moveTo(commitX, padT);
				ctx.lineTo(commitX, padT + waterfallH);
				ctx.stroke();
				ctx.setLineDash([]);
				ctx.fillStyle = CHORD_COLORS.committed;
				ctx.font = canvasFont(w, 9);
				ctx.textAlign = 'center';
				ctx.fillText('commit deadline', commitX, padT + waterfallH + 14);
			}
		}

		// ── Human melody row ─────────────────────────────────────
		ctx.fillStyle = '#fef9f0';
		ctx.beginPath();
		ctx.roundRect(padL, melodyY, gridW, melodyH, 3);
		ctx.fill();
		ctx.strokeStyle = '#e5e7eb';
		ctx.lineWidth = 0.8;
		ctx.beginPath();
		ctx.roundRect(padL, melodyY, gridW, melodyH, 3);
		ctx.stroke();

		const beatW = barW / BEATS_PER_BAR;
		const noteRectH = melodyH * 0.22;

		for (let col = 0; col < BARS_TO_SHOW; col++) {
			const absBar = currentBar - pastBars + col;
			if (absBar < 0) continue;
			const melIdx = absBar % MELODY.length;
			const barsAhead = absBar - currentBar;

			for (let beat = 0; beat < BEATS_PER_BAR; beat++) {
				const semi = MELODY[melIdx][beat];
				// Map semitone (0–12) → vertical position
				const noteY = melodyY + melodyH * 0.08 + (1 - semi / 13) * (melodyH * 0.72);
				const noteX = padL + (col - phase) * barW + beat * beatW + beatW * 0.08;
				const noteW = beatW * 0.78;
				if (noteX + noteW < padL || noteX > padL + gridW) continue;

				const isCurrentBeat =
					barsAhead === 0 && beat === Math.floor(phase * BEATS_PER_BAR);

				ctx.globalAlpha = barsAhead < 0 ? 0.25 : barsAhead === 0 ? 0.9 : 0.45;
				ctx.fillStyle = isCurrentBeat ? '#FF9500' : '#e07020';
				ctx.beginPath();
				ctx.roundRect(noteX, noteY, noteW, noteRectH, 2);
				ctx.fill();

				// Border for current beat
				if (isCurrentBeat) {
					ctx.strokeStyle = '#FF9500';
					ctx.lineWidth = 1.5;
					ctx.beginPath();
					ctx.roundRect(noteX, noteY, noteW, noteRectH, 2);
					ctx.stroke();
				}

				ctx.globalAlpha = 1;

				// Note name inside the rect (if big enough)
				if (barsAhead === 0 && noteW > 20) {
					ctx.fillStyle = '#ffffff';
					ctx.font = canvasFont(w, 9);
					ctx.textAlign = 'center';
					ctx.fillText(
						NOTE_NAMES[semi % 12],
						noteX + noteW / 2,
						noteY + noteRectH / 2 + 3
					);
				}
			}
		}

		// ── Server request pulse ─────────────────────────────────
		const reqCycle = (phase * BAR_MS) % 600;
		if (playing && reqCycle < 300) {
			const reqAlpha = Math.sin((reqCycle / 300) * Math.PI) * 0.6;
			ctx.globalAlpha = reqAlpha;
			ctx.fillStyle = '#6741d9';
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'right';
			ctx.fillText('server request', w - padR, padT + waterfallH / 2);
			ctx.globalAlpha = 1;
		}

		// ── Legend ────────────────────────────────────────────────
		const legend = [
			{ color: CHORD_COLORS.playing, label: 'playing now' },
			{ color: CHORD_COLORS.committed, label: 'committed' },
			...(lookaheadOn
				? [{ color: CHORD_COLORS.uncommitted, label: 'uncommitted' }]
				: []),
			{ color: '#e07020', label: 'human melody' }
		];

		let lx = padL;
		legend.forEach(({ color, label }) => {
			ctx.fillStyle = color;
			ctx.fillRect(lx, h - 14, 9, 9);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 10);
			ctx.textAlign = 'left';
			ctx.fillText(label, lx + 13, h - 6);
			lx += ctx.measureText(label).width + 30;
		});

		// Mode label
		ctx.fillStyle = lookaheadOn ? '#3498DB' : '#9ca3af';
		ctx.font = canvasFont(w, 11);
		ctx.textAlign = 'right';
		ctx.fillText(
			lookaheadOn ? `Lookahead: ${LOOKAHEAD_BARS} bars` : 'No lookahead',
			w - padR,
			h - 6
		);
	}

	function tick(ts: number) {
		if (!running) return;
		if (playing) {
			const dt = ts - lastTs;
			lastTs = ts;
			phase += (dt * SPEED) / BAR_MS;
			if (phase >= 1) {
				phase -= 1;
				barCount = (barCount + 1) % (CHORDS.length * 2);
			}
			scheduleAudio();
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
	<VizPanel title="Anticipation & Lookahead" titleColor="var(--blue)">
		{#snippet controls()}
			<VizButton color="var(--blue)" onclick={toggleMute}>
				{muted ? '🔇 Unmute' : '🔊 Mute'}
			</VizButton>
			<VizButton color="var(--blue)" onclick={toggleLookahead}>
				{lookaheadOn ? 'Disable Lookahead' : 'Enable Lookahead'}
			</VizButton>
			<VizButton color="var(--blue)" onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--blue)" onclick={reset}>
				Reset
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:240px"></canvas>
		{#snippet caption()}
			The waterfall display: AI chord predictions cascade toward the playhead. <b>With lookahead</b>, committed chords (blue, solid) are shown 2 bars ahead — the human can anticipate and react. Uncommitted chords (purple) may still change. <b>Without lookahead</b>, the future is opaque. Unmute to hear the melody and chords.
		{/snippet}
	</VizPanel>
</div>
