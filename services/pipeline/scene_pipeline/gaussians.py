import hashlib
from pathlib import Path

import numpy as np


def validate_ply(path: Path):
    required = {"x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
                "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"}
    with path.open("rb") as stream:
        header = []
        for _ in range(128):
            line = stream.readline(512)
            if not line.endswith(b"\n"):
                raise ValueError("Invalid or oversized Gaussian PLY header")
            text = line.decode("ascii").strip()
            header.append(text)
            if text == "end_header":
                break
        else:
            raise ValueError("Gaussian PLY header is too long")
        if header[0] != "ply" or "format binary_little_endian 1.0" not in header:
            raise ValueError("Expected standard binary little-endian Idol Gaussian PLY")
        count = None
        properties = []
        for line in header:
            if line.startswith("element vertex "):
                count = int(line.rsplit(" ", 1)[1])
            elif line.startswith("element "):
                raise ValueError("Unexpected extra PLY elements")
            elif line.startswith("property "):
                parts = line.split()
                if len(parts) != 3 or parts[1] not in ("float", "float32"):
                    raise ValueError("Expected floating-point Gaussian properties")
                properties.append(parts[2])
        if count is None or not 1 <= count <= 1_048_576 or not required.issubset(properties):
            raise ValueError("Missing or invalid Gaussian PLY properties/count")
        if len(set(properties)) != len(properties):
            raise ValueError("Duplicate Gaussian PLY properties")
        data = np.frombuffer(stream.read(), dtype=np.dtype([(name, "<f4") for name in properties]))
    if len(data) != count:
        raise ValueError("Gaussian PLY payload length does not match header")
    for name in properties:
        if not np.isfinite(data[name]).all():
            raise ValueError(f"Nonfinite Gaussian property: {name}")
    scales = np.column_stack([data[f"scale_{axis}"] for axis in range(3)])
    if np.any(scales < -30) or np.any(scales > 10):
        raise ValueError("Implausible Gaussian log-scale")
    rotations = np.column_stack([data[f"rot_{axis}"] for axis in range(4)])
    if not np.allclose(np.linalg.norm(rotations, axis=1), 1, atol=.03):
        raise ValueError("Gaussian rotations are not normalized")
    minimum = [float(data[name].min()) for name in ("x", "y", "z")]
    maximum = [float(data[name].max()) for name in ("x", "y", "z")]
    if any(hi - lo <= 1e-8 or abs(lo) > 100 or abs(hi) > 100 for lo, hi in zip(minimum, maximum)):
        raise ValueError("Degenerate or implausible Gaussian bounds")
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "gaussian_count": count,
        "bounds": {"min": minimum, "max": maximum},
        "coordinates": "right-handed-y-up",
    }
