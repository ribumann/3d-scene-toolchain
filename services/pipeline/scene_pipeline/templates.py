from .models import Case, Edge, Evidence, Node, Scene, Source


def node(identifier, label, category, position, size, color, shape="box"):
    return Node(
        id=identifier, label=label, category=category, position=position,
        size=size, color=color, shape=shape,
        evidence=Evidence(
            origin="generated", confidence=1,
            note="Deterministic illustrative geometry from the scenario template, not reconstructed evidence.",
        ),
    )


def route(identifier, first, second, kind="process", points=None):
    return Edge(
        id=identifier, source=first.id, target=second.id, kind=kind,
        points=points or [
            (first.position[0], 0.18, first.position[2]),
            (second.position[0], 0.18, second.position[2]),
        ],
        label=f"{first.label} to {second.label}",
    )


def compile_prompt(case: Case) -> Scene:
    scene = Scene(
        id=case.id, case_id=case.id, name=case.title, description=case.summary,
        nodes=[], sources=[Source(id="prompt", kind="description", filename="case prompt")],
    )
    if case.id == "P01":
        departments = [
            ("Produce", "#52966b"), ("Bakery", "#c79c64"), ("Dairy", "#8ab4c1"),
            ("Pantry", "#b2a288"), ("Frozen", "#7498c5"), ("Household", "#ab8cb3"),
        ]
        scene.nodes.append(node("floor", "Store floor", "ground", (0, -0.12, 0), (28, .2, 24), "#e4e9e9"))
        for index, (label, color) in enumerate(departments):
            x = -10 + index * 4
            for bay in range(3):
                z = -7 + bay * 4
                scene.nodes.append(node(f"aisle-{index}-{bay}", f"{label} bay {bay + 1}", "shelf", (x, 1.15, z), (1.5, 2.3, 3.2), color))
            scene.nodes.append(node(f"endcap-{index}", f"{label} endcap", "endcap", (x, .7, 4), (1.7, 1.4, 1.3), color))
        for index in range(3):
            scene.nodes.append(node(f"checkout-{index}", f"Checkout {index + 1}", "checkout", (-7 + index * 6, .6, 8), (3, 1.2, 1.5), "#416b80"))
        a = scene.nodes[1]
        b = scene.nodes[-1]
        scene.edges.append(route("shopping-route", a, b, "visitor", [(-12, .15, 8), (-12, .15, -9), (-8, .15, -9), (-8, .15, 5.5), (10, .15, 5.5), (10, .15, 8), (5, .15, 8)]))
    elif case.id == "P02":
        scene.nodes.append(node("floor", "Assembly hall", "ground", (0, -.12, 0), (36, .2, 18), "#e4e9eb"))
        labels = ["Wafer loading", "Die attach", "Wire bonding", "Encapsulation", "Singulation", "Electrical test", "Packaged output"]
        stations = []
        for index, label in enumerate(labels):
            x = -14 + index * 4.6
            machine = node(f"station-{index}", label, "machine", (x, 1.4, 0), (3, 2.8, 3.4), "#7b9fae" if index % 2 else "#527f95")
            stations.append(machine)
            scene.nodes.extend([
                machine,
                node(f"station-top-{index}", f"{label} housing", "housing", (x, 3.1, 0), (2.5, .6, 2.8), "#cbd8dd"),
                node(f"station-display-{index}", f"{label} control", "control", (x, 1.9, 1.76), (1.1, .7, .12), "#253d52"),
            ])
            if index < len(labels) - 1:
                scene.nodes.append(node(f"buffer-{index}", f"Buffer {index + 1}", "buffer", (x + 2.3, .45, 0), (1.2, .9, 1.2), "#b7a56d"))
        for index in range(len(stations) - 1):
            scene.edges.append(route(f"flow-{index}", stations[index], stations[index + 1], points=[
                (stations[index].position[0], .25, 3),
                (stations[index + 1].position[0], .25, 3),
            ]))
    elif case.id == "P03":
        scene.nodes.append(node("ground", "Zoo grounds", "ground", (0, -.14, 0), (36, .25, 30), "#bad0b1"))
        habitats = [
            ("savanna", "Savanna habitat", (-9, .18, -6), (12, .4, 9), "#c3ae75"),
            ("aviary", "Aviary", (9, .18, -6), (11, .4, 9), "#88ae86"),
            ("woodland", "Woodland habitat", (-9, .18, 7), (12, .4, 8), "#73966d"),
            ("aquatic", "Aquatic habitat", (9, .18, 7), (11, .4, 8), "#78adbf"),
        ]
        zones = []
        for identifier, label, pos, size, color in habitats:
            zone = node(identifier, label, "habitat", pos, size, color)
            zones.append(zone)
            scene.nodes.append(zone)
            x, _, z = pos
            for side, dx, dz, dims in [
                ("north", 0, -size[2] / 2, (size[0], 1.4, .14)),
                ("south", 0, size[2] / 2, (size[0], 1.4, .14)),
                ("west", -size[0] / 2, 0, (.14, 1.4, size[2])),
                ("east", size[0] / 2, 0, (.14, 1.4, size[2])),
            ]:
                scene.nodes.append(node(f"{identifier}-{side}", f"{label} boundary", "fence", (x + dx, .9, z + dz), dims, "#77816d"))
            for j in range(3):
                tx, tz = x - 3 + j * 2.8, z - 1
                scene.nodes.extend([
                    node(f"{identifier}-trunk-{j}", "Tree trunk", "vegetation", (tx, 1, tz), (.35, 2, .35), "#8a7560", "cylinder"),
                    node(f"{identifier}-tree-{j}", "Tree canopy", "vegetation", (tx, 2.7, tz), (2, 2.5, 2), "#4d845d", "cone"),
                ])
            if identifier != "aquatic":
                scene.nodes.append(node(f"{identifier}-animal", "Illustrative animal proxy", "animal", (x + 1, .9, z + 1.7), (1.6, 1, .8), "#b99976", "sphere"))
        entrance = node("entrance", "Entrance plaza", "entrance", (0, .1, 12.5), (5, .25, 3), "#a5b4b1")
        scene.nodes.append(entrance)
        scene.edges.append(route("visitor-circuit", entrance, zones[0], "visitor", [(0, .3, 12.5), (0, .3, 0), (-16, .3, 0), (-16, .3, -12), (16, .3, -12), (16, .3, 0), (0, .3, 0), (0, .3, 12.5)]))
    else:
        raise ValueError("Description compilation currently supports the three explicit PoC scenarios P01-P03")
    return Scene.model_validate(scene.model_dump())
