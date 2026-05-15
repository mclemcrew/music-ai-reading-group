<script lang="ts">
	import { base } from '$app/paths';

	let {
		src,
		alt,
		caption
	}: {
		src: string;
		alt: string;
		caption?: string;
	} = $props();
</script>

<figure>
	<img src="{base}{src}" {alt} loading="lazy" />
	{#if caption}
		<figcaption>{caption}</figcaption>
	{/if}
</figure>

<style>
	figure {
		margin: 1.5rem 0;
	}

	img {
		max-width: 100%;
		height: auto;
		border-radius: 8px;
		border: 1px solid var(--border);
	}

	figcaption {
		margin-top: 0.5rem;
		font-size: 0.8rem;
		color: var(--text-muted);
		font-family: var(--font-display);
		text-align: center;
	}
</style>
