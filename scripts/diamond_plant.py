"""Authored module-level diamond plant twin; never inferred engineering geometry."""

import argparse
import hashlib
import html
import json
import math
from pathlib import Path

from PIL import Image

from scene_pipeline.models import Asset, Case, Edge, Evidence, Node, Scene, Source
from scripts.plant_geometry import glb
from scripts.trial_contracts import TrialManifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "25070e70285e9228ab4453dbd0cf70a844a11922"
SOURCE = ROOT / "inputs/diamond-plant/D01.png"
ASSUMPTION = "Authored simulation dimensions and topology, not camera-calibrated measurements or recovered hidden equipment."
TYPES = {
    "crusher": ("Crushing / feed preparation", [8, 7, 7], [.19, .62, .108, .173], -27),
    "scrubber": ("Rotary scrubber", [12, 5, 7], [.295, .648, .128, .126], -13),
    "screen": ("Wet sizing screen", [10, 5, 7], [.433, .675, .106, .124], 0),
    "dms": ("Dense-medium separation", [8, 12, 8], [.536, .599, .080, .217], 12),
    "medium": ("Drain / rinse / medium recovery", [12, 6, 8], [.623, .631, .146, .174], 25),
    "sorter": ("Enclosed X-ray sorting", [6, 4, 5], [.820, .685, .072, .107], 37),
    "hopper": ("Shared raw-feed hopper", [8, 7.6, 8], [.015, .382, .110, .205], -44),
    "thickener": ("Water-recovery thickener", [16, 6, 16], [.339, .027, .181, .154], -7),
    "water": ("Process-water tank", [6, 7, 6], [.533, .036, .069, .131], 8),
    "lab": ("Secure recovery / inspection lab", [6, 6, 11], [.897, .349, .096, .178], 47),
    "control": ("Electrical / control hut", [8, 4.4, 5], [.357, .825, .082, .080], -5),
    "tailings": ("Tailings handling zone", [14, 4, 12], [.797, .080, .137, .180], 39),
}
LINE_KINDS = tuple(TYPES)[:6]
SHARED_Z = {"hopper": 0, "thickener": -29, "water": -28, "lab": 0, "control": 31, "tailings": -29}
COMPONENTS = {
    "crusher": ("feeder", "crusher-drive", "bearing"),
    "scrubber": ("drum-drive", "wash-pump"),
    "screen": ("exciter", "spray-manifold"),
    "dms": ("feed-pump", "density-meter", "cyclone-bank"),
    "medium": ("magnetic-separator", "medium-pump", "rinse-screen", "level-sensor"),
    "sorter": ("feed-belt", "xray-enclosure", "reject-actuator"),
    "hopper": ("level-sensor", "distributor"),
    "thickener": ("rake-drive", "underflow-pump", "level-sensor"),
    "water": ("level-sensor", "supply-pump"),
    "lab": ("product-scale", "secure-inventory"),
    "control": ("plc", "power-meter"),
    "tailings": ("sump-pump", "inventory"),
}
METRICS = {
    "motor_current": ("A", [0, 250]), "bearing_temperature": ("Cel", [15, 110]),
    "vibration_rms": ("mm/s", [0, 20]), "ore_flow": ("t/h", [0, 150]),
    "water_flow": ("m3/h", [0, 300]), "level": ("%", [0, 100]),
    "medium_density": ("kg/m3", [2000, 3500]), "feed_pressure": ("kPa", [0, 600]),
    "product_mass": ("g", [0, 1000]), "power": ("kW", [0, 500]),
}
KIND_METRICS = {
    "crusher": ("motor_current", "bearing_temperature", "vibration_rms", "ore_flow"),
    "scrubber": ("motor_current", "water_flow"),
    "screen": ("vibration_rms", "water_flow"),
    "dms": ("medium_density", "feed_pressure", "motor_current"),
    "medium": ("motor_current", "level"),
    "sorter": ("ore_flow", "motor_current"),
    "hopper": ("level", "ore_flow"),
    "thickener": ("level", "motor_current", "water_flow"),
    "water": ("level", "water_flow"),
    "lab": ("product_mass",),
    "control": ("power",),
    "tailings": ("level", "water_flow"),
}
METRIC_COMPONENTS = {
    "crusher": ("crusher-drive", "bearing", "bearing", "feeder"),
    "scrubber": ("drum-drive", "wash-pump"),
    "screen": ("exciter", "spray-manifold"),
    "dms": ("density-meter", "feed-pump", "feed-pump"),
    "medium": ("magnetic-separator", "level-sensor"),
    "sorter": ("feed-belt", "feed-belt"),
    "hopper": ("level-sensor", "distributor"),
    "thickener": ("level-sensor", "rake-drive", "underflow-pump"),
    "water": ("level-sensor", "supply-pump"),
    "lab": ("product-scale",),
    "control": ("power-meter",),
    "tailings": ("inventory", "sump-pump"),
}


