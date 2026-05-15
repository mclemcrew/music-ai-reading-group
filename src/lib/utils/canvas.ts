const DPR = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;

export interface CanvasSetup {
	ctx: CanvasRenderingContext2D;
	w: number;
	h: number;
}

export function setupCanvas(canvas: HTMLCanvasElement): CanvasSetup {
	const rect = canvas.getBoundingClientRect();
	const w = rect.width;
	if (!(canvas as any)._logicalH) (canvas as any)._logicalH = rect.height;
	const h = (canvas as any)._logicalH as number;
	canvas.width = Math.round(w * DPR);
	canvas.height = Math.round(h * DPR);
	canvas.style.height = h + 'px';
	const ctx = canvas.getContext('2d')!;
	ctx.scale(DPR, DPR);
	return { ctx, w, h };
}

export const CANVAS_BG = '#ffffff';
export const CANVAS_GRID = 'rgba(0,0,0,0.1)';
export const CANVAS_LABEL = 'rgba(31,29,27,0.78)';

/**
 * Returns a scaled font string for canvas drawing.
 * Scales proportionally from a 900px reference width, clamped to 65-120%.
 * Minimum rendered size is 8px.
 */
export function canvasFont(w: number, size: number, weight = ''): string {
	const scale = Math.max(0.65, Math.min(1.2, w / 900));
	const px = Math.max(8, Math.round(size * scale));
	return `${weight ? weight + ' ' : ''}${px}px "Quicksand", system-ui, sans-serif`;
}

/**
 * Returns a scaled padding value for canvas drawing.
 * Scales proportionally from a 900px reference width, clamped to 60-100%.
 */
export function canvasPad(w: number, base: number): number {
	const scale = Math.max(0.6, Math.min(1, w / 900));
	return Math.round(base * scale);
}

export function observeVisibility(
	el: Element,
	onVisible: () => void,
	onHidden: () => void
): IntersectionObserver {
	const obs = new IntersectionObserver(
		(entries) => {
			entries.forEach((e) => (e.isIntersecting ? onVisible() : onHidden()));
		},
		{ threshold: 0.05 }
	);
	obs.observe(el);
	return obs;
}
