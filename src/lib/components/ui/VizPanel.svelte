<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		titleColor = 'var(--teal)',
		caption,
		controls,
		children
	}: {
		title: string;
		titleColor?: string;
		caption?: Snippet;
		controls?: Snippet;
		children: Snippet;
	} = $props();
</script>

<div class="viz-panel">
	<div class="viz-header">
		<h3 style="color: {titleColor}">{title}</h3>
		{#if controls}
			<div class="viz-controls">
				{@render controls()}
			</div>
		{/if}
	</div>
	<div class="viz-body">
		{@render children()}
	</div>
	{#if caption}
		<div class="viz-caption">{@render caption()}</div>
	{/if}
</div>

<style>
	.viz-panel {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		overflow: hidden;
		margin: 1.5rem 0;
	}

	.viz-header {
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--border);
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.75rem;
	}

	.viz-header h3 {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.9rem;
		font-weight: 500;
	}

	.viz-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.viz-body {
		position: relative;
	}

	.viz-body :global(canvas) {
		display: block;
		width: 100%;
	}

	.viz-caption {
		padding: 0.8rem 1.5rem;
		border-top: 1px solid var(--border);
		font-size: 0.8rem;
		color: var(--text-muted);
		font-family: var(--font-mono);
	}

	@media (max-width: 640px) {
		.viz-header {
			padding: 0.75rem 1rem;
		}
		.viz-caption {
			padding: 0.6rem 1rem;
		}
	}
</style>
