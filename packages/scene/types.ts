export type Vec3 = [number, number, number];
export type Evidence = {
  origin: "observed" | "inferred" | "assumed" | "generated";
  confidence: number;
  reviewed: boolean;
  source_id?: string | null;
  note: string;
};
export type SceneNode = {
  id: string;
  label: string;
  category: string;
  shape: "box" | "cylinder" | "sphere" | "cone" | "plane";
  position: Vec3;
  rotation: Vec3;
  size: Vec3;
  color: string;
  visible: boolean;
  evidence: Evidence;
  asset_id?: string | null;
};
export type SceneEdge = {
  id: string;
  source: string;
  target: string;
  kind: "process" | "visitor" | "conveyor" | "adjacency";
  points: Vec3[];
  label: string;
};
export type SceneAsset = {
  id: string;
  kind: "glb" | "ply";
  uri: string;
  sha256: string;
  node_id?: string | null;
  provenance: Record<string, unknown>;
};
export type Scene = {
  schema_version: "1.0";
  id: string;
  case_id: string;
  name: string;
  description: string;
  revision: number;
  units: "meters";
  coordinates: "right-handed-y-up";
  nodes: SceneNode[];
  edges: SceneEdge[];
  assets: SceneAsset[];
  sources: { id: string; kind: string; filename: string; sha256?: string | null }[];
};
export type Case = {
  id: string;
  title: string;
  input_type: "prompt" | "photo" | "diagram" | "plan" | "generated";
  summary: string;
  source_filename: string | null;
  prompt: string;
  status: "ready" | "awaiting_input";
  source_url: string | null;
};
export type Job = {
  id: string;
  case_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  stages: string[];
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
};