def source_metadata():
    data = json.loads((ROOT / "cases/diamond-plant-source.json").read_text())
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != data["sha256"]:
        raise ValueError("Plant source photograph changed")
    with Image.open(SOURCE) as image:
        if image.format != "PNG" or list(image.size) != [data["width"], data["height"]]:
            raise ValueError("Plant source format or dimensions changed")
    return data


def design():
    source = source_metadata()
    modules = []
    for line, z in (("A", -16), ("B", 0), ("C", 16)):
        for kind in LINE_KINDS:
            title, size, _, x = TYPES[kind]
            modules.append({
                "id": f"D01.{line}.{kind}", "label": f"{line} / {title}", "kind": kind, "line": line,
                "position": [x, size[1] / 2, z], "size": size, "rotation": [0, 0, 0],
                "visible": True, "appearance_concept": kind, "ports": [],
                "geometry_evidence": "manual-module-reconstruction-from-synthetic-reference",
            })
    for kind, z in SHARED_Z.items():
        title, size, _, x = TYPES[kind]
        modules.append({
            "id": f"D01.shared.{kind}", "label": title, "kind": kind, "line": "shared",
            "position": [x, size[1] / 2, z], "size": size, "rotation": [0, 0, 0],
            "visible": True, "appearance_concept": kind, "ports": [],
            "geometry_evidence": "manual-module-reconstruction-from-synthetic-reference",
        })
    by_id = {module["id"]: module for module in modules}
    streams = []

    def connect(identifier, source_id, target_id, material, transport, utility=False, source_port=None, target_port=None):
        source_id = source_id if source_id.startswith("D01.") else f"D01.shared.{source_id}"
        target_id = target_id if target_id.startswith("D01.") else f"D01.shared.{target_id}"
        endpoints = []
        for module_id, port_id, direction, side in (
            (source_id, source_port or material + "-out", "out", .5),
            (target_id, target_port or material + "-in", "in", -.5),
        ):
            module = by_id[module_id]
            if not any(port["id"] == port_id for port in module["ports"]):
                module["ports"].append({
                    "id": port_id, "direction": direction, "material": material,
                    "local_position_m": [side * module["size"][0], 0, 0],
                })
            endpoints.append({"module_id": module_id, "port_id": port_id})
        streams.append({
            "id": ("utility-" if utility else "process-") + identifier,
            "source": endpoints[0], "target": endpoints[1],
            "material": material, "transport": transport,
            "evidence": "authored-process-assumption", "visible_by_default": not utility,
        })

    for line in "ABC":
        ids = {kind: f"D01.{line}.{kind}" for kind in LINE_KINDS}
        connect(f"{line}-feed", "hopper", ids["crusher"], "ore", "belt")
        connect(f"{line}-crush", ids["crusher"], ids["scrubber"], "crushed-ore", "belt")
        connect(f"{line}-wash", ids["scrubber"], ids["screen"], "washed-ore", "chute")
        connect(f"{line}-size", ids["screen"], ids["dms"], "sized-ore", "chute")
        connect(f"{line}-sinks", ids["dms"], ids["medium"], "sinks", "pipe")
        connect(f"{line}-floats", ids["dms"], ids["medium"], "floats", "pipe")
        connect(f"{line}-concentrate", ids["medium"], ids["sorter"], "concentrate", "belt")
        connect(f"{line}-reject", ids["medium"], "tailings", "washed-tailings", "belt")
        connect(f"{line}-sorter-reject", ids["sorter"], "tailings", "sorter-rejects", "belt")
        connect(f"{line}-product", ids["sorter"], "lab", "recovered-product", "secure-transfer")
        connect(f"{line}-fines", ids["screen"], "thickener", "screen-fines-slurry", "pipe", True)
        connect(f"{line}-effluent", ids["medium"], "thickener", "wash-effluent", "pipe", True)
        connect(f"{line}-medium-recycle", ids["medium"], ids["dms"], "ferrosilicon-medium", "pipe", True)
        for kind in ("scrubber", "screen", "medium"):
            connect(f"{line}-{kind}-water", "water", ids[kind], "process-water", "pipe", True)
    connect("water-return", "thickener", "water", "recovered-water", "pipe", True)
    connect("thickener-underflow", "thickener", "tailings", "thickener-underflow", "pipe", True)
    equipment, tags = [], []
    for module in modules:
        for component in COMPONENTS[module["kind"]]:
            equipment.append({
                "id": module["id"] + "." + component, "module_id": module["id"],
                "name": component, "geometry": "logical-child-no-independent-geometry",
            })
        for metric, component in zip(KIND_METRICS[module["kind"]], METRIC_COMPONENTS[module["kind"]], strict=True):
            unit, limits = METRICS[metric]
            tags.append({
                "id": module["id"] + "." + metric, "module_id": module["id"],
                "equipment_id": module["id"] + "." + component,
                "metric": metric, "value_type": "double", "unit": unit,
                "simulation_envelope": limits, "envelope_evidence": "fictional-demo-values-not-operating-limits",
                "suggested_interval_ms": 1000,
            })
    metadata = {
        "schema_version": 1, "plant_id": "D01", "name": "Diamond recovery / three-line plant",
        "abstraction": "process-module-with-logical-equipment-children",
        "units": "meters", "coordinates": "right-handed-y-up",
        "axes": {"x": "east", "y": "up", "z": "south"}, "origin": "site-center-at-ground",
        "site_size_m": [100, 16, 75], "scale_evidence": ASSUMPTION,
        "source": source, "modules": modules, "equipment": equipment, "streams": streams, "telemetry_tags": tags,
        "reconstruction": {
            "geometry": "authored-parametric-module-meshes-matched-to-reviewed-image-layout",
            "photogrammetry": False, "independent_idol_generations": 0,
            "gaussian_status": "not-run-capacity-unavailable",
            "gaussian_blocker": "Existing Italy North Spot T4 restart returned Azure SkuNotAvailable.",
            "repetition": "Three explicit authored instances per line-module concept; not independently recovered identical equipment.",
        },
        "assumptions": [
            ASSUMPTION,
            "Photograph is synthetic. Back faces, internal components and pipe routing are authored.",
            "Grizzly / oversize handling is contained in the feed-preparation module; oversize is not presumed barren waste.",
            "DMS sinks and floats both pass through drain / rinse and medium recovery before product or tailings.",
            "The photograph does not establish XRT versus XRL. The demo assumes enclosed XRT recovery; XRF elemental analysis is not the selected sorting principle.",
            "Lab cleaning, inspection and security are logical functions, not recovered internal machinery.",
            "Tailings handling includes assumed downstream dewatering / containment, not an engineering design.",
            "No throughput, diamond recovery percentage, water balance, safety interlock or operating setpoint is certified.",
        ],
        "references": [
            {"title": "SGS Bateman diamond recovery modular plants", "url": "https://www.sgs.com/-/media/sgscorp/documents/corporate/brochures/sgs-nr-diamond-recovery-en.cdn.en-MU.pdf"},
            {"title": "TOMRA diamond sorting technology and flowsheets", "url": "https://www.tomra.com/en-gb/mining/media-center/news/2021/tomra-new-diamond-microsite"},
        ],
        "telemetry_event_contract": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object", "additionalProperties": False,
            "required": ["timestamp", "plant_id", "module_id", "equipment_id", "tag_id", "value", "unit", "quality"],
            "properties": {
                "timestamp": {"type": "string", "format": "date-time"},
                "plant_id": {"const": "D01"}, "module_id": {"enum": [m["id"] for m in modules]},
                "equipment_id": {"enum": [e["id"] for e in equipment]},
                "tag_id": {"enum": [tag["id"] for tag in tags]},
                "value": {"type": "number"}, "unit": {"type": "string"},
                "quality": {"enum": ["good", "uncertain", "bad"]},
            },
            "$comment": "Consumers must join tag_id to telemetry_tags and verify module_id, equipment_id and unit match that tag. Schema enums alone cannot enforce those cross-field relationships.",
        },
    }
    validate_design(metadata)
    return metadata


