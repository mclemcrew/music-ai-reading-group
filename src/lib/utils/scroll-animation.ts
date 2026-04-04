import { animate, stagger } from 'animejs';

export function animateOnScroll(
	elements: HTMLElement[],
	animProps: Record<string, any>
) {
	if (!elements.length) return;

	elements.forEach((el) => {
		el.style.opacity = '0';
		el.style.transform = 'translateY(16px)';
	});

	const obs = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				if (!entry.isIntersecting) return;
				animate(elements, {
					translateY: [20, 0],
					opacity: [0, 1],
					delay: stagger(100, { start: 100 }),
					ease: 'outExpo',
					duration: 700,
					...animProps
				});
				obs.unobserve(entry.target);
			});
		},
		{ threshold: 0.15 }
	);

	obs.observe(elements[0].parentElement || elements[0]);
	return obs;
}
