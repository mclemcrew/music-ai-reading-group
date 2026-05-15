<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { animate, stagger } from 'animejs';
	import { sessions, findPaper, type TopicColor } from '$lib/data/sessions';

	let listRef: HTMLElement | undefined = $state();

	// Newest first for display.
	const ordered = [...sessions].reverse();

	// Filter axes.
	let activeTopics = $state<string[]>([]);
	let activeYears = $state<number[]>([]);
	let onlyNotes = $state(false);

	// Unique chips, derived from data so they stay in sync as sessions are added.
	const topicChips: { topic: string; color: TopicColor }[] = (() => {
		const seen = new Map<string, TopicColor>();
		for (const s of sessions) if (!seen.has(s.topic)) seen.set(s.topic, s.topicColor);
		return [...seen].map(([topic, color]) => ({ topic, color }));
	})();

	const yearChips: number[] = [...new Set(sessions.flatMap((s) => s.papers.map((p) => p.year)))]
		.sort((a, b) => b - a);

	function toggle<T>(arr: T[], value: T): T[] {
		return arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value];
	}

	const filteredSessions = $derived.by(() => {
		return ordered
			.map((session) => {
				const papers = session.papers.filter((p) => {
					if (activeTopics.length > 0 && !activeTopics.includes(session.topic)) return false;
					if (activeYears.length > 0 && !activeYears.includes(p.year)) return false;
					if (onlyNotes && !p.hasPost) return false;
					return true;
				});
				return { ...session, papers };
			})
			.filter((s) => s.papers.length > 0);
	});

	const visibleCounts = $derived.by(() => {
		const sCount = filteredSessions.length;
		const pCount = filteredSessions.reduce((n, s) => n + s.papers.length, 0);
		return { sessions: sCount, papers: pCount };
	});

	const filtersActive = $derived(
		activeTopics.length > 0 || activeYears.length > 0 || onlyNotes
	);

	function clearFilters() {
		activeTopics = [];
		activeYears = [];
		onlyNotes = false;
	}

	onMount(() => {
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced || !listRef) return;
		animate(listRef.querySelectorAll('.session-card'), {
			translateY: [20, 0],
			opacity: [0, 1],
			delay: stagger(70, { start: 100 }),
			duration: 550,
			ease: 'outExpo'
		});
	});
</script>

<svelte:head>
	<title>Papers — Music AI Reading Group</title>
	<meta
		name="description"
		content="Every paper the Music AI Reading Group has worked through, filterable by topic, year, and whether we wrote up notes."
	/>
</svelte:head>

<section class="container page-header">
	<a href="{base}/" class="back-link">
		<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
			<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
		</svg>
		Back to reading log
	</a>
	<h1>Papers</h1>
	<p class="lede">
		Every paper we've worked through, newest first. Filter by topic, year, or whether we wrote up notes.
	</p>
</section>

