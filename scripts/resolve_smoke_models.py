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
# Actual successful private smoke 43011155168; batch retries must not float to main.
I02_BATCH_REVISIONS = {
    "idol_revision": "2731c2291fc65a797c5cb627a5e5526fc1490902",
    "dinov3_revision": "c807c9eeea853df70aec4069e6f56b28ddc82acc",
    "flux2_revision": "26afe3a78bb242c0a8bb181dcc8937bb16e5c66c",
    "detector_revision": "a2bb814dd30d776dcf7e30523b00659f4f141c71",
    "segmenter_revision": "ee5bba1d82bb8749febdf90f45e84b687142ba03",
}


class ReadinessError(RuntimeError):
    pass


def resolve_models(api, download, token, cache, revisions=None):
    pins = {}
    for output, repository in MODELS.items():
        arguments = {"repo_id": repository, "token": token}
        if revisions is not None:
            arguments["revision"] = revisions[output]
        revision = api.model_info(**arguments).sha
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ReadinessError(f"{repository}: immutable model revision unavailable")
        if revisions is not None and revision != revisions[output]:
            raise ReadinessError(f"{repository}: verified batch revision changed")
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
    if os.environ.get("PACKAGE_ONLY") == "true" and os.environ.get("PUBLISH_PILOTS") != "true":
        print("Package-only readiness failed: explicit publish_pilots approval is required.", file=sys.stderr)
        return 1
    if os.environ.get("PUBLISH_PILOTS") == "true" and os.environ.get("SMOKE_SOURCE") != "public-preview":
        print("Publication readiness failed: select the explicitly approved public-preview source route.", file=sys.stderr)
        return 1
    if not token:
        print("HF readiness failed: HF_TOKEN secret is missing.", file=sys.stderr)
        return 1
    if os.environ.get("REQUIRE_GPU_RUNNER") == "true" and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", os.environ.get("RUNNER_LABEL", "")
    ):
        print("HF readiness failed: configure the isolated SCENE_GPU_RUNNER label.", file=sys.stderr)
        return 1
    if os.environ.get("I02_OBJECT_BATCH") == "true" and os.environ.get("SMOKE_SOURCE") not in ("private-original", "public-preview"):
        print("I02 batch readiness failed: choose private-original or explicitly approved public-preview; no GPU work queued.", file=sys.stderr)
        return 1
    if os.environ.get("I02_OBJECT_BATCH") == "true":
        cases = os.environ.get("PILOT_CASES", "I02").split()
        trial = os.environ.get("TRIAL_BATCH") == "true"
        allowed = ("T01", "T02", "T03", "R01", "R02", "R03") if trial else ("I01", "I02", "I03", "I04", "I05", "G01", "G02", "G03")
        if trial and os.environ.get("TRIAL_VARIANTS") not in ("both", "baseline", "optimized"):
            print("Select baseline, optimized or both trial variants.", file=sys.stderr)
            return 1
        if not cases or len(cases) != len(set(cases)) or any(case not in allowed for case in cases):
            print("Pilot batch readiness failed: use unique I01-I05/G01-G03 case IDs; no GPU work queued.", file=sys.stderr)
            return 1
    try:
        with tempfile.TemporaryDirectory(prefix="scene-model-gates-") as cache:
            pins = resolve_models(
                HfApi(), hf_hub_download, token, cache,
                I02_BATCH_REVISIONS if os.environ.get("I02_OBJECT_BATCH") == "true" or os.environ.get("ILLUSTRATION_BATCH") == "true" else None,
            )
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
