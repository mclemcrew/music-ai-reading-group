<script lang="ts">
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';

	let container: HTMLElement;

	onMount(() => {
		const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		const obs = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (!entry.isIntersecting) return;
					if (reducedMotion) {
						container.querySelectorAll('rect, circle').forEach((el) => {
							(el as SVGElement).style.opacity = '1';
						});
					} else {
						animate(container.querySelectorAll('rect, circle'), {
							opacity: [0, 1],
							scale: [0.9, 1],
							delay: stagger(80),
							duration: 600,
							ease: 'outExpo'
						});
					}
					obs.unobserve(entry.target);
				});
			},
			{ threshold: 0.15 }
		);
		obs.observe(container);
		return () => obs.disconnect();
	});
</script>

<div class="signal-chain-svg" bind:this={container}>
	<svg viewBox="0 0 800 220" xmlns="http://www.w3.org/2000/svg">
		<!-- Neural Network -->
		<rect x="20" y="70" width="120" height="80" rx="8" fill="rgba(224,112,32,0.08)" stroke="#e07020" stroke-width="1.5" />
		<text x="80" y="105" text-anchor="middle" fill="#e07020" font-weight="600" font-size="11">Neural</text>
		<text x="80" y="122" text-anchor="middle" fill="#e07020" font-weight="600" font-size="11">Network</text>

		<!-- Arrow to oscillator -->
		<line x1="140" y1="85" x2="220" y2="45" stroke="#e07020" stroke-width="1.2" opacity="0.4" />
		<text x="160" y="52" fill="#6b7280" font-size="9">f0, A, c_k</text>

		<!-- Oscillator Bank -->
		<rect x="220" y="15" width="150" height="55" rx="8" fill="rgba(224,112,32,0.06)" stroke="#e07020" stroke-width="1.5" />
		<text x="295" y="40" text-anchor="middle" fill="#e07020" font-weight="500" font-size="11">Oscillator Bank</text>
		<text x="295" y="56" text-anchor="middle" fill="#6b7280" font-size="9">cumsum + sin</text>

		<!-- Arrow to noise -->
		<line x1="140" y1="135" x2="220" y2="160" stroke="#1a9e8f" stroke-width="1.2" opacity="0.4" />
		<text x="160" y="158" fill="#6b7280" font-size="9">H_l</text>

		<!-- Filtered Noise -->
		<rect x="220" y="140" width="150" height="55" rx="8" fill="rgba(26,158,143,0.06)" stroke="#1a9e8f" stroke-width="1.5" />
		<text x="295" y="165" text-anchor="middle" fill="#1a9e8f" font-weight="500" font-size="11">Filtered Noise</text>
		<text x="295" y="181" text-anchor="middle" fill="#6b7280" font-size="9">FFT x H → IFFT</text>

		<!-- Lines to mix -->
		<line x1="370" y1="43" x2="440" y2="100" stroke="#e07020" stroke-width="1.2" opacity="0.3" />
		<line x1="370" y1="168" x2="440" y2="112" stroke="#1a9e8f" stroke-width="1.2" opacity="0.3" />

		<!-- Mix circle -->
		<circle cx="455" cy="106" r="18" fill="rgba(124,77,255,0.06)" stroke="#7c4dff" stroke-width="1.5" />
		<text x="455" y="110" text-anchor="middle" fill="#7c4dff" font-size="16">+</text>

		<!-- Line to reverb -->
		<line x1="473" y1="106" x2="520" y2="106" stroke="#7c4dff" stroke-width="1.2" opacity="0.3" />

		<!-- Reverb -->
		<rect x="520" y="81" width="120" height="50" rx="8" fill="rgba(124,77,255,0.06)" stroke="#7c4dff" stroke-width="1.5" />
		<text x="580" y="104" text-anchor="middle" fill="#7c4dff" font-weight="500" font-size="11">Reverb</text>
		<text x="580" y="119" text-anchor="middle" fill="#6b7280" font-size="9">conv in freq domain</text>

		<!-- Arrow to output -->
		<line x1="640" y1="106" x2="690" y2="106" stroke="#2979ff" stroke-width="1.5" opacity="0.4" />
		<polygon points="688,100 700,106 688,112" fill="#2979ff" opacity="0.5" />

		<!-- Output -->
		<rect x="705" y="86" width="80" height="40" rx="8" fill="rgba(41,121,255,0.06)" stroke="#2979ff" stroke-width="1.5" />
		<text x="745" y="110" text-anchor="middle" fill="#2979ff" font-weight="600" font-size="11">Output</text>
	</svg>
</div>

<style>
	.signal-chain-svg {
		margin: 1.5rem 0;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
	}

	svg {
		width: 100%;
		height: auto;
		font-family: var(--font-mono);
	}
</style>
