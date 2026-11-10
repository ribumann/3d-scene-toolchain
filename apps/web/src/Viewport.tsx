import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Grid, Line, OrbitControls } from "@react-three/drei";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import type { Scene, SceneAsset, SceneNode, Vec3 } from "../../../packages/scene/types";
import { pointOnRoute, routePoints, splatFit, visibleNodes } from "./model";
import { fitModelToNode } from "./assets";

type Props = {
  scene: Scene; selected: string | null; onSelect: (id: string) => void;
  mode: "geometry" | "splat"; isolated: string | null; labels: boolean;
  playing: boolean; speed: number; cameraView: { kind: "orbit" | "top" | "reset"; serial: number };
};

function assetNode(asset: SceneAsset, nodes: SceneNode[]) {
  return nodes.find(node => asset.node_id === node.id || node.asset_id === asset.id);
}

class CanvasBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() {
    return this.state.error ? <div className="viewport-message" role="alert">3D viewport unavailable: {this.state.error}. Check WebGL support and reload.</div> : this.props.children;
  }
}

function Camera({ scene, view }: { scene: Scene; view: Props["cameraView"] }) {
  const { camera } = useThree();
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null);
  const framing = useMemo(() => {
    if (!scene.nodes.length) return { center: new THREE.Vector3(), distance: 18 };
    const box = new THREE.Box3();
    scene.nodes.forEach(node => {
      const p = new THREE.Vector3(...node.position);
      const half = new THREE.Vector3(...node.size).multiplyScalar(0.5);
      box.expandByPoint(p.clone().sub(half)); box.expandByPoint(p.clone().add(half));
    });
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    return { center, distance: Math.max(12, size.length() * 1.1) };
  }, [scene.id]); // Editing a position should not move the camera.
  useEffect(() => {
    const { center, distance } = framing;
    camera.position.copy(center).add(view.kind === "top"
      ? new THREE.Vector3(0, distance, 0.001)
      : new THREE.Vector3(distance * 0.7, distance * 0.65, distance * 0.7));
    camera.near = 0.1; camera.far = Math.max(1000, distance * 10);
    camera.updateProjectionMatrix();
    if (controls.current) { controls.current.target.copy(center); controls.current.update(); }
  }, [camera, framing, view]);
  return <OrbitControls ref={controls} makeDefault enableDamping />;
}

function NodeMesh({ node, selected, proxy, onSelect }: { node: SceneNode; selected: boolean; proxy: boolean; onSelect: () => void }) {
  return <group position={node.position} rotation={node.rotation}>
    <mesh scale={node.shape === "plane" ? [node.size[0], node.size[2], 1] : node.size} rotation={node.shape === "plane" ? [-Math.PI / 2, 0, 0] : [0, 0, 0]} onClick={event => { event.stopPropagation(); onSelect(); }}>
      {node.shape === "cylinder" ? <cylinderGeometry args={[0.5, 0.5, 1, 24]} /> :
       node.shape === "sphere" ? <sphereGeometry args={[0.5, 24, 16]} /> :
       node.shape === "cone" ? <coneGeometry args={[0.5, 1, 24]} /> :
       node.shape === "plane" ? <planeGeometry args={[1, 1]} /> :
       <boxGeometry args={[1, 1, 1]} />}
      <meshStandardMaterial color={selected ? "#397bc2" : node.color} transparent={proxy} opacity={proxy ? 0 : 1} depthWrite={!proxy} side={THREE.DoubleSide} />
    </mesh>
    {selected && <lineSegments scale={node.size}><edgesGeometry args={[new THREE.BoxGeometry(1.02, 1.02, 1.02)]} /><lineBasicMaterial color="#1761aa" /></lineSegments>}
  </group>;
}

// Labels belong to the existing DOM root. Drei Html creates a separate root per
// label, whose synchronous teardown races React's StrictMode effect replay.
function LabelProjection({ nodes, elements }: { nodes: SceneNode[]; elements: Map<string, HTMLSpanElement> }) {
  const { camera, size } = useThree();
  const position = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    for (const node of nodes) {
      const element = elements.get(node.id);
      if (!element) continue;
      position.set(0, node.size[1] / 2 + 0.25, 0).applyEuler(new THREE.Euler(...node.rotation)).add(new THREE.Vector3(...node.position)).project(camera);
      const visible = position.z >= -1 && position.z <= 1 && Math.abs(position.x) <= 1.2 && Math.abs(position.y) <= 1.2;
      element.style.display = visible ? "block" : "none";
      element.style.transform = `translate(-50%, -50%) translate(${(position.x + 1) * size.width / 2}px, ${(1 - position.y) * size.height / 2}px)`;
    }
  });
  return null;
}

