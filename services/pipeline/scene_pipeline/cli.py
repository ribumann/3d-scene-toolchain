import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from .jobs import Runner
from .models import Scene
from .store import Store


def preflight():
    dependencies = {}
    for name in ("blender", "tesseract", "az", "nvidia-smi"):
        dependencies[name] = shutil.which(name)
    gpu = None
    if dependencies["nvidia-smi"]:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout.strip()
    return {
        "tools": dependencies, "gpu": gpu,
        "model_access_configured": bool(os.environ.get("HF_TOKEN")),
        "pins_configured": {key: bool(os.environ.get(key)) for key in (
            "SCENE_IDOL_MODEL_REVISION", "SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION",
            "SCENE_DETECTOR_REVISION", "SCENE_SEGMENTER_REVISION",
        )},
        "note": "Credential presence is not access verification; model licenses and CUDA inference still require smoke tests.",
    }


def main():
    parser = argparse.ArgumentParser(description="Reproducible hybrid scene pipeline")
    parser.add_argument("--data-dir", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    commands.add_parser("schema")
    commands.add_parser("cases")
    export = commands.add_parser("export")
    export.add_argument("case_id")
    export.add_argument("--out", type=Path, required=True)
    batch = commands.add_parser("run")
    batch.add_argument("--cases", nargs="+", default=["P01", "P02", "P03"])
    batch.add_argument("--stages", nargs="+", choices=("extract", "blender", "idol"), default=["extract"])
    batch.add_argument("--report", type=Path, required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    if arguments.command == "schema":
        print(json.dumps(Scene.model_json_schema(), indent=2))
        return
    if arguments.command == "preflight":
        print(json.dumps(preflight(), indent=2))
        return
    if arguments.command == "serve":
        if arguments.data_dir:
            os.environ["SCENE_DATA_DIR"] = str(arguments.data_dir.resolve())
        import uvicorn
        uvicorn.run("scene_pipeline.api:app", host="127.0.0.1", port=arguments.port)
        return
    store = Store(arguments.data_dir)
    if arguments.command == "cases":
        print(json.dumps([case.model_dump() for case in store.cases()], indent=2))
    elif arguments.command == "export":
        scene = store.current(arguments.case_id)
        if scene is None:
            parser.error("Case has no scene; supply its source and extract it first")
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(scene.model_dump_json(indent=2))
    elif arguments.command == "run":
        from .models import JobRequest
        JobRequest(stages=arguments.stages)
        runner = Runner(store)
        results = []
        try:
            for case_id in arguments.cases:
                identifier = uuid.uuid4().hex
                store.create_job(identifier, case_id, arguments.stages)
                runner.execute(identifier)
                results.append(store.job(identifier))
        finally:
            runner.close()
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(json.dumps(results, indent=2))
        print(json.dumps([{"case_id": job["case_id"], "status": job["status"], "error": job["error"]} for job in results], indent=2))
        if any(job["status"] != "succeeded" for job in results):
            sys.exit(1)


if __name__ == "__main__":
    main()
