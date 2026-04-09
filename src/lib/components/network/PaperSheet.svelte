<script lang="ts">
	import { onMount } from 'svelte';
	import { animate } from 'animejs';
	import { base } from '$app/paths';
	import type { Paper, Cluster } from '$lib/data/papers';

	let {
		paper,
		cluster,
		onClose
	}: {
		paper: Paper | null;
		cluster: Cluster | null;
		onClose: () => void;
	} = $props();

	let sheetEl: HTMLDivElement;
	let visible = $state(false);
	let reducedMotion = false;

	onMount(() => {
		reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	});

	// When paper becomes non-null, slide in.
	$effect(() => {
		if (paper && sheetEl) {
			visible = true;
			if (reducedMotion) return;
			animate(sheetEl, {
				translateY: ['100%', '0%'],
				opacity: [0, 1],
				duration: 400,
				ease: 'outExpo'
			});
		}
	});

	function handleClose() {
		if (!sheetEl || reducedMotion) {
			visible = false;
			onClose();
			return;
		}
		animate(sheetEl, {
			translateY: ['0%', '100%'],
			opacity: [1, 0],
			duration: 300,
			ease: 'inExpo',
			onComplete: () => {
				visible = false;
				onClose();
			}
		});
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
	}
</script>

<svelte:window onkeydown={onKey} />

{#if paper && cluster}
	<div
		bind:this={sheetEl}
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby="sheet-title"
		style:--cluster-color={`var(${cluster.colorVar})`}
	>
		<div class="sheet-header">
			<div class="sheet-meta">
				<span class="cluster-chip">{cluster.label}</span>
				<span class="year">{paper.year}</span>
			</div>
			<button class="close-btn" onclick={handleClose} aria-label="Close paper details">
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
				</svg>
			</button>
		</div>

		<h2 id="sheet-title">{paper.title}</h2>
		<p class="authors">{paper.authorsShort}</p>
		<p class="blurb">{paper.blurb}</p>

		<div class="sheet-links">
			<a href={paper.link} target="_blank" rel="noopener" class="link-btn primary">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
				</svg>
				Read paper
			</a>
			{#if paper.postSlug}
				<a href="{base}/posts/{paper.postSlug}" class="link-btn secondary">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/>
					</svg>
					Session notes
				</a>
			{/if}
			{#if paper.excalidraw}
				<a href={paper.excalidraw} target="_blank" rel="noopener" class="link-btn secondary">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>
					</svg>
					Slides
				</a>
			{/if}
		</div>
	</div>
{/if}

<style>
	.sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		background: var(--surface);
		border-top: 2px solid var(--cluster-color, var(--orange));
		border-top-left-radius: 16px;
		border-top-right-radius: 16px;
		padding: 1.25rem 1.25rem 2rem;
		padding-bottom: max(2rem, env(safe-area-inset-bottom));
		box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.08);
		z-index: 100;
		max-height: 60vh;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
	}

	.sheet-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 0.5rem;
	}

	.sheet-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.cluster-chip {
		font-family: var(--font-mono);
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--cluster-color, var(--orange));
		background: var(--surface-2);
		padding: 0.25rem 0.7rem;
		border-radius: 12px;
		border: 1px solid var(--cluster-color, var(--orange));
	}

	.year {
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.close-btn {
		background: transparent;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		padding: 0.4rem;
		margin: -0.4rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		min-width: 44px;
		min-height: 44px;
	}

	.close-btn:hover,
	.close-btn:active {
		background: var(--surface-2);
		color: var(--text);
	}

	.sheet h2 {
		font-family: var(--font-display);
		font-size: 1.2rem;
		font-weight: 700;
		line-height: 1.3;
		color: var(--text);
		margin: 0.5rem 0 0.35rem;
	}

	.authors {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		color: var(--text-muted);
		margin: 0 0 1rem;
	}

	.blurb {
		font-size: 0.95rem;
		line-height: 1.6;
		color: var(--text);
		margin: 0 0 1.25rem;
	}

	.sheet-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}

	.link-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		padding: 0.55rem 0.95rem;
		border-radius: 8px;
		text-decoration: none;
		transition: all 0.15s ease;
		min-height: 44px;
	}

	.link-btn.primary {
		background: var(--cluster-color, var(--orange));
		color: white;
		border: 1px solid var(--cluster-color, var(--orange));
	}

	.link-btn.primary:hover,
	.link-btn.primary:active {
		filter: brightness(0.92);
		text-decoration: none;
	}

	.link-btn.secondary {
		background: var(--surface-2);
		color: var(--text);
		border: 1px solid var(--border);
	}

	.link-btn.secondary:hover,
	.link-btn.secondary:active {
		border-color: var(--cluster-color, var(--orange));
		color: var(--cluster-color, var(--orange));
		text-decoration: none;
	}

	/* Desktop: slide in from the right instead of bottom sheet */
	@media (min-width: 768px) {
		.sheet {
			left: auto;
			right: 1.5rem;
			bottom: 1.5rem;
			top: auto;
			width: 400px;
			max-height: calc(100vh - 3rem);
			border-radius: 16px;
			border: 1px solid var(--border);
			border-top: 2px solid var(--cluster-color, var(--orange));
			box-shadow: 0 12px 48px rgba(0, 0, 0, 0.12);
		}
	}
</style>
