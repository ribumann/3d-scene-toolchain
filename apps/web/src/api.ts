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
  status: "not_run" | "processing" | "failed" | "partial" | "succeeded" | "proposals";
  objects: number;
  failed_objects: number;
  reference_origin: "ai-generated" | "user-supplied-original";
  input_kind: "user-approved-public-webp-preview";
  not_original_bytes: true;
  layout: "inferred-not-metric";
  scene: string | null;
};
export type TrialStatus = {
  trial_id: "T01" | "T02" | "T03" | "R01" | "R02" | "R03";
  variant: "baseline" | "optimized";
  status: "not_run" | "processing" | "failed" | "partial" | "succeeded" | "interrupted";
  scene: string | null;
  report: {
    expected_objects: number; detected_objects: number; usable_crops: number;
    objects_succeeded?: number; objects_failed?: number; published_instances?: number;
    cache_hits: number; cache_misses: number; resumed: number; independent_generations: number;
    seconds_this_run: number; supervision: string; failure_reason: string | null;
    rejected: { node_id: string; reason: string; duplicate_of?: string }[];
    objects: { node_id: string; status: string; failure_reason?: string; timing: { seconds?: number } }[];
    settings: { count: number; steps: number; seed: number; model_pins: Record<string, string>; sdk_revision: string };
  } | null;
  definition: {
    title: string;
    source: { kind: "generated-photographic-scene"; generator: string; prompt: string; sha256: string } | {
      kind: "licensed-real-photograph"; sha256: string; creator: string; source_page: string;
      original_sha256: string; license: "CC-BY-SA-4.0"; license_url: string;
      changes: string; derivative_license: "CC-BY-SA-4.0"; derivative_changes: string; limitations: string;
    };
    expected_inventory: { identity: string; category: string; count: number }[];
    layout_kind: string;
  };
};

export function createApi(staticDemo = false) {
  const publishedScenes = new Set(["P01", "P02", "P03"]);
  let quality: Promise<{ version: number; assets: Record<string, unknown> }> | undefined;
  let plantFiles: Promise<Record<string, string>> | undefined;
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
        if (/^(D01|I0[1-5]|G0[1-3]|[TR]0[1-3]-(baseline|optimized)|(?:P0[1-3]|I01|I04|I05)-illustrated)$/.test(item.id) && item.status === "ready") publishedScenes.add(item.id);
      }
      return cases;
    },
    pilots: () => staticDemo ? call<PilotStatus[]>("/demo/pilots.json") : Promise.resolve<PilotStatus[]>([]),
    trials: () => staticDemo ? call<TrialStatus[]>("/demo/trials.json") : Promise.resolve<TrialStatus[]>([]),
    scene: async (id: string) => {
      if (staticDemo && !publishedScenes.has(id)) {
        return Promise.reject(new ApiError(409, "Reference preview only: no reconstructed 3D scene is published for this case. P01-P03 are separate procedural examples, not reconstructions of the references."));
      }
      const scene = await call<Scene>(staticDemo ? `/demo/${id}.json` : `${casePath(id)}/scene`);
      if (staticDemo) {
        if (scene.case_id !== id) throw new ApiError(422, "Published scene identity does not match the selected case.");
        if (id === "D01") {
          const files = await (plantFiles ??= call<Record<string, string>>("/plant/files.json"));
          return { ...scene, assets: scene.assets.map(asset => {
            const match = /^\/api\/assets\/plant\/(modules\/(?:crusher|scrubber|screen|dms|medium|sorter|hopper|thickener|water|lab|control|tailings)\.glb)$/.exec(asset.uri);
            if (!match || asset.kind !== "glb" || asset.provenance.method !== "authored-parametric-module" ||
                !/^[a-f0-9]{64}$/.test(asset.sha256) || files[match[1]] !== asset.sha256) {
              throw new ApiError(422, "Plant model path or authored geometry hash is invalid.");
            }
            return { ...asset, uri: "/plant/" + match[1] };
          }) };
        }
        const assessments = scene.assets.length ? await (quality ??= call<{ version: number; assets: Record<string, unknown> }>("/demo/quality.json")) : null;
        if (assessments && (assessments.version !== 1 || !assessments.assets || typeof assessments.assets !== "object")) {
          throw new ApiError(422, "Published geometry quality report is invalid.");
        }
        return { ...scene, assets: scene.assets.map(asset => {
          const trial = /^[TR]0[1-3]-(baseline|optimized)$/.test(id);
          const illustrated = /^(P0[1-3]|I01|I04|I05)-illustrated$/.test(id);
          const match = illustrated ? /^\/api\/assets\/illustrations\/[A-Za-z0-9_.-]+\.ply$/.test(asset.uri) : trial
            ? new RegExp(`^/api/assets/trials/${id.slice(0, 3)}/${id.slice(4)}/[A-Za-z0-9_.-]+\\.ply$`).test(asset.uri)
            : new RegExp(`^/api/assets/pilot/${id}/[A-Za-z0-9_.-]+\\.ply$`).test(asset.uri);
          if (!match) {
            throw new ApiError(422, "Published scene has an unapproved asset path.");
          }
          const assessment = assessments?.assets[asset.sha256];
          if (!assessment || typeof assessment !== "object" || !("sha256" in assessment) || assessment.sha256 !== asset.sha256) {
            throw new ApiError(422, "Published appearance has no matching hash-bound geometry assessment.");
          }
          return {
            ...asset, provenance: { ...asset.provenance, geometry_quality: assessment },
            uri: illustrated ? asset.uri.replace("/api/assets/illustrations/", "/illustration-assets/") : trial ? asset.uri.replace("/api/assets/trials/", "/trial-assets/") : asset.uri.replace("/api/assets/", "/pilot-assets/"),
          };
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
