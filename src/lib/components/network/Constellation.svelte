<script lang="ts">
	import { onMount } from 'svelte';
	import { animate, createTimeline, stagger, svg } from 'animejs';
	import type { Paper, Cluster } from '$lib/data/papers';
	import type { Layout } from '$lib/data/paper-layout';

	let {
		papers,
		clusters,
		layout,
		selectedId = $bindable(),
		focusedClusterId = null,
		viewBox = { w: 1000, h: 1000 }
	}: {
		papers: Paper[];
		clusters: Cluster[];
		layout: Layout;
		selectedId: string | null;
		focusedClusterId?: string | null;
		viewBox?: { w: number; h: number };
	} = $props();

	let svgEl: SVGSVGElement;
	let hasAnimated = false;

	// Derived: which cluster is currently "active" for focus/dim effects.
	let activeCluster = $derived(
		selectedId ? (papers.find((p) => p.id === selectedId)?.clusterId ?? null) : focusedClusterId
	);

	// Color lookup: cluster id → css var
	const clusterColorById = new Map(clusters.map((c) => [c.id, c.colorVar]));

	// Constants for node visual sizes (used so we can animate from 0 to final)
	const RING_RADIUS = 18;
	const DOT_RADIUS = 6;
	const SELECTED_RING_RADIUS = 22;
	const SELECTED_DOT_RADIUS = 8;

	onMount(() => {
		if (!svgEl) return;
		const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

		// Mark the SVG as ready so CSS can reveal elements that had opacity:0 initial state.
		// For reduced motion we skip animation entirely — CSS rule below sets everything to visible.
		svgEl.classList.add('ready');

		if (reducedMotion) {
			// Snap to final state — no animation.
			svgEl
				.querySelectorAll<SVGCircleElement>('.node-ring')
				.forEach((el) => el.setAttribute('r', String(RING_RADIUS)));
			svgEl
				.querySelectorAll<SVGCircleElement>('.node-dot')
				.forEach((el) => el.setAttribute('r', String(DOT_RADIUS)));
			hasAnimated = true;
			return;
		}

		// Sequenced entrance using createTimeline (anime.js v4)
		const tl = createTimeline({
			defaults: { ease: 'outExpo' }
		});

		// 1. Cluster hulls fade in
		tl.add(
			'.hull',
			{
				opacity: [0, 0.35],
				duration: 900
			},
			0
		);

		// 2. Cluster labels fade in
		tl.add(
			'.cluster-label',
			{
				opacity: [0, 1],
				duration: 600
			},
			150
		);

		// 3. Edges draw in using createDrawable (v4 way)
		tl.add(
			svg.createDrawable('.edge'),
			{
				draw: ['0 0', '0 1'],
				duration: 700,
				delay: stagger(35),
				ease: 'inOutQuad'
			},
			250
		);

		// 4. Node rings pop in (animating the r attribute — no CSS transform conflicts)
		tl.add(
			'.node-ring',
			{
				r: [0, RING_RADIUS],
				duration: 700,
				delay: stagger(55, { from: 'center' }),
				ease: 'outElastic(1, .55)'
			},
			500
		);

		// 5. Inner dots follow the rings
		tl.add(
			'.node-dot',
			{
				r: [0, DOT_RADIUS],
				duration: 600,
				delay: stagger(55, { from: 'center' }),
				ease: 'outBack(1.5)'
			},
			560
		);

		// 6. Year + author labels fade in
		tl.add(
			'.node-text',
			{
				opacity: [0, 1],
				translateY: [6, 0],
				duration: 500,
				delay: stagger(40, { from: 'center' })
			},
			680
		);

		hasAnimated = true;
	});

	// Selection animation: when a node becomes selected, bounce its inner circle.
	$effect(() => {
		if (!svgEl || !hasAnimated || !selectedId) return;
		const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reducedMotion) return;

		const selectedNode = svgEl.querySelector(`[data-id="${selectedId}"]`);
		if (!selectedNode) return;

		const ring = selectedNode.querySelector('.node-ring');
		const dot = selectedNode.querySelector('.node-dot');
		if (ring) {
			animate(ring, {
				r: [RING_RADIUS, SELECTED_RING_RADIUS * 1.15, SELECTED_RING_RADIUS],
				duration: 500,
				ease: 'outElastic(1, .6)'
			});
		}
		if (dot) {
			animate(dot, {
				r: [DOT_RADIUS, SELECTED_DOT_RADIUS * 1.2, SELECTED_DOT_RADIUS],
				duration: 500,
				ease: 'outElastic(1, .6)'
			});
		}
	});

	// When deselected, animate back to default sizes
	$effect(() => {
		if (!svgEl || !hasAnimated || selectedId) return;
		const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reducedMotion) return;

		const prevSelected = svgEl.querySelectorAll('[data-was-selected="true"]');
		prevSelected.forEach((node) => {
			const ring = node.querySelector('.node-ring');
			const dot = node.querySelector('.node-dot');
			if (ring) animate(ring, { r: RING_RADIUS, duration: 300, ease: 'outQuad' });
			if (dot) animate(dot, { r: DOT_RADIUS, duration: 300, ease: 'outQuad' });
			node.removeAttribute('data-was-selected');
		});
	});

	// Tap vs pan debounce: only fire click when movement is minimal.
	let downX = 0;
	let downY = 0;
	function onPointerDown(e: PointerEvent) {
		downX = e.clientX;
		downY = e.clientY;
	}
	function onPointerUp(e: PointerEvent, id: string) {
		const dx = e.clientX - downX;
		const dy = e.clientY - downY;
		if (Math.hypot(dx, dy) > 6) return;
		// Mark the currently-selected node so deselection effect can animate it back
		if (selectedId && selectedId !== id) {
			const prev = svgEl.querySelector(`[data-id="${selectedId}"]`);
			prev?.setAttribute('data-was-selected', 'true');
		}
		if (selectedId === id) {
			const prev = svgEl.querySelector(`[data-id="${id}"]`);
			prev?.setAttribute('data-was-selected', 'true');
		}
		selectedId = selectedId === id ? null : id;
	}
	function onBackgroundTap(e: MouseEvent) {
		if (e.target === svgEl) {
			if (selectedId) {
				const prev = svgEl.querySelector(`[data-id="${selectedId}"]`);
				prev?.setAttribute('data-was-selected', 'true');
			}
			selectedId = null;
		}
	}

	// Keyboard navigation: arrow keys cycle through papers in the active cluster.
	function onKeydown(e: KeyboardEvent, id: string) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			selectedId = id;
			return;
		}
		if (e.key === 'Escape') {
			selectedId = null;
			return;
		}
		if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
			e.preventDefault();
			const currentPaper = papers.find((p) => p.id === id);
			if (!currentPaper) return;
			const siblings = papers.filter((p) => p.clusterId === currentPaper.clusterId);
			const idx = siblings.findIndex((p) => p.id === id);
			const dir = e.key === 'ArrowRight' ? 1 : -1;
			const next = siblings[(idx + dir + siblings.length) % siblings.length];
			const el = svgEl.querySelector(`[data-id="${next.id}"]`) as SVGGElement | null;
			el?.focus();
			selectedId = next.id;
		}
	}
