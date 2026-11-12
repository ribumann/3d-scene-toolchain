import { describe, expect, it } from "vitest";
import { caseFromQuery, pointOnRoute, routePoints, splatFit, splatIssue, updateNode, visibleNodes } from "./model";
import type { Scene } from "../../../packages/scene/types";

const scene: Scene = {
  schema_version: "1.0", id: "s", case_id: "P01", name: "test", description: "", revision: 3,
  units: "meters", coordinates: "right-handed-y-up", sources: [], assets: [], edges: [],
  nodes: [{ id: "a", label: "A", category: "item", shape: "box", position: [0, 0, 0],
    rotation: [0, 0, 0], size: [1, 1, 1], color: "#fff", visible: true,
    evidence: { origin: "assumed", confidence: 0.5, reviewed: false, note: "" } }],
};
describe("scene view model", () => {
  it("selects only catalog-known case links and keeps the normal default without a query", () => {
    const ids = ["P01", "I01", "I02", "I03"];
    expect(caseFromQuery("?case=I02", ids)).toEqual({ caseId: "I02" });
    expect(caseFromQuery("?case=I03", ids)).toEqual({ caseId: "I03" });
    expect(caseFromQuery("?other=value", ids)).toEqual({ caseId: "P01" });
  });
  it("reports invalid or ambiguous case links rather than silently selecting the wrong scene", () => {
    for (const search of ["?case=unknown", "?case=", "?case=../P01", "?case=I02&case=I01"]) {
      expect(caseFromQuery(search, ["P01", "I01", "I02"])).toEqual({
        caseId: "P01", error: "Invalid or unavailable case link. Showing P01 instead.",
      });
    }
  });
  it("updates immutably without changing the revision", () => {
    const changed = updateNode(scene, "a", { position: [2, 0, 0] });
    expect(changed.revision).toBe(3);
    expect(scene.nodes[0].position).toEqual([0, 0, 0]);
    expect(changed.nodes[0].position).toEqual([2, 0, 0]);
  });
  it("filters hidden and isolated nodes", () => {
    expect(visibleNodes(updateNode(scene, "a", { visible: false }), null)).toHaveLength(0);
    expect(visibleNodes(scene, "other")).toHaveLength(0);
  });
  it("interpolates along actual route distance", () => {
    expect(pointOnRoute([[0, 0, 0], [1, 0, 0], [1, 3, 0]], 0.5)).toEqual([1, 1, 0]);
    expect(pointOnRoute([[1, 1, 1], [1, 1, 1]], 0.3)).toEqual([1, 1, 1]);
  });
  it("does not invent a route when endpoints are absent", () => {
    expect(routePoints({ id: "e", source: "a", target: "missing", kind: "process", points: [], label: "" }, scene)).toEqual([]);
  });
  it("fits y-up splat bounds to a node without changing axes", () => {
    const asset = { id: "p", kind: "ply" as const, uri: "/api/assets/a.ply", sha256: "", provenance: { bounds: { min: [0, -1, 0], max: [2, 1, 4] } } };
    expect(splatFit(asset, { ...scene.nodes[0], size: [4, 6, 8] })).toEqual({ center: [1, 0, 2], scale: [2, 2, 2] });
    expect(splatFit({ ...asset, provenance: {} }, scene.nodes[0])).toBeNull();
  });
  it("fits visible covariance support rather than centers and preserves proportions", () => {
    const asset = {
      id: "p", kind: "ply" as const, uri: "/object.ply", sha256: "", provenance: {
        bounds: { min: [0, 0, 0], max: [1, 1, 1] },
        geometry_quality: { status: "accepted", render_bounds: { min: [-1, -2, -3], max: [3, 2, 5] } },
      },
    };
    const fit = splatFit(asset, { ...scene.nodes[0], size: [8, 12, 16] });
    expect(fit).toEqual({ center: [1, 0, 1], scale: [2, 2, 2] });
  });
  it("excludes rejected, malformed and severely disproportionate appearances with a reason", () => {
    const asset = {
      id: "p", kind: "ply" as const, uri: "/object.ply", sha256: "",
      provenance: { bounds: { min: [-.5, -.5, -.5], max: [.5, .5, .5] } },
    };
    expect(splatFit(asset, { ...scene.nodes[0], size: [1, 8, 1] })).not.toBeNull();
    expect(splatFit(asset, { ...scene.nodes[0], size: [1, 8.001, 1] })).toBeNull();
    expect(splatIssue(asset, { ...scene.nodes[0], size: [1, 80, 1] })).toContain("aspect distortion");
    const rejected = { ...asset, provenance: { ...asset.provenance, geometry_quality: {
      status: "excluded", reasons: ["extreme_center_outliers"],
    } } };
    expect(splatFit(rejected, scene.nodes[0])).toBeNull();
    expect(splatIssue(rejected, scene.nodes[0])).toContain("extreme_center_outliers");
    expect(splatFit({ ...asset, provenance: { ...asset.provenance, geometry_quality: {} } }, scene.nodes[0])).toBeNull();
  });
});
