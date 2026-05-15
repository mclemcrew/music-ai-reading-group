import { getAllPosts } from '$lib/utils/post-loader';

export async function load() {
	const posts = await getAllPosts();
	return { posts };
}