</script>

<svg
	bind:this={svgEl}
	viewBox={`0 0 ${viewBox.w} ${viewBox.h}`}
	xmlns="http://www.w3.org/2000/svg"
	role="group"
	aria-label="Paper constellation"
	onclick={onBackgroundTap}
	preserveAspectRatio="xMidYMid meet"
>
	<!-- Cluster hulls (subtle dashed outlines) -->
	<g class="hulls">
		{#each clusters as cluster}
			{@const center = layout.clusterCenters.get(cluster.id)}
			{@const members = papers.filter((p) => p.clusterId === cluster.id)}
			{#if center && members.length > 0}
				<circle
					class="hull"
					class:dim={activeCluster && activeCluster !== cluster.id}
					class:focus={activeCluster === cluster.id}
					data-cluster-id={cluster.id}
					cx={center.x}
					cy={center.y}
					r={members.length === 1 ? 120 : 180}
					fill="none"
					stroke={`var(${cluster.colorVar})`}
					stroke-width="1.5"
					stroke-dasharray="6 6"
				/>
			{/if}
		{/each}
	</g>

	<!-- Cluster labels (positioned above cluster centers) -->
	<g class="labels">
		{#each clusters as cluster}
			{@const center = layout.clusterCenters.get(cluster.id)}
			{#if center}
				<text
					class="cluster-label"
					class:dim={activeCluster && activeCluster !== cluster.id}
					data-cluster-id={cluster.id}
					x={center.x}
					y={center.y - 205}
					text-anchor="middle"
					fill={`var(${cluster.colorVar})`}
					font-family="DM Mono, monospace"
					font-size="26"
					font-weight="600"
				>
					{cluster.label}
				</text>
			{/if}
		{/each}
	</g>

	<!-- Edges (drawn under nodes) -->
	<g class="edges">
		{#each layout.edges as edge (edge.id)}
			<line
				class="edge"
				class:dim={activeCluster && activeCluster !== edge.clusterId}
				data-kind={edge.kind}
				data-cluster-id={edge.clusterId}
				x1={edge.fromX}
				y1={edge.fromY}
				x2={edge.toX}
				y2={edge.toY}
				stroke={`var(${clusterColorById.get(edge.clusterId) ?? '--text-muted'})`}
				stroke-width={edge.kind === 'related' ? 2 : 1}
				stroke-dasharray={edge.kind === 'related' ? '0' : '4 4'}
			/>
		{/each}
	</g>

	<!-- Nodes (drawn above edges) -->
	<g class="nodes">
		{#each papers as paper (paper.id)}
			{@const pos = layout.papers.get(paper.id)}
			{#if pos}
				{@const color = `var(${clusterColorById.get(paper.clusterId) ?? '--orange'})`}
				{@const isSelected = paper.id === selectedId}
				{@const isDim = activeCluster && paper.clusterId !== activeCluster && !isSelected}
				<!-- Outer g: positioning only (SVG transform attribute) -->
				<g
					class="node"
					class:selected={isSelected}
					class:dim={isDim}
					data-id={paper.id}
					data-cluster-id={paper.clusterId}
					role="button"
					tabindex="0"
					aria-label={`${paper.title}, ${paper.authorsShort}, ${paper.year}`}
					transform={`translate(${pos.x}, ${pos.y})`}
					onpointerdown={onPointerDown}
					onpointerup={(e) => onPointerUp(e, paper.id)}
					onkeydown={(e) => onKeydown(e, paper.id)}
				>
					<!-- Hit target (Fitts's law, 36px radius invisible) -->
					<circle r="36" fill="transparent" class="hit" />
					<!-- Outer ring: r animated from 0 → RING_RADIUS during entrance -->
					<circle
						class="node-ring"
						r="0"
						fill="white"
						stroke={color}
						stroke-width="3"
					/>
					<!-- Inner dot -->
					<circle class="node-dot" r="0" fill={color} />
					<!-- Year label -->
					<text
						class="node-text node-year"
						y="48"
						text-anchor="middle"
						fill={color}
						font-family="DM Mono, monospace"
						font-size="18"
						font-weight="700"
					>
						{paper.year}
					</text>
					<!-- Authors label -->
					<text
						class="node-text node-authors"
						y="68"
						text-anchor="middle"
						fill="var(--text-muted)"
						font-family="DM Mono, monospace"
						font-size="13"
					>
						{paper.authorsShort}
					</text>
				</g>
			{/if}
		{/each}
	</g>
</svg>

<style>
	svg {
		width: 100%;
		height: 100%;
		display: block;
		user-select: none;
		touch-action: pan-y;
	}

	/* Initial state — everything hidden until JS sets the .ready class */
	.hull {
		opacity: 0;
		transition: opacity 0.4s ease;
	}
	.edge {
		opacity: 0;
		transition: opacity 0.4s ease;
	}
	.cluster-label {
		opacity: 0;
		transition: opacity 0.4s ease;
	}
	.node-text {
		opacity: 0;
	}

	/* Reduced-motion: snap everything visible immediately — no JS required */
	@media (prefers-reduced-motion: reduce) {
		.hull { opacity: 0.35 !important; }
		.edge { opacity: 1 !important; }
		.cluster-label { opacity: 1 !important; }
		.node-text { opacity: 1 !important; }
	}

	/* Nodes */
	.node {
		cursor: pointer;
		outline: none;
	}

	.node:focus-visible .node-ring {
		stroke-width: 5;
	}

	.node.dim {
		opacity: 0.18;
		transition: opacity 0.3s ease;
	}

	.node.selected .node-ring,
	.node.selected .node-dot {
		filter: drop-shadow(0 0 10px currentColor);
	}

	/* Edge dim state */
	.edge.dim {
		opacity: 0.08 !important;
	}

	.edge[data-kind='related'] {
		stroke-opacity: 0.6;
	}
	.edge[data-kind='cluster'] {
		stroke-opacity: 0.35;
	}

	/* Hull dim/focus states */
	.hull.dim {
		opacity: 0.08 !important;
	}

	.hull.focus {
		stroke-width: 2.2;
		opacity: 0.65 !important;
	}

	/* Cluster label dim */
	.cluster-label.dim {
		opacity: 0.2 !important;
	}
</style>
