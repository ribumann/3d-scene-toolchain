import { describe, expect, it } from "vitest";
import { parseSceneImport } from "./interchange";
import type { Scene } from "../../../packages/scene/types";

const scene: Scene = {
  schema_version: "1.0", id: "s", case_id: "I01", name: "Manual correction", description: "",
  revision: 1, units: "meters", coordinates: "right-handed-y-up", assets: [],
  sources: [{ id: "image", kind: "image", filename: "input.png", sha256: "abc" }],
  nodes: [{ id: "stable-a", label: "OCR corrected", category: "vessel", shape: "box",
    position: [1, 2, 3], rotation: [0, 0, 0], size: [1, 2, 3], color: "#123456", visible: true,
    evidence: { origin: "observed", reviewed: false, confidence: 0.6, source_id: "image", note: "" } }],
  edges: [],
};
describe("scene JSON import", () => {
  it("uses the current revision, preserves IDs and never auto-reviews evidence", () => {
    const result = parseSceneImport(JSON.stringify(scene), "I01", 8, "abc");
    expect(result.revision).toBe(8);
    expect(result.nodes[0].id).toBe("stable-a");
    expect(result.nodes[0].evidence.reviewed).toBe(false);
  });
  it("rejects a different case or source hash", () => {
    expect(() => parseSceneImport(JSON.stringify(scene), "I02", 1)).toThrow("case_id");
    expect(() => parseSceneImport(JSON.stringify(scene), "I01", 1, "other")).toThrow("SHA-256");
  });
  it("rejects broken topology and duplicate IDs", () => {
    expect(() => parseSceneImport(JSON.stringify({ ...scene, nodes: [scene.nodes[0], scene.nodes[0]] }), "I01", 1)).toThrow("unique");
    expect(() => parseSceneImport(JSON.stringify({ ...scene, edges: [{ id: "e", source: "stable-a", target: "missing", points: [], label: "", kind: "process" }] }), "I01", 1)).toThrow("endpoints");
  });
  it("rejects malformed vectors and executable or remote asset URLs", () => {
    expect(() => parseSceneImport(JSON.stringify({ ...scene, nodes: [{ ...scene.nodes[0], position: [1, 2] }] }), "I01", 1)).toThrow("finite");
    for (const uri of ["javascript:alert(1)", "https://example.com/a.glb", "/api/assets/../a.glb"]) {
      expect(() => parseSceneImport(JSON.stringify({ ...scene, assets: [{ id: "a", kind: "glb", uri, sha256: "", provenance: {} }] }), "I01", 1)).toThrow("asset URIs");
    }
  });
});