def validate_design(metadata):
    modules = {item["id"]: item for item in metadata["modules"]}
    equipment = {item["id"]: item for item in metadata["equipment"]}
    if len(modules) != 24 or len(modules) != len(metadata["modules"]) or len(equipment) != len(metadata["equipment"]):
        raise ValueError("Plant equipment inventory is invalid")
    if any(item["module_id"] not in modules for item in equipment.values()):
        raise ValueError("Unknown equipment parent")
    ids = set()
    for module in modules.values():
        for i, size in enumerate(module["size"]):
            position = module["position"][i]
            if not math.isfinite(size) or size <= 0 or not math.isfinite(position):
                raise ValueError("Invalid plant dimensions")
            lower, upper = (0, 16) if i == 1 else (-metadata["site_size_m"][i] / 2, metadata["site_size_m"][i] / 2)
            if position - size / 2 < lower - 1e-8 or position + size / 2 > upper + 1e-8:
                raise ValueError("Module exceeds authored site bounds")
        ports = module["ports"]
        if len({port["id"] for port in ports}) != len(ports):
            raise ValueError("Duplicate module ports")
        for port in ports:
            if len(port["local_position_m"]) != 3 or not all(math.isfinite(value) for value in port["local_position_m"]):
                raise ValueError("Invalid port position")
    for index, first in enumerate(metadata["modules"]):
        for second in metadata["modules"][index + 1:]:
            if all(abs(first["position"][axis] - second["position"][axis]) <
                   (first["size"][axis] + second["size"][axis]) / 2 - 1e-8 for axis in (0, 2)):
                raise ValueError("Plant module footprints overlap")
    for stream in metadata["streams"]:
        if stream["id"] in ids:
            raise ValueError("Duplicate stream IDs")
        ids.add(stream["id"])
        for endpoint, direction in (("source", "out"), ("target", "in")):
            reference = stream[endpoint]
            ports = modules[reference["module_id"]]["ports"]
            if not any(port["id"] == reference["port_id"] and port["direction"] == direction and port["material"] == stream["material"] for port in ports):
                raise ValueError("Invalid stream port reference")
    if len({tag["id"] for tag in metadata["telemetry_tags"]}) != len(metadata["telemetry_tags"]):
        raise ValueError("Duplicate telemetry tag IDs")
    for tag in metadata["telemetry_tags"]:
        if tag["module_id"] not in modules or equipment[tag["equipment_id"]]["module_id"] != tag["module_id"]:
            raise ValueError("Invalid telemetry attachment")


