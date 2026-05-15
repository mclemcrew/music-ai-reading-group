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

	const VIOLET = '#7c4dff';
	const ORANGE = '#e07020';
	const TEAL = '#1a9e8f';
	const ROSE = '#d62a70';
	const GREY = '#9ca3af';

	type Frame =
		| 'ghost'
		| 'hauntology'
		| 'plundering'
		| 'silicon-naturalism'
		| 'instrumentality';

	const FRAMES: Frame[] = [
		'ghost',
		'hauntology',
		'plundering',
		'silicon-naturalism',
		'instrumentality'
	];

	const FRAME_LABELS: Record<Frame, string> = {
		ghost: 'Ghost in the machine',
		hauntology: 'Sonic hauntology',
		plundering: 'Plundered archives',
		'silicon-naturalism': 'Silicon naturalism',
		instrumentality: 'Just-an-instrument'
	};

	const FRAME_DESC: Record<Frame, string> = {
		ghost:
			'Pop-culture trope: AI is a haunting presence inside the device. Pulls aesthetics toward uncanny, eerie, in-between.',
		hauntology:
			'Mark Fisher / Derrida: the present is constituted by the traces of pasts that didn’t fully arrive. Pulls aesthetics toward decayed, dust, vinyl crackle.',
		plundering:
			'AI as archival recombination — plundering vast datasets and resituating them. Pulls aesthetics toward glitch, collage, recognition-but-displacement.',
		'silicon-naturalism':
			'Frame the model as a new kind of natural process — turbulence, weather, ecology. Pulls aesthetics toward continuous, generative, indifferent.',
		instrumentality:
			'Refuse the AI framing entirely; treat it as an instrument or effects unit. Pulls aesthetics toward the player’s sonic vocabulary.'
	};

	// Position frames in 2D: x = AI-sounding ↔ instrument-sounding, y = narrative-shaped ↔ technology-shaped.
	// Same convention as the paper's framing: high "narrative-shaped" means cultural story dominates.
	const FRAME_POS: Record<Frame, { x: number; y: number; color: string }> = {
		ghost: { x: 0.18, y: 0.85, color: VIOLET },
		hauntology: { x: 0.28, y: 0.92, color: VIOLET },
		plundering: { x: 0.4, y: 0.7, color: ROSE },
		'silicon-naturalism': { x: 0.55, y: 0.55, color: TEAL },
		instrumentality: { x: 0.85, y: 0.18, color: ORANGE }
	};

	let frame = $state<Frame>('hauntology');

	// Smooth highlight position (lerp towards selected frame)
	let highlight = { x: 0, y: 0, tx: 0, ty: 0 };

	function setFrame(f: Frame) {
		frame = f;
		const p = FRAME_POS[f];
		highlight.tx = p.x;
		highlight.ty = p.y;
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';

		const padL = canvasPad(w, 50);
		const padR = canvasPad(w, 18);
		const padT = canvasPad(w, 24);
		const padB = canvasPad(w, 38);
		const plotL = padL;
		const plotR = w - padR;
		const plotT = padT;
		const plotB = h - padB;
		const plotW = plotR - plotL;
		const plotH = plotB - plotT;

		// Quadrant background tints
		ctx.save();
		ctx.globalAlpha = 0.04;
		ctx.fillStyle = VIOLET;
		ctx.fillRect(plotL, plotT, plotW / 2, plotH / 2); // top-left: AI-sounding × narrative-shaped
		ctx.fillStyle = ORANGE;
		ctx.fillRect(plotL + plotW / 2, plotT + plotH / 2, plotW / 2, plotH / 2); // bottom-right
		ctx.restore();

		// Quadrant labels
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('narrative does the work', plotL + 8, plotT + 6);
		ctx.textAlign = 'right';
		ctx.textBaseline = 'top';
		ctx.fillText('— "this sounds AI"', plotR - 8, plotT + 6);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'bottom';
		ctx.fillText('technology does the work', plotL + 8, plotB - 6);
		ctx.textAlign = 'right';
		ctx.fillText('— "this is the instrument"', plotR - 8, plotB - 6);

		// Axes
		ctx.strokeStyle = '#dde0e6';
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		ctx.moveTo(plotL, plotB);
		ctx.lineTo(plotR, plotB);
		ctx.moveTo(plotL, plotT);
		ctx.lineTo(plotL, plotB);
		ctx.stroke();

		// Axis tick labels
		ctx.fillStyle = GREY;
		ctx.font = canvasFont(w, 10, '500');
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('AI-sounding', plotL, plotB + 6);
		ctx.textAlign = 'right';
		ctx.fillText('instrument-sounding', plotR, plotB + 6);
		ctx.save();
		ctx.translate(plotL - 16, (plotT + plotB) / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.fillText('how much the cultural story is doing →', 0, 0);
		ctx.restore();

		// Highlight halo at selected position (smooth)
		const hx = plotL + highlight.x * plotW;
		const hy = plotB - highlight.y * plotH;
		ctx.save();
		const grad = ctx.createRadialGradient(hx, hy, 6, hx, hy, 70);
		grad.addColorStop(0, 'rgba(124,77,255,0.18)');
		grad.addColorStop(1, 'rgba(124,77,255,0)');
		ctx.fillStyle = grad;
		ctx.fillRect(plotL, plotT, plotW, plotH);
		ctx.restore();

		// Plot all frames
		FRAMES.forEach((f) => {
			const p = FRAME_POS[f];
			const x = plotL + p.x * plotW;
			const y = plotB - p.y * plotH;
			const isActive = f === frame;
			ctx.save();
			ctx.globalAlpha = isActive ? 0.3 : 0.12;
			ctx.fillStyle = p.color;
			ctx.beginPath();
			ctx.arc(x, y, isActive ? 14 : 8, 0, Math.PI * 2);
			ctx.fill();
			ctx.globalAlpha = 1;
			ctx.strokeStyle = p.color;
			ctx.lineWidth = isActive ? 2 : 1.2;
			ctx.beginPath();
			ctx.arc(x, y, isActive ? 7 : 5, 0, Math.PI * 2);
			ctx.stroke();
			ctx.restore();

			// Label
			ctx.fillStyle = isActive ? p.color : GREY;
			ctx.font = canvasFont(w, isActive ? 11 : 10, isActive ? '600' : '500');
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText(FRAME_LABELS[f], x + 12, y);
		});

		// Active frame description box
		const desc = FRAME_DESC[frame];
		const boxY = plotT + 6;
		const boxX = plotL + plotW / 2 + 20;
		const boxW = plotR - boxX - 6;
		const lines = wrap(ctx, desc, boxW - 14, canvasFont(w, 10));
		const lineH = 14;
		const boxH = lines.length * lineH + 16;
		ctx.save();
		ctx.fillStyle = '#fff';
		ctx.globalAlpha = 0.9;
		ctx.beginPath();
		ctx.roundRect(boxX, boxY, boxW, boxH, 4);
		ctx.fill();
		ctx.globalAlpha = 1;
		ctx.strokeStyle = FRAME_POS[frame].color;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.roundRect(boxX, boxY, boxW, boxH, 4);
		ctx.stroke();
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10);
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		lines.forEach((line, i) => {
			ctx.fillText(line, boxX + 8, boxY + 8 + i * lineH);
		});
		ctx.restore();
	}

	function wrap(
		ctx: CanvasRenderingContext2D,
		text: string,
		maxW: number,
		font: string
	): string[] {
		ctx.font = font;
		const words = text.split(/\s+/);
		const lines: string[] = [];
		let cur = '';
		for (const wd of words) {
			const trial = cur ? cur + ' ' + wd : wd;
			if (ctx.measureText(trial).width > maxW && cur) {
				lines.push(cur);
				cur = wd;
			} else {
				cur = trial;
			}
		}
		if (cur) lines.push(cur);
		return lines;
	}

	function tick() {
		if (!running) {
			raf = requestAnimationFrame(tick);
			return;
		}
		const dx = highlight.tx - highlight.x;
		const dy = highlight.ty - highlight.y;
		if (Math.abs(dx) > 0.002 || Math.abs(dy) > 0.002) {
			highlight.x += dx * 0.16;
			highlight.y += dy * 0.16;
			draw();
		}
		raf = requestAnimationFrame(tick);
	}

	onMount(() => {
		const init = FRAME_POS[frame];
		highlight.x = init.x;
		highlight.y = init.y;
		highlight.tx = init.x;
		highlight.ty = init.y;
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
		frame;
		draw();
	});
</script>

<div bind:this={container}>
	<VizPanel title="What story is doing the work?" titleColor="var(--violet)">
		{#snippet controls()}
			{#each FRAMES as f}
				<VizButton color="var(--violet)" active={frame === f} onclick={() => setFrame(f)}>
					{FRAME_LABELS[f]}
				</VizButton>
			{/each}
		{/snippet}
		<canvas bind:this={canvas} style="width:100%;height:340px"></canvas>
		{#snippet caption()}
			Five common cultural framings for AI music, plotted by how "AI-sounding" the resulting
			work tends to feel and how much of that feeling is doing narrative work versus technical
			work. The Pelinski paper concentrates on the upper-left region — where the cultural
			story is doing more of the lifting than the technology. Click each framing to see what
			it pulls toward.
		{/snippet}
	</VizPanel>
</div>
