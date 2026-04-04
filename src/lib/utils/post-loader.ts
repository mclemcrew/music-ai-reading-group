export interface PostMeta {
	title: string;
	subtitle?: string;
	date: string;
	authors?: string[];
	tags?: string[];
	description?: string;
	published?: boolean;
	slug: string;
}

export async function getAllPosts(): Promise<PostMeta[]> {
	const modules = import.meta.glob('/src/posts/*.svx', { eager: true });

	const posts: PostMeta[] = [];

	for (const [path, module] of Object.entries(modules)) {
		const slug = path.split('/').pop()!.replace('.svx', '');
		const meta = (module as any).metadata;
		if (meta?.published !== false) {
			posts.push({ ...meta, slug });
		}
	}

	return posts.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}