def trial_manifest(metadata):
    source = metadata["source"]
    trial = {
        "id": "D01", "title": metadata["name"],
        "source": {key: source[key] for key in ("filename", "sha256", "kind", "generator", "prompt", "publication_approved")},
        "detector_phrases": ["industrial machine", "tank", "control cabinet"],
        "expected_inventory": [], "reviewed_objects": [], "instances": [],
        "layout_kind": "manual-relative-not-metric",
    }
    trial["source"]["url"] = f"https://raw.githubusercontent.com/ribumann/3d-scene-toolchain/{SOURCE_REVISION}/inputs/diamond-plant/D01.png"
    for kind, (_, _, box, _) in TYPES.items():
        category = "tank" if kind in ("water", "thickener") else "control cabinet" if kind == "control" else "industrial machine"
        count = 3 if kind in LINE_KINDS else 1
        trial["expected_inventory"].append({"identity": kind, "category": category, "count": count})
        trial["reviewed_objects"].append({
            "id": kind, "identity": kind, "category": category, "box": box, "reviewed": True,
            "reusable_asset_id": f"D01-concept-{kind}",
        })
    for module in metadata["modules"]:
        trial["instances"].append({
            "id": module["id"], "object_id": module["kind"], "position": module["position"],
            "rotation": module["rotation"], "size": module["size"],
        })
    return TrialManifest.model_validate({"schema_version": 1, "trials": [trial]})


