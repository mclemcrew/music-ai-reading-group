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

	type Pattern = 'hands-off' | 'observational' | 'concurrent' | 'directive' | 'terminating';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let raf = 0;
	let running = true;
	let pattern = $state<Pattern>('hands-off');
	let cyclePlaying = $state(false);
	let cycleStart = 0;
	const CYCLE_MS = 2400;
	const ORDER: Pattern[] = ['hands-off', 'observational', 'concurrent', 'directive', 'terminating'];

	const TEAL = '#1a9e8f';
	const ORANGE = '#e07020';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const RED = '#e03131';
	const GREY = '#9ca3af';

	const PATTERN_META: Record<
		Pattern,
		{ label: string; pct: string; color: string; note: string }
	> = {
		'hands-off': {
			label: 'Hands-off',
			pct: '70.1%',
			color: TEAL,
			note: 'Full delegation. User disengages to focus on other tasks.'
		},
		observational: {
			label: 'Observational',
			pct: '68.7%',
			color: BLUE,
			note: 'User watches without intervening. Builds mental model of the agent.'
		},
		concurrent: {
			label: 'Concurrent',
			pct: '31.8%',
			color: VIOLET,
			note: 'User and agent edit the same artifact at the same time. The category most agent architectures cannot see.'
		},
		directive: {
			label: 'Directive',
			pct: '28.5%',
			color: ORANGE,
			note: 'Verbal redirection. "Make it blue, not red."'
		},
		terminating: {
			label: 'Terminating',
			pct: '8.9%',
			color: RED,
			note: 'Stop the agent before completion. Cheap in human-AI work, expensive in human-human work.'
		}
	};

	function roundedRect(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		r: number
	) {
		ctx.beginPath();
		ctx.roundRect(x, y, w, h, r);
	}

	function drawCanvasArtifact(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number
	) {
		ctx.strokeStyle = 'rgba(0,0,0,0.18)';
		ctx.lineWidth = 1;
		roundedRect(ctx, x, y, w, h, 4);
		ctx.stroke();
		// faint grid
		ctx.strokeStyle = 'rgba(0,0,0,0.06)';
		ctx.lineWidth = 0.6;
		for (let i = 1; i < 4; i++) {
			ctx.beginPath();
			ctx.moveTo(x + (w * i) / 4, y);
			ctx.lineTo(x + (w * i) / 4, y + h);
			ctx.stroke();
		}
		for (let i = 1; i < 3; i++) {
			ctx.beginPath();
			ctx.moveTo(x, y + (h * i) / 3);
			ctx.lineTo(x + w, y + (h * i) / 3);
			ctx.stroke();
		}
	}

	function drawCursor(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		color: string,
		label: string,
		canvasW: number
	) {
		// arrow cursor
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.moveTo(x, y);
		ctx.lineTo(x + 9, y + 11);
		ctx.lineTo(x + 4, y + 11);
		ctx.lineTo(x + 2, y + 16);
		ctx.lineTo(x, y);
		ctx.closePath();
		ctx.fill();
		// label pill
		ctx.fillStyle = color + '22';
		const labelW = label.length * 5 + 10;
		roundedRect(ctx, x + 10, y - 4, labelW, 12, 6);
		ctx.fill();
		ctx.fillStyle = color;
		ctx.font = canvasFont(canvasW, 9, 'bold');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, x + 10 + labelW / 2, y + 2);
	}

	function drawWorkZone(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		color: string,
		dashed: boolean,
		filled: boolean
	) {
		if (filled) {
			ctx.fillStyle = color + '18';
			roundedRect(ctx, x, y, w, h, 3);
			ctx.fill();
		}
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		if (dashed) ctx.setLineDash([3, 3]);
		roundedRect(ctx, x, y, w, h, 3);
		ctx.stroke();
		ctx.setLineDash([]);
	}

	function drawSpeechBubble(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		text: string,
		color: string,
		canvasW: number
	) {
		const padding = 6;
		ctx.font = canvasFont(canvasW, 10);
		const tw = ctx.measureText(text).width;
		const w = tw + padding * 2;
		const h = 18;
		ctx.fillStyle = '#fff';
		ctx.strokeStyle = color;
		ctx.lineWidth = 1.2;
		roundedRect(ctx, x, y, w, h, 4);
		ctx.fill();
		ctx.stroke();
		// tail
		ctx.beginPath();
		ctx.moveTo(x + 6, y + h);
		ctx.lineTo(x + 10, y + h + 5);
		ctx.lineTo(x + 14, y + h);
		ctx.closePath();
		ctx.fillStyle = '#fff';
		ctx.fill();
		ctx.strokeStyle = color;
		ctx.beginPath();
		ctx.moveTo(x + 6, y + h);
		ctx.lineTo(x + 10, y + h + 5);
		ctx.lineTo(x + 14, y + h);
		ctx.stroke();

		ctx.fillStyle = color;
		ctx.font = canvasFont(canvasW, 10, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(text, x + padding, y + h / 2);
	}

	function drawX(
		ctx: CanvasRenderingContext2D,
		cx: number,
		cy: number,
		r: number,
		color: string
	) {
		ctx.strokeStyle = color;
		ctx.lineWidth = 2.4;
		ctx.beginPath();
		ctx.moveTo(cx - r, cy - r);
		ctx.lineTo(cx + r, cy + r);
		ctx.moveTo(cx + r, cy - r);
		ctx.lineTo(cx - r, cy + r);
		ctx.stroke();
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 24);
		const padY = canvasPad(w, 24);

		// Artifact canvas
		const artX = padX;
		const artY = padY + 26;
		const artW = w - padX * 2;
		const artH = h - artY - padY - 28;

		drawCanvasArtifact(ctx, artX, artY, artW, artH);

		// Title above artifact
		const meta = PATTERN_META[pattern];
		ctx.fillStyle = meta.color;
		ctx.font = canvasFont(w, 12, 'bold');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(meta.label, artX, padY + 10);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11);
		ctx.fillText(meta.pct + ' of turns', artX + meta.label.length * 7 + 18, padY + 10);

		// Caption at bottom
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		// wrap long captions
		const words = meta.note.split(' ');
		let line = '';
		const maxCharsPerLine = Math.floor((w - padX * 2) / 5.6);
		const lines: string[] = [];
		for (const word of words) {
			if ((line + word).length > maxCharsPerLine) {
				lines.push(line.trim());
				line = word + ' ';
			} else {
				line += word + ' ';
			}
		}
		if (line.trim()) lines.push(line.trim());
		const lineY = artY + artH + 14;
		lines.forEach((l, i) => ctx.fillText(l, artX, lineY + i * 12));

		// Pattern-specific drawing
		const cw = artW;
		const ch = artH;

		if (pattern === 'hands-off') {
			// Agent works in center; user cursor is outside the canvas (top-right) on "other task"
			drawWorkZone(
				ctx,
				artX + cw * 0.3,
				artY + ch * 0.3,
				cw * 0.4,
				ch * 0.4,
				ORANGE,
				false,
				true
			);
			drawCursor(ctx, artX + cw * 0.45, artY + ch * 0.45, ORANGE, 'agent', w);
			// User off-canvas, positioned with label-room to the right
			drawCursor(ctx, artX + cw - 80, artY - 18, TEAL, 'user', w);
			// Faint trail to indicate user is elsewhere
			ctx.strokeStyle = TEAL + '55';
			ctx.lineWidth = 0.8;
			ctx.setLineDash([2, 3]);
			ctx.beginPath();
			ctx.moveTo(artX + cw - 74, artY - 14);
			ctx.lineTo(artX + cw - 40, artY - 22);
			ctx.stroke();
			ctx.setLineDash([]);
			ctx.fillStyle = TEAL + 'cc';
			ctx.font = canvasFont(w, 10, 'bold');
			ctx.textAlign = 'right';
			ctx.fillText('on other task', artX + cw - 4, artY - 24);
		} else if (pattern === 'observational') {
			drawWorkZone(
				ctx,
				artX + cw * 0.3,
				artY + ch * 0.3,
				cw * 0.4,
				ch * 0.4,
				ORANGE,
				false,
				true
			);
			drawCursor(ctx, artX + cw * 0.45, artY + ch * 0.45, ORANGE, 'agent', w);
			// User cursor present but outside agent's work zone
			drawCursor(ctx, artX + cw * 0.8, artY + ch * 0.2, TEAL, 'user', w);
			// "watching" eye glyph
			ctx.strokeStyle = TEAL + 'cc';
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.arc(artX + cw * 0.78, artY + ch * 0.18, 6, 0, Math.PI * 2);
			ctx.stroke();
			ctx.beginPath();
			ctx.arc(artX + cw * 0.78, artY + ch * 0.18, 2.5, 0, Math.PI * 2);
			ctx.fillStyle = TEAL;
			ctx.fill();
		} else if (pattern === 'concurrent') {
			// Agent zone and user zone OVERLAP — the central CLEO finding
			drawWorkZone(
				ctx,
				artX + cw * 0.2,
				artY + ch * 0.3,
				cw * 0.4,
				ch * 0.4,
				ORANGE,
				false,
				true
			);
			drawWorkZone(
				ctx,
				artX + cw * 0.45,
				artY + ch * 0.4,
				cw * 0.4,
				ch * 0.4,
				TEAL,
				false,
				true
			);
			// Overlap shading
			ctx.fillStyle = VIOLET + '33';
			roundedRect(ctx, artX + cw * 0.45, artY + ch * 0.4, cw * 0.15, ch * 0.3, 3);
			ctx.fill();
			ctx.strokeStyle = VIOLET;
			ctx.lineWidth = 1.4;
			ctx.setLineDash([3, 2]);
			roundedRect(ctx, artX + cw * 0.45, artY + ch * 0.4, cw * 0.15, ch * 0.3, 3);
			ctx.stroke();
			ctx.setLineDash([]);

			drawCursor(ctx, artX + cw * 0.32, artY + ch * 0.45, ORANGE, 'agent', w);
			drawCursor(ctx, artX + cw * 0.6, artY + ch * 0.55, TEAL, 'user', w);

			// Overlap label
			ctx.fillStyle = VIOLET;
			ctx.font = canvasFont(w, 9, 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'top';
			ctx.fillText(
				'shared edits',
				artX + cw * 0.525,
				artY + ch * 0.4 + ch * 0.3 + 2
			);
		} else if (pattern === 'directive') {
			drawWorkZone(
				ctx,
				artX + cw * 0.3,
				artY + ch * 0.3,
				cw * 0.4,
				ch * 0.4,
				ORANGE,
				false,
				true
			);
			drawCursor(ctx, artX + cw * 0.45, artY + ch * 0.45, ORANGE, 'agent', w);
			// User cursor with speech bubble pointing at agent zone
			drawCursor(ctx, artX + cw * 0.78, artY + ch * 0.18, TEAL, 'user', w);
			drawSpeechBubble(
				ctx,
				artX + cw * 0.6,
				artY + ch * 0.08,
				'blue, not red',
				TEAL,
				w
			);
		} else if (pattern === 'terminating') {
			drawWorkZone(
				ctx,
				artX + cw * 0.3,
				artY + ch * 0.3,
				cw * 0.4,
				ch * 0.4,
				ORANGE,
				true,
				false
			);
			// Faded agent cursor (about to be stopped)
			ctx.globalAlpha = 0.5;
			drawCursor(ctx, artX + cw * 0.45, artY + ch * 0.45, ORANGE, 'agent', w);
			ctx.globalAlpha = 1;
			// User clicks stop
			drawCursor(ctx, artX + cw * 0.5, artY + ch * 0.5, TEAL, 'user', w);
			// Big red X over the agent's work
			drawX(ctx, artX + cw * 0.5, artY + ch * 0.5, 24, RED);
		}
	}

	function setPattern(p: Pattern) {
		pattern = p;
		if (cyclePlaying) {
			cyclePlaying = false;
			cancelAnimationFrame(raf);
		}
		draw();
	}

	function tickCycle() {
		if (!running || !cyclePlaying) return;
		const elapsed = performance.now() - cycleStart;
		const idx = Math.floor(elapsed / CYCLE_MS) % ORDER.length;
		if (ORDER[idx] !== pattern) {
			pattern = ORDER[idx];
			draw();
		}
		raf = requestAnimationFrame(tickCycle);
	}

	function toggleCycle() {
		if (cyclePlaying) {
			cyclePlaying = false;
			cancelAnimationFrame(raf);
		} else {
			cyclePlaying = true;
			cycleStart = performance.now();
			tickCycle();
		}
	}

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {},
			() => {
				if (cyclePlaying) {
					cyclePlaying = false;
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
	<VizPanel title="Five Action Patterns · CLEO" titleColor="var(--violet)">
		{#snippet controls()}
			<div class="pattern-row">
				{#each ORDER as p}
					<VizButton
						color={PATTERN_META[p].color}
						active={pattern === p}
						onclick={() => setPattern(p)}
					>
						{PATTERN_META[p].label}
					</VizButton>
				{/each}
			</div>
			<VizButton color="var(--violet)" active={cyclePlaying} onclick={toggleCycle}>
				{cyclePlaying ? 'Pause' : 'Cycle'}
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:280px"></canvas>
		{#snippet caption()}
			Toggle the five patterns. The percentages sum to more than 100 because Son et al.'s
			coding allows up to five categories per turn. The pattern most current music-AI agents
			cannot perceive is <em>Concurrent</em>: the overlap region marks edits both the user
			and the agent are making to the same artifact at the same time.
		{/snippet}
	</VizPanel>
</div>

<style>
	.pattern-row {
		display: flex;
		gap: 0.3rem;
		padding-right: 0.5rem;
		border-right: 1px solid var(--border);
		margin-right: 0.25rem;
		flex-wrap: wrap;
	}
</style>
