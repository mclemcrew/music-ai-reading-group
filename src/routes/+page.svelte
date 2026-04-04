<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { animate, stagger } from 'animejs';

	let { data } = $props();

	// Schedule data from the Google Sheet
	const sessions = [
		{
			week: 'Week 1',
			date: '2026-03-19',
			topic: 'Signal Processing & ML',
			topicColor: 'orange',
			recording: null as { url: string; passcode: string } | null,
			papers: [
				{
					title: 'DDSP: Differentiable Digital Signal Processing',
					authors: 'Engel, Hantrakul, Gu, Roberts',
					year: 2020,
					link: 'https://arxiv.org/abs/2001.04643',
					hasPost: true,
					postSlug: 'ddsp-from-scratch',
					excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/7mA11Gu7KXU'
				},
				{
					title: 'A Review of Differentiable Digital Signal Processing for Music & Speech Synthesis',
					authors: 'Hayes, Shier, Saitis, Fazekas',
					year: 2024,
					link: 'https://arxiv.org/abs/2308.15422',
					hasPost: false,
					excalidraw: null as string | null
				}
			]
		},
		{
			week: 'Week 2',
			date: '2026-03-26',
			topic: 'Music Transcription',
			topicColor: 'teal',
			recording: null as { url: string; passcode: string } | null,
			papers: [
				{
					title: 'A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation',
					authors: 'Bittner, Bosch, Rubinstein, Meseguer-Brocal, Ewert',
					year: 2022,
					link: 'https://arxiv.org/pdf/2203.09893',
					hasPost: true,
					postSlug: 'music-transcription',
					excalidraw: null as string | null
				},
				{
					title: 'MT3: Multi-Task Multitrack Music Transcription',
					authors: 'Gardner, Simon, Manilow, Hawthorne, Engel',
					year: 2021,
					link: 'https://arxiv.org/pdf/2111.03017',
					hasPost: true,
					postSlug: 'music-transcription',
					excalidraw: null as string | null
				},
				{
					title: 'Onsets and Frames: Dual-Objective Piano Transcription',
					authors: 'Hawthorne, Elsen, Song, Roberts, Simon, Raffel, Engel, Oore, Eck',
					year: 2017,
					link: 'https://arxiv.org/pdf/1710.11153',
					hasPost: true,
					postSlug: 'music-transcription',
					excalidraw: null as string | null
				}
			]
		},
		{
			week: 'Week 3',
			date: '2026-04-02',
			topic: 'Music Generation',
			topicColor: 'violet',
			recording: {
				url: 'https://uaudio.zoom.us/rec/share/tQ1lJVI7ebYkkMVbSDeiVjopNV7dkr160gOCwLkSzdIJPyIBwmHP5OZZ-kCdnC0A.UEFQBxkQyMmCPH4-',
				passcode: 'Di!3?KhN'
			},
			papers: [
				{
					title: 'VampNet: Music Generation via Masked Acoustic Token Modeling',
					authors: 'Garcia, Tsuda, Shier, Bryan, Fierro, Agostinelli',
					year: 2023,
					link: 'https://arxiv.org/abs/2307.04686',
					hasPost: false,
					excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/6vP3sw0sD6C'
				},
				{
					title: 'Anticipatory Music Transformer',
					authors: 'Thickstun, Hall, Donahue, Liang',
					year: 2023,
					link: 'https://arxiv.org/abs/2306.08620',
					hasPost: false,
					excalidraw: 'https://link.excalidraw.com/l/8sDmlvduhSt/1IR71UHPGmr'
				}
			]
		}
	];

	const timezones = [
		{ city: 'California', time: '7:00 AM', tz: 'PST' },
		{ city: 'Chicago', time: '9:00 AM', tz: 'CDT' },
		{ city: 'New York', time: '10:00 AM', tz: 'EDT' },
		{ city: 'Europe', time: '4:00 PM', tz: 'CEST' }
	];

	let bars: HTMLElement[] = [];
	let heroRef: HTMLElement;
	let scheduleRef: HTMLElement;
	let postsRef = $state<HTMLElement | undefined>(undefined);

	const BAR_COUNT = 36;

	onMount(() => {
		// Entrance: bars grow up from nothing, left to right
		animate(bars, {
			scaleY: [0, 1],
			opacity: [0, 0.65],
			duration: 550,
			delay: stagger(18, { start: 150 }),
			ease: 'outExpo'
		});

		// Continuous traveling sine wave — 2 wavelengths scrolling left→right
		let raf: number;
		function tick(ts: number) {
			const t = ts * 0.00125; // ~1 full cycle per 5s
			bars.forEach((bar, i) => {
				const phase = (i / (BAR_COUNT - 1)) * Math.PI * 4; // 2 wavelengths
				const s = 0.08 + 0.9 * (0.5 + 0.5 * Math.sin(t - phase));
				bar.style.transform = `scaleY(${s.toFixed(3)})`;
			});
			raf = requestAnimationFrame(tick);
		}
		raf = requestAnimationFrame(tick);

		// Hero text entrance
		animate(heroRef.querySelectorAll('.hero-text > *'), {
			translateY: [30, 0],
			opacity: [0, 1],
			delay: stagger(80, { start: 200 }),
			duration: 700,
			ease: 'outExpo'
		});

		const scheduleObs = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (!e.isIntersecting) return;
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

		return () => cancelAnimationFrame(raf);
	});
