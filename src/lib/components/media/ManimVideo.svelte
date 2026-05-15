<script lang="ts">
	import { base } from '$app/paths';

	let {
		src,
		poster,
		caption,
		autoplay = false,
		loop = false
	}: {
		src: string;
		poster?: string;
		caption?: string;
		autoplay?: boolean;
		loop?: boolean;
	} = $props();

	const type = src.endsWith('.webm') ? 'video/webm' : 'video/mp4';
</script>

<figure class="manim-video">
	<video
		controls
		playsinline
		preload="metadata"
		poster={poster ? `${base}${poster}` : undefined}
		{autoplay}
		{loop}
		muted={autoplay}
	>
		<source src="{base}{src}" {type} />
		Your browser does not support the video tag.
	</video>
	{#if caption}
		<figcaption>{caption}</figcaption>
	{/if}
</figure>

<style>
	.manim-video {
		margin: 1.5rem 0;
	}

	video {
		width: 100%;
		max-width: 100%;
		border-radius: 12px;
		border: 1px solid var(--border);
		background: var(--surface);
	}

	figcaption {
		margin-top: 0.5rem;
		font-size: 0.8rem;
		color: var(--text-muted);
		font-family: var(--font-display);
		text-align: center;
	}
</style>
