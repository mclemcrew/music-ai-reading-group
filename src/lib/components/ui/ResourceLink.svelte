<script lang="ts">
	let {
		href,
		label,
		host,
		category,
		categoryType = 'paper'
	}: {
		href: string;
		label: string;
		host: string;
		category: string;
		categoryType?: 'paper' | 'demo' | 'tool' | 'dataset';
	} = $props();
</script>

<a class="resource-link" {href} target="_blank" rel="noopener">
	<div>
		<div class="category {categoryType}">{category}</div>
		<div class="label">{label}</div>
		<div class="host">{host}</div>
	</div>
</a>

<style>
	.resource-link {
		display: block;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem 1.25rem;
		text-decoration: none;
		color: var(--text);
		transition: all 0.2s ease;
	}

	.resource-link:hover,
	.resource-link:active {
		border-color: var(--orange);
		box-shadow: 0 2px 12px var(--orange-glow);
		text-decoration: none;
	}

	.category {
		font-family: var(--font-display);
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: 0.3rem;
	}

	.category.paper {
		color: var(--orange);
	}
	.category.demo {
		color: var(--violet);
	}
	.category.tool {
		color: var(--teal);
	}
	.category.dataset {
		color: var(--blue);
	}

	.label {
		font-weight: 600;
		font-size: 0.92rem;
		margin-bottom: 0.2rem;
	}

	.host {
		font-size: 0.75rem;
		color: var(--text-muted);
		font-family: var(--font-display);
	}
</style>
