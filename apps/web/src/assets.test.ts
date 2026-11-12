import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { fitModelToNode, fitSplatToNode } from "./assets";
import type { SceneAsset, SceneNode } from "../../../packages/scene/types";

describe("splat source-coordinate normalization", () => {
  const node = { position: [10, 4, -2], rotation: [0, Math.PI / 2, 0], size: [4, 12, 24] } as SceneNode;
  const asset: SceneAsset = {
    id: "idol", kind: "ply", uri: "/object.ply", sha256: "",
    provenance: {
      model: "speridlabs/idol", sdk_revision: "8db700349a5570aac390e4780fa32e3eed6b587a",
      bounds: { min: [1, 2, 3], max: [3, 6, 9] },
    },
  };
  const transform = (provenance = asset.provenance) => {
    const object = new THREE.Object3D();
    fitSplatToNode(object, { ...asset, provenance }, node);
    object.updateMatrixWorld(true);
    return object;
  };
  it("makes the pinned Idol export upright around its center before semantic rotation", () => {
    const object = transform();
    const center = object.localToWorld(new THREE.Vector3(2, 4, 6));
    expect(center.distanceTo(new THREE.Vector3(...node.position))).toBeLessThan(1e-10);
    const point = object.localToWorld(new THREE.Vector3(2.2, 3.6, 6.6));
    expect(point.x).toBeCloseTo(8.8);
    expect(point.y).toBeCloseTo(4.8);
    expect(point.z).toBeCloseTo(-2.4);
    expect(object.matrixWorld.determinant()).toBeGreaterThan(0);
    const up = new THREE.Vector3(0, -1, 0).applyQuaternion(object.quaternion);
    expect(up.distanceTo(new THREE.Vector3(0, 1, 0))).toBeLessThan(1e-10);
  });
  it("preserves normal y-up splats and unrecognized SDK conventions", () => {
    for (const provenance of [
      { bounds: asset.provenance.bounds },
      { ...asset.provenance, model: "another-generator" },
      { ...asset.provenance, sdk_revision: "another-revision" },
    ]) {
      const object = transform(provenance);
      const point = object.localToWorld(new THREE.Vector3(2.2, 3.6, 6.6));
      expect(point.x).toBeCloseTo(11.2);
      expect(point.y).toBeCloseTo(3.2);
      expect(point.z).toBeCloseTo(-2.4);
    }
  });
});

describe("GLB semantic normalization", () => {
  const node = { position: [10, 4, -2], rotation: [0, 0, 0], size: [4, 6, 8] } as SceneNode;
  it("centers authored geometry and fits the semantic node size", () => {
    const object = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2));
    object.position.set(3, 5, 7);
    const fitted = fitModelToNode(object, node);
    fitted.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(fitted);
    expect(bounds.getCenter(new THREE.Vector3()).toArray()).toEqual(node.position);
    expect(bounds.getSize(new THREE.Vector3()).toArray()).toEqual(node.size);
  });
  it("applies semantic rotation outside the fitted model", () => {
    const fitted = fitModelToNode(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1)), { ...node, rotation: [0, Math.PI / 2, 0] });
    fitted.updateMatrixWorld(true);
    const size = new THREE.Box3().setFromObject(fitted).getSize(new THREE.Vector3());
    expect(size.x).toBeCloseTo(8);
    expect(size.z).toBeCloseTo(4);
  });
});
