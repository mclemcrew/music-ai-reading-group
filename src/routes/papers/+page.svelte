<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { papers, clusters } from '$lib/data/papers';
	import { computeLayout } from '$lib/data/paper-layout';
	import Constellation from '$lib/components/network/Constellation.svelte';
	import PaperSheet from '$lib/components/network/PaperSheet.svelte';

	// Logical viewBox for the constellation. 1000x1000 keeps integer-friendly coordinates.
	const viewBox = { w: 1000, h: 1000 };

	// Layout is pure — recomputed whenever the papers/clusters data changes.
	const layout = computeLayout(papers, clusters, viewBox);

	// State
	let selectedId = $state<string | null>(null);
	let scrollStep = $state(0);
	let tourDone = $state(false);

	// Sorted cluster list used for the tour sequence and derived state.
	const sortedClusters = [...clusters].sort((a, b) => a.order - b.order);

	// Build the full list of step contents: overview + one per cluster + release.
	type StepContent = {
		num: string;
		title: string;
		body: string;
		clusterId: string | null;
		colorVar: string | null;
	};
	const stepContents: StepContent[] = [
		{
			num: '01',
			title: "The papers we've read",
			body:
				"Every paper the reading group has covered so far, arranged by theme. Scroll to walk through each cluster, then tap any node to read more.",
			clusterId: null,
			colorVar: null
		},
		...sortedClusters.map((c, i) => ({
			num: String(i + 2).padStart(2, '0'),
			title: c.label,
			body: c.blurb,
			clusterId: c.id,
			colorVar: c.colorVar
		})),
		{
			num: String(sortedClusters.length + 2).padStart(2, '0'),
			title: 'Explore',
			body:
				"Tap any paper to see what we took from it, who wrote it, and where to read more. The constellation grows each week as the group reads new work.",
			clusterId: null,
			colorVar: null
		}
	];

	// Derived: while the tour is running, focus the cluster for the current step.
	let focusedClusterId = $derived.by(() => {
		if (selectedId || tourDone) return null;
		return stepContents[scrollStep]?.clusterId ?? null;
	});

	// Derived sheet data
	let selectedPaper = $derived(
		selectedId ? (papers.find((p) => p.id === selectedId) ?? null) : null
	);
	let selectedCluster = $derived(
		selectedPaper ? (clusters.find((c) => c.id === selectedPaper!.clusterId) ?? null) : null
	);

	// Current step content for the mobile overlay card
	let currentStep = $derived(stepContents[scrollStep] ?? stepContents[0]);

	function closeSheet() {
		selectedId = null;
	}

	function replayTour() {
		const intro = document.getElementById('tour-anchor');
		if (intro) {
			tourDone = false;
			scrollStep = 0;
			intro.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
	}

	// scrollama integration
	onMount(async () => {
		if (typeof window === 'undefined') return;
		const scrollama = (await import('scrollama')).default;

		const scroller = scrollama();
		scroller
			.setup({
				step: '.scroll-trigger',
				offset: 0.5,
				debug: false
			})
			.onStepEnter((response) => {
				const idx = Number(response.element.dataset.step);
				scrollStep = idx;
				if (response.element.dataset.final === 'true') {
					tourDone = true;
				} else if (idx < stepContents.length - 1) {
					tourDone = false;
				}
			});

		const onResize = () => scroller.resize();
		window.addEventListener('resize', onResize);

		return () => {
			window.removeEventListener('resize', onResize);
			scroller.destroy();
		};
	});
</script>

<svelte:head>
	<title>Paper Constellation · Music AI Reading Group</title>
	<meta
		name="description"
		content="An interactive map of every paper the Music AI Reading Group has read, clustered by theme."
	/>
</svelte:head>

<div class="papers-nav">
	<a href="{base}/" class="back-link">
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
		</svg>
		Back
	</a>
</div>

<div class="papers-intro">
	<h1>Paper Constellation</h1>
	<p class="subtitle">
		Every paper we've read, clustered by theme. Scroll to take the tour, then tap any node to read
		more.
	</p>
</div>

<!-- Scrollytelling section: sticky graphic + parallel scroll triggers -->
<section id="tour-anchor" class="tour-section">
	<!-- Graphic column: sticky on both mobile and desktop -->
	<div class="graphic-col">
		<div class="graphic-sticky">
			<div class="constellation-box">
				<Constellation
					{papers}
					{clusters}
					{layout}
					bind:selectedId
					{focusedClusterId}
					{viewBox}
				/>
			</div>
			<!-- Mobile-only step overlay: shows the active step card floating at the bottom of the graphic -->
			<div
				class="mobile-step-overlay"
				class:tour-done={tourDone}
				style:--cluster-color={currentStep.colorVar
					? `var(${currentStep.colorVar})`
					: 'var(--orange)'}
			>
				<div class="step-card">
					<span class="step-num">{currentStep.num}</span>
					<h3>{currentStep.title}</h3>
					<p>{currentStep.body}</p>
				</div>
			</div>
		</div>
	</div>

	<!-- Steps column: on desktop these cards are visible in flow; on mobile they're invisible scroll triggers -->
	<div class="steps-col">
		{#each stepContents as step, i}
			<div
				class="scroll-trigger"
				data-step={i}
				data-final={i === stepContents.length - 1 ? 'true' : 'false'}
			>
				<div
					class="step-card desktop-card"
					style:--cluster-color={step.colorVar ? `var(${step.colorVar})` : 'var(--orange)'}
				>
					<span class="step-num">{step.num}</span>
					<h3>{step.title}</h3>
					<p>{step.body}</p>
				</div>
			</div>
		{/each}
	</div>
</section>

<!-- Free-explore footer -->
<section class="explore-footer">
	<p class="explore-hint">
		{#if tourDone}
			Explore freely — tap any paper on the map above.
		{:else}
			Scroll through each cluster, or jump to free explore.
		{/if}
	</p>
	<button class="replay-btn" onclick={replayTour}>
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
		</svg>
		Replay tour
	</button>
</section>

<!-- SSR-friendly accessible list fallback, hidden when JS hydrates -->
<noscript>
	<section class="fallback-list">
		<h2>All papers (by cluster)</h2>
		{#each sortedClusters as cluster}
			{@const members = papers.filter((p) => p.clusterId === cluster.id)}
			<h3 style:color={`var(${cluster.colorVar})`}>{cluster.label}</h3>
			<ul>
				{#each members as p}
					<li>
						<a href={p.link} target="_blank" rel="noopener">
							<strong>{p.title}</strong> — {p.authorsShort}, {p.year}
						</a>
						<p>{p.blurb}</p>
					</li>
				{/each}
			</ul>
		{/each}
	</section>
</noscript>

<!-- Paper detail drawer -->
<PaperSheet paper={selectedPaper} cluster={selectedCluster} onClose={closeSheet} />

<style>
	.papers-nav {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1.25rem 1.5rem 0;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--text-muted);
		text-decoration: none;
	}

	.back-link:hover,
	.back-link:active {
		color: var(--orange);
		text-decoration: none;
	}

	.papers-intro {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem 1.5rem 1rem;
		text-align: center;
	}

	.papers-intro h1 {
		font-family: var(--font-display);
		font-size: clamp(1.8rem, 4vw, 2.6rem);
		font-weight: 700;
		letter-spacing: -0.02em;
		color: var(--text);
		margin-bottom: 0.6rem;
	}

	.papers-intro .subtitle {
		color: var(--text-muted);
		font-size: 1rem;
		font-weight: 300;
		max-width: 520px;
		margin: 0 auto;
	}

	/* ═══════════════════════════════════════════════════
	   Tour section layout
	   Mobile-first: single column, sticky graphic on top,
	   scroll triggers below (invisible on mobile).
	   Desktop: grid, sticky graphic left, visible cards right.
	   ═══════════════════════════════════════════════════ */
	.tour-section {
		position: relative;
		max-width: 1200px;
		margin: 2rem auto 0;
		padding: 0 1rem;
	}

	/* ── Graphic column (mobile) ── */
	.graphic-col {
		position: relative;
		z-index: 1;
	}

	.graphic-sticky {
		position: sticky;
		top: 1rem;
		height: calc(100svh - 2rem);
		max-height: 720px;
	}

	.constellation-box {
		position: relative;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 16px;
		height: 100%;
		overflow: hidden;
	}

	/* Mobile step overlay: floats inside the graphic box at the bottom */
	.mobile-step-overlay {
		position: absolute;
		left: 1rem;
		right: 1rem;
		bottom: 1rem;
		pointer-events: none;
		z-index: 2;
		transition: opacity 0.35s ease, transform 0.35s ease;
	}

	.mobile-step-overlay.tour-done {
		opacity: 0;
		transform: translateY(20px);
	}

	.mobile-step-overlay .step-card {
		background: rgba(255, 255, 255, 0.93);
		-webkit-backdrop-filter: blur(14px);
		backdrop-filter: blur(14px);
		border: 1px solid var(--border);
		border-left: 3px solid var(--cluster-color, var(--orange));
		border-radius: 12px;
		padding: 1rem 1.2rem;
		box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
	}

	.step-num {
		display: block;
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--text-muted);
		letter-spacing: 0.1em;
		margin-bottom: 0.3rem;
	}

	.step-card h3 {
		font-family: var(--font-display);
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--cluster-color, var(--text));
		margin: 0 0 0.4rem;
	}

	.step-card p {
		font-size: 0.88rem;
		line-height: 1.55;
		color: var(--text);
		margin: 0;
	}

	/* ── Steps column (mobile: invisible scroll triggers) ── */
	.steps-col {
		position: relative;
		z-index: 0;
	}

	.scroll-trigger {
		/* Mobile: each trigger is a tall invisible section that scrollama watches */
		min-height: 80vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem 0;
	}

	.scroll-trigger:first-child {
		min-height: 50vh;
	}

	.scroll-trigger:last-child {
		min-height: 60vh;
	}

	/* Mobile: desktop cards hidden (overlay is used instead) */
	.desktop-card {
		display: none;
	}

	/* ═══════════════════════════════════════════════════
	   Desktop layout (>= 768px): side-by-side grid
	   ═══════════════════════════════════════════════════ */
	@media (min-width: 768px) {
		.tour-section {
			display: grid;
			grid-template-columns: 1.3fr 1fr;
			gap: 3rem;
			padding: 0 2rem;
		}

		.graphic-sticky {
			top: 2rem;
			height: calc(100svh - 4rem);
			max-height: 760px;
			align-self: start;
		}

		/* Mobile overlay hidden on desktop */
		.mobile-step-overlay {
			display: none;
		}

		/* Desktop cards visible in scroll column */
		.desktop-card {
			display: block;
			max-width: 420px;
		}

		.scroll-trigger {
			min-height: 80vh;
			justify-content: flex-start;
		}

		.scroll-trigger:first-child {
			min-height: 50vh;
		}

		.scroll-trigger:last-child {
			min-height: 60vh;
		}

		.desktop-card {
			background: var(--surface);
			border: 1px solid var(--border);
			border-left: 3px solid var(--cluster-color, var(--orange));
			border-radius: 12px;
			padding: 1.5rem 1.75rem;
			box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
		}
	}

	/* ── Explore footer ── */
	.explore-footer {
		max-width: 1200px;
		margin: 4rem auto 5rem;
		padding: 2rem 1.5rem;
		text-align: center;
		border-top: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}

	.explore-hint {
		color: var(--text-muted);
		font-size: 0.95rem;
		margin: 0;
	}

	.replay-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.65rem 1.2rem;
		font-family: var(--font-mono);
		font-size: 0.82rem;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.replay-btn:hover,
	.replay-btn:active {
		border-color: var(--orange);
		color: var(--orange);
	}

	.fallback-list {
		max-width: 800px;
		margin: 2rem auto;
		padding: 2rem 1.5rem;
	}

	.fallback-list h3 {
		margin-top: 2rem;
		font-family: var(--font-mono);
		font-size: 1rem;
	}

	.fallback-list ul {
		list-style: none;
		padding: 0;
	}

	.fallback-list li {
		margin-bottom: 1.5rem;
		padding: 1rem;
		border: 1px solid var(--border);
		border-radius: 8px;
	}
</style>
