<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, observeVisibility, canvasFont, canvasPad } from '$lib/utils/canvas';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let visible = false;
	let running = true;
	let raf = 0;
	let activeStage = $state(-1);
	let playing = $state(false);
	let startTime = 0;

	const TOKEN_MS = 900;
	const NUM_STAGES = 7;

	const C_ENCODER = '#1a9e8f';
	const C_PROJ = '#7c4dff';
	const C_LLM = '#2979ff';
	const C_AUDIO_TOK = '#e07020';
	const C_TEXT_TOK = '#9ca3af';

	const T_AUDIO = 12;
	const N_LLM = 8;
	const M_TEXT = 6;

	function roundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

	function drawBlock(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		color: string,
		label: string,
		sublabel: string,
		glyph: string,
		active: boolean,
		canvasW: number
	) {
		const a = active ? 1 : 0.55;
		if (active) {
			ctx.shadowColor = color;
			ctx.shadowBlur = 12;
		}
		ctx.fillStyle = color + (active ? '14' : '08');
		roundedRect(ctx, x, y, w, h, 8);
		ctx.fill();
		ctx.strokeStyle = color;
		ctx.globalAlpha = a;
		ctx.lineWidth = active ? 1.8 : 1;
		roundedRect(ctx, x, y, w, h, 8);
		ctx.stroke();
		ctx.globalAlpha = 1;
		ctx.shadowBlur = 0;

		ctx.fillStyle = active ? color : color + 'aa';
		ctx.font = canvasFont(canvasW, 11, active ? 'bold' : '');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, x + w / 2, y + h / 2 - 5);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(canvasW, 9);
		ctx.fillText(sublabel, x + w / 2, y + h / 2 + 9);

		// Glyph in top-right
		ctx.font = canvasFont(canvasW, 11);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'top';
		ctx.fillStyle = active ? color : color + 'aa';
		ctx.fillText(glyph, x + w - 5, y + 3);
	}

	function drawArrow(ctx: CanvasRenderingContext2D, x1: number, y: number, x2: number, active: boolean) {
		ctx.strokeStyle = active ? '#333' : 'rgba(0,0,0,0.25)';
		ctx.lineWidth = active ? 1.4 : 1;
		ctx.beginPath();
		ctx.moveTo(x1, y);
		ctx.lineTo(x2 - 5, y);
		ctx.stroke();
		ctx.beginPath();
		ctx.moveTo(x2, y);
		ctx.lineTo(x2 - 6, y - 3);
		ctx.lineTo(x2 - 6, y + 3);
		ctx.closePath();
		ctx.fillStyle = active ? '#333' : 'rgba(0,0,0,0.25)';
		ctx.fill();
	}

	function drawTokenRow(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		count: number,
		tokW: number,
		tokH: number,
		gap: number,
		color: string,
		active: boolean,
		alpha: number,
		canvasW: number,
		shapeLabel: string
	) {
		ctx.globalAlpha = alpha;
		for (let i = 0; i < count; i++) {
			const tx = x + i * (tokW + gap);
			if (active) {
				ctx.shadowColor = color;
				ctx.shadowBlur = 8;
			}
			ctx.fillStyle = color + (active ? '1f' : '10');
			roundedRect(ctx, tx, y, tokW, tokH, 3);
			ctx.fill();
			ctx.strokeStyle = color;
			ctx.lineWidth = active ? 1.4 : 0.9;
			roundedRect(ctx, tx, y, tokW, tokH, 3);
			ctx.stroke();
			ctx.shadowBlur = 0;
		}
		ctx.globalAlpha = 1;

		// Shape label below
		ctx.fillStyle = active ? color : color + 'cc';
		ctx.font = canvasFont(canvasW, 9, active ? 'bold' : '');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.globalAlpha = alpha;
		ctx.fillText(shapeLabel, x + (count * (tokW + gap) - gap) / 2, y + tokH + 4);
		ctx.globalAlpha = 1;
	}

	function drawWaveform(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, active: boolean, canvasW: number) {
		if (active) {
			ctx.shadowColor = C_AUDIO_TOK;
			ctx.shadowBlur = 10;
		}
		ctx.strokeStyle = active ? C_AUDIO_TOK : C_AUDIO_TOK + '99';
		ctx.lineWidth = active ? 1.6 : 1.1;
		ctx.beginPath();
		const cy = y + h / 2;
		ctx.moveTo(x, cy);
		const steps = 60;
		for (let i = 0; i <= steps; i++) {
			const t = i / steps;
			const px = x + t * w;
			const env = Math.sin(t * Math.PI);
			const py = cy + Math.sin(t * Math.PI * 6) * (h * 0.35) * env;
			ctx.lineTo(px, py);
		}
		ctx.stroke();
		ctx.shadowBlur = 0;

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(canvasW, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('16 kHz waveform', x + w / 2, y + h + 4);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 12);
		const padY = canvasPad(w, 14);
		const cy = h / 2;

		// Width budget across stages — proportions
		// waveform | enc | tok-row1 | proj | tok-row2 + text | llm
		const usable = w - padX * 2;
		const wfW = usable * 0.10;
		const blockW = usable * 0.13;
		const blockH = 50;
		const arrowW = usable * 0.025;
		const tokAW = (usable * 0.16);
		const tokBW = (usable * 0.22); // both audio (8) + text (6)
		// Compute remaining and distribute
		const totalFixed = wfW + blockW * 3 + arrowW * 4 + tokAW + tokBW;
		const slack = usable - totalFixed;
		const lead = padX + Math.max(0, slack / 2);

		let cx = lead;

		// 1. Waveform
		const wfH = 44;
		drawWaveform(ctx, cx, cy - wfH / 2, wfW, wfH, activeStage === 0, w);
		cx += wfW;

		// arrow
		drawArrow(ctx, cx, cy, cx + arrowW, activeStage >= 1);
		cx += arrowW;

		// 2. Audio Encoder
		drawBlock(ctx, cx, cy - blockH / 2, blockW, blockH, C_ENCODER, 'Audio Encoder', 'AF-Whisper / AST', '❄', activeStage === 1, w);
		// label above
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillText('frozen', cx + blockW / 2, cy - blockH / 2 - 4);
		cx += blockW;

		drawArrow(ctx, cx, cy, cx + arrowW, activeStage >= 2);
		cx += arrowW;

		// 3. Audio token row 1 — (T, d_audio)
		const tok1Count = T_AUDIO;
		const tok1Gap = 2;
		const tok1W = (tokAW - (tok1Count - 1) * tok1Gap) / tok1Count;
		const tok1H = 22;
		const tok1Alpha = activeStage >= 2 ? 1 : 0;
		if (activeStage >= 2) {
			drawTokenRow(ctx, cx, cy - tok1H / 2, tok1Count, tok1W, tok1H, tok1Gap, C_AUDIO_TOK, activeStage === 2, tok1Alpha, w, '(T=12, d_audio=1280)');
		}
		cx += tokAW;

		drawArrow(ctx, cx, cy, cx + arrowW, activeStage >= 3);
		cx += arrowW;

		// 4. Projection block
		drawBlock(ctx, cx, cy - blockH / 2, blockW, blockH, C_PROJ, 'Projection', 'MLP / Linear', '🔥', activeStage === 3, w);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillText('trainable', cx + blockW / 2, cy - blockH / 2 - 4);
		cx += blockW;

		drawArrow(ctx, cx, cy, cx + arrowW, activeStage >= 4);
		cx += arrowW;

		// 5/6. Audio (compressed) tokens + text tokens at same level
		const tok2Gap = 3;
		const totalTokB = N_LLM + M_TEXT;
		const tok2W = (tokBW - (totalTokB - 1) * tok2Gap - 8) / totalTokB; // 8px separator
		const tok2H = 22;

		const audioStart = cx;
		if (activeStage >= 4) {
			drawTokenRow(ctx, audioStart, cy - tok2H / 2, N_LLM, tok2W, tok2H, tok2Gap, C_PROJ, activeStage === 4, 1, w, '(N=8, d_llm)');
		}
		const audioEnd = audioStart + N_LLM * (tok2W + tok2Gap) - tok2Gap;

		// separator
		const sepX = audioEnd + 4;
		const textStart = sepX + 4;

		if (activeStage >= 5) {
			ctx.strokeStyle = 'rgba(0,0,0,0.18)';
			ctx.lineWidth = 0.8;
			ctx.setLineDash([2, 2]);
			ctx.beginPath();
			ctx.moveTo(sepX, cy - tok2H / 2 - 2);
			ctx.lineTo(sepX, cy + tok2H / 2 + 2);
			ctx.stroke();
			ctx.setLineDash([]);

			drawTokenRow(ctx, textStart, cy - tok2H / 2, M_TEXT, tok2W, tok2H, tok2Gap, C_TEXT_TOK, activeStage === 5, 1, w, 'text (M=6, d_llm)');

			// bracket above showing combined sequence
			const bracketL = audioStart;
			const bracketR = textStart + M_TEXT * (tok2W + tok2Gap) - tok2Gap;
			const bY = cy - tok2H / 2 - 12;
			ctx.strokeStyle = activeStage === 5 ? C_PROJ : 'rgba(0,0,0,0.35)';
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(bracketL, bY + 4);
			ctx.lineTo(bracketL, bY);
			ctx.lineTo(bracketR, bY);
			ctx.lineTo(bracketR, bY + 4);
			ctx.stroke();
			ctx.fillStyle = activeStage === 5 ? C_PROJ : CANVAS_LABEL;
			ctx.font = canvasFont(w, 9, activeStage === 5 ? 'bold' : '');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'bottom';
			ctx.fillText('[ audio | text ]', (bracketL + bracketR) / 2, bY - 2);
		}
		cx += tokBW;

		drawArrow(ctx, cx, cy, cx + arrowW, activeStage >= 6);
		cx += arrowW;

		// 7. LLM block
		drawBlock(ctx, cx, cy - blockH / 2, blockW, blockH, C_LLM, 'LLM', 'Qwen-2.5 / Llama-2', '🔥❄', activeStage === 6, w);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'center';
		ctx.textBaseline = 'bottom';
		ctx.fillText('LoRA', cx + blockW / 2, cy - blockH / 2 - 4);
	}

	function tick() {
		if (!running) return;
		if (playing) {
			const elapsed = performance.now() - startTime;
			const newStage = Math.floor(elapsed / TOKEN_MS);
			if (newStage >= NUM_STAGES) {
				activeStage = NUM_STAGES - 1;
				playing = false;
				draw();
				return;
			}
			activeStage = newStage;
			draw();
			raf = requestAnimationFrame(tick);
		}
	}

	function togglePlay() {
		if (playing) {
			playing = false;
			cancelAnimationFrame(raf);
			draw();
		} else {
			if (activeStage >= NUM_STAGES - 1) activeStage = -1;
			startTime = performance.now() - Math.max(0, activeStage) * TOKEN_MS;
			playing = true;
			tick();
		}
	}

	function reset() {
		playing = false;
		activeStage = -1;
		cancelAnimationFrame(raf);
		draw();
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {
				visible = true;
			},
			() => {
				visible = false;
				if (playing) {
					playing = false;
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

<div bind:this={container}>
	<VizPanel title="End-to-End Fusion Pipeline" titleColor="var(--violet)">
		{#snippet controls()}
			<VizButton color="var(--violet)" active={playing} onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--violet)" onclick={reset}>Reset</VizButton>
			<div class="legend">
				<span class="dot" style="background:#1a9e8f"></span><span>Encoder</span>
				<span class="dot" style="background:#7c4dff"></span><span>Projector</span>
				<span class="dot" style="background:#e07020"></span><span>Audio tokens</span>
				<span class="dot" style="background:#9ca3af"></span><span>Text tokens</span>
			</div>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:220px"></canvas>
		{#snippet caption()}
			Same shape language at every stage. After projection, audio tokens are vectors of <code>d_llm</code> — indistinguishable in type from text token embeddings.
		{/snippet}
	</VizPanel>
</div>

<style>
	.legend {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-display);
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
