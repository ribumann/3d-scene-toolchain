import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import type { Case, Job, Scene, SceneNode, Vec3 } from "../../../packages/scene/types";
import { api, ApiError, readOnly, type PilotStatus, type TrialStatus } from "./api";
import TrialPanel from "./TrialPanel";
import PipelineGuide from "./PipelineGuide";
import { caseFromQuery, updateNode } from "./model";
import { parseSceneImport } from "./interchange";
const Viewport = lazy(() => import("./Viewport"));

const message = (error: unknown) => error instanceof Error ? error.message : String(error);
const activeJob = (job: Job) => job.status === "queued" || job.status === "running";

export default function App() {
  const [cases, setCases] = useState<Case[]>([]);
  const [pilotStatuses, setPilotStatuses] = useState<PilotStatus[]>([]);
  const [trialStatuses, setTrialStatuses] = useState<TrialStatus[]>([]);
  const [caseId, setCaseId] = useState("");
  const [scene, setScene] = useState<Scene | null>(null);
  const [sceneError, setSceneError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsError, setJobsError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"geometry" | "splat">("geometry");
  const [isolated, setIsolated] = useState<string | null>(null);
  const [labels, setLabels] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [playing, setPlaying] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [speed, setSpeed] = useState(1);
  const [cameraView, setCameraView] = useState<{ kind: "orbit" | "top" | "reset"; serial: number }>({ kind: "reset", serial: 0 });
  const [refresh, setRefresh] = useState(0);
  const [sourceError, setSourceError] = useState(false);
  const [sourceMetadata, setSourceMetadata] = useState<{ sha256: string; filename: string } | null>(null);
  const [metadataError, setMetadataError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const jsonInput = useRef<HTMLInputElement>(null);

  const currentCase = cases.find(item => item.id === caseId);
  const publicReference = readOnly && currentCase?.input_type !== "prompt" && !!currentCase?.source_url;
  const trial = trialStatuses.find(item => `${item.trial_id}-${item.variant}` === caseId);
  const referenceProvenance = trial ? trial.definition.source.kind === "licensed-real-photograph" ? "Licensed real photograph" : "Synthetic photographic input" : currentCase?.input_type === "generated" ? "AI-generated reference" : "Original reference";
  const pilot = pilotStatuses.find(item => item.case_id === caseId);
  const hasPublishedSplats = readOnly && !!scene?.assets.some(asset => asset.kind === "ply");
  const canUpload = !readOnly && !!currentCase && currentCase.input_type !== "prompt";
  const currentNode = scene?.nodes.find(node => node.id === selected);
  const currentJobs = jobs.filter(job => job.case_id === caseId);

  useEffect(() => {
    let active = true;
    setSourceMetadata(null); setMetadataError("");
    if (canUpload && currentCase?.source_filename) {
      api.sourceMetadata(caseId).then(data => { if (active) setSourceMetadata(data); })
        .catch(err => { if (active) setMetadataError(`Source metadata unavailable: ${message(err)}`); });
    }
    return () => { active = false; };
  }, [caseId, currentCase?.source_filename, canUpload, refresh]);
  useEffect(() => {
    let active = true;
    if (readOnly) api.pilots().then(data => { if (active) setPilotStatuses(data); })
      .catch(err => { if (active) setError(`Pilot status unavailable: ${message(err)}`); });
    if (readOnly) api.trials().then(data => { if (active) setTrialStatuses(data); })
      .catch(err => { if (active) setError(`Trial status unavailable: ${message(err)}`); });
    api.cases().then(data => {
      if (active) {
        const selection = readOnly ? caseFromQuery(window.location.search, data.map(item => item.id)) : { caseId: data[0]?.id || "" };
        setCases(data); setCaseId(previous => previous || selection.caseId);
        if ("error" in selection && selection.error) setError(selection.error);
      }
    })
      .catch(err => { if (active) setError(`Could not load cases: ${message(err)}`); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => { setReducedMotion(media.matches); if (media.matches) setPlaying(false); };
    media.addEventListener("change", changed);
    return () => media.removeEventListener("change", changed);
  }, []);
  useEffect(() => {
    if (readOnly) return;
    let active = true;
    async function loadJobs() {
      try { const data = await api.jobs(); if (active) { setJobs(data); setJobsError(""); } }
      catch (err) { if (active) setJobsError(`Could not load jobs: ${message(err)}`); }
    }
    void loadJobs();
    const timer = window.setInterval(loadJobs, 4000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!caseId) return;
    let active = true;
    setScene(null); setSceneError(""); setLoading(true); setSelected(null); setIsolated(null); setSourceError(false);
    api.scene(caseId).then(data => {
      if (active) { setScene(data); setDirty(false); setSelected(data.nodes[0]?.id ?? null); if (readOnly) setMode(data.assets.some(asset => asset.kind === "ply") ? "splat" : "geometry"); }
    }).catch(err => {
      if (active) setSceneError(err instanceof ApiError && err.status === 409 ? `${readOnly ? "No published scene" : "Scene awaiting input"}: ${message(err)}` : `Could not load scene: ${message(err)}`);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [caseId, refresh]);
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  const switchCase = (id: string) => {
    if (id === caseId || busy) return;
    if (dirty && !window.confirm("Discard unsaved scene edits and switch cases?")) return;
    if (readOnly) {
      const url = new URL(window.location.href);
      url.searchParams.set("case", id);
      window.history.replaceState(window.history.state, "", url);
    }
    setDirty(false); setError(""); setNotice(""); setCaseId(id);
  };
  const reload = () => {
    if (dirty && !window.confirm("Discard unsaved scene edits and reload the scene?")) return;
    setDirty(false); setError(""); setRefresh(value => value + 1);
  };
  const edit = (update: Partial<SceneNode>) => {
    if (readOnly || !scene || !selected || busy) return;
    setScene(updateNode(scene, selected, update)); setDirty(true); setNotice("");
  };
  const save = async () => {
    if (readOnly || !scene || !dirty || busy) return;
    setBusy(true); setError(""); setNotice("");
    try { const saved = await api.save(caseId, scene); setScene(saved); setDirty(false); setNotice(`Saved revision ${saved.revision}.`); }
    catch (err) { setError(err instanceof ApiError && err.status === 409 ? `Revision conflict: ${message(err)}. Your edits are still here; reload to discard them and fetch the latest scene.` : `Save failed: ${message(err)}. Your edits are still here.`); }
    finally { setBusy(false); }
  };
  const exportScene = () => {
    if (!scene) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(scene, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${caseId}-scene-r${scene.revision}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice(dirty ? "Exported JSON includes unsaved edits." : "Scene JSON exported.");
  };
  const importScene = async (file: File) => {
    if (readOnly || busy || !currentCase) return;
    if (dirty && !window.confirm("Import and save a replacement scene, discarding unsaved edits?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error("Scene JSON must be smaller than 10 MB.");
      const json = await file.text();
      const source = canUpload ? await api.sourceMetadata(caseId) : undefined;
      // Keep the loaded revision so concurrent changes cause a conflict rather
      // than silently rebasing the user's corrections onto someone else's work.
      // Initial scenes use a schema-valid revision 1; the API uses expected
      // revision 0 internally when no scene exists.
      const imported = parseSceneImport(json, caseId, scene?.revision ?? 1, source?.sha256);
      if (scene && imported.id !== scene.id) throw new Error("Scene ID must match the current scene; preserve stable semantic IDs when editing JSON.");
      const saved = await api.save(caseId, imported);
      setScene(saved); setSceneError(""); setDirty(false); setIsolated(null);
      setSelected(saved.nodes[0]?.id ?? null);
      setNotice(`Imported and saved revision ${saved.revision}. Review flags were preserved from JSON.`);
    } catch (err) {
      setError(`Import failed: ${message(err)}. The open scene has not been replaced.`);
    } finally { setBusy(false); if (jsonInput.current) jsonInput.current.value = ""; }
  };
  const upload = async (file: File) => {
    if (busy || !canUpload) return;
    if (dirty && !window.confirm("Uploading may replace the scene. Discard unsaved edits?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = await api.upload(caseId, file);
      setCases(previous => previous.map(item => item.id === updated.id ? updated : item));
      setDirty(false); setRefresh(value => value + 1); setNotice("Source uploaded. Run extraction if a new scene is needed.");
    } catch (err) { setError(`Upload failed: ${message(err)}`); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  };
  const start = async (stage: string) => {
    if (readOnly || busy) return;
    setBusy(true); setError("");
    try { const job = await api.start(caseId, stage); setJobs(previous => [job, ...previous.filter(item => item.id !== job.id)]); setNotice(`${stage} job ${job.status}.`); }
    catch (err) { setError(`Could not start ${stage}: ${message(err)}`); }
    finally { setBusy(false); }
  };
  const cancel = async (id: string) => {
    if (readOnly) return;
    setBusy(true); setError("");
    try { const job = await api.cancel(id); setJobs(previous => previous.map(item => item.id === job.id ? job : item)); }
    catch (err) { setError(`Could not cancel job: ${message(err)}`); }
    finally { setBusy(false); }
  };
  const select = useCallback((id: string) => { setSelected(id); setIsolated(previous => previous && previous !== id ? null : previous); }, []);
  const setView = (kind: "orbit" | "top" | "reset") => setCameraView(previous => ({ kind, serial: previous.serial + 1 }));

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">◈</span><div><strong>Scene Workbench</strong><span>Digital twin preparation</span></div></div>
      <div className="header-context"><span>WORKSPACE</span><strong>{currentCase ? `${currentCase.id} / ${currentCase.title}` : "Case library"}</strong></div>
      <div className="header-actions"><span className="save-state" aria-live="polite">{dirty ? "Unsaved edits" : scene ? `Revision ${scene.revision}` : "No scene loaded"}</span>{readOnly ? <strong className="tag">Read-only demo</strong> : <button className="primary" onClick={save} disabled={!dirty || busy}>Save changes</button>}</div>
    </header>
    {readOnly && <div className="demo-banner"><strong>Public read-only demo.</strong> Three procedural scenes and eight reference comparisons. Published pilot outputs are labeled separately from reference-only inputs and diagram proposals. Layout/depth/scale are inferred, not live digital twins. No uploads, saved edits or public backend.</div>}
    {(error || notice) && <div className={error ? "global-message error" : "global-message"} role={error ? "alert" : "status"}><span>{error || notice}</span><button aria-label="Dismiss message" onClick={() => { setError(""); setNotice(""); }}>×</button></div>}
    <div className="workspace">
      <aside className="library" aria-label="Case navigation">
        <div className="panel-heading"><div><h2>Cases</h2><p>Scene library</p></div><span className="count">{cases.length}</span></div>
        {!cases.length && <p className="muted inset">{error ? "Case library unavailable." : "Loading cases…"}</p>}
        {(["prompt", "reference", "generated", "trials"] as const).map(group => {
          const items = cases.filter(item => group === "trials" ? /^T0[1-3]-/.test(item.id) : /^T0[1-3]-/.test(item.id) ? false : group === "prompt" ? item.input_type === "prompt" : group === "generated" ? item.input_type === "generated" : !["prompt", "generated"].includes(item.input_type));
          if (!items.length) return null;
          return <div className="case-group" key={group}><h3>{group === "trials" ? "Trials" : group === "prompt" ? "Prompt scenarios" : group === "reference" ? readOnly ? "Original references" : "Reference inputs" : readOnly ? "AI-generated references" : "Generated inputs"}</h3>
            {items.map(item => <button key={item.id} className={`case-item ${caseId === item.id ? "active" : ""}`} onClick={() => switchCase(item.id)} disabled={busy} aria-current={caseId === item.id ? "page" : undefined}>
              <span className="case-id">{item.id}</span><span className="case-name">{item.title}<small>{readOnly && item.source_url ? pilotStatuses.find(p => p.case_id === item.id)?.status || trialStatuses.find(t => `${t.trial_id}-${t.variant}` === item.id)?.status || "Reference only" : item.status === "awaiting_input" ? "Awaiting input" : item.input_type}</small></span><span className={`status-dot ${item.status}`} aria-hidden="true" />
            </button>)}
          </div>;
        })}
      </aside>
      <main className="main-work">
        <div className="scene-title"><div><div className="breadcrumb">Cases <span>/</span> {currentCase?.id || "—"} <span>/</span> Scene</div><h1>{currentCase?.title || "Select a case"}</h1><p>{currentCase?.summary || "Choose a case to inspect its scene and source."}</p></div>
          <div className="scene-actions"><button onClick={exportScene} disabled={!scene || busy}>Export JSON</button>
            {!readOnly && <><input ref={jsonInput} className="visually-hidden" type="file" accept=".json,application/json" aria-label="Import scene JSON file" onChange={event => { const file = event.target.files?.[0]; if (file) void importScene(file); }} />
            <button onClick={() => jsonInput.current?.click()} disabled={!caseId || loading || busy || currentCase?.status === "awaiting_input"}>Import JSON</button></>}
            <button onClick={reload} disabled={!caseId || loading || busy}>{publicReference ? "Reload reference" : "Reload scene"}</button></div>
        </div>
        {readOnly && <PipelineGuide />}
        {trial && <TrialPanel trial={trial} onVariant={switchCase} />}
        {pilot && <div className="pilot-status" role="status"><strong>{pilot.status === "proposals" ? "Unreviewed diagram/plan proposals" : pilot.status === "partial" ? "Partial object reconstruction" : pilot.status === "succeeded" ? "Validated object outputs" : pilot.status === "processing" ? "Processing at publication snapshot" : pilot.status === "failed" ? "Pilot processing failed" : "Pilot not run"}</strong>
          <p>{pilot.status === "processing" ? "This source was active or had an unfinished running checkpoint. Its in-progress objects are not published; another snapshot is needed after it stops." : pilot.status === "proposals" ? `${pilot.objects} inferred region boxes; no Idol appearance or recovered process topology.` : `${pilot.objects} published object appearances; ${pilot.failed_objects} failed or unfinished distinct crops. Not a complete facility reconstruction.`} Compressed WebP input, not original bytes. Placement and scale are inferred.</p></div>}
        <section className="viewport-panel" aria-label={publicReference ? "Reference preview" : "3D scene"}>
          {(!publicReference || scene) && <div className="viewport-toolbar"><div className="segmented" aria-label="Display mode"><button aria-pressed={mode === "geometry"} onClick={() => setMode("geometry")} disabled={hasPublishedSplats}>Geometry</button><button aria-pressed={mode === "splat"} onClick={() => setMode("splat")} disabled={readOnly && !hasPublishedSplats} title={readOnly && !hasPublishedSplats ? "No GPU-generated splats are published for this case." : undefined}>Splat</button></div>
            <div className="toolbar-spacer" /><button onClick={() => setView("orbit")} disabled={!scene}>Orbit</button><button onClick={() => setView("top")} disabled={!scene}>Top</button><button onClick={() => setView("reset")} disabled={!scene}>Reset view</button><span className="divider" /><label className="check"><input type="checkbox" checked={labels} onChange={event => setLabels(event.target.checked)} /> Labels</label>
          </div>}
          {scene ? <Suspense fallback={<div className="empty-viewport">Loading 3D viewport…</div>}><Viewport scene={scene} selected={selected} onSelect={select} mode={mode} isolated={isolated} labels={labels} playing={playing} speed={speed} cameraView={cameraView} strictAssets={hasPublishedSplats} /></Suspense> :
            publicReference && currentCase ? <div className="reference-viewport">
              <div className="reference-heading"><h2>{referenceProvenance}</h2><p>{pilot?.scene ? sceneError || "Loading published pilot view…" : "No reconstructed 3D scene is published for this reference."}</p></div>
              {sourceError ? <div className="source-placeholder" role="alert">Reference preview could not be loaded. Use Reload reference to try again.</div> :
                <figure className="reference-figure"><img key={currentCase.id} src={`${currentCase.source_url}?v=${refresh}`} alt={`${referenceProvenance} for ${currentCase.title}, public WebP preview`} onError={() => setSourceError(true)} />
                  <figcaption>{trial ? "Approved generated PNG test input, not a real-site photograph." : "Metadata-stripped public WebP preview. Full original kept private."} <a href={currentCase.source_url ?? undefined} target="_blank" rel="noreferrer">Open reference preview (new tab)</a></figcaption>
                </figure>}
            </div> :
            <div className="empty-viewport"><div className="empty-symbol" aria-hidden="true">◇</div><h2>{loading ? "Loading scene…" : "Scene not available"}</h2><p>{loading ? "Fetching the current case." : sceneError || "Select a case to begin."}</p>{!loading && canUpload && currentCase?.status === "awaiting_input" && <button onClick={() => fileInput.current?.click()} disabled={busy}>Choose source image</button>}</div>}
          <div className="viewport-footer"><span><span className="footer-dot" /> {scene ? `${scene.nodes.length} ${pilot?.status === "proposals" ? "region proposals" : "objects"} · ${scene.edges.length} routes` : publicReference ? "Reference only" : "No scene"}</span><span>{scene ? `${publicReference ? "Assumed units" : scene.units} · Y up` : publicReference ? "No published 3D reconstruction" : "Waiting for scene data"}</span></div>
        </section>
        <section className="flow-bar" aria-label="Illustrative flow controls"><div><h2>Illustrative flow</h2><p>Routes indicate relationships, not simulated activity.</p></div><div className="flow-controls"><button onClick={() => setPlaying(value => !value)} disabled={!scene || !scene.edges.length}>{playing ? "Pause" : "Play"}</button><label>Speed <select value={speed} onChange={event => setSpeed(Number(event.target.value))} disabled={!scene}><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option></select></label>{reducedMotion && <span className="muted">Reduced motion preferred</span>}</div></section>
      </main>
      <aside className="inspector" aria-label="Scene inspector">
        <section className="inspector-section"><div className="section-heading"><h2>Source</h2><span className="tag">{currentCase?.input_type || "—"}</span></div>
          {currentCase?.source_url && !sourceError ? <img className="source-image" src={`${currentCase.source_url}${currentCase.source_url.includes("?") ? "&" : "?"}v=${refresh}`} alt={`Source for ${currentCase.title}`} onError={() => setSourceError(true)} /> :
            <div className="source-placeholder">{currentCase?.input_type === "prompt" ? "Prompt-based scenario" : sourceError ? "Source image could not be loaded." : "Source image not supplied"}</div>}
          <p className="source-copy">{trial ? trial.definition.source.kind === "licensed-real-photograph" ? `Real photograph by ${trial.definition.source.creator}. Photograph and generated source-derived adaptations: ${trial.definition.source.license}. Layout, depth and scale are inferred, not measured.` : `${trial.definition.source.generator}. Synthetic photographic input, not an actual site photograph. Source and manual layout are separate from generated appearance.` : publicReference ? `${referenceProvenance} supplied by the user. Public WebP preview, not original bytes or an inferred 3D result.` : currentCase?.prompt || currentCase?.source_filename || (currentCase?.input_type === "prompt" ? currentCase.summary : readOnly ? "No public reference preview is available for this case." : "Upload the original image to connect source evidence.")}</p>
          {publicReference && currentCase?.source_url && <a className="reference-link" href={currentCase.source_url} target="_blank" rel="noreferrer">Open reference comparison (new tab)</a>}
          {sourceMetadata && <details className="source-copy"><summary>Source metadata for JSON import</summary><p>{sourceMetadata.filename}</p><p>SHA-256: {sourceMetadata.sha256}</p><p>Include this exact hash in scene.sources. Import saves immediately; export first to keep a local copy. Nodes and routes can be corrected in JSON while preserving semantic IDs.</p></details>}
          {metadataError && <p className="inline-error">{metadataError}</p>}
          {canUpload && <><input ref={fileInput} type="file" accept="image/*" className="visually-hidden" onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); }} aria-label="Source image file" />
          <button className="wide" onClick={() => fileInput.current?.click()} disabled={busy}>Upload source image</button></>}
        </section>
        <section className="inspector-section"><div className="section-heading"><h2>Objects</h2><span className="count">{scene?.nodes.length ?? 0}</span></div>
          {scene?.nodes.length ? <div className="object-list" aria-label="Select an object">{scene.nodes.map(node => <button key={node.id} className={`object-item ${selected === node.id ? "active" : ""}`} aria-pressed={selected === node.id} onClick={() => select(node.id)}><span className="object-glyph" aria-hidden="true">◇</span><span>{node.label}<small>{node.category} {!node.visible && "· hidden"}</small></span></button>)}</div> : <p className="muted">Objects appear when a scene is available.</p>}
        </section>
        <section className="inspector-section"><div className="section-heading"><h2>Object details</h2>{currentNode && <span className="tag">{currentNode.evidence.origin}</span>}</div>
          {currentNode ? <><h3 className="object-title">{currentNode.label}</h3><p className="object-id">{currentNode.id}</p>
            <label className="field-label" htmlFor="object-label">Label</label><input id="object-label" className="text-field" type="text" value={currentNode.label} readOnly={readOnly} disabled={busy} onChange={event => edit({ label: event.target.value })} />
            <div className="object-actions">{!readOnly && <button onClick={() => edit({ visible: !currentNode.visible })} disabled={busy}>{currentNode.visible ? "Hide" : "Show"}</button>}<button onClick={() => setIsolated(isolated === currentNode.id ? null : currentNode.id)} aria-pressed={isolated === currentNode.id}>{isolated === currentNode.id ? "Show all" : "Isolate"}</button></div>
            {isolated && !currentNode.visible && <p className="muted">This isolated object is hidden. Show it to see it in the viewport.</p>}
            <label className="field-label">Position <span>meters · Y up</span></label><div className="position-fields">{(["X", "Y", "Z"] as const).map((axis, index) => <label key={axis}>{axis}<input type="number" step="0.1" value={currentNode.position[index]} readOnly={readOnly} disabled={busy} onChange={event => { const value = event.currentTarget.valueAsNumber; if (Number.isFinite(value)) { const position = [...currentNode.position] as Vec3; position[index] = value; edit({ position }); } }} /></label>)}</div>
            <dl className="evidence"><div><dt>Evidence</dt><dd>{currentNode.evidence.origin}</dd></div><div><dt>Confidence</dt><dd>{Math.round(currentNode.evidence.confidence * 100)}%</dd></div><div><dt>Source ID</dt><dd>{currentNode.evidence.source_id || "Not linked"}</dd></div></dl><p className="evidence-note">{currentNode.evidence.note || "No evidence note provided."}</p>
            <label className="check review-check"><input type="checkbox" checked={currentNode.evidence.reviewed} disabled={readOnly || busy} onChange={event => edit({ evidence: { ...currentNode.evidence, reviewed: event.target.checked } })} /> {readOnly ? "Evidence reviewed" : "Evidence reviewed by me"}</label>
          </> : <p className="muted">Select an object in the list or viewport to inspect its evidence and position.</p>}
        </section>
        <section className="inspector-section"><div className="section-heading"><h2>Pipeline jobs</h2></div>{readOnly ? <p className="muted">{pilot ? "Published pilot snapshots only. Failed objects are not replaced with synthetic appearances; diagram boxes are unreviewed proposals, not reconstructed equipment. No jobs can run from this public viewer." : "Unavailable in the public demo. Procedural scenes use deterministic template geometry, not image reconstruction, Blender exports or Idol results. Run the local workbench to author scenes and execute pipeline stages."}</p> : <><p className="muted">Run a stage on this case. Tool and model access may be required.</p><div className="job-actions"><button onClick={() => void start("extract")} disabled={!caseId || busy}>Extract</button><button onClick={() => void start("blender")} disabled={!caseId || busy}>Blender</button><button onClick={() => void start("idol")} disabled={!caseId || busy}>Idol</button></div></>}
          {jobsError && <p className="inline-error" role="status">{jobsError}</p>}
          {!currentJobs.length && <p className="muted">No jobs for this case.</p>}
          {currentJobs.map(job => <div className="job" key={job.id}><div><strong>{job.stages.join(" → ")}</strong><span className={`job-status ${job.status}`}>{job.status}</span></div><small>{job.id}</small>{job.error && <p className="inline-error">{job.error}</p>}{activeJob(job) && <button onClick={() => void cancel(job.id)} disabled={busy}>Cancel</button>}</div>)}
          {currentJobs.some(job => job.status === "succeeded") && <p className="muted">Reload the scene to see completed output.</p>}
        </section>
      </aside>
    </div>
    <footer className="app-footer"><span>Scene Workbench</span><span>Interpretive layouts · Not engineering-certified</span></footer>
  </div>;
}
