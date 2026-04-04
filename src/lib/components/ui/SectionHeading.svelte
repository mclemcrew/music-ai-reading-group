<script lang="ts">
	let {
		color = 'var(--orange)',
		children
	}: {
		color?: string;
		children: import('svelte').Snippet;
	} = $props();
</script>

<h2>
	<span class="accent" style="background: {color}"></span>
	{@render children()}
</h2>

<style>
	h2 {
		font-family: var(--font-body);
		font-size: clamp(1.2rem, 3vw, 1.5rem);
		font-weight: 600;
		color: var(--text);
		margin-bottom: 1.2rem;
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	.accent {
		width: 4px;
		height: 1.2em;
		border-radius: 2px;
		flex-shrink: 0;
	}
</style>
