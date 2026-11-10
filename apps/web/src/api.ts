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
export const api = {
  cases: () => request<Case[]>("/api/cases"),
  scene: (id: string) => request<Scene>(`${casePath(id)}/scene`),
  sourceMetadata: (id: string) => request<{ sha256: string; filename: string; width?: number; height?: number }>(`${casePath(id)}/source-metadata`),
  save: (id: string, scene: Scene) => request<Scene>(`${casePath(id)}/scene`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(scene),
  }),
  upload: (id: string, file: File) => {
    const body = new FormData(); body.append("file", file);
    return request<Case>(`${casePath(id)}/source`, { method: "POST", body });
  },
  jobs: () => request<Job[]>("/api/jobs"),
  start: (id: string, stage: string) => request<Job>(`${casePath(id)}/jobs`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stages: [stage] }),
  }),
  cancel: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
};
