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

	const GREY = '#9ca3af';
	const TEAL = '#1a9e8f';
	const VIOLET = '#7c4dff';
	const ORANGE = '#e07020';

	type Mode = 'tool' | 'instrument' | 'agent';
	const MODES: Mode[] = ['tool', 'instrument', 'agent'];

	const MODE_LABEL: Record<Mode, string> = {
		tool: 'Tool',
		instrument: 'Instrument',
		agent: 'Agent'
	};

	const MODE_COLOR: Record<Mode, string> = {
		tool: GREY,
		instrument: TEAL,
		agent: VIOLET
	};

	const MODE_DESC: Record<Mode, string> = {
		tool:
			'The musician chooses every output explicitly. The system suggests options on demand and waits — like a chord-suggestion plugin or auto-complete for MIDI.',
		instrument:
			'The musician shapes behaviour through performance, but the system contributes its own choices within a learned model. Like a tuned synth: you play it, but it has a voice.',
		agent:
			'The system perceives context and adapts strategy mid-performance. It can disagree, suggest, lead. By the Kim et al. bar, very few current systems clear this.'
	};

	const MODE_EXAMPLES: Record<Mode, string[]> = {
		tool: ['chord-suggest plugin', 'Magenta drums (offline)', 'AI mastering preset'],
		instrument: ['ROLI Seaboard', 'RAVE live model', 'Surfing Hyperparameters'],
		agent: ['Aria-Duet', 'ReaLJam', 'OMax improv partner']
	};

	let mode = $state<Mode>('instrument');
	let highlight = { x: 0, tx: 0 };
	// Animation phase for control-flow particles
	let phase = 0;

	function setMode(m: Mode) {
		mode = m;
		const idx = MODES.indexOf(m);
		highlight.tx = idx;
	}

	function drawHuman(
		ctx: CanvasRenderingContext2D,
		w: number,
		cx: number,
		cy: number,
		size: number,
		color: string,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.6;
		// Head
		ctx.beginPath();
		ctx.arc(cx, cy - size * 0.55, size * 0.22, 0, Math.PI * 2);
		ctx.stroke();
		// Body
		ctx.beginPath();
		ctx.moveTo(cx, cy - size * 0.32);
		ctx.lineTo(cx, cy + size * 0.18);
		// Arms
		ctx.moveTo(cx - size * 0.32, cy - size * 0.05);
		ctx.lineTo(cx + size * 0.32, cy - size * 0.05);
		// Legs
		ctx.moveTo(cx, cy + size * 0.18);
		ctx.lineTo(cx - size * 0.22, cy + size * 0.5);
		ctx.moveTo(cx, cy + size * 0.18);
		ctx.lineTo(cx + size * 0.22, cy + size * 0.5);
		ctx.stroke();
		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('musician', cx, cy + size * 0.55);
		ctx.restore();
	}

	function drawSystemBox(
		ctx: CanvasRenderingContext2D,
		w: number,
		x: number,
		y: number,
		ww: number,
		hh: number,
		color: string,
		title: string,
		mode: Mode,
		alpha: number
	) {
		ctx.save();
		ctx.globalAlpha = alpha * 0.06;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 6);
		ctx.fill();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.roundRect(x, y, ww, hh, 6);
		ctx.stroke();

		ctx.fillStyle = color;
		ctx.font = canvasFont(w, 12, '700');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(title, x + ww / 2, y + 8);

		// Inside the box: a glyph that varies by mode
		ctx.font = canvasFont(w, 9);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.textBaseline = 'middle';
		const cx = x + ww / 2;
		const midY = y + hh / 2 + 6;

		if (mode === 'tool') {
			// Static rows of presets
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			for (let i = 0; i < 3; i++) {
				ctx.beginPath();
				ctx.roundRect(x + 8, midY - 12 + i * 10, ww - 16, 7, 2);
				ctx.stroke();
			}
			ctx.fillStyle = CANVAS_LABEL;
			ctx.fillText('preset list', cx, midY + 22);
		} else if (mode === 'instrument') {
			// "Latent space" cloud
			ctx.strokeStyle = color;
			ctx.lineWidth = 0.8;
			ctx.globalAlpha = alpha * 0.55;
			for (let i = 0; i < 18; i++) {
				const a = (i / 18) * Math.PI * 2 + phase * 0.4;
				const r = 16 + ((i * 7) % 9);
				ctx.beginPath();
				ctx.arc(cx + Math.cos(a) * r, midY + Math.sin(a) * r * 0.6, 2, 0, Math.PI * 2);
				ctx.stroke();
			}
			ctx.globalAlpha = alpha;
			ctx.fillStyle = CANVAS_LABEL;
			ctx.fillText('learned sound world', cx, midY + 28);
		} else {
			// Agent: a planning glyph
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			const steps = 4;
			for (let i = 0; i < steps; i++) {
				const sx = x + 12 + (i * (ww - 24)) / (steps - 1);
				ctx.beginPath();
				ctx.arc(sx, midY, 4, 0, Math.PI * 2);
				ctx.stroke();
				if (i < steps - 1) {
					ctx.beginPath();
					ctx.moveTo(sx + 4, midY);
					ctx.lineTo(sx + (ww - 24) / (steps - 1) - 4, midY);
					ctx.stroke();
				}
			}
			ctx.fillStyle = CANVAS_LABEL;
			ctx.fillText('plan + adapt', cx, midY + 18);
		}
		ctx.restore();
	}

	function drawArrow(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y1: number,
		x2: number,
		y2: number,
		color: string,
		alpha: number,
		dashed = false,
		thickness = 1.2
	) {
		ctx.save();
		ctx.globalAlpha = alpha;
		ctx.strokeStyle = color;
		ctx.fillStyle = color;
		ctx.lineWidth = thickness;
		if (dashed) ctx.setLineDash([4, 3]);
		ctx.beginPath();
		ctx.moveTo(x1, y1);
		ctx.lineTo(x2, y2);
		ctx.stroke();
		ctx.setLineDash([]);
		const ang = Math.atan2(y2 - y1, x2 - x1);
		ctx.beginPath();
		ctx.moveTo(x2, y2);
		ctx.lineTo(x2 - 6 * Math.cos(ang - Math.PI / 6), y2 - 6 * Math.sin(ang - Math.PI / 6));
		ctx.lineTo(x2 - 6 * Math.cos(ang + Math.PI / 6), y2 - 6 * Math.sin(ang + Math.PI / 6));
		ctx.closePath();
		ctx.fill();
		ctx.restore();
	}

	function drawParticles(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y: number,
		x2: number,
		color: string,
		count: number,
		offset: number,
		alpha: number
	) {
		// Particles flowing from x1 to x2 along y
		ctx.save();
		ctx.fillStyle = color;
		for (let i = 0; i < count; i++) {
			const t = ((phase + offset + i / count) % 1);
			const px = x1 + (x2 - x1) * t;
			ctx.globalAlpha = alpha * Math.sin(t * Math.PI);
			ctx.beginPath();
			ctx.arc(px, y, 2, 0, Math.PI * 2);
			ctx.fill();
		}
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
		const padY = canvasPad(w, 14);
		const sysW = Math.min(190, (w - padX * 2) * 0.4);
		const humanX = padX + 36;
		const humanY = padY + 80;
		const humanSize = 56;

		// Spectrum bar at top
		const barX = padX;
		const barY = padY;
		const barW = w - padX * 2;
		const barH = 24;
		ctx.save();
		ctx.fillStyle = GREY;
		ctx.globalAlpha = 0.07;
		ctx.beginPath();
		ctx.roundRect(barX, barY, barW, barH, 12);
		ctx.fill();
		ctx.restore();
		// Tick stops
		MODES.forEach((m, i) => {
			const x = barX + (barW * (i + 0.5)) / MODES.length;
			const isActive = m === mode;
			ctx.save();
			ctx.fillStyle = MODE_COLOR[m];
			ctx.globalAlpha = isActive ? 1 : 0.4;
			ctx.beginPath();
			ctx.arc(x, barY + barH / 2, isActive ? 8 : 5, 0, Math.PI * 2);
			ctx.fill();
			ctx.fillStyle = isActive ? MODE_COLOR[m] : CANVAS_LABEL;
			ctx.globalAlpha = 1;
			ctx.font = canvasFont(w, 11, isActive ? '700' : '500');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			ctx.fillText(MODE_LABEL[m], x, barY + barH + 4);
			ctx.restore();
		});

		// Smooth highlight indicator (animated bar position)
		const hx = barX + (barW * (highlight.x + 0.5)) / MODES.length;
		ctx.save();
		ctx.strokeStyle = MODE_COLOR[mode];
		ctx.globalAlpha = 0.65;
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.roundRect(hx - 30, barY - 2, 60, barH + 4, 14);
		ctx.stroke();
		ctx.restore();

		// Spectrum endpoint labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('explicit control →', barX + 4, barY + barH + 22);
		ctx.textAlign = 'right';
		ctx.fillText('← intentional behavior', barX + barW - 4, barY + barH + 22);

		// Main scene: musician (left) + system box (right)
		const sceneTop = barY + barH + 50;
		const sceneH = h - sceneTop - 40;

		drawHuman(ctx, w, humanX, sceneTop + sceneH / 2, humanSize, ORANGE, 1);

		// System box
		const sysX = humanX + humanSize + 50;
		const sysY = sceneTop + 8;
		const sysH = sceneH - 16;
		const color = MODE_COLOR[mode];
		drawSystemBox(ctx, w, sysX, sysY, sysW, sysH, color, MODE_LABEL[mode], mode, 1);

		// Control flow arrows + particles between them, mode-dependent
		const fromX = humanX + humanSize * 0.4;
		const toX = sysX;
		const yA = sceneTop + sceneH * 0.32;
		const yB = sceneTop + sceneH * 0.68;

		// Tool: musician → system, dominant; small reply
		// Instrument: musician ↔ system, both bidirectional, equal
		// Agent: bidirectional, plus a self-loop on system (planning)
		if (mode === 'tool') {
			drawArrow(ctx, fromX, yA, toX - 4, yA, ORANGE, 0.85, false, 1.6);
			drawParticles(ctx, fromX + 8, yA, toX - 8, ORANGE, 4, 0, 0.65);
			drawArrow(ctx, toX, yB, fromX + 4, yB, color, 0.55, true, 1);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'center';
			ctx.fillText('command (chosen)', (fromX + toX) / 2, yA - 12);
			ctx.fillText('suggestion (passive)', (fromX + toX) / 2, yB + 10);
		} else if (mode === 'instrument') {
			drawArrow(ctx, fromX, yA, toX - 4, yA, ORANGE, 0.95, false, 1.6);
			drawParticles(ctx, fromX + 8, yA, toX - 8, ORANGE, 5, 0, 0.7);
			drawArrow(ctx, toX, yB, fromX + 4, yB, color, 0.95, false, 1.6);
			drawParticles(ctx, toX - 8, yB, fromX + 8, color, 5, 0.5, 0.7);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'center';
			ctx.fillText('gesture / performance', (fromX + toX) / 2, yA - 12);
			ctx.fillText('responsive sound', (fromX + toX) / 2, yB + 10);
		} else {
			drawArrow(ctx, fromX, yA, toX - 4, yA, ORANGE, 0.85, false, 1.6);
			drawParticles(ctx, fromX + 8, yA, toX - 8, ORANGE, 4, 0, 0.7);
			drawArrow(ctx, toX, yB, fromX + 4, yB, color, 1, false, 1.8);
			drawParticles(ctx, toX - 8, yB, fromX + 8, color, 6, 0.5, 0.85);
			// Self-loop on system
			ctx.save();
			ctx.strokeStyle = color;
			ctx.globalAlpha = 0.6;
			ctx.lineWidth = 1;
			ctx.setLineDash([3, 3]);
			ctx.beginPath();
			const lx = sysX + sysW + 6;
			ctx.arc(lx, sysY + sysH / 2, 14, -Math.PI * 0.85, Math.PI * 0.85);
			ctx.stroke();
			ctx.setLineDash([]);
			ctx.restore();
			ctx.fillStyle = color;
			ctx.font = canvasFont(w, 9);
			ctx.textAlign = 'left';
			ctx.fillText('plan / adapt', sysX + sysW + 12, sysY + sysH / 2 - 22);

			ctx.fillStyle = CANVAS_LABEL;
			ctx.textAlign = 'center';
			ctx.fillText('context (audio + history)', (fromX + toX) / 2, yA - 12);
			ctx.fillText('initiative (lead / follow)', (fromX + toX) / 2, yB + 10);
		}

		// Footer: examples
		const footerY = h - padY - 18;
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('examples in this cell:', padX, footerY);
		ctx.font = canvasFont(w, 9);
		ctx.fillStyle = color;
		ctx.fillText(MODE_EXAMPLES[mode].join('  ·  '), padX + 130, footerY);
	}

	function tick() {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		phase = (phase + 0.006) % 1;
		// Lerp highlight
		const dx = highlight.tx - highlight.x;
		if (Math.abs(dx) > 0.005) highlight.x += dx * 0.16;
		draw();
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		highlight.x = MODES.indexOf(mode);
		highlight.tx = highlight.x;
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
	<VizPanel title="Tool, instrument, agent — what's actually different?" titleColor="var(--violet)">
		{#snippet controls()}
			{#each MODES as m}
				<VizButton color={MODE_COLOR[m]} active={mode === m} onclick={() => setMode(m)}>
					{MODE_LABEL[m]}
				</VizButton>
			{/each}
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		<p class="desc">{MODE_DESC[mode]}</p>
		{#snippet caption()}
			Same musician, same system, different framings. The arrows show how control flows
			between them: a tool waits for commands, an instrument trades signals continuously,
			an agent also has its own internal loop (planning, adapting). Most current AI music
			systems sit ambiguously between tool and instrument — clearing the bar for "agent"
			by Kim et al.'s definition is rare.
		{/snippet}
	</VizPanel>
</div>

<style>
	.desc {
		margin: 0.5rem 0.75rem 0;
		padding: 0.5rem 0.75rem;
		border-left: 2px solid var(--violet);
		background: rgba(124, 77, 255, 0.04);
		font-size: 0.85rem;
		color: var(--text);
		border-radius: 0 4px 4px 0;
	}
</style>
