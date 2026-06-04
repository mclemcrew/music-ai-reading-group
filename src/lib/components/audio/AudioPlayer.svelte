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
	let currentTime = $state(0);
	let duration = $state(0);

	const accent = isTarget ? '#1a9e8f' : '#e07020';

	function fmt(s: number): string {
		if (!s || !isFinite(s)) return '0:00';
		const m = Math.floor(s / 60);
		const sec = Math.floor(s % 60);
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}

	onMount(async () => {
		const WaveSurfer = (await import('wavesurfer.js')).default;
		ws = WaveSurfer.create({
			container: waveDiv,
			// Played portion is the solid accent; the part still to play stays a faint
			// version of the same colour, so the contrast shows how far along you are.
			waveColor: isTarget ? 'rgba(26,158,143,0.22)' : 'rgba(224,112,32,0.2)',
			progressColor: accent,
			// Visible playhead so you can see the exact position.
			cursorColor: 'rgba(31,29,27,0.55)',
			cursorWidth: 2,
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
			duration = ws.getDuration();
		});

		ws.on('audioprocess', (t: number) => {
			currentTime = t;
		});
		// fires on seek/scrub too, so the readout stays correct when you click the wave
		ws.on('interaction', () => {
			currentTime = ws.getCurrentTime();
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
			currentTime = duration;
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
		<div class="ws-right">
			<span class="ws-time">{fmt(currentTime)} / {fmt(duration)}</span>
			<button class="ws-play-btn" onclick={toggle} aria-label={isPlaying ? 'Pause' : 'Play'}>
				{#if isPlaying}
					&#9646;&#9646;
				{:else}
					&#9654;
				{/if}
			</button>
		</div>
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

	.ws-item:hover,
	.ws-item:active {
		border-color: var(--orange);
	}

	.ws-item.target:hover,
	.ws-item.target:active {
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
		font-family: var(--font-display);
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.target-label {
		color: var(--teal) !important;
		font-weight: 500;
	}

	.ws-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.ws-time {
		font-family: var(--font-mono, ui-monospace, monospace);
		font-size: 0.7rem;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		opacity: 0.8;
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

	.ws-play-btn:hover,
	.ws-play-btn:active {
		border-color: var(--orange);
		color: var(--orange);
	}

	.ws-wave {
		min-height: 40px;
	}
</style>
