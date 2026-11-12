export default function PipelineGuide() {
  return <details className="pipeline-guide">
    <summary>How the pipeline works <span>Steps, optimizations and limits</span></summary>
    <div className="pipeline-guide-content">
      <p>Photographs become individual generated object appearances, not a measured facility twin. Open the steps below alongside the selected source and its execution report.</p>
      <ol className="pipeline-diagram" aria-label="Photographic reconstruction pipeline">
        <li><strong>Photo + inventory</strong><span>Approve the source and record target equipment.</span></li>
        <li><strong>Detect or review boxes</strong><span>Grounding DINO proposes boxes; reviewed boxes are explicit human supervision.</span></li>
        <li><strong>Mask + prepare crops</strong><span>SAM2 segments objects. Reject tiny/invalid crops; conservatively deduplicate overlapping reviewed identities.</span></li>
        <li><strong>Generate appearance</strong><span>Idol reconstructs each usable crop with pinned models: 32,768 Gaussians, 50 steps, seed 42.</span></li>
        <li><strong>Validate + reuse</strong><span>Check actual PLYs and hashes. Resume checkpoints; optimized trials reuse only exact crop-and-settings matches.</span></li>
        <li><strong>Compose + publish</strong><span>Attach provenance and inferred or manually authored layout; publish only approved references and validated outputs.</span></li>
      </ol>
      <div className="pipeline-notes">
        <p><strong>What is optimized?</strong> Crop before RGBA conversion to avoid full-frame temporary images for each object; output pixels stay identical. Invalid-crop rejection avoids unusable generations. Conservative deduplication avoids repeated proposals; exact successful-output caching avoids identical work. Reuse is not another independent reconstruction. Reviewed-box comparisons change the supervision, not just the algorithm; counts and timings do not establish accuracy or causal speedup.</p>
        <p><strong>Appearance is not layout.</strong> Generated shape/texture is separate from manually authored placements and inferred depth/scale. Prompt cases use deterministic procedural layouts; diagram/plan cases show unreviewed OCR/contour proposals, not reconstructed appearances or recovered process topology. This public viewer runs no inference and accepts no uploads.</p>
      </div>
    </div>
  </details>;
}
