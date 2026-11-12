import type { TrialStatus } from "./api";

export default function TrialPanel({ trial, onVariant }: { trial: TrialStatus; onVariant: (id: string) => void }) {
  const report = trial.report;
  const source = trial.definition.source;
  return <section className="pilot-status trial-panel" aria-label="Trial comparison">
    <div className="section-heading"><h2>{trial.trial_id} trial: {trial.status === "processing" ? "processing at snapshot" : trial.status.replace("_", " ")}</h2>
      <div className="segmented" aria-label="Trial variant">{(["baseline", "optimized"] as const).map(variant =>
        <button key={variant} aria-pressed={variant === trial.variant} onClick={() => onVariant(`${trial.trial_id}-${variant}`)}>{variant === "baseline" ? "Detector baseline" : "Reviewed-box comparison"}</button>)}</div>
    </div>
    <p>{source.kind === "licensed-real-photograph" ? <>Real photograph by {source.creator}: <a href={source.source_page} target="_blank" rel="noreferrer">original source</a>. Photograph and source-derived crops/splats: <a href={source.license_url} target="_blank" rel="noreferrer">{source.license}</a>, not the software MIT license.</> : "Synthetic photographic input, not a real-site photograph."} Optimized uses manual semantic boxes when supplied; this is a supervised workflow comparison, not proof automatic detection or 3D accuracy improved.</p>
    {source.kind === "licensed-real-photograph" && <p>{source.limitations}</p>}
    {report ? <>
      <dl className="trial-measurements">
        <div><dt>Target equipment</dt><dd>{report.expected_objects}</dd></div>
        <div><dt>Extraction proposals</dt><dd>{report.detected_objects}</dd></div>
        <div><dt>Usable crops</dt><dd>{report.usable_crops}</dd></div>
        <div><dt>Validated / failed</dt><dd>{report.objects_succeeded ?? 0} / {report.objects_failed ?? 0}</dd></div>
        <div><dt>New generations / reuse</dt><dd>{report.independent_generations} / {report.cache_hits}</dd></div>
        <div><dt>Resumed / cache misses</dt><dd>{report.resumed} / {report.cache_misses}</dd></div>
        <div><dt>Wall time, this run</dt><dd>{report.seconds_this_run}s</dd></div>
        <div><dt>Scene placements</dt><dd>{report.published_instances ?? 0}</dd></div>
      </dl>
      <p>{report.supervision} · {report.settings.count.toLocaleString()} Gaussians / {report.settings.steps} steps / seed {report.settings.seed}. Counts are not an accuracy score. Background contamination and masks still need review; layout/scale/depth are inferred or manually authored.</p>
      {report.failure_reason && <p className="inline-error" role="status">Trial incomplete: {report.failure_reason}. Only validated objects can be shown; no fallback appearances.</p>}
      {!!(report.rejected.length || report.objects.length) && <details><summary>Object outcomes and rejection reasons</summary>
        <ul>{report.rejected.map(item => <li key={`rejected-${item.node_id}`}>{item.node_id}: {item.reason}{item.duplicate_of ? ` (${item.duplicate_of})` : ""}</li>)}
          {report.objects.map(item => <li key={item.node_id}>{item.node_id}: {item.status}{item.timing.seconds !== undefined ? ` · ${item.timing.seconds}s` : ""}{item.failure_reason ? ` · ${item.failure_reason}` : ""}</li>)}</ul>
      </details>}
      <details><summary>Method and frozen model revisions</summary><p>{JSON.stringify(report.settings)}</p></details>
    </> : <p>{trial.status === "processing" ? "This variant was active at publication. No in-progress objects are published." : "No completed execution report is published for this variant yet."}</p>}
    <details><summary>Input provenance and expected inventory</summary>
      {source.kind === "licensed-real-photograph" ? <>
        <p>Preparation: {source.changes}</p><p>Adaptations: {source.derivative_changes}</p>
        <p>Original SHA256: {source.original_sha256}</p>
      </> : <><p>{source.generator}</p><p>{source.prompt}</p></>}
      <p>{trial.definition.expected_inventory.map(item => `${item.count} ${item.category} (${item.identity})`).join("; ")}</p>
      <p>Prepared source SHA256: {source.sha256}</p>
      <p>Exact crop/settings cache hits reuse one validated generation, not independent reconstructions. Explicit repeated placements are authored instances only. {trial.definition.layout_kind}.</p>
    </details>
  </section>;
}
