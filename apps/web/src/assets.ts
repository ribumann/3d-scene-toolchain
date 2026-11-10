import * as THREE from "three";
import type { SceneNode } from "../../../packages/scene/types";

/** Preserve authored geometry transforms inside a normalized semantic-node group. */
export function fitModelToNode(object: THREE.Object3D, node: SceneNode): THREE.Group {
  object.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(object);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  if (bounds.isEmpty() || !size.toArray().every(value => Number.isFinite(value) && value > 0)) {
    throw new Error("GLB has empty or degenerate bounds");
  }
  const outer = new THREE.Group();
  const normalized = new THREE.Group();
  const centered = new THREE.Group();
  centered.position.copy(center).negate();
  centered.add(object);
  normalized.scale.set(node.size[0] / size.x, node.size[1] / size.y, node.size[2] / size.z);
  normalized.add(centered);
  outer.position.set(...node.position);
  outer.rotation.set(...node.rotation);
  outer.add(normalized);
  return outer;
}
