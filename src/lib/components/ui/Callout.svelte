<script lang="ts">
	import type { Snippet } from 'svelte';

	type CalloutType = 'definition' | 'insight' | 'aside' | 'gotcha';

	let {
		type = 'insight' as CalloutType,
		label = '',
		children
	}: { type?: CalloutType; label?: string; children: Snippet } = $props();

	const labels: Record<CalloutType, string> = {
		definition: 'Definition',
		insight: 'Key idea',
		aside: 'Aside',
		gotcha: 'Heads up'
	};
</script>

<aside class="callout callout-{type}">
	<div class="callout-label">
		{#if type === 'definition'}
			<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
			</svg>
		{:else if type === 'insight'}
			<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M9 18h6" />
				<path d="M10 22h4" />
				<path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8a6 6 0 0 0-12 0c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
			</svg>
		{:else if type === 'aside'}
			<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M16 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11l5-5V5a2 2 0 0 0-2-2z" />
				<path d="M15 3v4a2 2 0 0 0 2 2h4" />
			</svg>
		{:else if type === 'gotcha'}
			<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
				<line x1="12" y1="9" x2="12" y2="13" />
				<line x1="12" y1="17" x2="12.01" y2="17" />
			</svg>
		{/if}
		<span>{label || labels[type]}</span>
	</div>
	<div class="callout-body">
		{@render children()}
	</div>
</aside>

<style>
	.callout {
		border: 1px solid var(--border);
		border-left-width: 3px;
		border-radius: 8px;
		padding: 0.85rem 1.1rem 1rem;
		margin: 1.5rem 0;
		background: var(--surface);
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.callout-definition {
		border-left-color: var(--orange);
		background: var(--orange-glow);
	}

	.callout-insight {
		border-left-color: var(--teal);
		background: var(--teal-glow);
	}

	.callout-aside {
		border-left-color: var(--violet);
		background: var(--violet-glow);
	}

	.callout-gotcha {
		border-left-color: var(--orange);
		background: var(--surface-2);
	}

	.callout-label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-bottom: 0.1rem;
	}

	.callout-definition .callout-label,
	.callout-gotcha .callout-label {
		color: var(--orange);
	}

	.callout-insight .callout-label {
		color: var(--teal);
	}

	.callout-aside .callout-label {
		color: var(--violet);
	}

	.callout-body :global(p) {
		margin: 0;
		font-size: 0.95rem;
		line-height: 1.6;
		color: var(--text);
	}

	.callout-body :global(p + p) {
		margin-top: 0.6rem;
	}

	.callout-body :global(code) {
		font-size: 0.85em;
	}

	.callout-body :global(strong) {
		font-weight: 600;
	}
</style>
