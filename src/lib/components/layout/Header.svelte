<script lang="ts">
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';
	import { page } from '$app/state';

	let menuOpen = $state(false);
	let noteHead: SVGEllipseElement | undefined = $state();
	let noteStem: SVGPathElement | undefined = $state();

	const links = [
		{ href: '/papers', label: 'Papers', match: (p: string) => p.startsWith('/papers') || p.startsWith('/sessions') },
		{ href: '/posts', label: 'Notes', match: (p: string) => p.startsWith('/posts') }
	];

	onMount(() => {
		if (!noteHead || !noteStem) return;
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced) return;
		const parts: (SVGGeometryElement)[] = [noteHead, noteStem];
		for (const p of parts) {
			const len = p.getTotalLength();
			p.style.strokeDasharray = `${len}`;
			p.style.strokeDashoffset = `${len}`;
		}
		animate(parts, {
			strokeDashoffset: 0,
			duration: 700,
			delay: stagger(150, { start: 250 }),
			ease: 'outQuad'
		});
	});
</script>

<header>
	<div class="bar">
		<a href="{base}/" class="site-title" aria-label="Music AI Reading Group — home">
			<svg class="mark" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<ellipse bind:this={noteHead} cx="9" cy="17" rx="4.6" ry="3.3" transform="rotate(-22 9 17)" />
				<path bind:this={noteStem} d="M13.2 14.5 L13.2 4" />
			</svg>
			<span>Music AI Reading Group</span>
		</a>

		<nav class="nav-desktop" aria-label="Primary">
			{#each links as link}
				{@const active = link.match(page.url.pathname.replace(base, '') || '/')}
				<a href="{base}{link.href}" class:active>{link.label}</a>
			{/each}
		</nav>

		<button
			class="nav-toggle"
			aria-label={menuOpen ? 'Close menu' : 'Open menu'}
			aria-expanded={menuOpen}
			onclick={() => (menuOpen = !menuOpen)}
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				{#if menuOpen}
					<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
				{:else}
					<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
				{/if}
			</svg>
		</button>
	</div>

	{#if menuOpen}
		<nav class="nav-mobile" aria-label="Primary mobile">
			{#each links as link}
				{@const active = link.match(page.url.pathname.replace(base, '') || '/')}
				<a href="{base}{link.href}" class:active onclick={() => (menuOpen = false)}>{link.label}</a>
			{/each}
		</nav>
	{/if}
</header>

<style>
	header {
		position: sticky;
		top: 0;
		z-index: 50;
		background: color-mix(in srgb, var(--bg) 88%, transparent);
		backdrop-filter: saturate(180%) blur(8px);
		-webkit-backdrop-filter: saturate(180%) blur(8px);
		border-bottom: 1px solid var(--border);
	}

	.bar {
		max-width: 960px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.85rem 1.5rem;
		padding-left: max(1.5rem, env(safe-area-inset-left));
		padding-right: max(1.5rem, env(safe-area-inset-right));
	}

	.site-title {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 1.05rem;
		color: var(--text);
		text-decoration: none;
		letter-spacing: -0.01em;
	}

	.site-title:hover {
		color: var(--orange);
		text-decoration: none;
	}

	.mark {
		color: var(--orange);
		flex-shrink: 0;
		transform: translateY(-1px);
	}

	.nav-desktop {
		display: flex;
		gap: 0.25rem;
		align-items: center;
	}

	.nav-desktop a {
		font-family: var(--font-display);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		text-decoration: none;
		padding: 0.45rem 0.8rem;
		border-radius: 6px;
		transition: color 0.15s, background 0.15s;
	}

	.nav-desktop a:hover {
		color: var(--orange);
		background: var(--orange-glow);
		text-decoration: none;
	}

	.nav-desktop a.active {
		color: var(--orange);
	}

	.nav-toggle {
		display: none;
		background: transparent;
		border: 1px solid var(--border);
		border-radius: 8px;
		min-height: 40px;
		min-width: 40px;
		padding: 0.4rem;
		color: var(--text);
		cursor: pointer;
		align-items: center;
		justify-content: center;
	}

	.nav-toggle:hover {
		border-color: var(--orange);
		color: var(--orange);
	}

	.nav-mobile {
		display: none;
		flex-direction: column;
		padding: 0.25rem 1rem 0.75rem;
		border-top: 1px solid var(--border);
		background: var(--surface);
	}

	.nav-mobile a {
		font-family: var(--font-display);
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		text-decoration: none;
		padding: 0.85rem 0.5rem;
	}

	.nav-mobile a.active {
		color: var(--orange);
	}

	@media (max-width: 640px) {
		.nav-desktop { display: none; }
		.nav-toggle { display: inline-flex; }
		.nav-mobile { display: flex; }
	}
</style>
