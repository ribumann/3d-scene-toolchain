import type { Scene, SceneAsset, SceneEdge, SceneNode, Vec3 } from "../../../packages/scene/types";

export function caseFromQuery(search: string, knownIds: readonly string[]): { caseId: string; error?: string } {
  const requested = new URLSearchParams(search).getAll("case");
  const fallback = knownIds[0] ?? "";
  if (!requested.length) return { caseId: fallback };
  if (requested.length === 1 && knownIds.includes(requested[0])) return { caseId: requested[0] };
  return {
    caseId: fallback,
    error: `Invalid or unavailable case link. ${fallback ? `Showing ${fallback} instead.` : "No cases are available."}`,
  };
}

export function updateNode(scene: Scene, id: string, update: Partial<SceneNode>): Scene {
  return { ...scene, nodes: scene.nodes.map(node => node.id === id ? { ...node, ...update } : node) };
}

export function visibleNodes(scene: Scene, isolated: string | null): SceneNode[] {
  return scene.nodes.filter(node => node.visible && (!isolated || node.id === isolated));
}

export function routePoints(edge: SceneEdge, scene: Scene): Vec3[] {
  if (edge.points.length >= 2) return edge.points;
  const source = scene.nodes.find(node => node.id === edge.source);
  const target = scene.nodes.find(node => node.id === edge.target);
  return source && target ? [source.position, target.position] : [];
}

export function pointOnRoute(points: Vec3[], fraction: number): Vec3 {
  if (!points.length) return [0, 0, 0];
  if (points.length === 1) return points[0];
  const lengths = points.slice(1).map((point, i) => Math.hypot(...point.map((v, axis) => v - points[i][axis])));
  const total = lengths.reduce((a, b) => a + b, 0);
  if (!total) return points[0];
  let distance = ((fraction % 1) + 1) % 1 * total;
  for (let i = 0; i < lengths.length; i++) {
    if (distance <= lengths[i] && lengths[i] > 0) {
      const t = distance / lengths[i];
      return points[i].map((v, axis) => v + (points[i + 1][axis] - v) * t) as Vec3;
    }

    distance -= lengths[i];
  }

  return points[points.length - 1];
}

export function splatFit(asset: SceneAsset, node: SceneNode): { center: Vec3; scale: Vec3 } | null {
  const bounds = asset.provenance.bounds;
  if (!bounds || typeof bounds !== "object" || !("min" in bounds) || !("max" in bounds)) return null;
  const { min, max } = bounds as { min: unknown; max: unknown };
  if (!Array.isArray(min) || !Array.isArray(max) || min.length !== 3 || max.length !== 3 ||
      !min.every(Number.isFinite) || !max.every(Number.isFinite) ||
      min.some((value, i) => max[i] <= value)) return null;
  return {
    center: min.map((value, i) => (value + max[i]) / 2) as Vec3,
    scale: min.map((value, i) => node.size[i] / (max[i] - value)) as Vec3,
  };
}
