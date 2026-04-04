<script lang="ts">
	let {
		text,
		color = 'var(--teal)'
	}: {
		text: string;
		color?: string;
	} = $props();
</script>

<span class="badge" style="color: {color}">{text}</span>

<style>
	.badge {
		display: inline-block;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 20px;
		padding: 0.3rem 1rem;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		letter-spacing: 0.03em;
	}
</style>
