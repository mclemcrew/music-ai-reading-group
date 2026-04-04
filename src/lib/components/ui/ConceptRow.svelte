<script lang="ts">
	let {
		title,
		titleColor = 'var(--orange)',
		description,
		svgContent
	}: {
		title: string;
		titleColor?: string;
		description: string;
		svgContent?: import('svelte').Snippet;
	} = $props();
</script>

<div class="concept-row">
	{#if svgContent}
		<div class="concept-figure">
			{@render svgContent()}
		</div>
	{/if}
	<div class="concept-text">
		<h4 style="color: {titleColor}">{title}</h4>
		<p>{@html description}</p>
	</div>
</div>

<style>
	.concept-row {
		display: flex;
		align-items: flex-start;
		gap: 1.5rem;
	}

	.concept-figure {
		flex-shrink: 0;
		width: 100px;
		height: 72px;
	}

	.concept-figure :global(svg) {
		width: 100%;
		height: 100%;
	}

	.concept-text h4 {
		font-family: var(--font-mono);
		font-size: 0.88rem;
		font-weight: 500;
		margin-bottom: 0.35rem;
	}

	.concept-text p {
		font-size: 0.85rem;
		color: var(--text-muted);
		margin-bottom: 0;
		line-height: 1.5;
	}

	@media (max-width: 640px) {
		.concept-row {
			flex-direction: column;
			gap: 0.75rem;
		}
		.concept-figure {
			width: 80px;
			height: 56px;
		}
	}
</style>