def scene_for(metadata, module_files):
    evidence = Evidence(origin="assumed", confidence=.5, reviewed=True, source_id="D01-source", note=ASSUMPTION)
    nodes, assets = [], []
    for module in metadata["modules"]:
        asset_id = "model-" + module["id"]
        nodes.append(Node(
            id=module["id"], label=module["label"], category="plant-" + module["kind"],
            position=module["position"], rotation=module["rotation"], size=module["size"],
            color="#437697", asset_id=asset_id, evidence=evidence,
        ))
        assets.append(Asset(
            id=asset_id, kind="glb", node_id=module["id"], uri=f"/api/assets/plant/modules/{module['kind']}.glb",
            sha256=hashlib.sha256(module_files[f"modules/{module['kind']}.glb"]).hexdigest(),
            provenance={"method": "authored-parametric-module", "source_sha256": metadata["source"]["sha256"], "concept": module["kind"]},
        ))
    by_id = {module["id"]: module for module in metadata["modules"]}
    edges = []
    for stream in metadata["streams"]:
        points = []
        for endpoint in ("source", "target"):
            reference = stream[endpoint]
            module = by_id[reference["module_id"]]
            port = next(p for p in module["ports"] if p["id"] == reference["port_id"])
            points.append(tuple(a + b for a, b in zip(module["position"], port["local_position_m"], strict=True)))
        # Utility trunks use a different elevation to distinguish return paths.
        height = .6 if stream["id"].startswith("utility-") else max(point[1] for point in points)
        points = [points[0], (points[0][0], height, points[0][2]), (points[1][0], height, points[0][2]), points[1]]
        edges.append(Edge(
            id=stream["id"], source=stream["source"]["module_id"], target=stream["target"]["module_id"],
            kind="conveyor" if stream["transport"] == "belt" else "process",
            points=points, label=stream["material"], evidence=evidence,
        ))
    return Scene(
        id="D01", case_id="D01", name=metadata["name"],
        description="Manual module-level reconstruction of a synthetic photograph. Authored parametric meshes, metre layout and process assumptions; no Gaussian or photogrammetric reconstruction is claimed.",
        nodes=nodes, assets=assets, edges=edges,
        sources=[Source(id="D01-source", kind="generated-photographic-scene", filename="D01.png", sha256=metadata["source"]["sha256"])],
    )


