<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { animate, stagger } from 'animejs';
	import { sessions, recentSessions } from '$lib/data/sessions';

	let { data } = $props();

	const featuredSessions = recentSessions(2);
	const totalSessions = sessions.length;
	const totalPapers = sessions.reduce((n, s) => n + s.papers.length, 0);
	const FEATURED_POSTS = 2;
	const featuredPosts = $derived(data.posts.slice(0, FEATURED_POSTS));
	const totalPosts = $derived(data.posts.length);

	const timezones = [
		{ city: 'California', time: '7:00 AM', tz: 'PST' },
		{ city: 'Chicago', time: '9:00 AM', tz: 'CDT' },
		{ city: 'New York', time: '10:00 AM', tz: 'EDT' },
		{ city: 'Europe', time: '4:00 PM', tz: 'CEST' }
	];

	let staffLines: SVGPathElement[] = [];
	let noteStems: SVGPathElement[] = [];
	let noteGroups: SVGGElement[] = [];
	let heroRef: HTMLElement;
	let scheduleRef: HTMLElement;
	let postsRef = $state<HTMLElement | undefined>(undefined);

	// Quarter notes scattered along the staff. Stems vertical (no group
	// rotation), heads tilted ~24° in the standard musical convention and
	// large enough to fill the staff space.
	const notePositions = [
		{ x: 200, y: 70 },
		{ x: 400, y: 55 },
		{ x: 580, y: 85 },
		{ x: 760, y: 70 },
		{ x: 950, y: 55 }
	];

	onMount(() => {
		const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

		if (!reducedMotion) {
			// Hero text entrance — starts immediately so it's the first thing visible
			animate(heroRef.querySelectorAll('.hero-text > *'), {
				translateY: [20, 0],
				opacity: [0, 1],
				delay: stagger(60),
				duration: 500,
				ease: 'outExpo'
			});

			// Staff lines + note stems draw on via stroke-dashoffset
			const drawOn: SVGGeometryElement[] = [...staffLines, ...noteStems];
			for (const el of drawOn) {
				if (!el) continue;
				const len = el.getTotalLength();
				el.style.strokeDasharray = `${len}`;
				el.style.strokeDashoffset = `${len}`;
			}
			animate(drawOn, {
				strokeDashoffset: 0,
				duration: 900,
				delay: stagger(45, { start: 200 }),
				ease: 'outQuad'
			});

			// Filled note heads fade in shortly after their stems start drawing
			for (const g of noteGroups) {
				if (g) g.style.opacity = '0';
			}
			animate(noteGroups, {
				opacity: [0, 0.85],
				duration: 500,
				delay: stagger(45, { start: 500 }),
				ease: 'outQuad'
			});
		}

		const scheduleObs = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (!e.isIntersecting) return;
					if (reducedMotion) return scheduleObs.disconnect();
					animate(scheduleRef.querySelectorAll('.session-card'), {
						translateY: [24, 0],
						opacity: [0, 1],
						delay: stagger(100),
						duration: 600,
						ease: 'outExpo'
					});
					scheduleObs.disconnect();
				});
			},
			{ threshold: 0.1 }
		);
		scheduleObs.observe(scheduleRef);

		const postsObs = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (!e.isIntersecting) return;
					if (!postsRef) return;
					if (reducedMotion) return postsObs.disconnect();
					animate(postsRef.querySelectorAll('.post-card'), {
						translateY: [20, 0],
						opacity: [0, 1],
						delay: stagger(80),
						duration: 600,
						ease: 'outExpo'
					});
					postsObs.disconnect();
				});
			},
			{ threshold: 0.1 }
		);
		if (postsRef) postsObs.observe(postsRef);

	});
</script>

<svelte:head>
	<title>Music Co-Creative AI Reading Group</title>
	<meta name="description" content="Weekly reading group exploring music and AI research: interactive papers, audio experiments, and visual explainers." />
</svelte:head>

