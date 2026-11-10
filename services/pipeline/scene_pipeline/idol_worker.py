import argparse
import hashlib
import json
import os
from pathlib import Path

from .extract import PrerequisiteError
from .gaussians import validate_ply

SDK_REVISION = "8db700349a5570aac390e4780fa32e3eed6b587a"


def generate(image: Path, destination: Path, mode="synthetic", seed=42, count=32768):
    if not image.is_file():
        raise ValueError(f"Reference image does not exist: {image.name}")
    if not 32768 <= count <= 1048576 or count % 32:
        raise ValueError("Idol count must be 32,768..1,048,576 and a multiple of 32")
    weights_revision = os.environ.get("SCENE_IDOL_MODEL_REVISION")
    if not weights_revision:
        raise PrerequisiteError("Pin SCENE_IDOL_MODEL_REVISION to the exact speridlabs/idol model commit")
    try:
        import torch
        from huggingface_hub import HfApi, hf_hub_download, snapshot_download
        from idol import IdolPipeline
    except ImportError as error:
        raise PrerequisiteError("Install the pinned Idol SDK and its declared dependencies in the GPU worker; see requirements-idol.txt") from error
    if not torch.cuda.is_available():
        raise PrerequisiteError("CUDA GPU is unavailable; configure the remote GPU worker instead of reporting synthetic success")
    dtype = "bf16" if torch.cuda.is_bf16_supported() else "fp32"
    if not all(len(value) == 40 and all(character in "0123456789abcdef" for character in value) for value in [weights_revision]):
        raise PrerequisiteError("SCENE_IDOL_MODEL_REVISION must be a full lowercase 40-character commit SHA")
    config_path = hf_hub_download("speridlabs/idol", "config.json", revision=weights_revision)
    config = json.loads(Path(config_path).read_text())
    # Encoder repository names in a weights config are not immutable pins.
    encoder_overrides = {}
    for key, environment in (("dinov3", "SCENE_DINOV3_REVISION"), ("flux2_vae", "SCENE_FLUX2_REVISION")):
        revision = os.environ.get(environment)
        if not revision or len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
            raise PrerequisiteError(f"Pin {environment} before loading gated encoders")
        repository = config["image_encoders"][key]
        HfApi().auth_check(repo_id=repository, repo_type="model")
        patterns = (
            ["config.json", "preprocessor_config.json", "model.safetensors",
             "model.safetensors.index.json", "model-*.safetensors"]
            if key == "dinov3" else ["vae/*.json", "vae/*.safetensors"]
        )
        encoder_overrides[key] = snapshot_download(repository, revision=revision, allow_patterns=patterns)
    model_path = snapshot_download("speridlabs/idol", revision=weights_revision, allow_patterns=[
        "config.json", "denoiser.safetensors", "decoder.safetensors",
        "decoder_gs.safetensors", "birefnet.safetensors",
    ])
    os.environ.setdefault("ATTN_BACKEND", "sdpa")
    pipeline = IdolPipeline.from_pretrained(
        model_path, device="cuda", dinov3_dtype=dtype,
        optimize=os.environ.get("SCENE_IDOL_COMPILE", "0") == "1",
        image_encoders=encoder_overrides,
    )
    output = pipeline(str(image), mode=mode, seed=seed, steps=50, num_gaussians=count)
    destination.mkdir(parents=True, exist_ok=True)
    ply = destination / "object.ply"
    output.gaussian.save_ply(str(ply))
    output.preprocessed_image.save(destination / "input.png")
    metadata = {
        **validate_ply(ply), "model": "speridlabs/idol",
        "input_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "model_revision": weights_revision, "sdk_revision": SDK_REVISION,
        "mode": mode, "seed": seed, "steps": 50, "dinov3_dtype": dtype,
        "camera": output.camera,
        "encoder_revisions": {key: os.environ[key] for key in ("SCENE_DINOV3_REVISION", "SCENE_FLUX2_REVISION")},
    }
    (destination / "generation.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("real", "synthetic"), default="synthetic")
    parser.add_argument("--count", type=int, default=32768)
    arguments = parser.parse_args()
    generate(arguments.image, arguments.out, arguments.mode, count=arguments.count)


if __name__ == "__main__":
    main()
