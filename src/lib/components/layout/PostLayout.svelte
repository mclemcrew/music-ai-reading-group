<script lang="ts">
	import { base } from '$app/paths';

	let {
		title = '',
		subtitle = '',
		date = '',
		authors = [],
		tags = [],
		badge = '',
		excalidraw = '',
		children
	}: {
		title?: string;
		subtitle?: string;
		date?: string;
		authors?: string[];
		tags?: string[];
		badge?: string;
		excalidraw?: string;
		children: import('svelte').Snippet;
	} = $props();
</script>

<div class="post-nav">
	<a href="{base}/" class="back-link">
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
		</svg>
		Back
	</a>
</div>

<article class="post">
	<header>
		<h1>
			{#if title.includes('DDSP')}
				<span class="ddsp">{title.split(' ')[0]}</span>
				<span class="from">{title.split(' ').slice(1, 2).join(' ')}</span>
				{title.split(' ').slice(2).join(' ')}
			{:else}
				{title}
			{/if}
		</h1>
		{#if subtitle}
			<p class="subtitle">{subtitle}</p>
		{/if}
		{#if badge}
			<span class="badge">{badge}</span>
		{/if}
		{#if excalidraw}
			<a href={excalidraw} target="_blank" rel="noopener" class="slides-link">
				<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
				View session slides
			</a>
		{/if}
		<div class="post-header-line"></div>
	</header>

	<div class="post-content">
		{@render children()}
	</div>
</article>

<style>
	.post-nav {
		max-width: 960px;
		margin: 0 auto;
		padding: 1.25rem 1.5rem 0;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--text-muted);
		text-decoration: none;
		transition: color 0.15s;
	}

	.back-link:hover {
		color: var(--orange);
		text-decoration: none;
	}

	.post {
		max-width: 960px;
		margin: 0 auto;
		padding: 0 1.5rem 2rem;
	}

	header {
		text-align: center;
		padding: 2rem 0 1.5rem;
		position: relative;
	}

	.slides-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-top: 0.75rem;
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--teal);
		text-decoration: none;
		border: 1px solid rgba(26, 158, 143, 0.3);
		background: var(--teal-glow);
		padding: 0.3rem 0.85rem;
		border-radius: 20px;
		transition: all 0.15s ease;
	}

	.slides-link:hover {
		background: var(--teal);
		color: white;
		border-color: var(--teal);
		text-decoration: none;
	}

	.post-header-line {
		width: 60px;
		height: 2px;
		background: var(--orange);
		margin: 1.5rem auto 0;
	}

	h1 {
		font-family: var(--font-body);
		font-size: clamp(1.8rem, 4vw, 2.8rem);
		font-weight: 700;
		letter-spacing: -0.02em;
		margin-bottom: 0.4rem;
	}

	.ddsp {
		color: var(--orange);
	}

	.from {
		color: var(--text-muted);
		font-weight: 300;
	}

	.subtitle {
		color: var(--text-muted);
		font-size: 1.05rem;
		font-weight: 300;
		margin-bottom: 1.2rem;
	}

	.badge {
		display: inline-block;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 20px;
		padding: 0.3rem 1rem;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--teal);
		letter-spacing: 0.03em;
	}

	.post-content {
		line-height: 1.65;
	}

	/* Constrain prose to comfortable reading measure, but let
	   visualizations, grids, and run boxes use full container width */
	.post-content :global(p),
	.post-content :global(ul),
	.post-content :global(ol) {
		max-width: 65ch;
	}

	.post-content :global(section) {
		margin-bottom: 2.5rem;
	}

	.post-content :global(h2) {
		font-size: clamp(1.2rem, 3vw, 1.5rem);
		font-weight: 600;
		color: var(--text);
		margin: 2rem 0 1.2rem;
	}

	.post-content :global(h3) {
		font-size: 1.1rem;
		color: var(--teal);
		margin: 1.5rem 0 0.75rem;
		font-weight: 600;
	}

	.post-content :global(p) {
		margin-bottom: 1rem;
	}

	.post-content :global(.muted) {
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.post-content :global(.concepts) {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		margin: 1rem 0;
	}

	.post-content :global(.concept-row) {
		display: flex;
		align-items: flex-start;
		gap: 1.5rem;
	}

	.post-content :global(.concept-figure) {
		flex-shrink: 0;
		width: 100px;
		height: 72px;
	}

	.post-content :global(.concept-figure svg) {
		width: 100%;
		height: 100%;
	}

	.post-content :global(.concept-text h4) {
		font-family: var(--font-mono);
		font-size: 0.88rem;
		font-weight: 500;
		margin-bottom: 0.35rem;
	}

	.post-content :global(.concept-text p) {
		font-size: 0.85rem;
		color: var(--text-muted);
		margin-bottom: 0;
		line-height: 1.5;
	}

	@media (max-width: 640px) {
		.post-content :global(.concept-row) {
			flex-direction: column;
			gap: 0.75rem;
		}
		.post-content :global(.concept-figure) {
			width: min(320px, 85vw);
			height: auto;
			aspect-ratio: 100 / 72;
		}
	}

	.post-content :global(.resources-grid) {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr));
		gap: 0.75rem;
		margin: 1rem 0;
	}

	.post-content :global(.run-box) {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		margin: 1.5rem 0;
	}

	@media (max-width: 640px) {
		.post {
			padding: 0 1rem 1.5rem;
		}
	}
</style>
