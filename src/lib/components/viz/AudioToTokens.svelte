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

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;
	let raf = 0;

	const ORANGE = '#e07020';
	const TEAL = '#1a9e8f';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const GREY = '#9ca3af';

	let progress = $state(0);
	let playing = $state(false);
	let playStart = 0;
	const PLAY_MS = 7000;
	let phase = 0;

	type Sound = 'speech' | 'piano' | 'drums';
	const SOUNDS: Sound[] = ['speech', 'piano', 'drums'];
	const SOUND_LABELS: Record<Sound, string> = {
		speech: 'speech',
		piano: 'piano note',
		drums: 'drum hit'
	};
	let sound = $state<Sound>('piano');

	function play() {
		progress = 0;
		playStart = performance.now();
		playing = true;
	}

	function showAll() {
		playing = false;
		progress = 1;
		draw();
	}

	const N_SAMPLES = 220; // waveform sample count
	const N_FRAMES = 16; // spectrogram time frames
	const N_MELS = 24; // spectrogram mel bins
	const N_ENCODER = 8; // encoded frame count after pooling
	const D_AUDIO = 6; // displayed dim per encoder vector
	const N_TOKENS = 4; // final token count after projector
	const D_LLM = 8; // displayed dim per LLM token

	// Generate waveform shape per sound type
	function genWaveform(): number[] {
		const out: number[] = new Array(N_SAMPLES);
		for (let i = 0; i < N_SAMPLES; i++) {
			const t = i / N_SAMPLES;
			let y = 0;
			if (sound === 'speech') {
				const env = Math.exp(-Math.abs(t - 0.5) * 4) * (1 + 0.4 * Math.sin(t * 18));
				y =
					Math.sin(t * 60 + Math.sin(t * 7) * 0.8) * 0.6 * env +
					Math.sin(t * 130) * 0.25 * env +
					(Math.sin(t * 280) - 0.5) * 0.15 * env;
			} else if (sound === 'piano') {
				const env = (1 - t) * (1 - t) * (1 - Math.exp(-t * 12));
				y =
					Math.sin(t * 30) * 0.5 * env +
					Math.sin(t * 60) * 0.28 * env +
					Math.sin(t * 90) * 0.18 * env +
					Math.sin(t * 120) * 0.1 * env;
			} else {
				// drums: noise burst with low-frequency rumble
				const env = Math.exp(-Math.max(0, t - 0.18) * 8);
				y =
					((Math.sin(t * 7) - 0.5) * 0.5 + (Math.sin(t * 11.3) - 0.5) * 0.45) * env +
					Math.sin(t * 6) * 0.3 * env;
			}
			out[i] = Math.max(-1, Math.min(1, y));
		}
		return out;
	}

	// Generate spectrogram (mel × time)
	function genSpectrogram(): number[][] {
		const out: number[][] = [];
		for (let m = 0; m < N_MELS; m++) {
			const row: number[] = [];
			for (let f = 0; f < N_FRAMES; f++) {
				const t = f / (N_FRAMES - 1);
				let v = 0;
				if (sound === 'speech') {
					const env = Math.exp(-Math.abs(t - 0.5) * 3.5);
					const formant1 = Math.exp(-Math.pow((m - 4) / 3, 2));
					const formant2 = Math.exp(-Math.pow((m - 11) / 3.5, 2));
					const formant3 = Math.exp(-Math.pow((m - 17) / 4, 2));
					v =
						(formant1 * 1.0 + formant2 * 0.7 + formant3 * 0.4) *
						env *
						(0.7 + 0.3 * Math.sin(t * 12));
				} else if (sound === 'piano') {
					const env = Math.exp(-t * 1.4);
					// Fundamental + harmonics
					const harmonics = [3, 8, 13, 18];
					harmonics.forEach((h, hi) => {
						v += Math.exp(-Math.pow((m - h) / 1.2, 2)) * env * (1 - hi * 0.18);
					});
				} else {
					const burst = Math.max(0, 1 - Math.abs(t - 0.18) * 6);
					const lowEmph = Math.exp(-Math.pow((m - 2) / 5, 2));
					const noise = Math.exp(-Math.pow((m - 14) / 10, 2));
					v = (lowEmph * 1.4 + noise * 0.5) * burst;
				}
				row.push(Math.max(0, Math.min(1, v)));
			}
			out.push(row);
		}
		return out;
	}

	// Encoder output: pooled along time, fewer frames each with D_AUDIO dim
	function genEncoded(spec: number[][]): number[][] {
		const out: number[][] = [];
		const poolStride = Math.floor(N_FRAMES / N_ENCODER);
		for (let f = 0; f < N_ENCODER; f++) {
			const t0 = f * poolStride;
			const t1 = Math.min(N_FRAMES, t0 + poolStride);
			const vec: number[] = [];
			for (let d = 0; d < D_AUDIO; d++) {
				let s = 0;
				let n = 0;
				for (let m = 0; m < N_MELS; m++) {
					const w = Math.cos(((m / N_MELS) * Math.PI * 4 + d * 1.7)) * 0.5 + 0.5;
					for (let t = t0; t < t1; t++) {
						s += spec[m][t] * w;
						n++;
					}
				}
				vec.push(s / Math.max(1, n));
			}
			out.push(vec);
		}
		return out;
	}

	// Projector: N_ENCODER → N_TOKENS, D_AUDIO → D_LLM
	function genTokens(enc: number[][]): number[][] {
		const out: number[][] = [];
		const stride = N_ENCODER / N_TOKENS;
		for (let t = 0; t < N_TOKENS; t++) {
			const i0 = Math.floor(t * stride);
			const i1 = Math.min(N_ENCODER, Math.floor((t + 1) * stride));
			const vec: number[] = [];
			for (let d = 0; d < D_LLM; d++) {
				let s = 0;
				let n = 0;
				for (let i = i0; i < i1; i++) {
					for (let dd = 0; dd < D_AUDIO; dd++) {
						const w = Math.cos((dd * 1.3 + d * 0.7)) * 0.5 + 0.5;
						s += enc[i][dd] * w;
						n++;
					}
				}
				vec.push(s / Math.max(1, n));
			}
			out.push(vec);
		}
		return out;
	}

	let waveform = genWaveform();
	let spectrogram = genSpectrogram();
	let encoded = genEncoded(spectrogram);
	let tokens = genTokens(encoded);

	function refreshData() {
		waveform = genWaveform();
		spectrogram = genSpectrogram();
		encoded = genEncoded(spectrogram);
		tokens = genTokens(encoded);
	}

	function setSound(s: Sound) {
		sound = s;
		refreshData();
		draw();
	}

	function drawWaveform(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		visT: number
	) {
		ctx.save();
		// Box
		ctx.strokeStyle = ORANGE;
		ctx.globalAlpha = 0.25;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		const midY = y + hh / 2;
		// Center line
		ctx.save();
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 0.7;
		ctx.beginPath();
		ctx.moveTo(x + 4, midY);
		ctx.lineTo(x + ww - 4, midY);
		ctx.stroke();
		ctx.restore();

		// Waveform
		ctx.save();
		ctx.strokeStyle = ORANGE;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		const visN = Math.floor(visT * waveform.length);
		for (let i = 0; i < visN; i++) {
			const px = x + 4 + ((ww - 8) * i) / (waveform.length - 1);
			const py = midY - waveform[i] * (hh / 2 - 4);
			if (i === 0) ctx.moveTo(px, py);
			else ctx.lineTo(px, py);
		}
		ctx.stroke();
		ctx.restore();

		// Playhead
		if (visT > 0 && visT < 1) {
			const phx = x + 4 + ((ww - 8) * visN) / (waveform.length - 1);
			ctx.save();
			ctx.strokeStyle = ORANGE;
			ctx.globalAlpha = 0.5;
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(phx, y + 4);
			ctx.lineTo(phx, y + hh - 4);
			ctx.stroke();
			ctx.restore();
		}

		// Title
		ctx.fillStyle = ORANGE;
		ctx.font = canvasFont(w, 11, '700');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('1. Waveform', x, y - 16);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('amplitude over time', x, y + hh + 4);
	}

	function drawSpectrogram(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		visT: number
	) {
		ctx.save();
		ctx.strokeStyle = TEAL;
		ctx.globalAlpha = 0.25;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		const innerX = x + 4;
		const innerY = y + 4;
		const innerW = ww - 8;
		const innerH = hh - 8;
		const cellW = innerW / N_FRAMES;
		const cellH = innerH / N_MELS;

		const visFrames = Math.floor(visT * N_FRAMES);
		for (let f = 0; f < visFrames; f++) {
			for (let m = 0; m < N_MELS; m++) {
				const v = spectrogram[m][f];
				ctx.fillStyle = TEAL;
				ctx.globalAlpha = v * 0.85 + 0.04;
				ctx.fillRect(innerX + f * cellW, innerY + (N_MELS - 1 - m) * cellH, cellW + 0.5, cellH + 0.5);
			}
		}
		ctx.globalAlpha = 1;

		// Frame markers
		ctx.fillStyle = TEAL;
		ctx.font = canvasFont(w, 11, '700');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('2. Mel spectrogram', x, y - 16);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('time × frequency, energy as brightness', x, y + hh + 4);

		// Axis
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 8);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'middle';
		ctx.fillText('hi', x - 2, y + 8);
		ctx.fillText('lo', x - 2, y + hh - 8);
	}

	function drawEncoder(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		visT: number
	) {
		// Encoder is shown as a rounded box with an inner stack label
		ctx.save();
		ctx.fillStyle = VIOLET;
		ctx.globalAlpha = 0.06;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = VIOLET;
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		// Stacked transformer "blocks"
		const N_BLOCK = 4;
		const blockMargin = 8;
		const blockW = ww - blockMargin * 2;
		const blockH = (hh - blockMargin * 2 - (N_BLOCK - 1) * 4) / N_BLOCK;
		for (let i = 0; i < N_BLOCK; i++) {
			const by = y + blockMargin + i * (blockH + 4);
			ctx.save();
			ctx.strokeStyle = VIOLET;
			ctx.globalAlpha = 0.7 + 0.3 * Math.sin(phase * 6 + i);
			ctx.lineWidth = 1;
			ctx.setLineDash([3, 2]);
			ctx.beginPath();
			ctx.roundRect(x + blockMargin, by, blockW, blockH, 3);
			ctx.stroke();
			ctx.setLineDash([]);
			ctx.restore();
		}

		ctx.fillStyle = VIOLET;
		ctx.font = canvasFont(w, 11, '700');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('3. Encoder', x, y - 16);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText('AST · AF-Whisper · Jukebox', x, y + hh + 4);

		// Inside label
		if (visT > 0.1) {
			ctx.fillStyle = VIOLET;
			ctx.font = canvasFont(w, 9, '500');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.globalAlpha = Math.min(1, (visT - 0.1) * 2);
			ctx.fillText('FROZEN', x + ww / 2, y + hh / 2);
			ctx.globalAlpha = 1;
		}
	}

	function drawVectorRow(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		vectors: number[][],
		dims: number,
		color: string,
		label: string,
		subtitle: string,
		visT: number
	) {
		ctx.save();
		ctx.strokeStyle = color;
		ctx.globalAlpha = 0.25;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 4);
		ctx.stroke();
		ctx.restore();

		const cnt = vectors.length;
		const gap = 4;
		const colW = (ww - gap * (cnt + 1)) / cnt;
		const cellH = (hh - 14) / dims;

		const visCount = Math.floor(visT * cnt);
		for (let i = 0; i < cnt; i++) {
			const colAlpha = i < visCount ? 1 : i === visCount ? Math.max(0, visT * cnt - visCount) : 0;
			if (colAlpha < 0.02) continue;
			const cx = x + gap + i * (colW + gap);
			ctx.save();
			ctx.globalAlpha = colAlpha;
			// Vector cells colored by magnitude
			for (let d = 0; d < dims; d++) {
				const v = vectors[i][d] || 0;
				ctx.fillStyle = color;
				ctx.globalAlpha = colAlpha * (Math.abs(v) * 0.85 + 0.08);
				ctx.fillRect(cx, y + 7 + d * cellH, colW, cellH - 0.5);
			}
			ctx.globalAlpha = colAlpha;
			ctx.strokeStyle = color;
			ctx.lineWidth = 0.8;
			ctx.beginPath();
			ctx.roundRect(cx, y + 7, colW, dims * cellH, 2);
			ctx.stroke();
			ctx.restore();

			// Index label below
			ctx.save();
			ctx.globalAlpha = colAlpha * 0.7;
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 8);
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			ctx.fillText(`v${i + 1}`, cx + colW / 2, y + hh - 12);
			ctx.restore();
		}

		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 11, '700');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText(label, x, y - 16);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.fillText(subtitle, x, y + hh + 4);
	}

	function drawArrow(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y1: number,
		x2: number,
		y2: number,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = GREY;
		ctx.fillStyle = GREY;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.moveTo(x1, y1);
		ctx.lineTo(x2, y2);
		ctx.stroke();
		const ang = Math.atan2(y2 - y1, x2 - x1);
		ctx.beginPath();
		ctx.moveTo(x2, y2);
		ctx.lineTo(x2 - 6 * Math.cos(ang - Math.PI / 6), y2 - 6 * Math.sin(ang - Math.PI / 6));
		ctx.lineTo(x2 - 6 * Math.cos(ang + Math.PI / 6), y2 - 6 * Math.sin(ang + Math.PI / 6));
		ctx.closePath();
		ctx.fill();
		ctx.restore();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 14);
		const padY = canvasPad(w, 22);

		// Five panels arranged left-to-right
		const colGap = canvasPad(w, 14);
		const arrowGap = canvasPad(w, 16);
		const inner = w - padX * 2;
		const colW = (inner - arrowGap * 4) / 5;
		const colH = h - padY * 2 - 18;

		const stages = [
			{ x: padX, w: colW, p: progress, fn: 'wave' },
			{ x: padX + colW + arrowGap, w: colW, p: Math.max(0, progress * 1.4 - 0.18), fn: 'spec' },
			{ x: padX + (colW + arrowGap) * 2, w: colW, p: Math.max(0, progress * 1.6 - 0.4), fn: 'enc' },
			{ x: padX + (colW + arrowGap) * 3, w: colW, p: Math.max(0, progress * 1.8 - 0.55), fn: 'audio' },
			{ x: padX + (colW + arrowGap) * 4, w: colW, p: Math.max(0, progress * 2 - 0.78), fn: 'tokens' }
		];

		// Draw each
		drawWaveform(ctx, w, stages[0].x, padY, stages[0].w, colH, Math.min(1, stages[0].p));
		drawSpectrogram(ctx, w, stages[1].x, padY, stages[1].w, colH, Math.min(1, stages[1].p));
		drawEncoder(ctx, w, stages[2].x, padY, stages[2].w, colH, Math.min(1, stages[2].p));
		drawVectorRow(
			ctx,
			w,
			stages[3].x,
			padY,
			stages[3].w,
			colH,
			encoded,
			D_AUDIO,
			BLUE,
			'4. Audio embeddings',
			'd_audio · many frames',
			Math.min(1, stages[3].p)
		);
		drawVectorRow(
			ctx,
			w,
			stages[4].x,
			padY,
			stages[4].w,
			colH,
			tokens,
			D_LLM,
			ORANGE,
			'5. Audio tokens',
			'd_llm · few tokens',
			Math.min(1, stages[4].p)
		);

		// Arrows between
		const arrY = padY + colH / 2;
		for (let i = 0; i < 4; i++) {
			const aFrom = stages[i].x + stages[i].w + 2;
			const aTo = stages[i + 1].x - 2;
			const a = Math.min(1, Math.max(0, stages[i].p * 1.5 - 0.6));
			drawArrow(ctx, aFrom, arrY, aTo, arrY, 0.25 + a * 0.55);
		}

		// Stage 4→5 has a small "projector" tag mid-arrow
		const a45 = Math.min(1, Math.max(0, stages[3].p * 1.5 - 0.4));
		if (a45 > 0.2) {
			const labX = (stages[3].x + stages[3].w + stages[4].x) / 2;
			ctx.save();
			ctx.globalAlpha = a45;
			ctx.fillStyle = '#fff';
			ctx.beginPath();
			ctx.roundRect(labX - 28, arrY - 9, 56, 18, 3);
			ctx.fill();
			ctx.strokeStyle = ORANGE;
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.roundRect(labX - 28, arrY - 9, 56, 18, 3);
			ctx.stroke();
			ctx.fillStyle = ORANGE;
			ctx.font = canvasFont(w, 9, '600');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText('projector', labX, arrY);
			ctx.restore();
		}

		// Bottom hint label
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('these final tokens go straight into the LLM, just like text tokens', w / 2, h - padY + 6);
	}

	function tick(ts: number) {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		phase = (phase + 0.012) % 1;
		if (playing) {
			const elapsed = ts - playStart;
			progress = Math.min(1, elapsed / PLAY_MS);
			draw();
			if (progress >= 1) playing = false;
		} else {
			// Keep encoder block animations alive
			draw();
		}
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		progress = 1;
		draw();
		const obs = observeVisibility(
			container,
			() => {
				running = true;
				draw();
			},
			() => {
				running = false;
			}
		);
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		raf = requestAnimationFrame(tick);
		return () => {
			running = false;
			cancelAnimationFrame(raf);
			obs.disconnect();
			window.removeEventListener('resize', onResize);
		};
	});
</script>

<div bind:this={container}>
	<VizPanel
		title="Waveform → tokens: what an audio LM actually sees"
		titleColor="var(--orange)"
	>
		{#snippet controls()}
			{#each SOUNDS as s}
				<VizButton color="var(--orange)" active={sound === s} onclick={() => setSound(s)}>
					{SOUND_LABELS[s]}
				</VizButton>
			{/each}
			<VizButton color="var(--orange)" active={playing} onclick={play}>Play</VizButton>
			<VizButton color="var(--orange)" onclick={showAll}>Show all</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:280px"></canvas>
		{#snippet caption()}
			A 1-second clip enters as a waveform (raw amplitude). It gets converted to a mel
			spectrogram (frequency content over time, brighter = more energy at that frequency).
			A frozen encoder reads that spectrogram and emits a sequence of audio embeddings — many
			high-dimensional vectors, one per pooled time frame. The projector compresses those into
			a small bundle of "audio tokens" of the same dimension as the LLM's text tokens. From
			the LLM's perspective, the audio prefix is just more tokens.
		{/snippet}
	</VizPanel>
</div>