def layout_svg(metadata):
    shapes = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1280" viewBox="-10 -12 120 96" role="img" aria-labelledby="title description">',
              '<title id="title">Diamond recovery plant - authored site layout</title>',
              '<desc id="description">100 by 75 metre illustrative site. X east, Z south. Three parallel lines, shared utilities. Not surveyed or engineered.</desc>',
              '<rect x="-10" y="-12" width="120" height="96" fill="#f3f6f7"/>',
              '<text x="0" y="-6" font-family="sans-serif" font-size="2.8" fill="#23384a">D01 / Three-line diamond recovery plant</text>',
              '<rect width="100" height="75" fill="white" stroke="#85949c" stroke-width=".2"/>']
    modules = {module["id"]: module for module in metadata["modules"]}
    for stream in metadata["streams"]:
        if not stream["visible_by_default"]:
            continue
        a, b = [modules[stream[endpoint]["module_id"]]["position"] for endpoint in ("source", "target")]
        shapes.append(f'<path d="M {a[0]+50} {a[2]+37.5} H {b[0]+50} V {b[2]+37.5}" stroke="#8aa7b8" stroke-width=".2" fill="none"/>')
    for module in modules.values():
        x, _, z = module["position"]
        width, _, depth = module["size"]
        title = html.escape(module["id"] + " / " + module["label"])
        shapes.append(f'<g><title>{title}</title><rect x="{x+50-width/2}" y="{z+37.5-depth/2}" width="{width}" height="{depth}" rx=".3" fill="#dbe9f0" stroke="#326f98" stroke-width=".2"/>'
                      f'<text x="{x+50}" y="{z+37.5}" text-anchor="middle" font-family="sans-serif" font-size="1.15" fill="#23384a">{html.escape(module["kind"])}</text></g>')
    shapes += ['<path d="M 0 79 H 10 M 0 78 V 80 M 10 78 V 80" stroke="#23384a" stroke-width=".2"/>',
               '<text x="12" y="80" font-family="sans-serif" font-size="1.5">10 m / authored scale, not measured / North up</text></svg>']
    return "\n".join(shapes).encode()


def apply_reconstructed_appearances(scene, metadata, files, package):
    from scripts.package_trials import validate_trial_package

    publication, _ = validate_trial_package(package, ROOT / "cases/diamond-plant-trial.json")
    entry = next(item for item in publication["trials"] if item["variant"] == "optimized")
    if not entry["scene"]:
        raise ValueError("Plant publication has no completed optimized reconstruction")
    reconstructed = Scene.model_validate_json((package / entry["scene"]).read_text())
    nodes = {node.id: node for node in scene.nodes}
    if any(node.id not in nodes for node in reconstructed.nodes):
        raise ValueError("Reconstructed plant references an unknown module")
    assets = {asset.id: asset for asset in reconstructed.assets}
    shared = {}
    replaced = set()
    for recovered in reconstructed.nodes:
        asset = assets[recovered.asset_id]
        parent = asset.provenance["parent_node_id"]
        identifier = "D01-splat-" + parent
        if identifier not in shared:
            relative = f"splats/{parent}.ply"
            files[relative] = (package / f"assets/D01/optimized/{parent}.ply").read_bytes()
            shared[identifier] = asset.model_copy(update={
                "id": identifier, "node_id": None, "uri": "/api/assets/plant/" + relative,
            }, deep=True)
        node = nodes[recovered.id]
        replaced.add(node.asset_id)
        node.asset_id = identifier
    scene.assets = [asset for asset in scene.assets if asset.id not in replaced] + list(shared.values())
    metadata["appearance_assets"] = [asset.model_dump(mode="json") for asset in scene.assets]
    for module in metadata["modules"]:
        module["appearance_asset_id"] = nodes[module["id"]].asset_id
    scene.description = (
        "Single-image SAM2/Idol component Gaussian reconstruction from the original synthetic plant photograph. "
        "Repeated modules share reconstructed appearances; metric placement, connectivity and telemetry remain authored assumptions. "
        "Unreconstructed modules retain explicitly authored mesh models. Gaussian screening is not semantic accuracy certification."
    )
    metadata["reconstruction"] = {
        "method": "reviewed-boxes+sam2+idol",
        "independent_idol_generations": entry["report"]["independent_generations"],
        "reconstructed_concepts": len(shared), "gaussian_module_placements": len(reconstructed.nodes),
        "authored_mesh_fallbacks": len(scene.nodes) - len(reconstructed.nodes),
        "source_sha256": metadata["source"]["sha256"],
        "layout": "authored-metric-assumptions-not-surveyed",
        "display": {
            "fit": "uniform-aspect-fit-visible-four-sigma-bounds-grounded-inside-authored-module-envelope",
            "idol_sdk_rotation_x_radians": math.pi,
            "asset_uri_prefix": "/api/assets/plant/",
            "public_uri_prefix": "/plant/",
        },
        "report": entry["report"],
    }
    files["reconstruction.json"] = (json.dumps(metadata["reconstruction"], indent=2) + "\n").encode()


