import io
import logging
import os
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from .jobs import Runner
from .models import JobRequest, Scene
from .store import ConflictError, Store

MAX_UPLOAD = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000
logger = logging.getLogger(__name__)


def create_app(directory=None):
    store = Store(directory)
    runner = Runner(store)

    @asynccontextmanager
    async def lifespan(app):
        runner.start()
        yield
        runner.close()

    app = FastAPI(title="Scene Toolchain", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.runner = runner

    @app.middleware("http")
    async def reject_cross_origin_mutation(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            allowed = {
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:8000", "http://127.0.0.1:8000",
            }
            configured = os.environ.get("SCENE_WEB_ORIGIN")
            if configured:
                allowed.add(configured.rstrip("/"))
            if origin and origin not in allowed:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Cross-origin mutation is not allowed"}, status_code=403)
        return await call_next(request)

    def definition(case_id):
        try:
            return store.definition(case_id)
        except KeyError:
            raise HTTPException(404, "Unknown case") from None

    @app.get("/api/health")
    def health():
        return {"status": "ok", "gpu_execution": "separate_worker", "version": "0.1.0"}

    @app.get("/api/cases")
    def cases():
        return store.cases()

    @app.get("/api/cases/{case_id}/scene", response_model=Scene)
    def get_scene(case_id: str):
        definition(case_id)
        scene = store.current(case_id)
        if scene is None:
            raise HTTPException(409, "No scene exists yet. Upload the original image, then run extraction.")
        source = store.source(case_id)
        if source and store.current_source_hash(case_id) != source["sha256"]:
            raise HTTPException(409, "The uploaded source is newer than this scene. Run extraction or explicitly import a matching scene.")
        return scene

    @app.put("/api/cases/{case_id}/scene", response_model=Scene)
    def put_scene(case_id: str, scene: Scene):
        definition(case_id)
        if scene.case_id != case_id or scene.id != case_id:
            raise HTTPException(422, "Scene identity must match the case")
        try:
            with store.lock:
                source = store.source(case_id)
                existing = store.current(case_id)
                if source and not any(item.sha256 == source["sha256"] for item in scene.sources):
                    raise ConflictError("Imported scene must reference the uploaded source checksum")
                return store.save(scene, expected_revision=scene.revision if existing else 0, source_hash=source["sha256"] if source else None, manual=True)
        except ConflictError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/cases/{case_id}/revisions")
    def revisions(case_id: str):
        definition(case_id)
        with store.connect() as connection:
            rows = connection.execute("SELECT revision FROM revisions WHERE case_id=? ORDER BY revision DESC", (case_id,)).fetchall()
        return [row["revision"] for row in rows]

    @app.get("/api/cases/{case_id}/revisions/{revision}", response_model=Scene)
    def revision(case_id: str, revision: int):
        definition(case_id)
        with store.connect() as connection:
            row = connection.execute("SELECT body FROM revisions WHERE case_id=? AND revision=?", (case_id, revision)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown revision")
        return Scene.model_validate_json(row["body"])

    @app.post("/api/cases/{case_id}/source")
    async def upload_source(case_id: str, file: UploadFile = File(...)):
        case = definition(case_id)
        if case.input_type == "prompt":
            raise HTTPException(422, "Upload reference images into I01-I05 or G01-G03, not a description case")
        content = bytearray()
        while chunk := await file.read(65536):
            content.extend(chunk)
            if len(content) > MAX_UPLOAD:
                raise HTTPException(413, "Source image exceeds the 12 MiB limit")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = Image.open(io.BytesIO(content))
                if image.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("Only JPEG, PNG and WebP image content is supported")
                image.load()
                preview = ImageOps.exif_transpose(image).convert("RGB")
                output = io.BytesIO()
                preview.save(output, format="PNG")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
            raise HTTPException(422, f"Invalid source image: {error}") from error
        filename = Path((file.filename or "source").replace("\\", "/")).name[:200]
        store.save_source(case_id, bytes(content), output.getvalue(), filename)
        return next(item for item in store.cases() if item.id == case_id)

    @app.get("/api/cases/{case_id}/source")
    def source(case_id: str):
        definition(case_id)
        value = store.source(case_id)
        if not value:
            raise HTTPException(404, "Original source has not been uploaded")
        return FileResponse(value["preview_path"], media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/api/cases/{case_id}/source-metadata")
    def source_metadata(case_id: str):
        definition(case_id)
        value = store.source(case_id)
        if not value:
            raise HTTPException(404, "Original source has not been uploaded")
        with Image.open(value["preview_path"]) as image:
            width, height = image.size
        return {"sha256": value["sha256"], "filename": value["filename"], "width": width, "height": height}

    @app.get("/api/assets/{relative:path}")
    def asset(relative: str):
        try:
            path = store.asset_path(relative)
        except ValueError as error:
            raise HTTPException(403, str(error)) from error
        if not path.is_file() or path.suffix not in (".ply", ".glb", ".png", ".json"):
            raise HTTPException(404, "Unknown scene asset")
        return FileResponse(path)

    @app.post("/api/cases/{case_id}/jobs", status_code=202)
    def start_job(case_id: str, request: JobRequest):
        definition(case_id)
        return runner.submit(case_id, request.stages)

    @app.get("/api/jobs")
    def jobs():
        return store.jobs()

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        try:
            return store.job(job_id)
        except KeyError:
            raise HTTPException(404, "Unknown job") from None

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        try:
            current = store.job(job_id)
        except KeyError:
            raise HTTPException(404, "Unknown job") from None
        if current["status"] in ("succeeded", "failed", "cancelled"):
            raise HTTPException(409, "Job is already terminal")
        store.update_job(job_id, cancel_requested=1)
        return store.job(job_id)

    return app


app = create_app()