<section class="container filters" aria-label="Filter papers">
	<div class="filter-row">
		<span class="filter-label">Topic</span>
		<div class="chips">
			{#each topicChips as { topic, color } (topic)}
				{@const active = activeTopics.includes(topic)}
				<button
					type="button"
					class="chip topic-{color}"
					class:active
					aria-pressed={active}
					onclick={() => (activeTopics = toggle(activeTopics, topic))}
				>
					{topic}
				</button>
			{/each}
		</div>
	</div>

	<div class="filter-row">
		<span class="filter-label">Year</span>
		<div class="chips">
			{#each yearChips as year (year)}
				{@const active = activeYears.includes(year)}
				<button
					type="button"
					class="chip chip-year"
					class:active
					aria-pressed={active}
					onclick={() => (activeYears = toggle(activeYears, year))}
				>
					{year}
				</button>
			{/each}
		</div>
	</div>

	<div class="filter-row">
		<span class="filter-label">Notes</span>
		<div class="chips">
			<button
				type="button"
				class="chip chip-notes"
				class:active={onlyNotes}
				aria-pressed={onlyNotes}
				onclick={() => (onlyNotes = !onlyNotes)}
			>
				<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/>
				</svg>
				Has notes
			</button>
			{#if filtersActive}
				<button type="button" class="chip chip-clear" onclick={clearFilters}>
					Clear all
				</button>
			{/if}
		</div>
	</div>

	<p class="filter-count" aria-live="polite">
		{#if filtersActive}
			Showing {visibleCounts.papers} {visibleCounts.papers === 1 ? 'paper' : 'papers'}
			across {visibleCounts.sessions} {visibleCounts.sessions === 1 ? 'session' : 'sessions'}
		{:else}
			{visibleCounts.papers} papers across {visibleCounts.sessions} sessions
		{/if}
	</p>
</section>

<section class="container session-list" bind:this={listRef}>
	{#if filteredSessions.length === 0}
		<div class="empty">
			<p>No papers match those filters.</p>
			<button type="button" class="chip chip-clear" onclick={clearFilters}>Clear filters</button>
		</div>
	{/if}

	{#each filteredSessions as session (session.week)}
		{@const sessionPost = session.papers.find((p) => p.hasPost)?.postSlug}
		<article class="session-card">
			<header class="session-meta">
				<span class="session-week">{session.week}</span>
				<span class="session-date">{session.date}</span>
				<span class="topic-badge topic-{session.topicColor}">{session.topic}</span>
				<div class="session-actions">
					{#if session.recording}
						<a href={session.recording.url} target="_blank" rel="noopener" class="recording-btn" title="Passcode: {session.recording.passcode}">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
							Recording
						</a>
					{/if}
					{#if sessionPost}
						<a href="{base}/posts/{sessionPost}" class="read-post-btn">
							Notes
							<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
						</a>
					{/if}
				</div>
			</header>

			<div class="papers">
				{#each session.papers as paper (paper.id)}
					{@const related = (paper.relatedTo ?? [])
						.map((id) => findPaper(id))
						.filter((p): p is NonNullable<typeof p> => Boolean(p))}
					<div class="paper-row" id={paper.id}>
						<div class="paper-info">
							<a href={paper.link} target="_blank" rel="noopener" class="paper-title">{paper.title}</a>
							<div class="paper-meta">
								<span class="paper-authors">{paper.authors}</span>
								<span class="paper-year">{paper.year}</span>
								{#if paper.excalidraw}
									<a href={paper.excalidraw} target="_blank" rel="noopener" class="slides-link">
										<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
										Slides
									</a>
								{/if}
							</div>
							{#if paper.blurb}
								<p class="paper-blurb">{paper.blurb}</p>
							{/if}
							{#if related.length > 0}
								<div class="related">
									<span class="related-label">Related</span>
									{#each related as r (r.id)}
										<a href="#{r.id}" class="related-pill">{r.title}</a>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</article>
	{/each}
</section>

<style>
	.page-header {
		padding-top: 2.5rem;
		padding-bottom: 1.25rem;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-family: var(--font-display);
		font-size: 0.75rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		text-decoration: none;
		margin-bottom: 1.25rem;
	}

	.back-link:hover {
		color: var(--orange);
		text-decoration: none;
	}

	.page-header h1 {
		font-size: clamp(2rem, 4vw, 2.6rem);
		margin-bottom: 0.4rem;
	}

	.lede {
		color: var(--text-muted);
		font-size: 0.95rem;
		margin: 0;
		max-width: 60ch;
	}

	/* ── Filters ── */
	.filters {
		padding-top: 0.5rem;
		padding-bottom: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}

	.filter-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.filter-label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-muted);
		flex-shrink: 0;
		min-width: 3.2rem;
	}

	.chips {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-family: var(--font-display);
		font-size: 0.78rem;
		font-weight: 600;
		padding: 0.3rem 0.75rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
	}

	.chip:hover {
		color: var(--text);
		border-color: var(--text-muted);
	}

	.chip.active {
		color: var(--text);
		font-weight: 700;
	}

	/* Topic chip colors when active — outlined when inactive, filled-glow when active */
	.chip.topic-orange.active {
		background: var(--orange-glow);
		color: var(--orange);
		border-color: rgba(224, 112, 32, 0.5);
	}
	.chip.topic-teal.active {
		background: var(--teal-glow);
		color: var(--teal);
		border-color: rgba(26, 158, 143, 0.5);
	}
	.chip.topic-violet.active {
		background: var(--violet-glow);
		color: var(--violet);
		border-color: rgba(124, 77, 255, 0.5);
	}
	.chip.topic-blue.active {
		background: var(--blue-glow);
		color: var(--blue);
		border-color: rgba(41, 121, 255, 0.5);
	}
	.chip.topic-rose.active {
		background: var(--rose-glow);
		color: var(--rose);
		border-color: rgba(214, 56, 100, 0.5);
	}
	.chip.topic-amber.active {
		background: var(--amber-glow);
		color: var(--amber);
		border-color: rgba(199, 147, 36, 0.5);
	}
	.chip.topic-moss.active {
		background: var(--moss-glow);
		color: var(--moss);
		border-color: rgba(94, 138, 62, 0.5);
	}
	.chip.topic-plum.active {
		background: var(--plum-glow);
		color: var(--plum);
		border-color: rgba(155, 62, 124, 0.5);
	}

	.chip-year.active {
		background: var(--surface-2);
		color: var(--text);
		border-color: var(--text-muted);
	}

	.chip-notes.active {
		background: var(--surface-2);
		color: var(--text);
		border-color: var(--text-muted);
	}

	.chip-clear {
		color: var(--text-muted);
		border-style: dashed;
	}

	.chip-clear:hover {
		color: var(--orange);
		border-color: var(--orange);
		border-style: solid;
	}

	.filter-count {
		font-family: var(--font-display);
		font-size: 0.78rem;
		color: var(--text-muted);
		margin: 0.25rem 0 0;
	}

	/* ── Empty state ── */
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 2.5rem 1rem;
		color: var(--text-muted);
		border: 1px dashed var(--border);
		border-radius: 14px;
	}

	.empty p {
		margin: 0;
		font-size: 0.95rem;
	}

	/* ── Session list ── */
	.session-list {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		padding-bottom: 4rem;
	}

	.session-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		overflow: hidden;
	}

	.session-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface-2);
		flex-wrap: wrap;
	}

	.session-week {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 0.92rem;
	}

	.session-date {
		font-family: var(--font-display);
		font-size: 0.78rem;
		color: var(--text-muted);
	}

	.topic-badge {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		padding: 0.2rem 0.7rem;
		border-radius: 12px;
		margin-left: auto;
	}

	.topic-orange { background: var(--orange-glow); color: var(--orange); border: 1px solid rgba(224, 112, 32, 0.35); }
	.topic-teal { background: var(--teal-glow); color: var(--teal); border: 1px solid rgba(26, 158, 143, 0.35); }
	.topic-violet { background: var(--violet-glow); color: var(--violet); border: 1px solid rgba(124, 77, 255, 0.35); }
	.topic-blue { background: var(--blue-glow); color: var(--blue); border: 1px solid rgba(41, 121, 255, 0.35); }
	.topic-rose { background: var(--rose-glow); color: var(--rose); border: 1px solid rgba(214, 56, 100, 0.35); }
	.topic-amber { background: var(--amber-glow); color: var(--amber); border: 1px solid rgba(199, 147, 36, 0.35); }
	.topic-moss { background: var(--moss-glow); color: var(--moss); border: 1px solid rgba(94, 138, 62, 0.35); }
	.topic-plum { background: var(--plum-glow); color: var(--plum); border: 1px solid rgba(155, 62, 124, 0.35); }

	.session-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.recording-btn,
	.read-post-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.78rem;
		padding: 0.35rem 0.75rem;
		border-radius: 8px;
		text-decoration: none;
		white-space: nowrap;
		transition: all 0.15s;
	}

	.recording-btn {
		color: var(--violet);
		background: var(--violet-glow);
		border: 1px solid rgba(124, 77, 255, 0.35);
	}

	.recording-btn:hover {
		background: var(--violet);
		color: white;
		border-color: var(--violet);
		text-decoration: none;
	}

	.read-post-btn {
		color: var(--orange);
		background: var(--orange-glow);
		border: 1px solid rgba(224, 112, 32, 0.35);
	}

	.read-post-btn:hover {
		background: var(--orange);
		color: white;
		border-color: var(--orange);
		text-decoration: none;
	}

	.papers {
		padding: 0.5rem 0;
	}

	.paper-row {
		padding: 0.95rem 1.5rem;
		border-bottom: 1px solid var(--surface-3);
		transition: background 0.15s;
		scroll-margin-top: 1rem;
	}

	.paper-row:last-child {
		border-bottom: none;
	}

	.paper-row:hover {
		background: var(--surface-2);
	}

	.paper-row:target {
		background: var(--orange-glow);
	}

	.paper-title {
		display: block;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.95rem;
		color: var(--text);
		text-decoration: none;
		margin-bottom: 0.25rem;
		line-height: 1.4;
	}

	.paper-title:hover {
		color: var(--orange);
		text-decoration: none;
	}

	.paper-meta {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.paper-authors {
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.paper-year {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.75rem;
		color: var(--teal);
		background: var(--teal-glow);
		border: 1px solid rgba(26, 158, 143, 0.3);
		padding: 0.1rem 0.5rem;
		border-radius: 8px;
	}

	.slides-link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.72rem;
		color: var(--teal);
		text-decoration: none;
		border: 1px solid rgba(26, 158, 143, 0.4);
		background: var(--teal-glow);
		padding: 0.12rem 0.55rem;
		border-radius: 6px;
		transition: all 0.15s;
	}

	.slides-link:hover {
		background: var(--teal);
		color: white;
		border-color: var(--teal);
		text-decoration: none;
	}

	.paper-blurb {
		margin: 0.55rem 0 0;
		font-size: 0.85rem;
		line-height: 1.55;
		color: var(--text-muted);
		max-width: 70ch;
	}

	.related {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
		margin-top: 0.6rem;
	}

	.related-label {
		font-family: var(--font-display);
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-muted);
		margin-right: 0.15rem;
	}

	.related-pill {
		display: inline-block;
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--text-muted);
		background: var(--surface-2);
		border: 1px solid var(--border);
		padding: 0.18rem 0.55rem;
		border-radius: 999px;
		text-decoration: none;
		max-width: 28ch;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
	}

	.related-pill:hover {
		color: var(--orange);
		border-color: var(--orange);
		background: var(--orange-glow);
		text-decoration: none;
	}

	.session-card {
		opacity: 0;
	}

	@media (prefers-reduced-motion: reduce) {
		.session-card {
			opacity: 1 !important;
		}
	}

	@media (max-width: 640px) {
		.session-meta {
			padding: 0.75rem 1rem;
		}
		.paper-row {
			padding: 0.8rem 1rem;
		}
		.topic-badge {
			margin-left: 0;
		}
		.filter-label {
			min-width: auto;
		}
	}
</style>
