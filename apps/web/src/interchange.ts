import type { Scene } from "../../../packages/scene/types";

type RecordValue = Record<string, unknown>;
function record(value: unknown, path: string): asserts value is RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${path} must be an object.`);
}
function text(value: unknown, path: string): asserts value is string {
  if (typeof value !== "string") throw new Error(`${path} must be a string.`);
}
function vector(value: unknown, path: string) {
  if (!Array.isArray(value) || value.length !== 3 || !value.every(Number.isFinite)) throw new Error(`${path} must contain three finite numbers.`);
}
function choice(value: unknown, choices: string[], path: string) {
  if (typeof value !== "string" || !choices.includes(value)) throw new Error(`${path} must be one of ${choices.join(", ")}.`);
}
function optionalText(value: unknown, path: string) {
  if (value !== undefined && value !== null) text(value, path);
}
function entries(value: unknown, path: string): RecordValue[] {
  if (!Array.isArray(value)) throw new Error(`${path} must be an array.`);
  const ids = new Set<string>();
  value.forEach((item, index) => {
    record(item, `${path}[${index}]`); text(item.id, `${path}[${index}].id`);
    if (!item.id || ids.has(item.id)) throw new Error(`${path} IDs must be nonempty and unique.`);
    ids.add(item.id);
  });
  return value;
}

/** JSON only: no code evaluation, remote modules, or executable asset URLs. */
export function parseSceneImport(json: string, caseId: string, revision: number, sourceHash?: string): Scene {
  const value: unknown = JSON.parse(json);
  record(value, "Scene");
  if (value.case_id !== caseId) throw new Error(`Scene case_id must match ${caseId}.`);
  if (value.schema_version !== "1.0" || value.units !== "meters" || value.coordinates !== "right-handed-y-up") {
    throw new Error("Scene must use schema 1.0, meters and right-handed-y-up coordinates.");
  }
  for (const key of ["id", "name", "description"]) text(value[key], key);
  if (!Number.isInteger(value.revision) || (value.revision as number) < 1) throw new Error("revision must be a positive integer.");
  const nodes = entries(value.nodes, "nodes");
  const edges = entries(value.edges, "edges");
  const assets = entries(value.assets, "assets");
  const sources = entries(value.sources, "sources");
  const nodeIds = new Set(nodes.map(item => item.id));
  const sourceIds = new Set(sources.map(item => item.id));
  const assetIds = new Set(assets.map(item => item.id));
  nodes.forEach((node, index) => {
    const path = `nodes[${index}]`;
    for (const key of ["label", "category", "color"]) text(node[key], `${path}.${key}`);
    if (!/^#[0-9a-f]{6}$/i.test(node.color as string)) throw new Error(`${path}.color must be a six-digit hex color.`);
    choice(node.shape, ["box", "cylinder", "sphere", "cone", "plane"], `${path}.shape`);
    for (const key of ["position", "rotation", "size"]) vector(node[key], `${path}.${key}`);
    if ((node.size as number[]).some(size => size <= 0)) throw new Error(`${path}.size must be positive.`);
    if (typeof node.visible !== "boolean") throw new Error(`${path}.visible must be boolean.`);
    optionalText(node.asset_id, `${path}.asset_id`);
    if (node.asset_id && !assetIds.has(node.asset_id)) throw new Error(`${path}.asset_id does not exist.`);
    record(node.evidence, `${path}.evidence`);
    choice(node.evidence.origin, ["observed", "inferred", "assumed", "generated"], `${path}.evidence.origin`);
    if (typeof node.evidence.confidence !== "number" || !Number.isFinite(node.evidence.confidence) || node.evidence.confidence < 0 || node.evidence.confidence > 1) throw new Error(`${path} confidence must be between 0 and 1.`);
    if (typeof node.evidence.reviewed !== "boolean") throw new Error(`${path}.evidence.reviewed must be boolean.`);
    text(node.evidence.note, `${path}.evidence.note`);
    optionalText(node.evidence.source_id, `${path}.evidence.source_id`);
    if (node.evidence.source_id && !sourceIds.has(node.evidence.source_id)) throw new Error(`${path} source ID does not exist.`);
  });
  edges.forEach((edge, index) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) throw new Error(`edges[${index}] endpoints must reference existing node IDs.`);
    choice(edge.kind, ["process", "visitor", "conveyor", "adjacency"], `edges[${index}].kind`);
    text(edge.label, `edges[${index}].label`);
    if (!Array.isArray(edge.points)) throw new Error(`edges[${index}].points must be an array.`);
    edge.points.forEach((point, i) => vector(point, `edges[${index}].points[${i}]`));
  });
  assets.forEach((asset, index) => {
    choice(asset.kind, ["glb", "ply"], `assets[${index}].kind`);
    text(asset.uri, `assets[${index}].uri`);
    if (!/^\/api\/assets\/[A-Za-z0-9_./% -]+$/.test(asset.uri) || asset.uri.includes("..") || /%2e|%2f|%5c/i.test(asset.uri)) throw new Error("Imported asset URIs must be local /api/assets/ paths without traversal.");
    text(asset.sha256, `assets[${index}].sha256`);
    record(asset.provenance, `assets[${index}].provenance`);
    optionalText(asset.node_id, `assets[${index}].node_id`);
    if (asset.node_id && !nodeIds.has(asset.node_id)) throw new Error(`assets[${index}].node_id does not exist.`);
  });
  sources.forEach((source, index) => {
    text(source.kind, `sources[${index}].kind`); text(source.filename, `sources[${index}].filename`);
    optionalText(source.sha256, `sources[${index}].sha256`);
  });
  if (sourceHash && !sources.some(source => source.sha256 === sourceHash)) throw new Error("Scene sources must include the exact SHA-256 of the uploaded image.");
  return { ...value, revision } as Scene;
}
