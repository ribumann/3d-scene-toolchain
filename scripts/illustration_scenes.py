"""Reviewed relative layouts with explicitly invented, shared object appearances."""

import hashlib
from pathlib import Path

from scene_pipeline.models import Asset, Case, Edge, Evidence, Node, Scene, Source
from scene_pipeline.templates import compile_prompt

ROOT = Path(__file__).resolve().parents[1]
MACHINES = (
    "wafer-loader", "die-attach", "wire-bonder", "encapsulation",
    "singulation", "electrical-test", "packaged-output",
)


def illustration_scene(case_id, appearances):
    source_id = "prompt" if case_id.startswith("P") else "image"
    if source_id == "prompt":
        import json
        cases = [Case.model_validate(item) for item in json.loads((ROOT / "cases/manifest.json").read_text())]
        scene = compile_prompt(next(item for item in cases if item.id == case_id))
    else:
        reference = ROOT / f"apps/web/public/references/{case_id}.webp"
        scene = Scene(
            id=case_id, case_id=case_id, name=f"{case_id} reviewed illustrative layout",
            description="", nodes=[], sources=[Source(
                id="image", kind="diagram" if case_id != "I05" else "plan",
                filename=f"{case_id}.webp", sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
            )],
        )
    mappings = {}
    if case_id == "P01":
        for node in scene.nodes:
            if node.category in ("shelf", "endcap", "checkout"):
                mappings[node.id] = {"shelf": "grocery-shelf", "endcap": "grocery-endcap", "checkout": "checkout"}[node.category]
                if node.category == "shelf":
                    node.size = (node.size[2], node.size[1], node.size[0])
                    node.rotation = (0, 1.5707963267948966, 0)
    elif case_id == "P02":
        scene.nodes = [node for node in scene.nodes if node.category not in ("housing", "control")]
        for node in scene.nodes:
            if node.category == "machine":
                mappings[node.id] = MACHINES[int(node.id.rsplit("-", 1)[1])]
            elif node.category == "buffer":
                mappings[node.id] = "buffer-rack"
    elif case_id == "P03":
        scene.nodes = [node for node in scene.nodes if "-trunk-" not in node.id]
        for node in scene.nodes:
            if node.category == "vegetation":
                mappings[node.id] = "tree"
                node.label, node.position, node.size = "Illustrative complete tree", (node.position[0], 2.0, node.position[2]), (2, 4, 2)
            elif node.category == "animal":
                species = {"savanna": "giraffe", "aviary": "aviary-bird", "woodland": "woodland-deer"}[node.id.split("-")[0]]
                mappings[node.id] = species
                node.label = f"Illustrative {species}"
                node.size = {"giraffe": (3, 5, 1.4), "aviary-bird": (1.2, 1, .6), "woodland-deer": (1.8, 1.8, .8)}[species]
                node.position = (node.position[0], node.size[1] / 2, node.position[2])
    else:
        def add(identifier, label, concept, x, z, width=2.2, height=2.5, depth=2.2):
            scene.nodes.append(Node(
                id=identifier, label=label, category=concept, position=(x, height / 2, z),
                size=(width, height, depth), color="#7899a8",
                evidence=Evidence(
                    origin="inferred", confidence=.6, reviewed=True, source_id="image",
                    note="Reviewed 2D role/relative location; height and scale assumed. Generated appearance is not recovered from this source.",
                ),
            ))
            mappings[identifier] = concept
            return identifier

        def connect(first, second, note):
            nodes = {node.id: node for node in scene.nodes}
            a, b = nodes[first], nodes[second]
            scene.edges.append(Edge(
                id=f"flow-{len(scene.edges):03d}", source=first, target=second, kind="process",
                points=[(a.position[0], .2, a.position[2]), (b.position[0], .2, b.position[2])],
                label=f"{a.label} to {b.label}",
                evidence=Evidence(origin="observed", confidence=.9, reviewed=True, source_id="image",
                                  note=note + " Relative authored route, not a physical pipe or measured 3D trajectory."),
            ))

        if case_id == "I04":
            groups = [
                ("trim1", "Trim 1", 14, 14, -5, 14),
                ("trim2", "Trim 2", 13, 9, 14, -5),
                ("chassis1", "Chassis 1", 7, 9, -9, -19),
                ("chassis2", "Chassis 2", 10, -9, -19, -5),
                ("chassis3", "Chassis 3", 10, 4, -19, -5),
                ("final1", "Final 1", 14, 4, -1, 18),
                ("final2", "Final 2", 13, -2, 18, -1),
                ("inspect", "Inspect", 6, -2, -5, -12),
            ]
            chains = []
            for identity, label, count, x, start, end in groups:
                chain = [add(f"{identity}-{i+1:02d}", f"{label} station {i+1}", "assembly-station",
                             x, start + (end - start) * i / (count - 1), 1.7, 2.2, 1.1) for i in range(count)]
                for a, b in zip(chain, chain[1:]):
                    connect(a, b, "I04: numbered station order and visible directional arrows.")
                chains.append(chain)
            for index, (first, second) in enumerate(zip(chains, chains[1:])):
                a = next(node for node in scene.nodes if node.id == first[-1])
                b = next(node for node in scene.nodes if node.id == second[0])
                buffer = add(f"buffer-{index}", f"Inter-line buffer {index+1}", "buffer-rack",
                             (a.position[0] + b.position[0]) / 2, (a.position[2] + b.position[2]) / 2, 1.1, 1, 1.1)
                connect(first[-1], buffer, "I04: visible inter-line connector through a green buffer.")
                connect(buffer, second[0], "I04: visible inter-line connector through a green buffer.")
            engine = [add(f"engine-{i+1}", f"Engine station {i+1}", "assembly-station", -15, -9 - i * 1.6, 1.7, 2.2, 1.1) for i in range(6)]
            for a, b in zip(engine, engine[1:]):
                connect(a, b, "I04: engine stations 1 through 6.")
            buffer = add("engine-buffer", "Engine branch buffer", "buffer-rack", -12, -19, 1.1, 1, 1.1)
            connect(engine[-1], buffer, "I04: Engine output feeds the Chassis 2 entry buffer.")
            connect(buffer, chains[3][0], "I04: Engine branch enters Chassis 2 station 1, not the main line entrance.")
        elif case_id == "I01":
            for identifier, label, concept, x, z in [
                ("hard-bin", "Hard ore bin", "feed-hopper", -2, -16),
                ("weathered-bin", "Weathered ore bin", "feed-hopper", 1, -16),
                ("primary", "Primary crusher", "jaw-crusher", -5, -12),
                ("scrubber", "Scrubber", "rotary-scrubber", 5, -12),
                ("secondary", "Secondary crusher", "jaw-crusher", -14, -10),
                ("cone", "Cone crusher", "cone-crusher", -9, -1),
                ("screen", "Vibrating screen", "vibrating-screen", 6, -8),
                ("thickener1", "Thickener", "thickener", -5, 4),
                ("thickener2", "Thickener", "thickener", 9, 4),
                ("grinding", "Differential grinding mill", "grinding-mill", -8, 9),
                ("conveyor", "Conveyor", "belt-conveyor", -11, -7),
                ("pump", "Pump", "slurry-pump", 4, 2),
            ]:
                add(identifier, label, concept, x, z)
            connect("hard-bin", "primary", "I01: hard ore bin/feeder to primary crushing.")
            connect("weathered-bin", "scrubber", "I01: weathered ore bin/feeder to scrubber.")
            scene.description = "Curated equipment roles; only two unambiguous feed relationships are authored. Other junctions remain unasserted. "
        elif case_id == "I05":
            # Reviewed principal footprints, deliberately excluding roads and annotations.
            for identifier, label, box in [
                ("repair", "Repair and assembly inspection", (445, 279, 149, 48)),
                ("chassis", "Chassis body shop", (365, 349, 229, 90)),
                ("paint", "Body paint shop", (305, 452, 115, 210)),
                ("frame", "Frame assembly shop", (538, 452, 56, 120)),
                ("body", "Body assembly shop", (305, 662, 114, 299)),
                ("parts", "Engine and chassis parts shop", (477, 573, 116, 387)),
                ("forging", "Forging shop", (205, 773, 69, 84)),
                ("polishing", "Polishing shop", (205, 862, 69, 96)),
            ]:
                x, y, w, h = box
                add(identifier, label, "factory-building", (x+w/2-360)/30, (y+h/2-631.5)/30,
                    w/30, 2.0, h/30)
            scene.description = "Eight reviewed principal plan footprints. No process links are inferred from proximity. Building heights and facades are invented. "
        else:
            raise ValueError("Unsupported illustrated scene")
    scene.id = scene.case_id = f"{case_id}-illustrated"
    scene.name += " / illustrative splats"
    scene.description += " Generated reference -> reviewed mask -> Idol. Invented appearance; relative layout, not recovered scale or hidden geometry. Repeated assets are explicit authored instances, not independent reconstructions."
    retained = []
    for node in scene.nodes:
        concept = mappings.get(node.id)
        if concept is None:
            retained.append(node)
            continue
        if concept not in appearances:
            continue
        appearance = appearances[concept]
        node.asset_id = f"illustration-{concept}"
        node.evidence.origin = "generated"
        node.evidence.note += f" Explicit shared illustrative concept: {concept}; not a photo of the actual source object."
        retained.append(node)
        if not any(asset.id == node.asset_id for asset in scene.assets):
            scene.assets.append(Asset(
                id=node.asset_id, kind="ply", uri=f"/api/assets/illustrations/{concept}.ply",
                sha256=appearance["sha256"],
                provenance={**appearance, "concept": concept, "explicit_authored_instances": True},
            ))
    scene.nodes = retained
    ids = {node.id for node in scene.nodes}
    scene.edges = [edge for edge in scene.edges if edge.source in ids and edge.target in ids]
    for edge in scene.edges:
        if edge.evidence is None:
            edge.evidence = Evidence(origin="generated", confidence=1, reviewed=False, source_id=source_id,
                                     note="Authored scenario relationship, not observed physical connectivity.")
    if not scene.assets:
        raise ValueError(f"No reconstructed appearances available for {case_id}")
    return Scene.model_validate(scene.model_dump())
