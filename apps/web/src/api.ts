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

export function createApi(staticDemo = false) {
  const call = <T>(path: string, init?: RequestInit): Promise<T> => {
    if (staticDemo && path.startsWith("/api/")) {
      return Promise.reject(new ApiError(403, "The public demo is read-only. Run the local workbench for edits, uploads and pipeline jobs."));
    }
    return request<T>(path, init);
  };
  return {
    cases: () => call<Case[]>(staticDemo ? "/demo/cases.json" : "/api/cases"),
    scene: (id: string) => {
      if (staticDemo && !["P01", "P02", "P03"].includes(id)) {
        return Promise.reject(new ApiError(409, "Reference preview only: no reconstructed 3D scene is published for this case. P01-P03 are separate procedural examples, not reconstructions of the references."));
      }
      return call<Scene>(staticDemo ? `/demo/${id}.json` : `${casePath(id)}/scene`);
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
