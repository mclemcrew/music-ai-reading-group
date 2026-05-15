<script lang="ts">
	import { base } from '$app/paths';
	import type { PostMeta } from '$lib/utils/post-loader';

	let { post }: { post: PostMeta } = $props();
</script>

<a href="{base}/posts/{post.slug}" class="post-card">
	<div class="card-inner">
		<h2>{post.title}</h2>
		{#if post.subtitle}
			<p class="subtitle">{post.subtitle}</p>
		{/if}
		{#if post.description}
			<p class="description">{post.description}</p>
		{/if}
		<div class="meta">
			<time>{post.date}</time>
			{#if post.tags?.length}
				<div class="tags">
					{#each post.tags as tag}
						<span class="tag">{tag}</span>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</a>

<style>
	.post-card {
		display: block;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		text-decoration: none;
		color: var(--text);
		transition: all 0.2s ease;
	}

	.post-card:hover {
		border-color: var(--orange);
		box-shadow: 0 4px 20px var(--orange-glow);
		text-decoration: none;
	}

	h2 {
		font-size: 1.4rem;
		font-weight: 700;
		margin-bottom: 0.3rem;
		color: var(--text);
	}

	.subtitle {
		color: var(--text-muted);
		font-size: 0.95rem;
		font-weight: 300;
		margin-bottom: 0.5rem;
	}

	.description {
		color: var(--text-muted);
		font-size: 0.88rem;
		margin-bottom: 0.75rem;
	}

	.meta {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}

	time {
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.tags {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.tag {
		font-family: var(--font-display);
		font-size: 0.65rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.15rem 0.6rem;
		color: var(--teal);
	}
</style>