function Spark({ assets, nodes, onError, onLoaded }: { assets: SceneAsset[]; nodes: SceneNode[]; onError: (message: string) => void; onLoaded: (id: string, value: boolean) => void }) {
  const { gl, scene } = useThree();
  useEffect(() => {
    let active = true;
    let renderer: SparkRenderer | undefined;
    const meshes: SplatMesh[] = [];
    try {
      renderer = new SparkRenderer({ renderer: gl });
      renderer.name = "SparkRenderer";
      scene.add(renderer);
      for (const asset of assets) {
        onLoaded(asset.id, false);
        const node = assetNode(asset, nodes);
        const fit = node ? splatFit(asset, node) : null;
        if (node && !fit) { onError(`Splat ${asset.id} has missing or invalid bounds; editable geometry remains visible.`); continue; }
        const mesh = new SplatMesh({ url: asset.uri });
        mesh.name = asset.id;
        if (node && fit) {
          mesh.rotation.set(...node.rotation);
          mesh.scale.set(...fit.scale);
          const offset = new THREE.Vector3(...fit.center).multiply(mesh.scale).applyEuler(mesh.rotation);
          mesh.position.set(...node.position).sub(offset);
        }
        scene.add(mesh); meshes.push(mesh);
        mesh.initialized.then(() => { if (active) onLoaded(asset.id, true); }).catch((error: unknown) => { if (active) onError(`Splat ${asset.id} failed to load: ${String(error)}`); });
      }
    } catch (error) {
      onError(`Spark renderer failed: ${String(error)}`);
      meshes.forEach(mesh => { scene.remove(mesh); mesh.dispose(); });
      if (renderer) { scene.remove(renderer); renderer.dispose(); }
      return;
    }
    return () => { active = false; meshes.forEach(mesh => { scene.remove(mesh); mesh.dispose(); }); if (renderer) { scene.remove(renderer); renderer.dispose(); } };
  }, [gl, scene, assets, nodes, onError, onLoaded]);
  return null;
}

function ModelAsset({ asset, node, onError, onLoaded }: { asset: SceneAsset; node?: SceneNode; onError: (message: string) => void; onLoaded: (id: string, value: boolean) => void }) {
  const { scene } = useThree();
  useEffect(() => {
    let active = true;
    let object: THREE.Object3D | undefined;
    onLoaded(asset.id, false);
    const dispose = (root: THREE.Object3D) => root.traverse(item => {
      if (item instanceof THREE.Mesh) {
        item.geometry.dispose();
        const materials = Array.isArray(item.material) ? item.material : [item.material];
        materials.forEach(material => material.dispose());
      }
    });
    new GLTFLoader().load(asset.uri, result => {
      if (!active) { dispose(result.scene); return; }
      try {
        object = node ? fitModelToNode(result.scene, node) : result.scene;
        scene.add(object);
        onLoaded(asset.id, true);
      } catch (error) {
        dispose(result.scene);
        onError(`Model ${asset.id} could not be fitted: ${String(error)}`);
      }
    }, undefined, error => { if (active) onError(`Model ${asset.id} failed to load: ${String(error)}`); });
    return () => {
      active = false;
      if (object) {
        scene.remove(object);
        dispose(object);
      }
    };
  }, [asset, node, scene, onError, onLoaded]);
  return null;
}

