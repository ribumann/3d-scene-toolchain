import type { Case, Job, Scene } from "../../../packages/scene/types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body) {
        const value = body.detail;
        detail = typeof value === "string" ? value : JSON.stringify(value);
      }
    } catch { /* Non-JSON errors retain the HTTP status. */ }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

const casePath = (id: string) => `/api/cases/${encodeURIComponent(id)}`;
export const readOnly = import.meta.env.MODE === "demo";
export type PilotStatus = {
  case_id: string;
  status: "not_run" | "failed" | "partial" | "succeeded" | "proposals";
  objects: number;
  failed_objects: number;
  reference_origin: "ai-generated" | "user-supplied-original";
  input_kind: "user-approved-public-webp-preview";
  not_original_bytes: true;
  layout: "inferred-not-metric";
  scene: string | null;
};

export function createApi(staticDemo = false) {
  const publishedScenes = new Set(["P01", "P02", "P03"]);
  const call = <T>(path: string, init?: RequestInit): Promise<T> => {
    if (staticDemo && path.startsWith("/api/")) {
      return Promise.reject(new ApiError(403, "The public demo is read-only. Run the local workbench for edits, uploads and pipeline jobs."));
    }
    return request<T>(path, init);
  };
  return {
    cases: async () => {
      const cases = await call<Case[]>(staticDemo ? "/demo/cases.json" : "/api/cases");
      if (staticDemo) for (const item of cases) {
        if (/^(I0[1-5]|G0[1-3])$/.test(item.id) && item.status === "ready") publishedScenes.add(item.id);
      }
      return cases;
    },
    pilots: () => staticDemo ? call<PilotStatus[]>("/demo/pilots.json") : Promise.resolve<PilotStatus[]>([]),
    scene: async (id: string) => {
      if (staticDemo && !publishedScenes.has(id)) {
        return Promise.reject(new ApiError(409, "Reference preview only: no reconstructed 3D scene is published for this case. P01-P03 are separate procedural examples, not reconstructions of the references."));
      }
      const scene = await call<Scene>(staticDemo ? `/demo/${id}.json` : `${casePath(id)}/scene`);
      if (staticDemo) {
        if (scene.case_id !== id) throw new ApiError(422, "Published scene identity does not match the selected case.");
        return { ...scene, assets: scene.assets.map(asset => {
          if (!/^\/api\/assets\/pilot\/(I0[1-5]|G0[1-3])\/[A-Za-z0-9_.-]+\.ply$/.test(asset.uri)) {
            throw new ApiError(422, "Published scene has an unapproved asset path.");
          }
          return { ...asset, uri: asset.uri.replace("/api/assets/", "/pilot-assets/") };
        }) };
      }
      return scene;
    },
    sourceMetadata: (id: string) => call<{ sha256: string; filename: string; width?: number; height?: number }>(`${casePath(id)}/source-metadata`),
    save: (id: string, scene: Scene) => call<Scene>(`${casePath(id)}/scene`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(scene),
    }),
    upload: (id: string, file: File) => {
      const body = new FormData(); body.append("file", file);
      return call<Case>(`${casePath(id)}/source`, { method: "POST", body });
    },
    jobs: () => staticDemo ? Promise.resolve<Job[]>([]) : call<Job[]>("/api/jobs"),
    start: (id: string, stage: string) => call<Job>(`${casePath(id)}/jobs`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stages: [stage] }),
    }),
    cancel: (id: string) => call<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  };
}

export const api = createApi(readOnly);
