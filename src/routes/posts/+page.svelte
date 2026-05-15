<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { animate, stagger } from 'animejs';

	let { data } = $props();
	let listRef: HTMLElement | undefined = $state();

	onMount(() => {
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced || !listRef) return;
		animate(listRef.querySelectorAll('.post-card'), {
			translateY: [20, 0],
			opacity: [0, 1],
			delay: stagger(70, { start: 100 }),
			duration: 550,
			ease: 'outExpo'
		});
	});
</script>

<svelte:head>
	<title>All Notes — Music AI Reading Group</title>
</svelte:head>

<section class="container page-header">
	<a href="{base}/" class="back-link">
		<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
		</svg>
		Back to reading log
	</a>
	<h1>All Notes</h1>
	<p class="lede">Interactive write-ups from past sessions, newest first. {data.posts.length} {data.posts.length === 1 ? 'note' : 'notes'} so far.</p>
</section>

<section class="container posts-list" bind:this={listRef}>
	<div class="posts-grid">
		{#each data.posts as post}
			<a href="{base}/posts/{post.slug}" class="post-card">
				<div class="post-card-top">
					{#if post.tags?.length}
						<div class="post-tags">
							{#each post.tags.slice(0, 3) as tag}
								<span class="tag">{tag}</span>
							{/each}
						</div>
					{/if}
				</div>
				<h3>{post.title}</h3>
				{#if post.subtitle}<p class="post-subtitle">{post.subtitle}</p>{/if}
				{#if post.description}<p class="post-desc">{post.description}</p>{/if}
				<div class="post-footer">
					<time>{post.date}</time>
					<span class="post-read">Read →</span>
				</div>
			</a>
		{/each}
	</div>
</section>

<style>
	.page-header {
		padding-top: 2.5rem;
		padding-bottom: 1.5rem;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		text-decoration: none;
		margin-bottom: 1.25rem;
	}

	.back-link:hover {
		color: var(--orange);
		text-decoration: none;
	}

	.page-header h1 {
		font-size: clamp(2rem, 4vw, 2.6rem);
		margin-bottom: 0.4rem;
	}

	.lede {
		color: var(--text-muted);
		font-size: 0.95rem;
		margin: 0;
	}

	.posts-list {
		padding-bottom: 4rem;
	}

	.posts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 1.25rem;
	}

	.post-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 1.5rem;
		text-decoration: none;
		color: var(--text);
		transition: all 0.2s ease;
		opacity: 0;
	}

	.post-card:hover,
	.post-card:active {
		border-color: var(--orange);
		box-shadow: 0 4px 24px var(--orange-glow);
		text-decoration: none;
		transform: translateY(-2px);
	}

	.post-card h3 {
		font-family: var(--font-display);
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--text);
		line-height: 1.3;
		margin: 0;
	}

	.post-card-top {
		min-height: 1rem;
	}

	.post-tags {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.tag {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.7rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.15rem 0.55rem;
		color: var(--teal);
	}

	.post-subtitle {
		color: var(--text-muted);
		font-size: 0.85rem;
		font-weight: 300;
		margin: 0;
	}

	.post-desc {
		color: var(--text-muted);
		font-size: 0.83rem;
		line-height: 1.5;
		margin: 0;
		flex: 1;
	}

	.post-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.5rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--surface-3);
	}

	time {
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.post-read {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.78rem;
		color: var(--orange);
	}

	@media (prefers-reduced-motion: reduce) {
		.post-card { opacity: 1 !important; }
	}
</style>
