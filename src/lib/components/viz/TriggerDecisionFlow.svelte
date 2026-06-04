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

	type Trigger =
		| 'misaligned'
		| 'idea-spark'
		| 'detailing'
		| 'early-visibility'
		| 'quality-drop'
		| 'new-task';

	type Modality = 'verbal' | 'direct' | 'uncertain';

	type Action = 'concurrent' | 'directive' | 'terminating';

	let canvas: HTMLCanvasElement;
	let container: HTMLElement;
	let raf = 0;
	let running = true;
	let trigger = $state<Trigger | null>(null);
	let modality = $state<Modality | null>(null);
	let highlightPath = $state(false);

	const TEAL = '#1a9e8f';
	const ORANGE = '#e07020';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const RED = '#e03131';
	const GREY = '#9ca3af';

	const TRIGGERS: { id: Trigger; label: string; allowed: Action[] }[] = [
		{ id: 'idea-spark', label: 'Idea spark from WIP', allowed: ['concurrent'] },
		{ id: 'early-visibility', label: 'Need early visibility', allowed: ['concurrent'] },
		{ id: 'detailing', label: 'Ready for detailing', allowed: ['concurrent'] },
		{
			id: 'misaligned',
			label: 'Misaligned interpretation',
			allowed: ['concurrent', 'directive', 'terminating']
		},
		{
			id: 'quality-drop',
			label: 'Execution quality drop',
			allowed: ['concurrent', 'directive', 'terminating']
		},
		{ id: 'new-task', label: 'New task for agent', allowed: ['directive', 'terminating'] }
	];

	const MODALITIES: { id: Modality; label: string; routes: Action }[] = [
		{ id: 'direct', label: 'Direct manipulation easier', routes: 'concurrent' },
		{ id: 'verbal', label: 'Verbal explanation easier', routes: 'directive' },
		{ id: 'uncertain', label: 'Uncertain how to intervene', routes: 'terminating' }
	];

	const ACTIONS: { id: Action; label: string; color: string; pct: string }[] = [
		{ id: 'concurrent', label: 'Concurrent', color: VIOLET, pct: '31.8%' },
		{ id: 'directive', label: 'Directive', color: ORANGE, pct: '28.5%' },
		{ id: 'terminating', label: 'Terminating', color: RED, pct: '8.9%' }
	];

	function activeAction(): Action | null {
		if (!trigger || !modality) return null;
		const t = TRIGGERS.find((x) => x.id === trigger)!;
		const m = MODALITIES.find((x) => x.id === modality)!;
		if (t.allowed.includes(m.routes)) return m.routes;
		// blocked path — return null so we can render the "blocked" state
		return null;
	}

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

	function drawPill(
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		color: string,
		text: string,
		active: boolean,
		dimmed: boolean,
		canvasW: number,
		subtext?: string
	) {
		const alpha = dimmed ? 0.3 : 1;
		ctx.globalAlpha = alpha;
		if (active) {
			ctx.shadowColor = color;
			ctx.shadowBlur = 12;
		}
		ctx.fillStyle = color + (active ? '22' : '0c');
		roundedRect(ctx, x, y, w, h, h / 2);
		ctx.fill();
		ctx.strokeStyle = color;
		ctx.lineWidth = active ? 1.8 : 1;
		roundedRect(ctx, x, y, w, h, h / 2);
		ctx.stroke();
		ctx.shadowBlur = 0;
		ctx.fillStyle = active ? color : color + 'cc';
		ctx.font = canvasFont(canvasW, subtext ? 10 : 11, active ? 'bold' : '');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		if (subtext) {
			ctx.fillText(text, x + w / 2, y + h / 2 - 5);
			ctx.fillStyle = CANVAS_LABEL;
			ctx.font = canvasFont(canvasW, 9);
			ctx.fillText(subtext, x + w / 2, y + h / 2 + 7);
		} else {
			ctx.fillText(text, x + w / 2, y + h / 2);
		}
		ctx.globalAlpha = 1;
	}

	function drawConnector(
		ctx: CanvasRenderingContext2D,
		x1: number,
		y1: number,
		x2: number,
		y2: number,
		active: boolean,
		blocked: boolean
	) {
		ctx.strokeStyle = blocked
			? RED + (active ? 'cc' : '44')
			: active
				? '#333'
				: 'rgba(0,0,0,0.16)';
		ctx.lineWidth = active ? 1.6 : 1;
		ctx.setLineDash(blocked ? [4, 3] : []);
		ctx.beginPath();
		const midY = (y1 + y2) / 2;
		ctx.moveTo(x1, y1);
		ctx.bezierCurveTo(x1, midY, x2, midY, x2, y2);
		ctx.stroke();
		ctx.setLineDash([]);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padX = canvasPad(w, 16);
		const padY = canvasPad(w, 18);

		// Three rows: triggers (top), modality (middle), action (bottom)
		const rowH = (h - padY * 2) / 3;
		const trigY = padY + rowH * 0.5;
		const modY = padY + rowH * 1.5;
		const actY = padY + rowH * 2.5;

		// TRIGGER ROW (6 pills)
		const trigPillW = (w - padX * 2 - 5 * 6) / 6;
		const trigPillH = 38;
		const trigPositions: number[] = [];
		TRIGGERS.forEach((t, i) => {
			const x = padX + i * (trigPillW + 6);
			trigPositions.push(x + trigPillW / 2);
			const active = trigger === t.id;
			const dimmed = trigger !== null && trigger !== t.id;
			drawPill(ctx, x, trigY - trigPillH / 2, trigPillW, trigPillH, BLUE, t.label, active, dimmed, w);
		});

		// MODALITY ROW (3 pills)
		const modPillW = (w - padX * 2 - 5 * 3) / 3;
		const modPillH = 44;
		const modPositions: number[] = [];
		MODALITIES.forEach((m, i) => {
			const x = padX + i * (modPillW + 8) + (w - padX * 2 - 3 * modPillW - 16) / 2;
			modPositions.push(x + modPillW / 2);
			const active = modality === m.id;
			const dimmed = modality !== null && modality !== m.id;
			drawPill(ctx, x, modY - modPillH / 2, modPillW, modPillH, TEAL, m.label, active, dimmed, w);
		});

		// ACTION ROW (3 pills)
		const actPillW = (w - padX * 2 - 5 * 3) / 3;
		const actPillH = 44;
		const actPositions: number[] = [];
		const result = activeAction();
		ACTIONS.forEach((a, i) => {
			const x = padX + i * (actPillW + 8) + (w - padX * 2 - 3 * actPillW - 16) / 2;
			actPositions.push(x + actPillW / 2);
			const active = result === a.id;
			const dimmed = result !== null && result !== a.id;
			drawPill(
				ctx,
				x,
				actY - actPillH / 2,
				actPillW,
				actPillH,
				a.color,
				a.label,
				active,
				dimmed,
				w,
				a.pct
			);
		});

		// CONNECTORS: trigger → modality
		if (trigger) {
			const tIdx = TRIGGERS.findIndex((t) => t.id === trigger);
			const tX = trigPositions[tIdx];
			MODALITIES.forEach((m, i) => {
				const allowedFromTrigger = TRIGGERS[tIdx].allowed.includes(m.routes);
				const isSelected = modality === m.id;
				drawConnector(
					ctx,
					tX,
					trigY + trigPillH / 2,
					modPositions[i],
					modY - modPillH / 2,
					isSelected,
					!allowedFromTrigger
				);
			});
		}

		// CONNECTORS: modality → action
		if (modality) {
			const mIdx = MODALITIES.findIndex((m) => m.id === modality);
			const mX = modPositions[mIdx];
			const targetAction = MODALITIES[mIdx].routes;
			const aIdx = ACTIONS.findIndex((a) => a.id === targetAction);
			const aX = actPositions[aIdx];
			const blocked = trigger
				? !TRIGGERS.find((t) => t.id === trigger)!.allowed.includes(targetAction)
				: false;
			drawConnector(ctx, mX, modY + modPillH / 2, aX, actY - actPillH / 2, true, blocked);
		}

		// Status text under the bottom row
		if (trigger && modality) {
			ctx.fillStyle = result ? CANVAS_LABEL : RED;
			ctx.font = canvasFont(w, 10, result ? '' : 'bold');
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			const msg = result
				? 'Path: trigger → modality → action category'
				: "Path blocked: this trigger doesn't lead to this modality's action";
			ctx.fillText(msg, w / 2, actY + actPillH / 2 + 14);
		}

		// Row labels (left margin, vertical orientation if too wide)
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText('① trigger', padX, trigY - trigPillH / 2 - 8);
		ctx.fillText('② intervention modality', padX, modY - modPillH / 2 - 8);
		ctx.fillText('③ action category', padX, actY - actPillH / 2 - 8);
	}

	function setTrigger(t: Trigger) {
		trigger = trigger === t ? null : t;
		draw();
	}

	function setModality(m: Modality) {
		modality = modality === m ? null : m;
		draw();
	}

	function reset() {
		trigger = null;
		modality = null;
		draw();
	}

	$effect(() => {
		void trigger;
		void modality;
		draw();
	});

	onMount(() => {
		draw();
		const obs = observeVisibility(
			container,
			() => {},
			() => {}
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
	<VizPanel title="Decision Model · Trigger → Action" titleColor="var(--orange)">
		{#snippet controls()}
			<VizButton color="var(--orange)" onclick={reset}>Reset</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		{#snippet caption()}
			Pick a trigger from the top row, then an intervention modality from the middle. The
			bottom row resolves to the action category Son et al. observed for that combination.
			Dashed red lines mark paths the data does not support: e.g., <em>idea spark</em> never
			leads to <em>terminating</em>, only to <em>concurrent</em>. The trigger row pills are
			clickable.
		{/snippet}
	</VizPanel>
	<div class="picker">
		<div class="picker-row">
			<span class="picker-label">trigger</span>
			{#each TRIGGERS as t}
				<button
					class="chip"
					class:active={trigger === t.id}
					style="--chip-color: {BLUE}"
					onclick={() => setTrigger(t.id)}
				>
					{t.label}
				</button>
			{/each}
		</div>
		<div class="picker-row">
			<span class="picker-label">modality</span>
			{#each MODALITIES as m}
				<button
					class="chip"
					class:active={modality === m.id}
					style="--chip-color: {TEAL}"
					onclick={() => setModality(m.id)}
				>
					{m.label}
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.picker {
		padding: 0.75rem 1.5rem 1.25rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-top: none;
		border-radius: 0 0 12px 12px;
		margin-top: -1.5rem;
		margin-bottom: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.picker-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
	}

	.picker-label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-right: 0.4rem;
		min-width: 4.5rem;
	}

	.chip {
		font-family: var(--font-display);
		font-size: 0.75rem;
		padding: 0.3rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--chip-color, var(--border));
		color: var(--chip-color, var(--text-muted));
		background: transparent;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.chip:hover {
		background: var(--chip-color, var(--border));
		color: white;
		opacity: 0.85;
	}

	.chip.active {
		background: var(--chip-color, var(--border));
		color: white;
		font-weight: 600;
	}

	@media (max-width: 640px) {
		.picker {
			padding: 0.6rem 1rem 1rem;
		}
		.picker-label {
			min-width: 100%;
		}
	}
</style>
