<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, observeVisibility, canvasFont, canvasPad } from '$lib/utils/canvas';

	type ModuleState = 'frozen' | 'lora' | 'trainable';
	type Stage = { name: string; data: string; encoder: ModuleState; projector: ModuleState; llm: ModuleState };
	type Paper = { id: string; label: string; color: string; stages: Stage[] };

	const PAPERS: Paper[] = [
		{
			id: 'ltu', label: 'LTU', color: '#1a9e8f',
			stages: [
				{ name: 'Stage 1', data: 'Closed-ended classification + acoustic features', encoder: 'frozen', projector: 'trainable', llm: 'frozen' },
				{ name: 'Stage 2', data: '+ LoRA on LLM, closed-ended', encoder: 'frozen', projector: 'trainable', llm: 'lora' },
				{ name: 'Stage 3', data: 'All closed-ended tasks', encoder: 'frozen', projector: 'trainable', llm: 'lora' },
				{ name: 'Stage 4', data: '+ Open-ended QA (perception → understanding)', encoder: 'frozen', projector: 'trainable', llm: 'lora' }
			]
		},
		{
			id: 'llark', label: 'LLark', color: '#7c4dff',
			stages: [
				{ name: 'Stage 1', data: 'Music classification + acoustic features (closed-ended)', encoder: 'frozen', projector: 'trainable', llm: 'frozen' },
				{ name: 'Stage 2', data: '+ LoRA on LLaMA-2-7B-Chat', encoder: 'frozen', projector: 'trainable', llm: 'lora' },
				{ name: 'Stage 3', data: 'Captioning + reasoning', encoder: 'frozen', projector: 'trainable', llm: 'lora' },
				{ name: 'Stage 4', data: '+ Open-ended music QA', encoder: 'frozen', projector: 'trainable', llm: 'lora' }
			]
		},
		{
			id: 'mf', label: 'Music Flamingo', color: '#e07020',
			stages: [
				{ name: 'AF3-SFT', data: 'Improve AF3 base on music + multi-speaker ASR', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'MF-SFT', data: 'MF-Skills (~3M hours), MF-Think; RoTE added', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'MF-WarmUp', data: '300K cold-start CoT (gpt-oss-120b)', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'MF-GRPO', data: 'Group-relative policy opt with format/accuracy/structure rewards', encoder: 'frozen', projector: 'trainable', llm: 'trainable' }
			]
		},
		{
			id: 'afnext', label: 'Audio Flamingo Next', color: '#2979ff',
			stages: [
				{ name: 'Pre-train 1', data: 'Audio adapter alignment, 30s/8K context', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'Pre-train 2', data: 'Multilingual ASR, 1min/8K context', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'Mid-train 1', data: 'AudioSkills-XL, MF-Skills, 10min/24K context', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'Mid-train 2', data: 'Long-audio: 30min/128K context (Sequence Packing)', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'Post-train', data: 'GRPO with rule-based rewards + safety (386K)', encoder: 'frozen', projector: 'trainable', llm: 'trainable' },
				{ name: 'CoT-train', data: 'AF-Think-Time: timestamp-grounded reasoning chains', encoder: 'frozen', projector: 'trainable', llm: 'trainable' }
			]
		}
	];

	const STATE_COLORS = {
		frozen: '#1a9e8f',
		trainable: '#e07020',
		lora: '#7c4dff'
	};

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let running = true;
	let raf = 0;

	let paper: 'ltu' | 'llark' | 'mf' | 'afnext' = $state('ltu');
	let stageIdx = $state(0);
	let playing = $state(false);
	let lastStepTime = 0;

	// Pulse tracking: per-module pulse start time when state changes
	let pulseStart: Record<'encoder' | 'projector' | 'llm', number> = {
		encoder: 0,
		projector: 0,
		llm: 0
	};
	let prevStates: Record<'encoder' | 'projector' | 'llm', ModuleState> = {
		encoder: 'frozen',
		projector: 'trainable',
		llm: 'frozen'
	};

	const STEP_MS = 1500;
	const PULSE_MS = 300;

	function currentPaper(): Paper {
		return PAPERS.find((p) => p.id === paper)!;
	}

	function setPaper(id: typeof paper) {
		paper = id;
		stageIdx = 0;
		playing = false;
		const s = currentPaper().stages[0];
		prevStates = { encoder: s.encoder, projector: s.projector, llm: s.llm };
		pulseStart = { encoder: 0, projector: 0, llm: 0 };
	}

	function applyStageChange() {
		const s = currentPaper().stages[stageIdx];
		const now = performance.now();
		(['encoder', 'projector', 'llm'] as const).forEach((k) => {
			if (prevStates[k] !== s[k]) pulseStart[k] = now;
		});
		prevStates = { encoder: s.encoder, projector: s.projector, llm: s.llm };
	}

	function step() {
		const len = currentPaper().stages.length;
		if (stageIdx < len - 1) {
			stageIdx++;
			applyStageChange();
		}
	}

	function reset() {
		stageIdx = 0;
		playing = false;
		const s = currentPaper().stages[0];
		prevStates = { encoder: s.encoder, projector: s.projector, llm: s.llm };
		pulseStart = { encoder: 0, projector: 0, llm: 0 };
	}

	function togglePlay() {
		const len = currentPaper().stages.length;
		if (stageIdx >= len - 1 && !playing) {
			reset();
		}
		playing = !playing;
		lastStepTime = performance.now();
	}

	function stateGlyph(s: ModuleState): string {
		if (s === 'frozen') return '❄';
		if (s === 'trainable') return '🔥';
		return 'LoRA';
	}

	function stateLabel(s: ModuleState): string {
		if (s === 'frozen') return 'frozen';
		if (s === 'trainable') return 'trainable';
		return 'low-rank adapter';
	}

	function drawModuleBox(
		ctx: CanvasRenderingContext2D,
		x: number, y: number, w: number, h: number,
		name: string, state: ModuleState,
		key: 'encoder' | 'projector' | 'llm',
		fontW: number,
		now: number
	) {
		const r = 8;
		const color = STATE_COLORS[state];

		// Box outline
		ctx.fillStyle = '#ffffff';
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
		ctx.fill();
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
		ctx.stroke();

		// Module name
		ctx.fillStyle = 'rgba(0,0,0,0.7)';
		ctx.font = canvasFont(fontW, 11, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(name, x + 12, y + h / 2);

		// State chip on right
		const elapsed = now - pulseStart[key];
		const pulsing = elapsed < PULSE_MS;
		const pulseT = pulsing ? 1 - elapsed / PULSE_MS : 0;
		const scale = 1 + pulseT * 0.35;

		const chipPad = 10;
		const glyph = stateGlyph(state);
		ctx.font = canvasFont(fontW, state === 'lora' ? 10 : 14, state === 'lora' ? 'bold' : '');
		const glyphW = ctx.measureText(glyph).width;
		const chipW = glyphW + chipPad * 2;
		const chipH = h - 14;
		const chipX = x + w - chipW - 7;
		const chipY = y + 7;

		ctx.fillStyle = color + '1a';
		ctx.beginPath();
		ctx.roundRect(chipX, chipY, chipW, chipH, 6);
		ctx.fill();

		if (pulsing) {
			ctx.shadowColor = color;
			ctx.shadowBlur = 12 * pulseT;
		}
		ctx.strokeStyle = color;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.roundRect(chipX, chipY, chipW, chipH, 6);
		ctx.stroke();
		ctx.shadowBlur = 0;

		// Glyph text
		ctx.save();
		ctx.translate(chipX + chipW / 2, chipY + chipH / 2);
		ctx.scale(scale, scale);
		ctx.fillStyle = color;
		ctx.font = canvasFont(fontW, state === 'lora' ? 10 : 14, state === 'lora' ? 'bold' : '');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(glyph, 0, 1);
		ctx.restore();

		// State label below name (small)
		ctx.fillStyle = color;
		ctx.font = canvasFont(fontW, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(stateLabel(state), x + 12, y + h / 2 + 14);
	}

	function wrapText(ctx: CanvasRenderingContext2D, text: string, maxW: number, maxLines: number): string[] {
		const words = text.split(' ');
		const lines: string[] = [];
		let current = '';
		for (const word of words) {
			const test = current ? current + ' ' + word : word;
			if (ctx.measureText(test).width > maxW && current) {
				lines.push(current);
				current = word;
				if (lines.length === maxLines - 1) break;
			} else {
				current = test;
			}
		}
		if (lines.length < maxLines && current) {
			// truncate last line if remaining text wouldn't fit
			let remainder = current;
			const wordIdx = words.indexOf(current.split(' ').pop() || '') + 1;
			if (wordIdx < words.length) {
				remainder = current + ' ' + words.slice(wordIdx).join(' ');
			}
			while (ctx.measureText(remainder + '…').width > maxW && remainder.length > 0) {
				remainder = remainder.slice(0, -1);
			}
			if (wordIdx < words.length) lines.push(remainder + '…');
			else lines.push(current);
		}
		return lines;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const now = performance.now();
		const p = currentPaper();
		const stage = p.stages[stageIdx];

		const padX = canvasPad(w, 16);
		const padY = canvasPad(w, 14);

		// Left third: module boxes
		const leftW = Math.min(260, (w - padX * 2) * 0.4);
		const moduleAreaX = padX;
		const moduleAreaY = padY;
		const moduleAreaH = h - padY * 2;

		const modules: Array<{ name: string; key: 'encoder' | 'projector' | 'llm' }> = [
			{ name: 'Audio Encoder', key: 'encoder' },
			{ name: 'Projector', key: 'projector' },
			{ name: 'LLM', key: 'llm' }
		];

		const boxGap = 10;
		const boxH = (moduleAreaH - boxGap * (modules.length - 1)) / modules.length;

		modules.forEach((m, i) => {
			const by = moduleAreaY + i * (boxH + boxGap);
			drawModuleBox(ctx, moduleAreaX, by, leftW, boxH, m.name, stage[m.key], m.key, w, now);
		});

		// Connection lines between modules (line-art flow)
		ctx.strokeStyle = 'rgba(0,0,0,0.15)';
		ctx.lineWidth = 1;
		ctx.setLineDash([3, 3]);
		for (let i = 0; i < modules.length - 1; i++) {
			const y1 = moduleAreaY + i * (boxH + boxGap) + boxH;
			const y2 = moduleAreaY + (i + 1) * (boxH + boxGap);
			const cx = moduleAreaX + leftW / 2;
			ctx.beginPath();
			ctx.moveTo(cx, y1);
			ctx.lineTo(cx, y2);
			ctx.stroke();
		}
		ctx.setLineDash([]);

		// Right side: stage strip + caption
		const rightX = moduleAreaX + leftW + canvasPad(w, 24);
		const rightW = w - rightX - padX;

		// Stage strip header
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText(p.label.toUpperCase() + ' — TRAINING STAGES', rightX, padY + 10);

		const stripY = padY + 22;
		const stripH = 44;
		const n = p.stages.length;
		const cellGap = 6;
		const cellW = (rightW - cellGap * (n - 1)) / n;

		p.stages.forEach((st, i) => {
			const cx = rightX + i * (cellW + cellGap);
			const isCurrent = i === stageIdx;
			const isPast = i < stageIdx;
			const r = 6;

			// Cell
			if (isCurrent) {
				ctx.shadowColor = p.color;
				ctx.shadowBlur = 10;
			}
			ctx.fillStyle = isCurrent ? p.color + '14' : isPast ? p.color + '08' : '#ffffff';
			ctx.beginPath();
			ctx.roundRect(cx, stripY, cellW, stripH, r);
			ctx.fill();
			ctx.shadowBlur = 0;

			ctx.strokeStyle = isCurrent ? p.color : isPast ? p.color + '66' : 'rgba(0,0,0,0.2)';
			ctx.lineWidth = isCurrent ? 1.5 : 1;
			ctx.beginPath();
			ctx.roundRect(cx, stripY, cellW, stripH, r);
			ctx.stroke();

			// Stage number
			ctx.fillStyle = isCurrent ? p.color : isPast ? p.color + 'aa' : 'rgba(0,0,0,0.4)';
			ctx.font = canvasFont(w, 14, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.fillText(String(i + 1), cx + cellW / 2, stripY + stripH / 2 - 2);

			// Stage state mini-glyphs
			const miniY = stripY + stripH - 10;
			const miniGlyphs = [st.encoder, st.projector, st.llm];
			const miniSpacing = 12;
			const miniStart = cx + cellW / 2 - miniSpacing;
			miniGlyphs.forEach((s, gi) => {
				ctx.fillStyle = STATE_COLORS[s];
				ctx.font = canvasFont(w, s === 'lora' ? 6 : 8, s === 'lora' ? 'bold' : '');
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				const g = s === 'lora' ? 'L' : s === 'frozen' ? '❄' : '🔥';
				ctx.fillText(g, miniStart + gi * miniSpacing, miniY);
			});
		});

		// Stage name below current
		const nameY = stripY + stripH + 16;
		ctx.fillStyle = p.color;
		ctx.font = canvasFont(w, 12, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText(stage.name, rightX, nameY);

		// Data caption (wrapped)
		ctx.fillStyle = 'rgba(0,0,0,0.65)';
		ctx.font = canvasFont(w, 11);
		const captionMaxW = rightW;
		const lines = wrapText(ctx, stage.data, captionMaxW, 3);
		lines.forEach((line, li) => {
			ctx.fillText(line, rightX, nameY + 18 + li * 15);
		});

		// Progress indicator at bottom
		const progressY = h - padY - 4;
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText(`stage ${stageIdx + 1} / ${n}`, w - padX, progressY);
	}

	function tick(ts: number) {
		if (!running) return;

		if (playing) {
			const len = currentPaper().stages.length;
			if (ts - lastStepTime >= STEP_MS) {
				if (stageIdx < len - 1) {
					stageIdx++;
					applyStageChange();
					lastStepTime = ts;
				} else {
					playing = false;
				}
			}
		}

		// Always redraw while pulses may be active
		const now = performance.now();
		const anyPulse = (['encoder', 'projector', 'llm'] as const).some(
			(k) => now - pulseStart[k] < PULSE_MS
		);
		if (playing || anyPulse) {
			draw();
		}

		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		// init prevStates from initial stage
		const s = currentPaper().stages[0];
		prevStates = { encoder: s.encoder, projector: s.projector, llm: s.llm };

		const obs = observeVisibility(
			container,
			() => {
				running = true;
				draw();
				cancelAnimationFrame(raf);
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

	// Re-draw when state changes outside of RAF loop
	$effect(() => {
		// Track reactive deps so $effect re-runs
		stageIdx;
		paper;
		if (canvas) draw();
	});
</script>

<div bind:this={container}>
	<VizPanel title="Freeze Schedule" titleColor="var(--orange)">
		{#snippet controls()}
			{#each PAPERS as p}
				<VizButton color={p.color} active={paper === p.id} onclick={() => setPaper(p.id as typeof paper)}>
					{p.label}
				</VizButton>
			{/each}
			<span class="divider" aria-hidden="true"></span>
			<VizButton color="var(--orange)" onclick={step}>Step</VizButton>
			<VizButton color="var(--orange)" active={playing} onclick={togglePlay}>
				{playing ? 'Pause' : 'Play'}
			</VizButton>
			<VizButton color="var(--orange)" onclick={reset}>Reset</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:320px"></canvas>
		{#snippet caption()}
			Snowflake = frozen, flame = trainable, LoRA = low-rank adapters. The audio encoder stays frozen across every paper and every stage.
		{/snippet}
	</VizPanel>
</div>

<style>
	.divider {
		display: inline-block;
		width: 1px;
		height: 20px;
		background: var(--border);
		margin: 0 0.25rem;
	}
</style>
