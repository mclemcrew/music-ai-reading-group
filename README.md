# Music Co-Creative AI Reading Group

We read ML papers about music, try to actually understand them, and document what we learn. The site has interactive demos, from-scratch implementations, and write-ups for each session.

**Live site:** [mclemcrew.github.io/music-ai-reading-group](https://mclemcrew.github.io/music-ai-reading-group)

## Repo structure

```
src/
  posts/           .svx files (markdown + Svelte components) for each session
  lib/components/  reusable viz components, audio players, UI pieces
  routes/          SvelteKit pages (homepage, post template)

experiments/       from-scratch implementations that go with the posts
  ddsp/            DDSP additive synth (Week 1)
  transcription/   NMP/Basic Pitch note detection (Week 2)
  aria-duet/       Anticipatory Music Transformer live demo (Week 3)

static/audio/      generated WAV files + loss plots from the experiments
scripts/           helper scripts (new-post generator, etc.)
docs/              built site (deployed to GitHub Pages)
```

## Running the site locally

```bash
npm install
npm run dev        # starts at localhost:5173
```

To build for production:

```bash
npm run build      # outputs to docs/
npm run preview    # preview the build
```

## Running the experiments

Each experiment directory has its own `pyproject.toml` and uses [uv](https://astral.sh/uv) for dependency management. They're self-contained, so you can run them independently:

```bash
cd experiments/ddsp
uv sync
uv run ddsp_from_sratch.py

cd experiments/transcription
uv sync
uv run nmp_from_scratch.py
```

Output (WAV snapshots, loss curves, piano roll PNGs) goes to `static/audio/` so the dev server picks it up automatically.

## Writing a new post

```bash
npm run new-post "My Topic Title"
```

This creates a `.svx` file in `src/posts/` with frontmatter and a list of available components to import. Posts use [mdsvex](https://mdsvex.pngwn.io/) (markdown + Svelte), so you can mix prose with interactive components.

Set `published: true` in the frontmatter when it's ready to show up on the site.

## Adding a new experiment

1. Create a directory under `experiments/` (lowercase, kebab-case)
2. Add a `pyproject.toml` with your Python dependencies
3. Run `uv sync` to create the virtual environment
4. Write the script, have it output audio/images to `../../static/audio/`
5. Reference the outputs from your post using `AudioGrid` or `img` tags

## Contributing

Contributions are welcome, whether that's fixing a typo, adding a visualization, or writing up a new paper. The main things:

- Posts go in `src/posts/` as `.svx` files
- Viz components go in `src/lib/components/viz/` (canvas-based, using the shared `setupCanvas` utility)
- Experiments go in `experiments/` with their own `pyproject.toml`
- The site deploys from the `docs/` directory via GitHub Pages

If you're adding a new session write-up, the `new-post` script will scaffold everything for you.

## License

MIT
