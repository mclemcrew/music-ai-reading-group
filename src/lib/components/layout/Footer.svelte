<script lang="ts">
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';

	let noteHead: SVGEllipseElement | undefined = $state();
	let noteStem: SVGPathElement | undefined = $state();
	let mark: SVGSVGElement | undefined = $state();

	onMount(() => {
		if (!mark || !noteHead || !noteStem) return;
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced) return;

		const parts: SVGGeometryElement[] = [noteHead, noteStem];
		for (const p of parts) {
			const len = p.getTotalLength();
			p.style.strokeDasharray = `${len}`;
			p.style.strokeDashoffset = `${len}`;
		}

		const obs = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (!e.isIntersecting) continue;
					animate(parts, {
						strokeDashoffset: 0,
						duration: 800,
						delay: stagger(180),
						ease: 'outQuad'
					});
					obs.disconnect();
				}
			},
			{ threshold: 0.4 }
		);
		obs.observe(mark);
	});
</script>

<footer>
	<p class="aside">For the humans making music AI.</p>
	<p class="meta">
		Music AI Reading Group <span class="dot">·</span> notes and demos after reading music + ML papers
	</p>
	<p class="signature">
		<span>made with</span>
		<svg bind:this={mark} class="mark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<ellipse bind:this={noteHead} cx="9" cy="17" rx="4.6" ry="3.3" transform="rotate(-22 9 17)" />
			<path bind:this={noteStem} d="M13.2 14.5 L13.2 4" />
		</svg>
		<span>by</span>
		<a href="https://mclem.in" target="_blank" rel="noopener">MClem</a>
	</p>
</footer>

<style>
	footer {
		text-align: center;
		padding: 3rem 1.5rem 2.5rem;
		color: var(--text-muted);
		border-top: 1px solid var(--border);
		margin-top: 2rem;
	}

	footer p {
		margin: 0;
	}

	.aside {
		font-family: var(--font-hand);
		font-size: 1.35rem;
		color: var(--orange);
		line-height: 1.2;
		margin-bottom: 0.6rem;
		transform: rotate(-1deg);
	}

	.meta {
		font-size: 0.85rem;
		max-width: 36rem;
		margin: 0 auto 1.1rem;
		line-height: 1.5;
	}

	.dot {
		opacity: 0.5;
		margin: 0 0.25rem;
	}

	.signature {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-display);
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.signature .mark {
		color: var(--orange);
		transform: translateY(-1px);
	}

	.signature a {
		color: var(--text);
		text-decoration: none;
		border-bottom: 1px solid var(--orange);
		padding-bottom: 1px;
	}

	.signature a:hover {
		color: var(--orange);
		text-decoration: none;
	}
</style>
