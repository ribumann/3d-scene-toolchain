import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Group, Scene as ThreeScene } from "three";
import type { SceneAsset, SceneNode } from "../../../packages/scene/types";
import { Spark } from "./Viewport";

type MockMesh = Group & { splats?: object; url?: string; dispose: ReturnType<typeof vi.fn> };
const state = vi.hoisted(() => ({
  cleanup: undefined as (() => void) | undefined,
  ready: Promise.resolve(),
  meshes: [] as MockMesh[],
  disposedSources: [] as (object | undefined)[],
  scene: undefined as ThreeScene | undefined,
}));
vi.mock("react", async importOriginal => ({
  ...await importOriginal<typeof import("react")>(),
  useEffect: (effect: () => void | (() => void)) => { state.cleanup = effect() || undefined; },
}));
vi.mock("@react-three/fiber", () => ({
  Canvas: vi.fn(), useFrame: vi.fn(), useThree: () => ({ gl: {}, scene: state.scene }),
}));
vi.mock("@react-three/drei", () => ({ Grid: vi.fn(), Line: vi.fn(), OrbitControls: vi.fn() }));
vi.mock("@sparkjsdev/spark", async () => {
  const { Group } = await import("three");
  return {
    SparkRenderer: class extends Group { dispose = vi.fn(); },
    SplatMesh: class extends Group {
      url?: string;
      splats?: object;
      initialized: Promise<this>;
      dispose = vi.fn(() => { state.disposedSources.push(this.splats); });
      constructor(options: { url?: string; splats?: object }) {
        super();
        this.url = options.url;
        this.splats = options.splats ?? {};
        this.initialized = (options.url ? state.ready : Promise.resolve()).then(() => this);
        state.meshes.push(this);
      }
    },
  };
});

const asset: SceneAsset = {
  id: "tree", kind: "ply", uri: "/tree.ply", sha256: "",
  provenance: { bounds: { min: [-1, -1, -1], max: [1, 1, 1] } },
};
const first: SceneNode = {
  id: "first", asset_id: asset.id, label: "Tree", category: "tree", shape: "box",
  position: [2, 1, 3], rotation: [0, 0, 0], size: [2, 2, 2], color: "#fff", visible: true,
  evidence: { origin: "generated", confidence: 0.5, reviewed: false, note: "Authored instance." },
};
const second: SceneNode = { ...first, id: "second", position: [8, 1, 3] };
let resolve: () => void;
const cleanup = () => { const dispose = state.cleanup; state.cleanup = undefined; dispose?.(); };

beforeEach(() => {
  state.scene = new ThreeScene();
  state.meshes = [];
  state.disposedSources = [];
  state.ready = new Promise<void>(done => { resolve = done; });
});
afterEach(cleanup);

describe("shared splat placements", () => {
  it("loads once, places every instance, and disposes the shared source only through its owner", async () => {
    const onLoaded = vi.fn(), onError = vi.fn();
    Spark({ assets: [asset], nodes: [first, second], onLoaded, onError });
    expect(state.meshes).toHaveLength(1);
    resolve();
    await vi.waitFor(() => expect(onLoaded).toHaveBeenLastCalledWith(asset.id, true));
    const [owner, clone] = state.meshes;
    expect(state.meshes.filter(mesh => mesh.url)).toHaveLength(1);
    expect(clone.splats).toBe(owner.splats);
    expect(owner.position.toArray()).toEqual(first.position);
    expect(clone.position.toArray()).toEqual(second.position);
    expect(state.scene?.children.map(child => child.name)).toEqual(["SparkRenderer", "tree/first", "tree/second"]);
    const shared = owner.splats;
    cleanup();
    await vi.waitFor(() => expect(owner.dispose).toHaveBeenCalledOnce());
    expect(clone.dispose).toHaveBeenCalledOnce();
    expect(state.disposedSources).toEqual([undefined, shared]);
    expect(state.scene?.children).toHaveLength(0);
    expect(onError).not.toHaveBeenCalled();
  });

  it("renders a later isolated placement without the first instance", async () => {
    const onLoaded = vi.fn();
    Spark({ assets: [asset], nodes: [second], onLoaded, onError: vi.fn() });
    resolve();
    await vi.waitFor(() => expect(onLoaded).toHaveBeenLastCalledWith(asset.id, true));
    expect(state.meshes).toHaveLength(1);
    expect(state.meshes[0].name).toBe("tree/second");
    expect(state.meshes[0].position.toArray()).toEqual(second.position);
  });

  it("does not add late instances or report success after unmount", async () => {
    const onLoaded = vi.fn(), onError = vi.fn();
    Spark({ assets: [asset], nodes: [first, second], onLoaded, onError });
    cleanup();
    resolve();
    await vi.waitFor(() => expect(state.meshes[0].dispose).toHaveBeenCalledOnce());
    expect(state.meshes).toHaveLength(1);
    expect(state.scene?.children).toHaveLength(0);
    expect(onLoaded).not.toHaveBeenCalledWith(asset.id, true);
    expect(onError).not.toHaveBeenCalled();
  });
});
