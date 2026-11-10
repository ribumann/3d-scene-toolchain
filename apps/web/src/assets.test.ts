import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { fitModelToNode } from "./assets";
import type { SceneNode } from "../../../packages/scene/types";

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
