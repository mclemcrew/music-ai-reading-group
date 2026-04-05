<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, observeVisibility, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let visible = false;
	let running = true;
	let playing = $state(false);
	let activeIdx = $state(-1);
	let startTime = 0;

	const TOKEN_MS = 750; // ms to highlight each token

	// Token sequence for a C major chord (C4–E4–G4 then release)
	const tokens = [
		{ label: 'Inst[0]', desc: 'Instrument → Piano (GM 0)', color: '#1a9e8f' },
		{ label: 'Time[0]', desc: 'Time → t = 0 ms', color: '#e07020' },
		{ label: 'On', desc: 'Note-On events follow', color: '#7c4dff' },
		{ label: 'Note[60]', desc: 'Note → C4 (MIDI 60)', color: '#2979ff' },
		{ label: 'Note[64]', desc: 'Note → E4 (MIDI 64)', color: '#2979ff' },
		{ label: 'Note[67]', desc: 'Note → G4 (MIDI 67)', color: '#2979ff' },
		{ label: 'Time[50]', desc: 'Time → t = 500 ms', color: '#e07020' },
		{ label: 'Off', desc: 'Note-Off events follow', color: '#7c4dff' },
		{ label: 'Note[60]', desc: 'Note → C4 released', color: '#2979ff' },
		{ label: 'Note[64]', desc: 'Note → E4 released', color: '#2979ff' },
		{ label: 'Note[67]', desc: 'Note → G4 released', color: '#2979ff' },
		{ label: 'EOS', desc: 'End of 2.048-sec segment', color: '#9ca3af' }
	];

	// Layout computed per draw call based on canvas width
	let tokenRects: Array<{ x: number; y: number; w: number; h: number }> = [];

	// White keys C4–B5 (MIDI 60–83): 14 white keys
	const WHITE_KEY_MIDI = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83];
	// Note tokens: index → MIDI number
	const NOTE_TOKEN_MIDI: Record<number, number> = { 3: 60, 4: 64, 5: 67, 8: 60, 9: 64, 10: 67 };

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const cols = 6;
		const rows = 2;
		const padX = canvasPad(w, 10);
		const padY = canvasPad(w, 8);
		const keyH = 28;
		const descH = 20;
		const gridH = h - padY * 2 - keyH - descH;
		const slotW = (w - padX * 2) / cols;
		const slotH = gridH / rows;
		const tokW = slotW - 10;
		const tokH = slotH - 10;
		const r = 5;

		// Mini keyboard: C4–B5 (14 white keys)
		const activeMidi = activeIdx >= 0 ? NOTE_TOKEN_MIDI[activeIdx] : undefined;
		const kbY = padY;
		const kbW = w - padX * 2;
		const nWhite = WHITE_KEY_MIDI.length;
		const keyW = kbW / nWhite;
		const whiteH = keyH - 4;
		const blackH = whiteH * 0.6;
		// Black key positions: after white key indices 0,1,3,4,5 (C#,D#,F#,G#,A#) per octave
		const blackAfter = new Set([0, 1, 3, 4, 5, 7, 8, 10, 11, 12]);

		// Draw white keys first (full height, with visible borders)
		WHITE_KEY_MIDI.forEach((midi, ki) => {
			const kx = padX + ki * keyW;
			const isActive = activeMidi === midi;
			// White key fill
			ctx.fillStyle = isActive ? 'rgba(41,121,255,0.18)' : '#ffffff';
			ctx.fillRect(kx + 0.5, kbY, keyW - 1, whiteH);
			// Border
			ctx.strokeStyle = isActive ? '#2979ff' : 'rgba(0,0,0,0.18)';
			ctx.lineWidth = isActive ? 1.5 : 0.5;
			ctx.strokeRect(kx + 0.5, kbY, keyW - 1, whiteH);
			// Note name on active keys (at bottom of white key, below where black keys sit)
			if (isActive) {
				ctx.fillStyle = '#2979ff';
				ctx.font = canvasFont(w, 11, 'bold');
				ctx.textAlign = 'center';
				ctx.textBaseline = 'alphabetic';
				const noteNames = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
				const name = noteNames[midi % 12] + Math.floor(midi / 12 - 1);
				ctx.fillText(name, kx + keyW / 2, kbY + whiteH - 3);
			}
		});
		// Draw black keys on top
		WHITE_KEY_MIDI.forEach((_midi, ki) => {
			if (!blackAfter.has(ki)) return;
			const bkW = keyW * 0.55;
			const kx = padX + (ki + 1) * keyW - bkW / 2;
			ctx.fillStyle = '#2a2a2a';
			ctx.fillRect(kx, kbY, bkW, blackH);
			ctx.strokeStyle = 'rgba(0,0,0,0.3)';
			ctx.lineWidth = 0.5;
			ctx.strokeRect(kx, kbY, bkW, blackH);
		});
		// Orientation labels: C4, C5
		ctx.fillStyle = 'rgba(0,0,0,0.25)';
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('C4', padX + keyW / 2, kbY + whiteH - 3);
		ctx.fillText('C5', padX + 7 * keyW + keyW / 2, kbY + whiteH - 3);

		tokenRects = [];

		const tokGridY = padY + keyH; // token grid starts below keyboard
		tokens.forEach((tok, i) => {
			const col = i % cols;
			const row = Math.floor(i / cols);
			const cx = padX + (col + 0.5) * slotW;
			const cy = tokGridY + (row + 0.5) * slotH;
			const x = cx - tokW / 2;
			const y = cy - tokH / 2;
			const isActive = i === activeIdx;

			tokenRects[i] = { x, y, w: tokW, h: tokH };

			// Background fill
			ctx.fillStyle = isActive ? tok.color + '1a' : 'rgba(0,0,0,0.025)';
			ctx.beginPath();
			ctx.roundRect(x, y, tokW, tokH, r);
			ctx.fill();

			// Border
			ctx.strokeStyle = isActive ? tok.color : tok.color + '66';
			ctx.lineWidth = isActive ? 1.5 : 1;
			if (isActive) {
				ctx.shadowColor = tok.color;
				ctx.shadowBlur = 10;
			}
			ctx.beginPath();
			ctx.roundRect(x, y, tokW, tokH, r);
			ctx.stroke();
			ctx.shadowBlur = 0;

			// Token label text
			ctx.fillStyle = isActive ? tok.color : tok.color + 'aa';
			ctx.font = isActive ? canvasFont(w, 12, 'bold') : canvasFont(w, 12);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(tok.label, cx, cy);
		});

		// Description bar at bottom
		const descY = tokGridY + gridH + 6;
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		if (activeIdx >= 0) {
			const tok = tokens[activeIdx];
			ctx.fillStyle = tok.color;
			ctx.font = canvasFont(w, 12);
			ctx.fillText('→ ' + tok.desc, padX + 2, descY + 13);
		} else {
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 12);
			ctx.fillText('Press Play to step through the token sequence', padX + 2, descY + 13);
		}
	}

	let raf = 0;
	function tick() {
		if (!running) return;
		if (playing) {
			const elapsed = performance.now() - startTime;
			const newIdx = Math.floor(elapsed / TOKEN_MS);
			if (newIdx >= tokens.length) {
				playing = false;
				activeIdx = -1;
				draw();
				return;
			}
			activeIdx = newIdx;
			draw();
			raf = requestAnimationFrame(tick);
		}
	}

	function togglePlay() {
		if (playing) {
			playing = false;
			activeIdx = -1;
			cancelAnimationFrame(raf);
			draw();
		} else {
			startTime = performance.now();
			playing = true;
			tick();
		}
	}

	onMount(() => {
		draw();
		const panel = canvas.closest('.viz-panel')!;
		const obs = observeVisibility(
			panel,
			() => {
				visible = true;
			},
			() => {
				visible = false;
				if (playing) {
					playing = false;
					activeIdx = -1;
					cancelAnimationFrame(raf);
				}
			}
		);
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => {
			obs.disconnect();
			window.removeEventListener('resize', onResize);
			running = false;
			cancelAnimationFrame(raf);
		};
	});
</script>

<VizPanel title="MT3 Token Vocabulary" titleColor="var(--violet)">
	{#snippet controls()}
		<VizButton color="var(--violet)" active={playing} onclick={togglePlay}>
			{playing ? 'Stop' : 'Play'}
		</VizButton>
		<div class="legend">
			<span class="dot" style="background:#1a9e8f"></span><span>Instrument</span>
			<span class="dot" style="background:#e07020"></span><span>Time</span>
			<span class="dot" style="background:#7c4dff"></span><span>On/Off</span>
			<span class="dot" style="background:#2979ff"></span><span>Note</span>
			<span class="dot" style="background:#9ca3af"></span><span>EOS</span>
		</div>
	{/snippet}
	<canvas bind:this={canvas} height="160"></canvas>
	{#snippet caption()}
		Token sequence for a C–E–G major chord. ~400 tokens total in MT3's vocabulary encode every instrument, pitch, timing, and control event.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-mono);
		font-size: 0.65rem;
		color: var(--text-muted);
		flex-wrap: wrap;
	}

	.dot {
		display: inline-block;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	@media (max-width: 640px) {
		.legend {
			display: none;
		}
	}
</style>