</script>

<svelte:head>
	<title>Music Co-Creative AI Reading Group</title>
	<meta name="description" content="Weekly reading group exploring music and AI research: interactive papers, audio experiments, and visual explainers." />
</svelte:head>

<!-- ═══ HERO ═══ -->
<section class="hero" bind:this={heroRef}>
	<div class="hero-bg-svg" aria-hidden="true">
		<!-- Decorative background arcs -->
		<svg viewBox="0 0 1200 400" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
			<defs>
				<radialGradient id="grad1" cx="30%" cy="50%" r="60%">
					<stop offset="0%" stop-color="var(--orange)" stop-opacity="0.08" />
					<stop offset="100%" stop-color="var(--orange)" stop-opacity="0" />
				</radialGradient>
				<radialGradient id="grad2" cx="70%" cy="50%" r="60%">
					<stop offset="0%" stop-color="var(--teal)" stop-opacity="0.07" />
					<stop offset="100%" stop-color="var(--teal)" stop-opacity="0" />
				</radialGradient>
			</defs>
			<ellipse cx="300" cy="200" rx="420" ry="300" fill="url(#grad1)" />
			<ellipse cx="900" cy="200" rx="420" ry="300" fill="url(#grad2)" />
			<!-- Staff lines -->
			{#each [130, 155, 180, 205, 230] as y}
				<line x1="0" y1={y} x2="1200" y2={y} stroke="var(--border)" stroke-width="1" opacity="0.6" />
			{/each}
			<!-- Treble clef -->
			<text x="80" y="248" font-family="serif" font-size="155" text-anchor="middle" fill="var(--orange)" opacity="0.13">𝄞</text>
			<!-- Quarter notes suggestion -->
			{#each [200, 350, 500, 680, 820, 970] as x}
				<circle cx={x} cy={130 + (x % 50 === 0 ? 25 : x % 75 === 0 ? 0 : 50)} r="7" fill="var(--teal)" opacity="0.08" />
				<line x1={x + 7} y1={130 + (x % 50 === 0 ? 25 : x % 75 === 0 ? 0 : 50)} x2={x + 7} y2={130 + (x % 50 === 0 ? 25 : x % 75 === 0 ? 0 : 50) - 40} stroke="var(--teal)" stroke-width="1.5" opacity="0.10" />
			{/each}
		</svg>
	</div>

	<div class="hero-inner container">
		<div class="hero-text">
			<div class="hero-badge">Weekly Reading Group</div>
			<h1>
				Music<span class="accent-dot" style="color:var(--orange)">.</span>
				Co-Creative<span class="accent-dot" style="color:var(--teal)">.</span>
				AI
			</h1>
			<p class="hero-sub">We read ML papers about music, try to actually understand them, and document what we learn. Interactive demos, code, and a lot of questions along the way.</p>
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

		<!-- Animated waveform -->
		<div class="hero-waveform" aria-hidden="true">
			{#each Array(BAR_COUNT) as _, i}
				<div class="waveform-bar" bind:this={bars[i]}></div>
			{/each}
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
		{#each sessions as session}
			{@const sessionPost = session.papers.find((p) => p.hasPost)?.postSlug}
			<div class="session-card">
				<div class="session-meta">
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
</section>

<!-- ═══ PUBLISHED NOTES ═══ -->
{#if data.posts.length > 0}
<section class="posts-section container" bind:this={postsRef}>
	<div class="section-header">
		<h2><span class="h2-accent" style="background:var(--teal)"></span>Interactive Notes</h2>
		<p class="section-sub">Notes from past sessions</p>
	</div>

	<div class="posts-grid">
		{#each data.posts as post}
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

	.hero-bg-svg {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.hero-bg-svg svg {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.hero-inner {
		display: grid;
		grid-template-columns: 1fr 280px;
		gap: 3rem;
		align-items: center;
		padding-top: 4rem;
		padding-bottom: 3rem;
		position: relative;
	}

	.hero-text {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.hero-badge {
		display: inline-flex;
		align-items: center;
		font-family: var(--font-mono);
		font-size: 0.72rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--teal);
		background: var(--teal-glow);
		border: 1px solid rgba(26, 158, 143, 0.25);
		border-radius: 20px;
		padding: 0.3rem 0.9rem;
		width: fit-content;
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
		max-width: 480px;
		margin-bottom: 0.5rem;
	}

	.hero-actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		align-items: center;
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

	/* Waveform */
	.hero-waveform {
		display: flex;
		align-items: flex-end;
		gap: 3px;
		height: 130px;
	}

	.waveform-bar {
		flex: 1;
		height: 100%;
		background: var(--orange);
		border-radius: 2px 2px 0 0;
		opacity: 0.55;
		transform-origin: bottom;
		transform: scaleY(0.08);
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
		gap: 0.6rem;
		flex-wrap: wrap;
		font-family: var(--font-mono);
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
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--text-muted);
	}

	.topic-badge {
		font-family: var(--font-mono);
		font-size: 0.68rem;
		text-transform: uppercase;
		letter-spacing: 0.07em;
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
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--violet);
		background: var(--violet-glow);
		border: 1px solid rgba(124, 77, 255, 0.2);
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
		font-family: var(--font-mono);
		font-size: 0.65rem;
		color: var(--text-muted);
		white-space: nowrap;
	}

	.slides-link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-family: var(--font-mono);
		font-size: 0.68rem;
		color: var(--teal);
		text-decoration: none;
		border: 1px solid rgba(26, 158, 143, 0.25);
		background: var(--teal-glow);
		padding: 0.1rem 0.5rem;
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
		border: 1px solid rgba(224, 112, 32, 0.2);
	}

	.topic-teal {
		background: var(--teal-glow);
		color: var(--teal);
		border: 1px solid rgba(26, 158, 143, 0.2);
	}

	.topic-violet {
		background: var(--violet-glow);
		color: var(--violet);
		border: 1px solid rgba(124, 77, 255, 0.2);
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
		font-family: var(--font-mono);
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
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--orange);
		background: var(--orange-glow);
		border: 1px solid rgba(224, 112, 32, 0.2);
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

	.post-card:hover {
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
		font-family: var(--font-mono);
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
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--text-muted);
	}

	.post-read {
		font-family: var(--font-mono);
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
			grid-template-columns: 1fr;
			padding-top: 2.5rem;
			padding-bottom: 2rem;
			gap: 2rem;
		}

		.hero-waveform {
			height: 80px;
			gap: 3px;
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
</style>
