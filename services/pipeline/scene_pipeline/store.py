import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Case, Scene
from .templates import compile_prompt

ROOT = Path(__file__).resolve().parents[3]


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, directory: str | Path | None = None):
        self.root = Path(directory or os.environ.get("SCENE_DATA_DIR", ROOT / ".scene-data")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "assets").mkdir(exist_ok=True)
        (self.root / "sources").mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.database = self.root / "scene.sqlite3"
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS scenes (
                    case_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    body TEXT NOT NULL, source_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    case_id TEXT, revision INTEGER, body TEXT NOT NULL,
                    PRIMARY KEY (case_id, revision)
                );
                CREATE TABLE IF NOT EXISTS edited_scenes (case_id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS sources (
                    case_id TEXT PRIMARY KEY, original_path TEXT NOT NULL,
                    preview_path TEXT NOT NULL, sha256 TEXT NOT NULL,
                    filename TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status TEXT NOT NULL,
                    stages TEXT NOT NULL, result TEXT, error TEXT,
                    created_at TEXT NOT NULL, source_hash TEXT, expected_revision INTEGER,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
            """)
        self.definitions = {
            entry["id"]: Case.model_validate(entry)
            for entry in json.loads((ROOT / "cases" / "manifest.json").read_text())
        }
        with self.lock:
            for case in self.definitions.values():
                if case.input_type == "prompt" and self.current(case.id) is None:
                    self.save(compile_prompt(case))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def definition(self, case_id):
        if case_id not in self.definitions:
            raise KeyError(case_id)
        return self.definitions[case_id]

    def source(self, case_id):
        self.definition(case_id)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sources WHERE case_id=?", (case_id,)).fetchone()
        return dict(row) if row else None

    def cases(self):
        result = []
        for case in self.definitions.values():
            source = self.source(case.id)
            result.append(case.model_copy(update={
                "status": "ready" if case.input_type == "prompt" or source else "awaiting_input",
                "source_url": f"/api/cases/{case.id}/source" if source else None,
                "source_filename": source["filename"] if source else case.source_filename,
            }))
        return result

    def current(self, case_id) -> Scene | None:
        self.definition(case_id)
        with self.connect() as connection:
            row = connection.execute("SELECT body FROM scenes WHERE case_id=?", (case_id,)).fetchone()
        return Scene.model_validate_json(row["body"]) if row else None

    def current_source_hash(self, case_id):
        with self.connect() as connection:
            row = connection.execute("SELECT source_hash FROM scenes WHERE case_id=?", (case_id,)).fetchone()
        return row["source_hash"] if row else None

    def has_manual_edits(self, case_id):
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM edited_scenes WHERE case_id=?", (case_id,)).fetchone() is not None

    def save(self, scene: Scene, expected_revision=None, source_hash=None, manual=False):
        self.definition(scene.case_id)
        with self.lock, self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision,source_hash FROM scenes WHERE case_id=?", (scene.case_id,)).fetchone()
            current_revision = row["revision"] if row else 0
            if expected_revision is not None and current_revision != expected_revision:
                raise ConflictError(f"Scene changed from revision {expected_revision} to {current_revision}; reload before saving")
            updated = scene.model_copy(update={"revision": current_revision + 1})
            body = updated.model_dump_json()
            if source_hash is None and row:
                source_hash = row["source_hash"]
            connection.execute(
                "INSERT INTO scenes VALUES (?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET revision=excluded.revision,body=excluded.body,source_hash=excluded.source_hash",
                (scene.case_id, updated.revision, body, source_hash),
            )
            connection.execute("INSERT INTO revisions VALUES (?,?,?)", (scene.case_id, updated.revision, body))
            if manual:
                connection.execute("INSERT OR IGNORE INTO edited_scenes VALUES (?)", (scene.case_id,))
        return updated

    def save_source(self, case_id, content: bytes, preview: bytes, filename: str):
        case = self.definition(case_id)
        if case.input_type == "prompt":
            raise ValueError("Use an image case for image uploads; prompt cases preserve their description input")
        checksum = hashlib.sha256(content).hexdigest()
        folder = self.root / "sources" / case_id / checksum
        folder.mkdir(parents=True, exist_ok=True)
        original = folder / "original"
        display = folder / "preview.png"
        original.write_bytes(content)
        display.write_bytes(preview)
        with self.lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO sources VALUES (?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET original_path=excluded.original_path,preview_path=excluded.preview_path,sha256=excluded.sha256,filename=excluded.filename",
                (case_id, str(original), str(display), checksum, filename),
            )
        return checksum

    def create_job(self, identifier, case_id, stages):
        scene = self.current(case_id)
        source = self.source(case_id)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs (id,case_id,status,stages,created_at,source_hash,expected_revision) VALUES (?,?,?,?,?,?,?)",
                (identifier, case_id, "queued", json.dumps(stages),
                 datetime.now(timezone.utc).isoformat(), source["sha256"] if source else None,
                 scene.revision if scene else 0),
            )
        return self.job(identifier)

    def job(self, identifier):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise KeyError(identifier)
        job = dict(row)
        for field in ("stages", "result"):
            job[field] = json.loads(job[field]) if job[field] else None
        return job

    def jobs(self):
        with self.connect() as connection:
            ids = connection.execute("SELECT id FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
        return [self.job(row["id"]) for row in ids]

    def update_job(self, identifier, **fields):
        allowed = {"status", "result", "error", "cancel_requested"}
        if not fields or set(fields) - allowed:
            raise ValueError("Invalid job update")
        values = [json.dumps(value) if key == "result" and value is not None else value for key, value in fields.items()]
        with self.connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {','.join(key + '=?' for key in fields)} WHERE id=?",
                (*values, identifier),
            )

    def asset_path(self, relative):
        root = (self.root / "assets").resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Asset path is outside storage")
        return path
