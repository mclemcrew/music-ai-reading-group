<script lang="ts">
	import { onMount } from 'svelte';
	import VizPanel from '$lib/components/ui/VizPanel.svelte';
	import VizButton from '$lib/components/ui/VizButton.svelte';
	import { setupCanvas, CANVAS_BG, CANVAS_LABEL, canvasFont, canvasPad } from '$lib/utils/canvas';

	const N_FREQ = 96;
	const N_CB = 8;
	const ENTRIES_PER_CB = 16;
	let K = $state(1);
	let canvas: HTMLCanvasElement;

	// Seeded pseudo-random for deterministic codebooks
	function rng(seed: number): () => number {
		let s = seed >>> 0;
		return () => {
			s = (s * 1664525 + 1013904223) >>> 0;
			return s / 0xffffffff;
		};
	}

	function makeTarget(): number[] {
		const v = new Array(N_FREQ).fill(0);
		// Three harmonic peaks at semitone-spaced positions plus a low rumble
		const peaks = [
			{ pos: 10, amp: 0.95, w: 2.5 },
			{ pos: 22, amp: 0.7, w: 2.0 },
			{ pos: 35, amp: 0.55, w: 1.8 },
			{ pos: 52, amp: 0.35, w: 2.2 },
			{ pos: 68, amp: 0.22, w: 2.8 },
			{ pos: 82, amp: 0.15, w: 3.0 }
		];
		for (let i = 0; i < N_FREQ; i++) {
			for (const p of peaks) {
				v[i] += p.amp * Math.exp(-Math.pow((i - p.pos) / p.w, 2));
			}
		}
		// Smooth noise floor
		const r = rng(7);
		for (let i = 0; i < N_FREQ; i++) v[i] += 0.04 * (r() - 0.5);
		return v;
	}

	function makeCodebooks(): number[][][] {
		const cbs: number[][][] = [];
		for (let level = 0; level < N_CB; level++) {
			const r = rng(1000 + level * 137);
			const entries: number[][] = [];
			// Each level operates at a progressively finer scale: width decreases, amplitude decreases
			const width = Math.max(1.4, 8 - level * 0.9);
			const baseAmp = Math.pow(0.62, level); // exponential decay across levels
			for (let e = 0; e < ENTRIES_PER_CB; e++) {
				const entry = new Array(N_FREQ).fill(0);
				// 1-3 small Gaussian bumps with random sign and position
				const numBumps = 1 + Math.floor(r() * 3);
				for (let b = 0; b < numBumps; b++) {
					const pos = r() * N_FREQ;
					const sign = r() < 0.5 ? -1 : 1;
					const amp = baseAmp * (0.5 + 0.5 * r()) * sign;
					for (let i = 0; i < N_FREQ; i++) {
						entry[i] += amp * Math.exp(-Math.pow((i - pos) / width, 2));
					}
				}
				entries.push(entry);
			}
			cbs.push(entries);
		}
		return cbs;
	}

	const target = makeTarget();
	const codebooks = makeCodebooks();

	function greedyEncode(): { picks: number[]; reconstructions: number[][] } {
		const cumulative = new Array(N_FREQ).fill(0);
		const picks: number[] = [];
		const reconstructions: number[][] = [];
		for (let level = 0; level < N_CB; level++) {
			let bestIdx = 0;
			let bestErr = Infinity;
			for (let e = 0; e < ENTRIES_PER_CB; e++) {
				const cand = codebooks[level][e];
				let err = 0;
				for (let i = 0; i < N_FREQ; i++) {
					const r = target[i] - (cumulative[i] + cand[i]);
					err += r * r;
				}
				if (err < bestErr) {
					bestErr = err;
					bestIdx = e;
				}
			}
			picks.push(bestIdx);
			for (let i = 0; i < N_FREQ; i++) cumulative[i] += codebooks[level][bestIdx][i];
			reconstructions.push([...cumulative]);
		}
		return { picks, reconstructions };
	}

	const { picks, reconstructions } = greedyEncode();

	function rmse(a: number[], b: number[]): number {
		let s = 0;
		for (let i = 0; i < a.length; i++) {
			const d = a[i] - b[i];
			s += d * d;
		}
		return Math.sqrt(s / a.length);
	}

	function draw() {
		if (!canvas) return;
		const { ctx, w, h } = setupCanvas(canvas);
		ctx.fillStyle = CANVAS_BG;
		ctx.fillRect(0, 0, w, h);

		const cbStripH = 56;
		const padL = 44;
		const padR = 16;
		const padT = 28;
		const gap = 18;
		const recH = (h - padT - cbStripH - gap - 36) * 0.62;
		const resH = (h - padT - cbStripH - gap - 36) * 0.38;
		const plotW = w - padL - padR;

		const recon = K === 0 ? new Array(N_FREQ).fill(0) : reconstructions[K - 1];
		const residual = target.map((v, i) => v - recon[i]);

		// === Top panel: target + reconstruction ===
		const tMin = -0.15;
		const tMax = 1.1;
		const ty = (v: number) => padT + recH - ((v - tMin) / (tMax - tMin)) * recH;
		const tx = (i: number) => padL + (i / (N_FREQ - 1)) * plotW;

		// Zero line
		ctx.strokeStyle = 'rgba(31,29,27,0.18)';
		ctx.lineWidth = 0.6;
		ctx.beginPath();
		ctx.moveTo(padL, ty(0));
		ctx.lineTo(padL + plotW, ty(0));
		ctx.stroke();

		// Reconstruction (orange filled)
		ctx.beginPath();
		ctx.moveTo(padL, ty(0));
		for (let i = 0; i < N_FREQ; i++) {
			ctx.lineTo(tx(i), ty(recon[i]));
		}
		ctx.lineTo(padL + plotW, ty(0));
		ctx.closePath();
		ctx.fillStyle = 'rgba(224,112,32,0.22)';
		ctx.fill();
		ctx.strokeStyle = '#e07020';
		ctx.lineWidth = 1.8;
		ctx.beginPath();
		for (let i = 0; i < N_FREQ; i++) {
			const x = tx(i);
			const y = ty(recon[i]);
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Target (dashed dark)
		ctx.strokeStyle = '#1f1d1b';
		ctx.lineWidth = 1.3;
		ctx.setLineDash([4, 3]);
		ctx.beginPath();
		for (let i = 0; i < N_FREQ; i++) {
			const x = tx(i);
			const y = ty(target[i]);
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();
		ctx.setLineDash([]);

		// Title and legend
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 10, '600');
		ctx.textAlign = 'left';
		ctx.fillText('target  vs  reconstruction with K codebooks', padL, padT - 10);
		// Y-axis label
		ctx.save();
		ctx.translate(13, padT + recH / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.textAlign = 'center';
		ctx.font = canvasFont(w, 9);
		ctx.fillText('amplitude', 0, 0);
		ctx.restore();

		// === Middle panel: residual ===
		const resTopY = padT + recH + gap;
		const rMin = -0.6;
		const rMax = 0.6;
		const ry = (v: number) => resTopY + resH / 2 - (v / Math.max(rMax, -rMin)) * (resH / 2);
		// Zero line
		ctx.strokeStyle = 'rgba(31,29,27,0.18)';
		ctx.lineWidth = 0.6;
		ctx.beginPath();
		ctx.moveTo(padL, resTopY + resH / 2);
		ctx.lineTo(padL + plotW, resTopY + resH / 2);
		ctx.stroke();
		// Residual filled
		ctx.beginPath();
		ctx.moveTo(padL, resTopY + resH / 2);
		for (let i = 0; i < N_FREQ; i++) {
			ctx.lineTo(tx(i), ry(residual[i]));
		}
		ctx.lineTo(padL + plotW, resTopY + resH / 2);
		ctx.closePath();
		ctx.fillStyle = 'rgba(41,121,255,0.18)';
		ctx.fill();
		ctx.strokeStyle = '#2979ff';
		ctx.lineWidth = 1.4;
		ctx.beginPath();
		for (let i = 0; i < N_FREQ; i++) {
			const x = tx(i);
			const y = ry(residual[i]);
			i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
		}
		ctx.stroke();

		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.textAlign = 'left';
		ctx.fillText(`residual  (target − reconstruction)`, padL, resTopY - 4);
		ctx.textAlign = 'right';
		ctx.font = canvasFont(w, 9);
		ctx.fillStyle = '#2979ff';
		ctx.fillText(`RMSE = ${rmse(target, recon).toFixed(3)}`, padL + plotW, resTopY - 4);

		// === Bottom strip: 8 codebook indicators ===
		const stripY = h - cbStripH - 8;
		const stripStartX = padL;
		const stripW = plotW;
		const slotW = stripW / N_CB;
		ctx.textAlign = 'left';
		ctx.fillStyle = CANVAS_LABEL;
		ctx.font = canvasFont(w, 9, '600');
		ctx.fillText('codebooks (the picked entry in each is highlighted)', padL, stripY - 6);

		for (let level = 0; level < N_CB; level++) {
			const sx = stripStartX + level * slotW;
			const isUsed = level < K;
			const boxW = slotW - 8;
			const boxH = cbStripH - 16;

			// Box background
			ctx.strokeStyle = isUsed ? '#e07020' : 'rgba(31,29,27,0.22)';
			ctx.lineWidth = isUsed ? 1.4 : 0.8;
			ctx.fillStyle = isUsed ? 'rgba(224,112,32,0.06)' : 'rgba(31,29,27,0.02)';
			ctx.beginPath();
			ctx.roundRect(sx, stripY, boxW, boxH, 4);
			ctx.fill();
			ctx.stroke();

			// Mini-grid of 16 entries (4x4) inside each box
			const gridR = 4;
			const gridC = 4;
			const cellW = (boxW - 8) / gridC;
			const cellH = (boxH - 16) / gridR;
			const gridX = sx + 4;
			const gridY = stripY + 4;
			for (let e = 0; e < ENTRIES_PER_CB; e++) {
				const row = Math.floor(e / gridC);
				const col = e % gridC;
				const cx = gridX + col * cellW;
				const cy = gridY + row * cellH;
				const isPicked = isUsed && picks[level] === e;
				ctx.fillStyle = isPicked
					? '#e07020'
					: isUsed
						? 'rgba(224,112,32,0.18)'
						: 'rgba(31,29,27,0.1)';
				ctx.fillRect(cx + 0.5, cy + 0.5, cellW - 1.5, cellH - 1.5);
			}

			// Level label and picked index
			ctx.fillStyle = isUsed ? '#c8611a' : 'rgba(31,29,27,0.4)';
			ctx.font = canvasFont(w, 8, '600');
			ctx.textAlign = 'center';
			ctx.fillText(
				`cb ${level + 1}${isUsed ? ` · ${picks[level]}` : ''}`,
				sx + boxW / 2,
				stripY + boxH + 9
			);
		}
	}

	$effect(() => {
		void K;
		draw();
	});

	onMount(() => {
		draw();
		const onResize = () => draw();
		window.addEventListener('resize', onResize);
		return () => window.removeEventListener('resize', onResize);
	});
</script>

<VizPanel title="EnCodec: 8 codebooks add up to one frame" titleColor="var(--orange)">
	{#snippet controls()}
		<label class="slider-label">
			<span>K codebooks</span>
			<input type="range" min="0" max={N_CB} step="1" bind:value={K} />
			<span class="k-display">{K} / {N_CB}</span>
		</label>
		<VizButton onclick={() => (K = 0)}>None</VizButton>
		<VizButton onclick={() => (K = 1)}>K=1</VizButton>
		<VizButton onclick={() => (K = N_CB)}>All 8</VizButton>
	{/snippet}
	<canvas bind:this={canvas} height="340" style="height: 340px;"></canvas>
	{#snippet caption()}
		EnCodec encodes each audio frame as <strong>8 codebook indices</strong>. Codebook 1 picks the entry that best matches the raw frame; codebook 2 picks the entry that best matches the <em>residual</em>; codebook 3 corrects what's still left; and so on. Each level only has to cover what the previous levels missed, so codebooks deeper in the stack store progressively finer details. Drag the slider to stack codebooks one at a time and watch the residual shrink — when K = 8 the reconstruction nearly matches the target. <strong>This</strong> is what MERT's acoustic teacher asks the encoder to predict: not the raw spectrum, but which entry from each of the 8 codebooks was chosen.
	{/snippet}
</VizPanel>

<style>
	canvas {
		display: block;
		width: 100%;
		touch-action: none;
	}

	.slider-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.k-display {
		min-width: 3.5em;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--orange);
		text-align: right;
	}

	input[type='range'] {
		-webkit-appearance: none;
		width: 130px;
		height: 5px;
		background: var(--border);
		border-radius: 3px;
		outline: none;
		padding: 8px 0;
	}

	input[type='range']::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: var(--orange);
		cursor: pointer;
		box-shadow: 0 0 4px var(--orange-glow);
	}

	@media (max-width: 640px) {
		input[type='range'] {
			width: 90px;
		}
	}
</style>
