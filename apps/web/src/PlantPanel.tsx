export type PlantLayers = Record<"A" | "B" | "C" | "shared", boolean>;

export default function PlantPanel({ layers, onLayers, utilities, onUtilities }: {
  layers: PlantLayers; onLayers: (layers: PlantLayers) => void;
  utilities: boolean; onUtilities: (show: boolean) => void;
}) {
  return <section className="pilot-status" aria-label="Diamond plant reconstruction">
    <h2>Process modules, not every nut and bolt</h2>
    <p>24 manually reconstructed modules across three lines, with logical equipment children, directed material and utility streams, and telemetry attachment points. Meshes, dimensions and connections are authored simulation assumptions guided by the synthetic photograph, not photogrammetry.</p>
    <p><strong>Gaussian reconstruction has not run:</strong> the existing Italy North Spot T4 could not restart because capacity is unavailable. These are explicit parametric models, not substitute splats or claimed Idol results.</p>
    <div className="plant-downloads" aria-label="Plant downloads">
      <a href="/plant/D01.png" download>Source photograph</a>
      <a href="/plant/layout.svg" download>Scaled site plan</a>
      <a href="/plant/metadata.json" download>Twin metadata / JSON</a>
      <a href="/plant/plant.glb" download>Portable 3D model / GLB</a>
    </div>
    <fieldset className="plant-layers"><legend>Viewport layers only — exports keep the full plant</legend>
      {(["A", "B", "C", "shared"] as const).map(line => <label className="check" key={line}>
        <input type="checkbox" checked={layers[line]} onChange={event => onLayers({ ...layers, [line]: event.target.checked })} />
        {line === "shared" ? "Shared services" : `Line ${line}`}
      </label>)}
      <label className="check"><input type="checkbox" checked={utilities} onChange={event => onUtilities(event.target.checked)} /> Utility connections</label>
    </fieldset>
  </section>;
}
