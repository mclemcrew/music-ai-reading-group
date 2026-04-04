<script lang="ts">
	import { base } from '$app/paths';
</script>

<header>
	<a href="{base}/" class="site-title">Music AI Reading Group</a>
</header>

<style>
	header {
		text-align: center;
		padding: 1.5rem 0 1rem;
		border-bottom: 1px solid var(--border);
		margin-bottom: 0;
	}

	.site-title {
		font-family: var(--font-body);
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--text);
		text-decoration: none;
		letter-spacing: -0.01em;
	}

	.site-title:hover {
		color: var(--orange);
		text-decoration: none;
	}
</style>
