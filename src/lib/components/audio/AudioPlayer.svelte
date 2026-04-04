<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';

	let {
		src,
		label = '',
		isTarget = false,
		onPlay,
		onFinish
	}: {
		src: string;
		label?: string;
		isTarget?: boolean;
		onPlay?: () => void;
		onFinish?: () => void;
	} = $props();

	let waveDiv: HTMLElement;
	let ws: any = null;
	let isPlaying = $state(false);
	let ready = $state(false);

	onMount(async () => {
		const WaveSurfer = (await import('wavesurfer.js')).default;
		ws = WaveSurfer.create({
			container: waveDiv,
			waveColor: isTarget ? 'rgba(26,158,143,0.5)' : 'rgba(224,112,32,0.4)',
			progressColor: isTarget ? '#1a9e8f' : '#e07020',
			cursorColor: 'transparent',
			barWidth: 2,
			barGap: 1,
			barRadius: 1,
			height: 40,
			normalize: true,
			url: `${base}${src}`,
			backend: 'WebAudio'
		});

		ws.on('ready', () => {
			ready = true;
		});

		ws.on('play', () => {
			isPlaying = true;
			onPlay?.();
		});

		ws.on('pause', () => {
			isPlaying = false;
		});

		ws.on('finish', () => {
			isPlaying = false;
			onFinish?.();
		});

		return () => ws?.destroy();
	});

	export function pause() {
		ws?.pause();
	}

	function toggle() {
		ws?.playPause();
	}
</script>

<div class="ws-item" class:playing={isPlaying} class:target={isTarget}>
	<div class="ws-label">
		<span class:target-label={isTarget}>{label}</span>
		<button class="ws-play-btn" onclick={toggle} aria-label={isPlaying ? 'Pause' : 'Play'}>
			{#if isPlaying}
				&#9646;&#9646;
			{:else}
				&#9654;
			{/if}
		</button>
	</div>
	<div class="ws-wave" bind:this={waveDiv}></div>
</div>

<style>
	.ws-item {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.6rem 0.8rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.ws-item:hover {
		border-color: var(--orange);
	}

	.ws-item.target:hover {
		border-color: var(--teal);
	}

	.ws-item.playing {
		border-color: var(--orange);
		box-shadow: 0 0 12px var(--orange-glow);
	}

	.ws-item.playing.target {
		border-color: var(--teal);
		box-shadow: 0 0 12px var(--teal-glow);
	}

	.ws-label {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.4rem;
	}

	.ws-label span {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.target-label {
		color: var(--teal) !important;
		font-weight: 500;
	}

	.ws-play-btn {
		background: none;
		border: 1px solid var(--border);
		border-radius: 50%;
		width: 44px;
		height: 44px;
		min-height: 44px;
		min-width: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--text-muted);
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.ws-play-btn:hover {
		border-color: var(--orange);
		color: var(--orange);
	}

	.ws-wave {
		min-height: 40px;
	}
</style>
