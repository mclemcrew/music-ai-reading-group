import { error } from '@sveltejs/kit';

export async function load({ params }) {
	const modules = import.meta.glob('/src/posts/*.svx');
	const match = modules[`/src/posts/${params.slug}.svx`];

	if (!match) {
		throw error(404, `Post not found: ${params.slug}`);
	}

	const post = (await match()) as any;
	return {
		content: post.default,
		meta: post.metadata
	};
}
