<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import AudioPlayer from './AudioPlayer.svelte';

	let {
		prefix,
		steps,
		lossImage,
		lossAlt = 'Loss curve'
	}: {
		prefix: string;
		steps: string[];
		lossImage?: string;
		lossAlt?: string;
	} = $props();

	let players: Record<string, any> = {};
	let visible = $state(false);
	let container: HTMLElement;

	function handlePlay(step: string) {
		// Pause all other players
		for (const [key, player] of Object.entries(players)) {
			if (key !== step && player?.pause) {
				player.pause();
			}
		}
	}

	onMount(() => {
		const obs = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (!entry.isIntersecting) return;
					visible = true;
					obs.unobserve(entry.target);
				});
			},
			{ threshold: 0.1, rootMargin: '200px' }
		);
		obs.observe(container);
		return () => obs.disconnect();
	});
</script>

<div class="audio-grid-container" bind:this={container}>
	{#if visible}
		<div class="ws-grid">
			{#each steps as step}
				{@const isTarget = step === 'target'}
				{@const filename = isTarget
					? `/audio/${prefix}_target.wav`
					: `/audio/${prefix}_step${step}.wav`}
				{@const label = isTarget ? 'Target' : `Step ${parseInt(step)}`}
				<AudioPlayer
					src={filename}
					{label}
					{isTarget}
					onPlay={() => handlePlay(step)}
					bind:this={players[step]}
				/>
			{/each}
		</div>
		{#if lossImage}
			<div class="loss-plot">
				<img src="{base}{lossImage}" alt={lossAlt} loading="lazy" />
			</div>
		{/if}
	{:else}
		<div class="placeholder">Loading audio players...</div>
	{/if}
</div>

<style>
	.ws-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
		gap: 0.75rem;
		margin: 1rem 0;
	}

	.loss-plot {
		margin: 1.2rem 0;
		text-align: center;
	}

	.loss-plot img {
		max-width: 100%;
		height: auto;
		border-radius: 8px;
		border: 1px solid var(--border);
	}

	.placeholder {
		padding: 2rem;
		text-align: center;
		color: var(--text-muted);
		font-family: var(--font-display);
		font-size: 0.85rem;
	}

	@media (max-width: 640px) {
		.ws-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
