/**
 * Pure layout function for the paper constellation.
 *
 * Positions are derived from cluster membership so the viz rebalances automatically
 * when papers or clusters are added/removed. Deterministic — a stable hash on
 * `paper.id` introduces small jitter so the result feels organic without being random.
 */

import type { Cluster, Paper } from './papers';

export interface LaidOut {
	id: string;
	x: number;
	y: number;
}

export interface ClusterCenter {
	id: string;
	x: number;
	y: number;
}

export interface Edge {
	id: string;
	fromX: number;
	fromY: number;
	toX: number;
	toY: number;
	/** 'cluster' edges are papers to their cluster center; 'related' edges are explicit cross-links. */
	kind: 'cluster' | 'related';
	/** Cluster id of the source; used to dim edges when a different cluster is focused. */
	clusterId: string;
}

export interface Layout {
	papers: Map<string, LaidOut>;
	clusterCenters: Map<string, ClusterCenter>;
	edges: Edge[];
}

/** Deterministic 0..1 pseudo-random derived from a string (djb2). */
function hash01(s: string): number {
	let h = 5381;
	for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
	return ((h >>> 0) % 10000) / 10000;
}

/**
 * Computes positions for every paper and every cluster center, plus all derived edges.
 *
 * @param papers   Paper data
 * @param clusters Cluster data
 * @param viewBox  Logical coordinate space. 1000x1000 is the recommended default.
 */
export function computeLayout(
	papers: Paper[],
	clusters: Cluster[],
	viewBox: { w: number; h: number }
): Layout {
	const cx = viewBox.w / 2;
	const cy = viewBox.h / 2;

	const sortedClusters = [...clusters].sort((a, b) => a.order - b.order);
	const N = sortedClusters.length;

	// Cluster centers distributed around a circle centered on the viewBox.
	// Start angle of -PI/2 puts the first cluster at the top.
	const clusterRingRadius = Math.min(viewBox.w, viewBox.h) * (N === 1 ? 0 : 0.26);
	const clusterCenters = new Map<string, ClusterCenter>();
	sortedClusters.forEach((c, i) => {
		const angle = N === 1 ? 0 : (i / N) * Math.PI * 2 - Math.PI / 2;
		clusterCenters.set(c.id, {
			id: c.id,
			x: cx + clusterRingRadius * Math.cos(angle),
			y: cy + clusterRingRadius * Math.sin(angle)
		});
	});

	// Papers arranged in a ring around their cluster center.
	const paperPositions = new Map<string, LaidOut>();
	// Paper-ring radius scales gently with cluster population so densely packed
	// clusters don't overlap each other.
	const basePaperRadius = Math.min(viewBox.w, viewBox.h) * 0.12;

	for (const cluster of sortedClusters) {
		const center = clusterCenters.get(cluster.id)!;
		const members = papers.filter((p) => p.clusterId === cluster.id);
		const M = members.length;
		if (M === 0) continue;

		// Single paper sits at the center of its cluster; multiple papers ring it.
		const ringRadius = M === 1 ? 0 : basePaperRadius * (1 + (M - 2) * 0.12);

		members.forEach((p, i) => {
			if (M === 1) {
				paperPositions.set(p.id, { id: p.id, x: center.x, y: center.y });
				return;
			}
			const baseAngle = (i / M) * Math.PI * 2 - Math.PI / 2;
			// Deterministic jitter keeps layout from feeling mechanical.
			const jitterAngle = (hash01(p.id) - 0.5) * 0.4;
			const jitterRadial = (hash01(p.id + 'r') - 0.5) * ringRadius * 0.18;
			const angle = baseAngle + jitterAngle;
			const r = ringRadius + jitterRadial;
			paperPositions.set(p.id, {
				id: p.id,
				x: center.x + r * Math.cos(angle),
				y: center.y + r * Math.sin(angle)
			});
		});
	}

	// Derive edges.
	const edges: Edge[] = [];

	// Intra-cluster edges: every paper connects to its cluster center.
	for (const p of papers) {
		const pos = paperPositions.get(p.id);
		const center = clusterCenters.get(p.clusterId);
		if (!pos || !center) continue;
		// Skip if paper sits exactly on the center (single-member cluster).
		if (pos.x === center.x && pos.y === center.y) continue;
		edges.push({
			id: `cluster:${p.id}`,
			fromX: center.x,
			fromY: center.y,
			toX: pos.x,
			toY: pos.y,
			kind: 'cluster',
			clusterId: p.clusterId
		});
	}

	// Inter-cluster edges: explicit relatedTo links.
	// Deduplicated so A→B and B→A collapse into a single line.
	const seen = new Set<string>();
	for (const p of papers) {
		if (!p.relatedTo) continue;
		const from = paperPositions.get(p.id);
		if (!from) continue;
		for (const otherId of p.relatedTo) {
			const pair = [p.id, otherId].sort().join('|');
			if (seen.has(pair)) continue;
			seen.add(pair);
			const to = paperPositions.get(otherId);
			if (!to) continue;
			edges.push({
				id: `related:${pair}`,
				fromX: from.x,
				fromY: from.y,
				toX: to.x,
				toY: to.y,
				kind: 'related',
				clusterId: p.clusterId
			});
		}
	}

	return { papers: paperPositions, clusterCenters, edges };
}
