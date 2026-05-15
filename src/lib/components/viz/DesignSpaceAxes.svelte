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

	const TEAL = '#1a9e8f';
	const ORANGE = '#e07020';
	const VIOLET = '#7c4dff';
	const BLUE = '#2979ff';
	const ROSE = '#d62a70';
	const GREY = '#9ca3af';

	type Axis = 'input' | 'capability' | 'interaction' | 'output';
	const AXES: Axis[] = ['input', 'capability', 'interaction', 'output'];
	const AXIS_LABEL: Record<Axis, string> = {
		input: 'Input modality',
		capability: 'Agent capability',
		interaction: 'Interaction style',
		output: 'Output representation'
	};
	const AXIS_LO: Record<Axis, string> = {
		input: 'audio →',
		capability: 'transcribe →',
		interaction: 'tool →',
		output: 'audio →'
	};
	const AXIS_HI: Record<Axis, string> = {
		input: '← gesture',
		capability: '← compose',
		interaction: '← agent',
		output: '← symbolic'
	};

	type Category = 'instrument' | 'tool-style' | 'agent-claim' | 'reading-group';

	interface System {
		name: string;
		input: number;
		capability: number;
		interaction: number;
		output: number;
		category: Category;
	}

	// Approximate placements of representative systems across the 4 axes.
	// Values are 0..1 in the LO→HI direction defined above.
	const systems: System[] = [
		{ name: 'Aria-Duet', input: 0.55, capability: 0.78, interaction: 0.62, output: 0.7, category: 'agent-claim' },
		{ name: 'ReaLJam', input: 0.5, capability: 0.7, interaction: 0.55, output: 0.6, category: 'agent-claim' },
		{ name: 'OMax / SoMax', input: 0.2, capability: 0.65, interaction: 0.7, output: 0.85, category: 'instrument' },
		{ name: 'BachBot live', input: 0.25, capability: 0.55, interaction: 0.4, output: 0.8, category: 'tool-style' },
		{ name: 'RAVE live', input: 0.15, capability: 0.4, interaction: 0.55, output: 0.18, category: 'instrument' },
		{ name: 'MusicLM (offline)', input: 0.08, capability: 0.92, interaction: 0.15, output: 0.12, category: 'tool-style' },
		{ name: 'Surfing Hyperparams', input: 0.7, capability: 0.45, interaction: 0.55, output: 0.2, category: 'instrument' },
		{ name: 'Spire / gesture agent', input: 0.92, capability: 0.6, interaction: 0.65, output: 0.5, category: 'instrument' },
		{ name: 'Real-time accomp.', input: 0.2, capability: 0.7, interaction: 0.45, output: 0.25, category: 'tool-style' },
		{ name: 'AudioChat', input: 0.3, capability: 0.85, interaction: 0.45, output: 0.3, category: 'tool-style' },
		{ name: 'VampNet', input: 0.18, capability: 0.75, interaction: 0.3, output: 0.18, category: 'tool-style' },
		{ name: 'Anticipatory MT', input: 0.22, capability: 0.7, interaction: 0.35, output: 0.85, category: 'tool-style' },
		{ name: 'Disklavier ghost', input: 0.32, capability: 0.65, interaction: 0.6, output: 0.8, category: 'agent-claim' },
		{ name: 'Symbolic improv (BOB)', input: 0.28, capability: 0.6, interaction: 0.7, output: 0.88, category: 'instrument' },
		{ name: 'JamBot', input: 0.4, capability: 0.55, interaction: 0.55, output: 0.55, category: 'instrument' }
	];

	const categoryColor: Record<Category, string> = {
		instrument: TEAL,
		'tool-style': VIOLET,
		'agent-claim': ROSE,
		'reading-group': BLUE
	};

	let xAxis = $state<Axis>('input');
	let yAxis = $state<Axis>('capability');
	let highlightGaps = $state(true);

	// Smooth lerp positions
	const positions = systems.map(() => ({ tx: 0, ty: 0, x: 0, y: 0 }));

	function setX(a: Axis) {
		if (a === yAxis) return;
		xAxis = a;
	}
	function setY(a: Axis) {
		if (a === xAxis) return;
		yAxis = a;
	}

	function recomputeTargets(plotL: number, plotT: number, plotR: number, plotB: number) {
		const w = plotR - plotL;
		const h = plotB - plotT;
		systems.forEach((s, i) => {
			const xv = (s as any)[xAxis] as number;
			const yv = (s as any)[yAxis] as number;
			positions[i].tx = plotL + xv * w;
			positions[i].ty = plotB - yv * h;
		});
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = canvasPad(w, 40);
		const padR = canvasPad(w, 18);
		const padT = canvasPad(w, 22);
		const padB = canvasPad(w, 32);
		const plotL = padL;
		const plotR = w - padR;
		const plotT = padT;
		const plotB = h - padB;

		recomputeTargets(plotL, plotT, plotR, plotB);

		// Axes
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(plotL, plotB);
		ctx.lineTo(plotR, plotB);
		ctx.moveTo(plotL, plotT);
		ctx.lineTo(plotL, plotB);
		ctx.stroke();

		// Light grid
		ctx.strokeStyle = 'rgba(0,0,0,0.05)';
		for (let i = 1; i <= 4; i++) {
			const gx = plotL + ((plotR - plotL) * i) / 5;
			const gy = plotT + ((plotB - plotT) * i) / 5;
			ctx.beginPath();
			ctx.moveTo(gx, plotT);
			ctx.lineTo(gx, plotB);
			ctx.moveTo(plotL, gy);
			ctx.lineTo(plotR, gy);
			ctx.stroke();
		}

		// Axis labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 11, '600');
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(AXIS_LABEL[xAxis], (plotL + plotR) / 2, plotB + 18);

		ctx.save();
		ctx.translate(plotL - 28, (plotT + plotB) / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.fillText(AXIS_LABEL[yAxis], 0, 0);
		ctx.restore();

		// Axis tick labels (lo / hi)
		ctx.font = canvasFont(w, 9);
		ctx.textAlign = 'left';
		ctx.fillStyle = GREY;
		ctx.fillText(AXIS_LO[xAxis], plotL, plotB + 4);
		ctx.textAlign = 'right';
		ctx.fillText(AXIS_HI[xAxis], plotR, plotB + 4);
		ctx.textAlign = 'center';
		ctx.save();
		ctx.translate(plotL - 12, plotB);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'left';
		ctx.fillText(AXIS_LO[yAxis], 0, 0);
		ctx.restore();
		ctx.save();
		ctx.translate(plotL - 12, plotT);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'right';
		ctx.fillText(AXIS_HI[yAxis], 0, 0);
		ctx.restore();

		// Gap shading: highlight quadrants with low density
		if (highlightGaps) {
			const cells = 3;
			const cellW = (plotR - plotL) / cells;
			const cellH = (plotB - plotT) / cells;
			const cellCount: number[] = new Array(cells * cells).fill(0);
			systems.forEach((s) => {
				const xv = (s as any)[xAxis] as number;
				const yv = (s as any)[yAxis] as number;
				const cx = Math.min(cells - 1, Math.floor(xv * cells));
				const cy = Math.min(cells - 1, Math.floor(yv * cells));
				cellCount[cy * cells + cx]++;
			});
			ctx.save();
			for (let cy = 0; cy < cells; cy++) {
				for (let cx = 0; cx < cells; cx++) {
					if (cellCount[cy * cells + cx] === 0) {
						ctx.fillStyle = ORANGE;
						ctx.globalAlpha = 0.06;
						ctx.fillRect(plotL + cx * cellW, plotB - (cy + 1) * cellH, cellW, cellH);
					}
				}
			}
			ctx.restore();

			// Annotate one empty cell with a label
			const emptyIdx = cellCount.findIndex((c) => c === 0);
			if (emptyIdx >= 0) {
				const cx = emptyIdx % cells;
				const cy = Math.floor(emptyIdx / cells);
				ctx.fillStyle = ORANGE;
				ctx.globalAlpha = 0.85;
				ctx.font = canvasFont(w, 9, '500');
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				ctx.fillText(
					'empty cell',
					plotL + (cx + 0.5) * cellW,
					plotB - (cy + 0.5) * cellH
				);
				ctx.globalAlpha = 1;
			}
		}

		// Draw points
		systems.forEach((s, i) => {
			const p = positions[i];
			const color = categoryColor[s.category];
			ctx.save();
			ctx.globalAlpha = 0.18;
			ctx.fillStyle = color;
			ctx.beginPath();
			ctx.arc(p.x, p.y, 9, 0, Math.PI * 2);
			ctx.fill();
			ctx.globalAlpha = 1;
			ctx.strokeStyle = color;
			ctx.lineWidth = 1.4;
			ctx.beginPath();
			ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
			ctx.stroke();
			ctx.restore();
		});

		// Labels (only those that don't crowd)
		ctx.font = canvasFont(w, 9);
		ctx.fillStyle = CANVAS_LABEL;
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		systems.forEach((s, i) => {
			const p = positions[i];
			ctx.fillText(s.name, p.x + 8, p.y);
		});

		// Legend
		const legendY = padT - 6;
		ctx.font = canvasFont(w, 9, '500');
		ctx.textBaseline = 'middle';
		const legendItems: Array<[string, Category]> = [
			['instrument', 'instrument'],
			['tool-style', 'tool-style'],
			['agent claim', 'agent-claim']
		];
		let lx = plotR;
		[...legendItems].reverse().forEach(([label, cat]) => {
			const tw = ctx.measureText(label).width;
			ctx.fillStyle = categoryColor[cat];
			ctx.beginPath();
			ctx.arc(lx - tw - 14, legendY, 4, 0, Math.PI * 2);
			ctx.fill();
			ctx.fillStyle = CANVAS_LABEL;
			ctx.textAlign = 'right';
			ctx.fillText(label, lx, legendY);
			lx -= tw + 26;
		});
	}

	function tick() {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		let needs = false;
		for (const p of positions) {
			const dx = p.tx - p.x;
			const dy = p.ty - p.y;
			if (Math.abs(dx) > 0.2 || Math.abs(dy) > 0.2) {
				p.x += dx * 0.18;
				p.y += dy * 0.18;
				needs = true;
			}
		}
		if (needs) draw();
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		// Initialize positions immediately
		const rect = canvas.getBoundingClientRect();
		const w = rect.width;
		const padL = canvasPad(w, 40);
		const padR = canvasPad(w, 18);
		const padT = canvasPad(w, 22);
		const padB = canvasPad(w, 32);
		const plotL = padL;
		const plotR = w - padR;
		const plotT = padT;
		const plotB = rect.height - padB;
		recomputeTargets(plotL, plotT, plotR, plotB);
		positions.forEach((p) => {
			p.x = p.tx;
			p.y = p.ty;
		});

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

	$effect(() => {
		// Re-target when axes change
		xAxis;
		yAxis;
		highlightGaps;
		const rect = canvas?.getBoundingClientRect();
		if (!rect) return;
		const w = rect.width;
		const padL = canvasPad(w, 40);
		const padR = canvasPad(w, 18);
		const padT = canvasPad(w, 22);
		const padB = canvasPad(w, 32);
		recomputeTargets(padL, padT, w - padR, rect.height - padB);
	});
</script>

<div bind:this={container}>
	<VizPanel title="A live-music-agent design space (illustrative)" titleColor="var(--moss, #6f8a3a)">
		{#snippet controls()}
			<span class="ax-label">x:</span>
			{#each AXES as a}
				<VizButton color="var(--moss, #6f8a3a)" active={xAxis === a} onclick={() => setX(a)}>
					{AXIS_LABEL[a].split(' ')[0]}
				</VizButton>
			{/each}
			<span class="ax-label">y:</span>
			{#each AXES as a}
				<VizButton color="var(--moss, #6f8a3a)" active={yAxis === a} onclick={() => setY(a)}>
					{AXIS_LABEL[a].split(' ')[0]}
				</VizButton>
			{/each}
			<VizButton
				color="var(--orange)"
				active={highlightGaps}
				onclick={() => (highlightGaps = !highlightGaps)}
			>
				gaps
			</VizButton>
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:380px"></canvas>
		{#snippet caption()}
			An illustrative slice of the Kim et al. design space, populated with systems we've talked
			about in this reading group plus a few canonical references. Pick any two of the four
			axes; toggle <em>gaps</em> to highlight cells with no example systems. Position estimates
			are approximate and editorial — they're meant to spark whiteboard arguments, not settle
			them. The 184-system catalogue in the actual paper is the authoritative version.
		{/snippet}
	</VizPanel>
</div>

<style>
	.ax-label {
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--text-muted);
		margin: 0 0.3rem 0 0.5rem;
		font-weight: 600;
	}
</style>