function Route({ points, playing, speed }: { points: Vec3[]; playing: boolean; speed: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const progress = useRef(0);
  useFrame((_, delta) => {
    if (playing) progress.current += Math.min(delta, 0.1) * speed * 0.1;
    if (ref.current) ref.current.position.set(...pointOnRoute(points, progress.current));
  });
  if (points.length < 2) return null;
  return <>
    <Line points={points} color="#477da4" lineWidth={1.5} />
    <mesh ref={ref} position={points[0]}><sphereGeometry args={[0.16, 12, 8]} /><meshBasicMaterial color="#1666a9" /></mesh>
  </>;
}

function SceneContent(props: Props & { onError: (message: string) => void; labelElements: Map<string, HTMLSpanElement> }) {
  const [loaded, setLoaded] = useState<Record<string, boolean>>({});
  const onLoaded = useMemo(() => (id: string, value: boolean) => setLoaded(previous => previous[id] === value ? previous : { ...previous, [id]: value }), []);
  const nodes = useMemo(() => visibleNodes(props.scene, props.isolated), [props.scene.nodes, props.isolated]);
  const ids = useMemo(() => new Set(nodes.map(n => n.id)), [nodes]);
  const assets = useMemo(() => props.scene.assets.filter(asset => {
    const linked = assetNode(asset, props.scene.nodes);
    return linked ? ids.has(linked.id) : !asset.node_id;
  }), [props.scene.assets, props.scene.nodes, ids]);
  const splats = useMemo(() => assets.filter(a => a.kind === "ply"), [assets]);
  const models = useMemo(() => assets.filter(a => a.kind === "glb"), [assets]);
  return <>
    <color attach="background" args={["#edf3f7"]} />
    <ambientLight intensity={1.8} /><directionalLight position={[10, 20, 10]} intensity={2} />
    <Grid infiniteGrid fadeDistance={120} cellSize={1} sectionSize={5} cellColor="#c8d7e1" sectionColor="#a8bfce" position={[0, -0.02, 0]} />
    <Camera scene={props.scene} view={props.cameraView} />
    {props.mode === "splat" && splats.length > 0 && <Spark assets={splats} nodes={nodes} onError={props.onError} onLoaded={onLoaded} />}
    {models.map(asset => <ModelAsset key={asset.id} asset={asset} node={assetNode(asset, nodes)} onError={props.onError} onLoaded={onLoaded} />)}
    {props.labels && <LabelProjection nodes={nodes} elements={props.labelElements} />}
    {nodes.map(node => <NodeMesh key={node.id} node={node} selected={props.selected === node.id} onSelect={() => props.onSelect(node.id)}
      proxy={models.some(a => assetNode(a, nodes)?.id === node.id && loaded[a.id]) ||
        (props.mode === "splat" && splats.some(a => assetNode(a, nodes)?.id === node.id && loaded[a.id] && splatFit(a, node)))} />)}
    {props.scene.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)).map(edge => <Route key={edge.id} points={routePoints(edge, props.scene)} playing={props.playing} speed={props.speed} />)}
  </>;
}

export default function Viewport(props: Props) {
  const [errors, setErrors] = useState<string[]>([]);
  const labelElements = useMemo(() => new Map<string, HTMLSpanElement>(), []);
  const onError = useMemo(() => (message: string) => setErrors(previous => previous.includes(message) ? previous : [...previous, message]), []);
  useEffect(() => { setErrors([]); }, [props.scene.id, props.mode]);
  return <div className="canvas-wrap">
    <CanvasBoundary key={props.scene.id}><Canvas gl={{ antialias: false }} camera={{ position: [18, 18, 18], fov: 45 }}>
      <Suspense fallback={null}><SceneContent key={`${props.scene.id}-${props.mode}`} {...props} onError={onError} labelElements={labelElements} /></Suspense>
    </Canvas></CanvasBoundary>
    <div className="scene-label-overlay" aria-hidden="true">{props.labels && visibleNodes(props.scene, props.isolated).map(node =>
      <span key={node.id} ref={element => { if (element) labelElements.set(node.id, element); else labelElements.delete(node.id); }} className={`scene-label ${props.selected === node.id ? "selected" : ""}`}>{node.label}</span>
    )}</div>
    {props.mode === "splat" && !props.scene.assets.some(a => a.kind === "ply") && <div className="viewport-note">No splat asset for this scene. Showing editable geometry.</div>}
    {errors.length > 0 && <div className="viewport-error" role="alert">{errors.map(error => <div key={error}>{error}</div>)}</div>}
    <div className="viewport-hint">Drag to orbit · Scroll to zoom</div>
  </div>;
}
