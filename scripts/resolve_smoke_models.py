"""Verify gated config access and emit only approved immutable model pins."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

MODELS = {
    "idol_revision": "speridlabs/idol",
    "dinov3_revision": "facebook/dinov3-vith16plus-pretrain-lvd1689m",
    "flux2_revision": "black-forest-labs/FLUX.2-dev",
    "detector_revision": "IDEA-Research/grounding-dino-tiny",
    "segmenter_revision": "facebook/sam2.1-hiera-small",
}


class ReadinessError(RuntimeError):
    pass


def resolve_models(api, download, token, cache):
    pins = {}
    for output, repository in MODELS.items():
        revision = api.model_info(repo_id=repository, token=token).sha
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ReadinessError(f"{repository}: immutable model revision unavailable")
        pins[output] = revision
    for output, filename in (
        ("dinov3_revision", "config.json"),
        ("flux2_revision", "vae/config.json"),
        ("idol_revision", "config.json"),
    ):
        repository = MODELS[output]
        path = download(
            repo_id=repository, filename=filename, revision=pins[output],
            token=token, cache_dir=cache, force_download=True,
        )
        config = json.loads(Path(path).read_text())
        if not isinstance(config, dict):
            raise ReadinessError(f"{repository}: invalid downloaded config")
        if output == "idol_revision" and config.get("image_encoders") != {
            "dinov3": MODELS["dinov3_revision"],
            "flux2_vae": MODELS["flux2_revision"],
        }:
            raise ReadinessError("speridlabs/idol: encoder repositories differ from the approved gates")
    return pins


def main():
    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.errors import HfHubHTTPError
    from requests.exceptions import RequestException

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF readiness failed: HF_TOKEN secret is missing.", file=sys.stderr)
        return 1
    if os.environ.get("REQUIRE_GPU_RUNNER") == "true" and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", os.environ.get("RUNNER_LABEL", "")
    ):
        print("HF readiness failed: configure the isolated SCENE_GPU_RUNNER label.", file=sys.stderr)
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="scene-model-gates-") as cache:
            pins = resolve_models(HfApi(), hf_hub_download, token, cache)
    except HfHubHTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        print(f"HF readiness failed: model metadata/config request HTTP {status}. Check token scope and accepted model terms; no GPU work queued.", file=sys.stderr)
        return 1
    except (RequestException, OSError, ValueError, ReadinessError):
        print("HF readiness failed: model config/pin verification unavailable. No GPU work queued; service responses were suppressed.", file=sys.stderr)
        return 1
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        for output, revision in pins.items():
            stream.write(f"{output}={revision}\n")
            print(f"{MODELS[output]} {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
