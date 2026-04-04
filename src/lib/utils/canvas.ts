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
export const CANVAS_GRID = 'rgba(0,0,0,0.08)';
export const CANVAS_LABEL = 'rgba(0,0,0,0.38)';

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
