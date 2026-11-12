import * as THREE from "three";
import type { SceneAsset, SceneNode } from "../../../packages/scene/types";
import { splatFit } from "./model";

export function fitSplatToNode(object: THREE.Object3D, asset: SceneAsset, node: SceneNode): void {
  const fit = splatFit(asset, node);
  if (!fit) throw new Error("Splat has missing or invalid bounds");
  object.rotation.set(...node.rotation);
  if (asset.provenance.model === "speridlabs/idol" &&
      asset.provenance.sdk_revision === "8db700349a5570aac390e4780fa32e3eed6b587a") {
    // This SDK exports (x, y, z) -> (x, -z, y), so its PLY up is -Y.
    object.rotateX(Math.PI);
  }
  object.scale.set(...fit.scale);
  const offset = new THREE.Vector3(...fit.center).multiply(object.scale).applyQuaternion(object.quaternion);
  object.position.set(...node.position).sub(offset);
}

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
