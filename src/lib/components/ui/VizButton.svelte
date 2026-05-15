<script lang="ts">
	let {
		active = false,
		color = 'var(--orange)',
		onclick,
		children
	}: {
		active?: boolean;
		color?: string;
		onclick?: (e: MouseEvent) => void;
		children: import('svelte').Snippet;
	} = $props();
</script>

<button class="viz-btn" class:active style="--btn-color: {color}" onclick={onclick}>
	{@render children()}
</button>

<style>
	.viz-btn {
		font-family: var(--font-display);
		font-size: 0.75rem;
		padding: 0.35rem 0.8rem;
		border-radius: 5px;
		border: 1px solid var(--border);
		background: var(--surface-2);
		color: var(--text);
		cursor: pointer;
		transition: all 0.15s ease;
		min-height: 44px;
		min-width: 44px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.viz-btn:hover,
	.viz-btn:active {
		border-color: var(--btn-color);
		color: var(--btn-color);
	}

	.viz-btn.active {
		background: var(--btn-color);
		color: white;
		border-color: var(--btn-color);
	}
</style>