<!-- ═══ HERO ═══ -->
<section class="hero" bind:this={heroRef}>
	<div class="hero-bg-svg" aria-hidden="true">
		<svg viewBox="0 0 1200 150" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
			<!-- Hand-drawn-feel staff lines: slight bezier wobble, not perfectly straight -->
			{#each [25, 55, 85, 115, 145] as y, i}
				<path
					bind:this={staffLines[i]}
					d={`M 40 ${y + (i % 2 === 0 ? -0.6 : 0.8)} C 360 ${y + 1.4}, 720 ${y - 1.6}, 1160 ${y + (i % 2 === 0 ? 0.7 : -0.9)}`}
					stroke="var(--text-muted)"
					stroke-width="1"
					stroke-linecap="round"
					fill="none"
					opacity="0.36"
				/>
			{/each}
			<!-- Quarter notes: vertical stems, filled heads, tilted ~24° -->
			{#each notePositions as np, i}
				<g bind:this={noteGroups[i]}>
					<ellipse
						cx={np.x}
						cy={np.y}
						rx="11"
						ry="7.5"
						transform={`rotate(-24 ${np.x} ${np.y})`}
						fill="var(--orange)"
					/>
					<path
						bind:this={noteStems[i]}
						d={`M ${np.x + 10} ${np.y - 4} L ${np.x + 10} ${np.y - 40}`}
						stroke="var(--orange)"
						stroke-width="1.6"
						stroke-linecap="round"
						fill="none"
					/>
				</g>
			{/each}
		</svg>
	</div>

	<div class="hero-inner container">
		<div class="hero-text">
			<h1>
				Music<span class="accent-dot" style="color:var(--orange)">.</span>
				Co-Creative<span class="accent-dot" style="color:var(--teal)">.</span>
				AI
			</h1>
			<p class="hero-sub">We meet weekly to read a paper or two at the intersection of music and ML. After each session, we write up notes, post the slides, and sometimes record video or build a small demo. Most of what we make ends up on this site.</p>
			<div class="hero-actions">
				<a href="https://groups.google.com/g/music-co-creative-ai" target="_blank" rel="noopener" class="btn-primary">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
						<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
					</svg>
					Join the Group
				</a>
				<a href="https://docs.google.com/spreadsheets/d/1uTtK5jWXybRhE_QTXmANw3RZwg019n2m30_M1g3lrIA/edit?usp=sharing" target="_blank" rel="noopener" class="btn-secondary">
					View Full Schedule
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
					</svg>
				</a>
				<a href="https://github.com/mclemcrew/music-ai-reading-group" target="_blank" rel="noopener" class="btn-secondary">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
					</svg>
					GitHub
				</a>
			</div>
		</div>
	</div>

	<!-- Time zones -->
	<div class="timezone-strip">
		<div class="container">
			<div class="tz-inner">
				<span class="tz-label">Meets weekly ·</span>
				{#each timezones as tz, i}
					<span class="tz-item">
						<span class="tz-city">{tz.city}</span>
						<span class="tz-time">{tz.time} {tz.tz}</span>
					</span>
					{#if i < timezones.length - 1}<span class="tz-sep">·</span>{/if}
				{/each}
			</div>
		</div>
	</div>
</section>

<!-- ═══ SCHEDULE ═══ -->
<section class="schedule-section container" bind:this={scheduleRef}>
	<div class="section-header">
		<h2><span class="h2-accent" style="background:var(--orange)"></span>Reading Schedule</h2>
		<p class="section-sub">What we're currently reading</p>
	</div>

	<div class="sessions">
		{#each featuredSessions as session}
			{@const sessionPost = session.papers.find((p) => p.hasPost)?.postSlug}
			<div class="session-card">
				<div class="session-meta topic-{session.topicColor}">
					<span class="session-week">{session.week}</span>
					<span class="session-date">{session.date}</span>
					<span class="topic-badge topic-{session.topicColor}">{session.topic}</span>
					<div class="session-actions">
						{#if session.recording}
							<div class="recording-wrap">
								<a href={session.recording.url} target="_blank" rel="noopener" class="recording-btn" title="Passcode: {session.recording.passcode}">
									<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
									Recording
								</a>
								<span class="recording-pw">pw: {session.recording.passcode}</span>
							</div>
						{/if}
						{#if sessionPost}
							<a href="{base}/posts/{sessionPost}" class="read-post-btn">
								Read session notes
								<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
							</a>
						{/if}
					</div>
				</div>
				<div class="session-papers">
					{#each session.papers as paper}
						<div class="paper-row">
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
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/each}
	</div>

	{#if totalSessions > featuredSessions.length}
		<div class="schedule-more">
			<a href="{base}/papers" class="all-sessions-link">
				Browse all {totalPapers} papers
				<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
			</a>
		</div>
	{/if}
</section>

<!-- ═══ PUBLISHED NOTES ═══ -->
{#if data.posts.length > 0}
<section class="posts-section container" bind:this={postsRef}>
	<div class="section-header">
		<h2><span class="h2-accent" style="background:var(--teal)"></span>Interactive Notes</h2>
		<p class="section-sub">Notes from past sessions</p>
	</div>

	<div class="posts-grid">
		{#each featuredPosts as post}
			<a href="{base}/posts/{post.slug}" class="post-card">
				<div class="post-card-top">
					{#if post.tags?.length}
						<div class="post-tags">
							{#each post.tags.slice(0, 3) as tag}
								<span class="tag">{tag}</span>
							{/each}
						</div>
					{/if}
				</div>
				<h3>{post.title}</h3>
				{#if post.subtitle}<p class="post-subtitle">{post.subtitle}</p>{/if}
				{#if post.description}<p class="post-desc">{post.description}</p>{/if}
				<div class="post-footer">
					<time>{post.date}</time>
					<span class="post-read">Read →</span>
				</div>
			</a>
		{/each}
	</div>

	{#if totalPosts > featuredPosts.length}
		<div class="schedule-more">
			<a href="{base}/posts" class="all-sessions-link">
				Browse all {totalPosts} notes
				<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
			</a>
		</div>
	{/if}
</section>
{/if}

<!-- ═══ ABOUT ═══ -->
<section class="about-section container">
	<div class="about-grid">
		<div class="about-card">
			<div class="about-icon">
				<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
				</svg>
			</div>
			<h3>What we read</h3>
			<p>ML papers about music: synthesis, transcription, generative models, anything with a loss function and an audio output. We work through one or two a week.</p>
		</div>
		<div class="about-card">
			<div class="about-icon">
				<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
				</svg>
			</div>
			<h3>How we share</h3>
			<p>Each session gets interactive notes with visualizations and audio demos (and usually some PyTorch). The goal is real intuition, not just a summary of the abstract.</p>
		</div>
		<div class="about-card">
			<div class="about-icon">
				<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
					<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
				</svg>
			</div>
			<h3>Who it's for</h3>
			<p>Researchers, engineers, musicians, students. Anyone who wants to actually dig into the papers rather than just hear about them. Show up, ask questions, bring coffee.</p>
		</div>
	</div>
	<div class="join-cta">
		<p>Want in, have a paper to suggest, or want to present one?</p>
		<a href="https://groups.google.com/g/music-co-creative-ai" target="_blank" rel="noopener" class="btn-primary">
			Join the Google Group
		</a>
	</div>
</section>

<style>
	/* ── Hero ── */
	.hero {
		position: relative;
		overflow: hidden;
		background: var(--bg);
		border-bottom: 1px solid var(--border);
		padding-bottom: 0;
	}

	/* Top decoration band: wobbly staff lines + scattered hand-drawn notes.
	   Sits in the upper portion of the hero only, so it never overlaps the
	   H1 / paragraph / button row that follows. */
	.hero-bg-svg {
		position: absolute;
		top: 1.5rem;
		left: 0;
		right: 0;
		height: clamp(110px, 14vw, 150px);
		pointer-events: none;
		opacity: 0.85;
	}

	.hero-bg-svg svg {
		width: 100%;
		height: 100%;
		display: block;
	}

	.hero-inner {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: clamp(9rem, 16vw, 11rem);
		padding-bottom: 3rem;
		position: relative;
		max-width: 720px;
		margin-left: auto;
		margin-right: auto;
		text-align: center;
	}

	.hero-text {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}

	h1 {
		font-family: var(--font-display);
		font-size: clamp(2.2rem, 5vw, 3.6rem);
		font-weight: 700;
		line-height: 1.15;
		letter-spacing: -0.02em;
	}

	.accent-dot {
		font-weight: 700;
	}

	.hero-sub {
		font-size: clamp(0.95rem, 2vw, 1.1rem);
		color: var(--text-muted);
		font-weight: 300;
		max-width: 560px;
		margin: 0 auto 0.5rem;
	}

	.hero-actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
	}

	.btn-primary {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--orange);
		color: white;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.9rem;
		padding: 0.65rem 1.3rem;
		border-radius: 8px;
		text-decoration: none;
		transition: all 0.2s ease;
		min-height: 44px;
	}

	.btn-primary:hover {
		background: #c8611a;
		text-decoration: none;
		transform: translateY(-1px);
		box-shadow: 0 4px 16px var(--orange-glow);
	}

	.btn-secondary {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		background: transparent;
		color: var(--text-muted);
		font-family: var(--font-display);
		font-weight: 500;
		font-size: 0.88rem;
		padding: 0.65rem 1.1rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		text-decoration: none;
		transition: all 0.2s ease;
		min-height: 44px;
	}

	.btn-secondary:hover {
		border-color: var(--orange);
		color: var(--orange);
		text-decoration: none;
	}

	/* Timezone strip */
	.timezone-strip {
		background: var(--surface);
		border-top: 1px solid var(--border);
		padding: 0.75rem 0;
	}

	.tz-inner {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		flex-wrap: wrap;
		font-family: var(--font-display);
		font-size: 0.78rem;
	}

	.tz-label {
		color: var(--text-muted);
	}

	.tz-item {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}

	.tz-city {
		font-weight: 500;
		color: var(--text);
	}

	.tz-time {
		color: var(--orange);
	}

	.tz-sep {
		color: var(--border);
	}

	/* ── Section shared ── */
	.schedule-section,
	.posts-section,
	.about-section {
		padding-top: 3.5rem;
		padding-bottom: 3.5rem;
	}

	.section-header {
		margin-bottom: 2rem;
	}

	.section-header h2 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: clamp(1.3rem, 3vw, 1.7rem);
		font-weight: 700;
		margin-bottom: 0.35rem;
	}

	.h2-accent {
		width: 4px;
		height: 1.2em;
		border-radius: 2px;
		flex-shrink: 0;
	}

	.section-sub {
		color: var(--text-muted);
		font-size: 0.92rem;
		margin: 0;
	}

	/* ── Schedule ── */
	.sessions {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
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
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	.topic-badge {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 0.2rem 0.7rem;
		border-radius: 12px;
		margin-left: auto;
	}

	.session-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.recording-wrap {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.recording-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.78rem;
		color: var(--violet);
		background: var(--violet-glow);
		border: 1px solid rgba(124, 77, 255, 0.35);
		padding: 0.35rem 0.75rem;
		border-radius: 8px;
		text-decoration: none;
		white-space: nowrap;
		transition: all 0.15s;
		flex-shrink: 0;
	}

	.recording-btn:hover {
		background: var(--violet);
		color: white;
		text-decoration: none;
		border-color: var(--violet);
	}

	.recording-pw {
		font-family: var(--font-display);
		font-weight: 500;
		font-size: 0.8rem;
		color: var(--text);
		white-space: nowrap;
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
		flex-shrink: 0;
	}

	.slides-link:hover {
		background: var(--teal);
		color: white;
		text-decoration: none;
		border-color: var(--teal);
	}

	.topic-orange {
		background: var(--orange-glow);
		color: var(--orange);
		border: 1px solid rgba(224, 112, 32, 0.35);
	}

	.topic-teal {
		background: var(--teal-glow);
		color: var(--teal);
		border: 1px solid rgba(26, 158, 143, 0.35);
	}

	.topic-violet {
		background: var(--violet-glow);
		color: var(--violet);
		border: 1px solid rgba(124, 77, 255, 0.35);
	}

	.topic-blue {
		background: var(--blue-glow);
		color: var(--blue);
		border: 1px solid rgba(41, 121, 255, 0.35);
	}

	.topic-rose {
		background: var(--rose-glow);
		color: var(--rose);
		border: 1px solid rgba(214, 56, 100, 0.35);
	}

	.topic-amber {
		background: var(--amber-glow);
		color: var(--amber);
		border: 1px solid rgba(199, 147, 36, 0.35);
	}

	.topic-moss {
		background: var(--moss-glow);
		color: var(--moss);
		border: 1px solid rgba(94, 138, 62, 0.35);
	}

	.topic-plum {
		background: var(--plum-glow);
		color: var(--plum);
		border: 1px solid rgba(155, 62, 124, 0.35);
	}

	.session-meta.topic-orange {
		background: var(--orange-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(224, 112, 32, 0.28);
	}

	.session-meta.topic-teal {
		background: var(--teal-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(26, 158, 143, 0.3);
	}

	.session-meta.topic-violet {
		background: var(--violet-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(124, 77, 255, 0.28);
	}

	.session-meta.topic-blue {
		background: var(--blue-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(41, 121, 255, 0.28);
	}

	.session-meta.topic-rose {
		background: var(--rose-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(214, 56, 100, 0.3);
	}

	.session-meta.topic-amber {
		background: var(--amber-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(199, 147, 36, 0.32);
	}

	.session-meta.topic-moss {
		background: var(--moss-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(94, 138, 62, 0.32);
	}

	.session-meta.topic-plum {
		background: var(--plum-glow);
		color: var(--text);
		border: none;
		border-bottom: 1px solid rgba(155, 62, 124, 0.3);
	}

	.session-papers {
		padding: 0.5rem 0;
	}

	.paper-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.9rem 1.5rem;
		border-bottom: 1px solid var(--surface-3);
		transition: background 0.15s;
	}

	.paper-row:last-child {
		border-bottom: none;
	}

	.paper-row:hover {
		background: var(--surface-2);
	}

	.paper-info {
		flex: 1;
		min-width: 0;
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
		font-size: 0.72rem;
		color: var(--teal);
		background: var(--teal-glow);
		padding: 0.1rem 0.5rem;
		border-radius: 8px;
	}

	.read-post-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 0.78rem;
		color: var(--orange);
		background: var(--orange-glow);
		border: 1px solid rgba(224, 112, 32, 0.35);
		padding: 0.35rem 0.75rem;
		border-radius: 8px;
		text-decoration: none;
		white-space: nowrap;
		transition: all 0.15s;
		flex-shrink: 0;
	}

	.read-post-btn:hover {
		background: var(--orange);
		color: white;
		text-decoration: none;
		border-color: var(--orange);
	}

	.schedule-more {
		margin-top: 1.5rem;
		display: flex;
		justify-content: flex-end;
	}

	.all-sessions-link {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-family: var(--font-display);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		text-decoration: none;
		padding: 0.5rem 0.85rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
	}

	.all-sessions-link:hover {
		color: var(--orange);
		border-color: var(--orange);
		background: var(--orange-glow);
		text-decoration: none;
	}

	/* ── Posts ── */
	.posts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 1.25rem;
	}

	.post-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 1.5rem;
		text-decoration: none;
		color: var(--text);
		transition: all 0.2s ease;
	}

	.post-card:hover,
	.post-card:active {
		border-color: var(--orange);
		box-shadow: 0 4px 24px var(--orange-glow);
		text-decoration: none;
		transform: translateY(-2px);
	}

	.post-card h3 {
		font-family: var(--font-display);
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--text);
		line-height: 1.3;
		margin: 0;
	}

	.post-card-top {
		min-height: 1rem;
	}

	.post-tags {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.tag {
		font-family: var(--font-display);
		font-size: 0.65rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.15rem 0.55rem;
		color: var(--teal);
	}

	.post-subtitle {
		color: var(--text-muted);
		font-size: 0.85rem;
		font-weight: 300;
		margin: 0;
	}

	.post-desc {
		color: var(--text-muted);
		font-size: 0.83rem;
		line-height: 1.5;
		margin: 0;
		flex: 1;
	}

	.post-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.5rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--surface-3);
	}

	time {
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--text-muted);
	}

	.post-read {
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--orange);
	}

	/* ── About ── */
	.about-section {
		border-top: 1px solid var(--border);
	}

	.about-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 2rem;
		margin-bottom: 3rem;
	}

	.about-card {
		padding: 0.25rem 0;
	}

	.about-icon {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 0.9rem;
		color: var(--orange);
	}

	.about-card h3 {
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 700;
		margin-bottom: 0.5rem;
		color: var(--teal);
	}

	.about-card p {
		font-size: 0.88rem;
		color: var(--text-muted);
		line-height: 1.6;
		margin: 0;
	}

	.join-cta {
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}

	.join-cta p {
		color: var(--text-muted);
		font-size: 0.95rem;
		margin: 0;
	}

	/* ── Responsive ── */
	@media (max-width: 760px) {
		.hero-inner {
			padding-top: clamp(7rem, 22vw, 9rem);
			padding-bottom: 2rem;
			gap: 1.25rem;
		}

		.hero-bg-svg {
			top: 1rem;
			height: clamp(90px, 24vw, 130px);
		}

		.hero-sub {
			max-width: 100%;
		}

		.session-meta {
			padding: 0.75rem 1rem;
		}

		.recording-pw {
			display: none;
		}

		.paper-row {
			padding: 0.75rem 1rem;
			flex-direction: column;
			align-items: flex-start;
			gap: 0.5rem;
		}

		.topic-badge {
			margin-left: 0;
		}
	}

	/* Hide animated elements initially so there's no flash
	   before JS entrance animations run */
	.hero-text > :global(*) {
		opacity: 0;
	}

	.session-card {
		opacity: 0;
	}

	.post-card {
		opacity: 0;
	}

	/* If user prefers reduced motion, show everything immediately */
	@media (prefers-reduced-motion: reduce) {
		.hero-text > :global(*),
		.session-card,
		.post-card {
			opacity: 1 !important;
		}
	}
</style>