def public_files(metadata, splat_package=None):
    files = {"D01.png": SOURCE.read_bytes(), "layout.svg": layout_svg(metadata)}
    for kind in TYPES:
        _, size, _, _ = TYPES[kind]
        files[f"modules/{kind}.glb"] = glb([{"id": kind, "kind": kind, "position": [0, 0, 0], "size": size}])
    scene = scene_for(metadata, files)
    if splat_package is not None:
        apply_reconstructed_appearances(scene, metadata, files, splat_package)
    for stream, edge in zip(metadata["streams"], scene.edges, strict=True):
        stream["route_points_m"] = edge.model_dump(mode="json")["points"]
    connections = []
    for edge in scene.edges:
        for index, (a, b) in enumerate(zip(edge.points, edge.points[1:])):
            delta = [b[i] - a[i] for i in range(3)]
            distance = math.sqrt(sum(x * x for x in delta))
            if distance < 1e-8:
                continue
            vector = [x / distance for x in delta]
            quaternion = [0, -vector[2], vector[1], 1 + vector[0]]
            length = math.sqrt(sum(x * x for x in quaternion))
            quaternion = [x / length for x in quaternion] if length > 1e-8 else [0, 1, 0, 0]
            belt = edge.kind == "conveyor"
            connections.append({
                "id": f"{edge.id}.{index}", "kind": "link-belt" if belt else "link-pipe",
                "position": [(a[i] + b[i]) / 2 for i in range(3)],
                "size": [distance, .22 if belt else .12, .8 if belt else .12], "quaternion": quaternion,
            })
    files["plant.glb"] = glb([*metadata["modules"], *connections])
    metadata["scene_sha256"] = hashlib.sha256((scene.model_dump_json(indent=2) + "\n").encode()).hexdigest()
    files["metadata.json"] = (json.dumps(metadata, indent=2, allow_nan=False) + "\n").encode()
    files["files.json"] = (json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, indent=2) + "\n").encode()
    return scene, files


def publish(public, splat_package=None):
    metadata = design()
    scene, files = public_files(metadata, splat_package)
    if public.is_symlink() or public.exists() and not public.is_dir():
        raise ValueError("Unsafe public plant directory")
    if public.exists():
        for path in public.rglob("*"):
            if path.is_symlink() or path.is_file() and path.relative_to(public).as_posix() not in files:
                raise ValueError("Unexpected public plant content")
    public.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = public / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    case = Case(
        id="D01", title=metadata["name"], input_type="generated", status="ready",
        summary=(
            f"{metadata['reconstruction']['reconstructed_concepts']} photo-derived Gaussian concepts / "
            f"{metadata['reconstruction']['gaussian_module_placements']} authored placements; "
            "single-image approximation, not measured facility geometry."
        ) if splat_package is not None else
        "24 authored process modules / 3 lines. Manual image-guided reconstruction, not recovered metric geometry. Gaussian inference is pending GPU capacity.",
        source_filename="D01.png", source_url="/plant/D01.png",
    )
    return case, scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-trial-manifest", action="store_true")
    args = parser.parse_args()
    metadata = design()
    if args.write_trial_manifest:
        (ROOT / "cases/diamond-plant-trial.json").write_text(trial_manifest(metadata).model_dump_json(indent=2) + "\n")
    print(json.dumps({"modules": len(metadata["modules"]), "streams": len(metadata["streams"]), "equipment": len(metadata["equipment"]), "telemetry_tags": len(metadata["telemetry_tags"])}))


if __name__ == "__main__":
    main()
