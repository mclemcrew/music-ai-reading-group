import adapter from '@sveltejs/adapter-static';
import { mdsvex } from 'mdsvex';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('@sveltejs/kit').Config} */
const config = {
	extensions: ['.svelte', '.svx'],
	preprocess: [
		mdsvex({
			extensions: ['.svx'],
			layout: join(__dirname, 'src/lib/components/layout/PostLayout.svelte'),
			remarkPlugins: [remarkMath],
			rehypePlugins: [rehypeKatex]
		})
	],
	kit: {
		adapter: adapter({
			pages: 'docs',
			assets: 'docs',
			fallback: undefined,
			precompress: false,
			strict: true
		}),
		paths: {
			base: process.env.NODE_ENV === 'production' ? '/music-ai-reading-group' : ''
		}
	}
};

export default config;
