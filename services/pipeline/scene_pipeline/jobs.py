import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .extract import PrerequisiteError, extract_diagram, extract_photo
from .gaussians import validate_ply
from .models import Asset, Scene
from .store import ROOT, ConflictError
from .templates import compile_prompt

logger = logging.getLogger(__name__)


class CancelledError(RuntimeError):
    pass


class Runner:
    def __init__(self, store):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scene-worker")
        self.stopping = False

    def start(self):
        for job in self.store.jobs():
            if job["status"] == "running":
                self.store.update_job(job["id"], status="failed", error="Worker was interrupted; retry the job. Existing revisions were preserved.")
            elif job["status"] == "queued":
                self.executor.submit(self.execute, job["id"])

    def close(self):
        self.stopping = True
        self.executor.shutdown(wait=True, cancel_futures=False)

    def submit(self, case_id, stages):
        identifier = uuid.uuid4().hex
        job = self.store.create_job(identifier, case_id, stages)
        self.executor.submit(self.execute, identifier)
        return job

    def check_cancelled(self, identifier):
        if self.stopping or self.store.job(identifier)["cancel_requested"]:
            raise CancelledError("Job cancelled; completed scene revisions remain available")

    def command(self, identifier, arguments, output, timeout=600):
        self.check_cancelled(identifier)
        output.mkdir(parents=True, exist_ok=True)
        log_path = output / f"command-{uuid.uuid4().hex[:8]}.log"
        with log_path.open("w+") as log:
            process = subprocess.Popen(arguments, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
            began = time.monotonic()
            try:
                while process.poll() is None:
                    self.check_cancelled(identifier)
                    if time.monotonic() - began > timeout:
                        raise TimeoutError(f"Stage exceeded its {timeout}-second limit")
                    time.sleep(.2)
            except BaseException:
                # The child may itself launch render/model subprocesses.
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
            if process.returncode:
                log.seek(0)
                diagnostic = log.read()[-6000:]
                raise RuntimeError(f"Stage command exited {process.returncode}:\n{diagnostic}")

    def execute(self, identifier):
        job = self.store.job(identifier)
        if job["status"] != "queued":
            return
        result = {"stages": [], "artifacts": [], "warnings": []}
        try:
            self.check_cancelled(identifier)
            self.store.update_job(identifier, status="running")
            case = self.store.definition(job["case_id"])
            source = self.store.source(case.id)
            source_hash = source["sha256"] if source else None
            if source_hash != job["source_hash"]:
                raise ConflictError("Source changed after the job was queued; submit a new job")
            scene = self.store.current(case.id)
            revision = scene.revision if scene else 0
            if revision != job["expected_revision"]:
                raise ConflictError("Scene changed after the job was queued; submit a new job")
            folder = self.store.asset_path(f"{case.id}/{identifier}")
            folder.mkdir(parents=True, exist_ok=True)
            for stage in job["stages"]:
                self.check_cancelled(identifier)
                started = time.monotonic()
                if stage == "extract":
                    if self.store.has_manual_edits(case.id):
                        raise ConflictError("Extraction would replace an existing edited/generated revision. Export it and explicitly import a new scene instead; automatic overwrite is disabled.")
                    if case.input_type == "prompt":
                        scene = compile_prompt(case)
                    else:
                        if not source:
                            raise PrerequisiteError("Original source image is missing; upload it before extraction")
                        scene, report = (
                            extract_diagram(case, source, folder / "extraction")
                            if case.input_type in ("diagram", "plan")
                            else extract_photo(case, source, folder / "extraction")
                        )
                        result["extraction"] = report
                    self.check_cancelled(identifier)
                    scene = self.publish(scene, revision, source_hash)
                    revision = scene.revision
                elif stage == "blender":
                    if scene is None:
                        raise PrerequisiteError("No scene exists; extract the source first")
                    binary = os.environ.get("BLENDER_BIN") or shutil.which("blender")
                    if not binary or not Path(binary).is_file():
                        raise PrerequisiteError("Blender is unavailable; install it or set BLENDER_BIN to an executable")
                    snapshot = folder / "scene-input.json"
                    snapshot.write_text(scene.model_dump_json(indent=2))
                    self.command(identifier, [binary, "--background", "--python", str(ROOT / "blender" / "build_scene.py"), "--", "--scene", str(snapshot), "--out", str(folder / "blender")], folder)
                    glb = folder / "blender" / "scene.glb"
                    if not glb.is_file() or glb.read_bytes()[:4] != b"glTF":
                        raise ValueError("Blender did not produce a valid GLB")
                    relative = glb.relative_to(self.store.root / "assets").as_posix()
                    asset = Asset(id=f"mesh-{identifier}", kind="glb", uri=f"/api/assets/{relative}", sha256=hashlib.sha256(glb.read_bytes()).hexdigest(), provenance={"scene_revision": revision, "coordinates": "right-handed-y-up"})
                    updated = scene.model_copy(deep=True)
                    updated.assets = [a for a in updated.assets if not (a.kind == "glb" and a.node_id is None)] + [asset]
                    scene = self.publish(Scene.model_validate(updated.model_dump()), revision, source_hash)
                    revision = scene.revision
                    result["artifacts"].append(asset.model_dump())
                elif stage == "idol":
                    if scene is None:
                        raise PrerequisiteError("No scene exists; extract/build the source first")
                    candidate = next((node for node in scene.nodes if node.visible and node.category not in ("ground", "fence", "vegetation", "control")), None)
                    if candidate is None:
                        raise ValueError("No suitable visible object candidate exists for Idol")
                    image = self.reference_for(case.id, candidate.id, folder)
                    destination = folder / "idol"
                    self.command(identifier, [sys.executable, "-m", "scene_pipeline.idol_worker", "--image", str(image), "--out", str(destination), "--mode", "real" if case.input_type == "photo" else "synthetic"], folder, timeout=1800)
                    metadata = json.loads((destination / "generation.json").read_text())
                    ply = destination / "object.ply"
                    metadata.update(validate_ply(ply))
                    relative = ply.relative_to(self.store.root / "assets").as_posix()
                    asset = Asset(id=f"splat-{identifier}", kind="ply", uri=f"/api/assets/{relative}", sha256=metadata["sha256"], node_id=candidate.id, provenance=metadata)
                    updated = scene.model_copy(deep=True)
                    previous_asset = next(node.asset_id for node in updated.nodes if node.id == candidate.id)
                    updated.assets = [a for a in updated.assets if a.id != previous_asset] + [asset]
                    for node in updated.nodes:
                        if node.id == candidate.id:
                            node.asset_id = asset.id
                    scene = self.publish(Scene.model_validate(updated.model_dump()), revision, source_hash)
                    revision = scene.revision
                    result["artifacts"].append(asset.model_dump())
                result["stages"].append({"stage": stage, "seconds": time.monotonic() - started, "revision": revision})
                self.store.update_job(identifier, result=result)
            self.check_cancelled(identifier)
            (folder / "scene.json").write_text(scene.model_dump_json(indent=2))
            (folder / "report.json").write_text(json.dumps(result, indent=2))
            self.store.update_job(identifier, status="succeeded", result=result)
        except CancelledError as error:
            self.store.update_job(identifier, status="cancelled", error=str(error), result=result)
        except Exception as error:
            logger.exception("Scene job %s failed", identifier)
            self.store.update_job(identifier, status="failed", error=str(error), result=result)

    def assert_source(self, case_id, expected):
        source = self.store.source(case_id)
        if (source["sha256"] if source else None) != expected:
            raise ConflictError("Source changed during processing; stale results were not published")

    def publish(self, scene, revision, source_hash):
        with self.store.lock:
            self.assert_source(scene.case_id, source_hash)
            return self.store.save(scene, expected_revision=revision, source_hash=source_hash)

    def reference_for(self, case_id, node_id, current_folder):
        # Images are tied to the exact source hash or scene revision via the
        # successful job snapshot; never reuse an arbitrary similarly named crop.
        current = self.store.current(case_id)
        source = self.store.source(case_id)
        for job in self.store.jobs():
            if job["case_id"] != case_id or job["status"] != "succeeded":
                continue
            folder = self.store.asset_path(f"{case_id}/{job['id']}")
            if source and job["source_hash"] == source["sha256"]:
                crop = folder / "extraction" / f"{node_id}.png"
                if crop.is_file():
                    return crop
            snapshot = folder / "scene-input.json"
            if snapshot.is_file():
                previous = Scene.model_validate_json(snapshot.read_text())
                previous_node = next((node for node in previous.nodes if node.id == node_id), None)
                current_node = next((node for node in current.nodes if node.id == node_id), None)
                if previous_node and current_node and previous_node.model_dump(exclude={"asset_id"}) == current_node.model_dump(exclude={"asset_id"}):
                    crop = folder / "blender" / "references" / f"{node_id}.png"
                    if crop.is_file():
                        return crop
        crop = current_folder / "blender" / "references" / f"{node_id}.png"
        if crop.is_file():
            return crop
        crop = current_folder / "extraction" / f"{node_id}.png"
        if crop.is_file():
            return crop
        raise PrerequisiteError(f"No valid isolated reference for {node_id}; run Blender or photo extraction first")
