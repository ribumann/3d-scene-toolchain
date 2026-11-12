export default function PipelineGuide() {
  return <details className="pipeline-guide">
    <summary>How the pipeline works <span>Steps, optimizations and limits</span></summary>
    <div className="pipeline-guide-content">
      <p>Photographs supply observed inputs; generated photographs illustrate objects described only by prompts or schemata. Neither route recovers a measured facility twin. Compare each result with its source and execution report.</p>
      <ol className="pipeline-diagram" aria-label="Photographic reconstruction pipeline">
        <li><strong>Source + inventory</strong><span>Approve a photograph, or generate and review photographic references from object descriptions.</span></li>
        <li><strong>Detect or review boxes</strong><span>Grounding DINO proposes boxes; reviewed boxes are explicit human supervision.</span></li>
        <li><strong>Mask + prepare crops</strong><span>SAM2 segments objects. Reject tiny/invalid crops; conservatively deduplicate overlapping reviewed identities.</span></li>
        <li><strong>Generate appearance</strong><span>Idol reconstructs each usable crop with pinned models: 32,768 Gaussians, 50 steps, seed 42.</span></li>
        <li><strong>Validate + reuse</strong><span>Check PLYs, visible Gaussian extents and exact-hash visual exclusions. Resume valid checkpoints; reuse only exact crop-and-settings matches.</span></li>
        <li><strong>Compose + publish</strong><span>Place explicitly authored instances and source-supported connections; keep invented appearance and inferred scale clearly labeled.</span></li>
      </ol>
      <div className="pipeline-notes">
        <p><strong>What is optimized?</strong> Crop before RGBA conversion to avoid full-frame temporary images for each object; output pixels stay identical. Invalid-crop rejection avoids unusable generations. Conservative deduplication avoids repeated proposals; exact successful-output caching avoids identical work. Reuse is not another independent reconstruction. Reviewed-box comparisons change the supervision, not just the algorithm; counts and timings do not establish accuracy or causal speedup.</p>
        <p><strong>Keep shapes within their boxes.</strong> Fit visible Gaussian extents uniformly, without stretching each axis. Exclude extreme support/outliers and appearances requiring over 8× aspect distortion against their provisional boxes; show the rejection reason, not a replacement box. This heuristic does not certify object identity, hidden geometry or metric dimensions.</p>
        <p><strong>Appearance is not layout.</strong> Original prompt cases retain procedural layouts; original diagram/plan cases retain unreviewed region proposals. Illustrated counterparts add generated appearances and reviewed or scenario-authored relationships. Shared concepts are authored instances, not separate recoveries. Plan proximity alone never creates a connection. This public viewer runs no inference and accepts no uploads.</p>
        <p><strong>Better inputs.</strong> Keep complete objects and their bases in frame, with sharp detail, diffuse light, separation from neighbors and a visible scale reference. Capture several consistent viewpoints when possible. For schemata, provide readable labels, explicit arrow directions and an equipment inventory. A single picture cannot establish hidden geometry, dimensions or working pipe connections.</p>
      </div>
    </div>
  </details>;
}
