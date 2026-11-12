export type PlantLayers = Record<"A" | "B" | "C" | "shared", boolean>;

export default function PlantPanel({ layers, onLayers, utilities, onUtilities, splatConcepts, splatPlacements }: {
  layers: PlantLayers; onLayers: (layers: PlantLayers) => void;
  utilities: boolean; onUtilities: (show: boolean) => void;
  splatConcepts: number; splatPlacements: number;
}) {
  return <section className="pilot-status" aria-label="Diamond plant reconstruction">
    <h2>Process modules, not every nut and bolt</h2>
    <p>24 modules across three lines, with logical equipment children, directed material and utility streams, and telemetry attachment points. Dimensions, placement and connections remain authored simulation assumptions, not surveyed geometry.</p>
    {splatConcepts > 0 ? <p><strong>Photo-derived Gaussian appearances:</strong> {splatConcepts} component crops from the original synthetic photograph were segmented with SAM2 and reconstructed with Idol, shared across {splatPlacements} authored placements. Single-image geometry is approximate; screening can hide poor results. Any unreconstructed modules remain explicit mesh models. The portable GLB below retains the authored model, not the splats.</p> :
      <p><strong>Authored geometry only:</strong> no Gaussian reconstruction is included in this publication.</p>}
    <div className="plant-downloads" aria-label="Plant downloads">
      <a href="/plant/D01.png" download>Source photograph</a>
      <a href="/plant/layout.svg" download>Scaled site plan</a>
      <a href="/plant/metadata.json" download>Twin metadata / JSON</a>
      <a href="/plant/plant.glb" download>Portable 3D model / GLB</a>
      {splatConcepts > 0 && <a href="/plant/reconstruction.json" download>Reconstruction evidence / JSON</a>}
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
