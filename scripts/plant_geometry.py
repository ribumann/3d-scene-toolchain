"""Small deterministic glTF exporter for explicitly authored process modules."""

import json
import math
import struct


def primitive(shape, size, position=(0, 0, 0), color="#437697", tilt=0):
    return {"shape": shape, "size": list(size), "position": list(position), "color": color, "tilt": tilt}


def module_geometry(kind):
    p = primitive
    if kind == "link-belt":
        return [p("box", (1, 1, 1), color="#4d5960")]
    if kind == "link-pipe":
        return [p("cylinder", (1, 1, 1), color="#326f98", tilt=math.pi / 2)]
    gray, blue, rail = "#85949c", "#326f98", "#e7bb46"
    parts = [p("box", (1, .05, 1), (0, -.475, 0), "#b4bec2")]
    if kind in ("crusher", "screen", "medium", "dms", "hopper"):
        for x in (-.38, .38):
            for z in (-.36, .36):
                parts.append(p("box", (.035, .46, .035), (x, -.22, z), gray))
        parts.append(p("box", (.9, .045, .84), (0, -.01, 0), gray))
        for z in (-.41, .41):
            parts.append(p("box", (.9, .025, .02), (0, .13, z), rail))
    if kind == "crusher":
        parts += [p("box", (.65, .42, .62), (0, .24, 0), blue),
                  p("frustum", (.55, .12, .5), (0, .44, 0), gray)]
    elif kind == "scrubber":
        parts += [p("cylinder", (.55, .92, .55), (0, .08, 0), blue, math.pi / 2)]
        for x in (-.32, .32):
            parts.append(p("box", (.12, .23, .62), (x, -.31, 0), gray))
    elif kind == "screen":
        parts += [p("box", (.85, .17, .7), (0, .23, 0), blue, -.17),
                  p("box", (.64, .3, .56), (0, -.3, 0), gray)]
        for x in (-.3, -.15, 0, .15, .3):
            parts.append(p("box", (.015, .02, .7), (x, .37 - .17 * x, 0), rail))
    elif kind == "dms":
        for x in (-.37, .37):
            for z in (-.33, .33):
                parts.append(p("box", (.035, .91, .035), (x, .025, z), gray))
        for x in (-.23, .23):
            parts += [p("cylinder", (.4, .18, .4), (x, -.35, 0), blue),
                      p("frustum", (.23, .36, .23), (x, .22, 0), gray),
                      p("cylinder", (.23, .1, .23), (x, .45, 0), gray)]
        parts.append(p("box", (.9, .025, .8), (0, .38, 0), rail))
    elif kind == "medium":
        parts += [p("box", (.67, .26, .64), (0, -.2, 0), blue),
                  p("cylinder", (.33, .72, .33), (0, .23, 0), gray, math.pi / 2),
                  p("box", (.14, .26, .32), (.4, .27, 0), blue)]
    elif kind == "hopper":
        parts += [p("frustum", (.9, .4, .84), (0, .25, 0), gray),
                  p("box", (.9, .08, .84), (0, .46, 0), blue)]
    elif kind in ("thickener", "water"):
        height = .77 if kind == "water" else .45
        parts += [p("cylinder", (.92, height, .92), (0, -.4 + height / 2, 0), blue),
                  p("cylinder", (.88, .025, .88), (0, -.4 + height, 0), "#627f8b")]
        if kind == "thickener":
            parts += [p("box", (.95, .04, .08), (0, .09, 0), gray),
                      p("box", (.025, .4, .025), (0, .29, 0), rail)]
        else:
            parts.append(p("cylinder", (.2, .08, .2), (0, .41, 0), gray))
    elif kind == "tailings":
        parts += [p("box", (.96, .24, .06), (0, -.32, z), gray) for z in (-.46, .46)]
        parts += [p("box", (.06, .24, .9), (x, -.32, 0), gray) for x in (-.45, .45)]
        parts.append(p("frustum", (.82, .37, .75), (0, -.16, 0), "#746f68"))
    else:
        parts.append(p("box", (.92, .75, .88), (0, -.05, 0), gray))
        parts += [p("box", (.98, .07, .96), (0, .36, 0), "#d0d5d6"),
                  p("box", (.18, .44, .025), (-.2, -.2, .45), blue)]
        if kind == "sorter":
            parts.append(p("box", (.4, .12, .35), (0, .46, 0), blue))
    return parts


def triangles(shape, segments=24):
    if shape == "box":
        vertices = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
        for a, b, c, d in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            yield [vertices[i] for i in (a, b, c)]
            yield [vertices[i] for i in (a, c, d)]
    else:
        bottom_radius = .2 if shape == "frustum" else .5
        for i in range(segments):
            a, b = 2 * math.pi * i / segments, 2 * math.pi * (i + 1) / segments
            lower = [(bottom_radius * math.cos(t), -.5, bottom_radius * math.sin(t)) for t in (a, b)]
            upper = [(.5 * math.cos(t), .5, .5 * math.sin(t)) for t in (a, b)]
            yield [lower[0], upper[0], lower[1]]
            yield [lower[1], upper[0], upper[1]]
            yield [(0, -.5, 0), lower[0], lower[1]]
            yield [(0, .5, 0), upper[1], upper[0]]


def glb(modules):
    """Export a portable scene, preserving module IDs and metre coordinates."""
    document = {
        "asset": {"version": "2.0", "generator": "Scene Workbench authored module reconstruction"},
        "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [],
        "materials": [], "accessors": [], "bufferViews": [], "buffers": [],
    }
    binary = bytearray()
    materials = {}
    for module in modules:
        parts = module_geometry(module["kind"])
        points = []
        for part in parts:
            cosine, sine = math.cos(part["tilt"]), math.sin(part["tilt"])
            for triangle in triangles(part["shape"]):
                for vertex in triangle:
                    x, y, z = [a * b for a, b in zip(vertex, part["size"], strict=True)]
                    points.append([x * cosine - y * sine + part["position"][0],
                                   x * sine + y * cosine + part["position"][1], z + part["position"][2]])
        lower = [min(point[i] for point in points) for i in range(3)]
        upper = [max(point[i] for point in points) for i in range(3)]
        scale = [module["size"][i] / (upper[i] - lower[i]) for i in range(3)]
        translation = [module["position"][i] - (upper[i] + lower[i]) / 2 * scale[i] for i in range(3)]
        parent = len(document["nodes"])
        document["scenes"][0]["nodes"].append(parent)
        document["nodes"].append({
            "name": module["id"], "translation": translation, "scale": scale,
            "rotation": module.get("quaternion", [0, 0, 0, 1]),
            "children": [], "extras": {"geometry_evidence": "authored-not-photogrammetry"},
        })
        for part in parts:
            positions, normals = [], []
            for triangle in triangles(part["shape"]):
                a, b, c = triangle
                u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
                normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                length = math.sqrt(sum(x * x for x in normal))
                positions.extend(triangle)
                normals.extend([[x / length for x in normal]] * 3)
            attributes = {}
            for key, values in (("POSITION", positions), ("NORMAL", normals)):
                offset = len(binary)
                binary.extend(struct.pack("<" + "f" * (len(values) * 3), *(x for vertex in values for x in vertex)))
                view = len(document["bufferViews"])
                document["bufferViews"].append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset, "target": 34962})
                accessor = {"bufferView": view, "componentType": 5126, "count": len(values), "type": "VEC3"}
                if key == "POSITION":
                    accessor.update(min=[min(v[i] for v in values) for i in range(3)], max=[max(v[i] for v in values) for i in range(3)])
                attributes[key] = len(document["accessors"])
                document["accessors"].append(accessor)
            color = part["color"]
            if color not in materials:
                materials[color] = len(document["materials"])
                document["materials"].append({"pbrMetallicRoughness": {
                    "baseColorFactor": [*(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)), 1],
                    "metallicFactor": .15, "roughnessFactor": .75,
                }})
            mesh = len(document["meshes"])
            document["meshes"].append({"primitives": [{"attributes": attributes, "material": materials[color]}]})
            document["nodes"][parent]["children"].append(len(document["nodes"]))
            document["nodes"].append({
                "mesh": mesh, "translation": part["position"], "scale": part["size"],
                "rotation": [0, 0, math.sin(part["tilt"] / 2), math.cos(part["tilt"] / 2)],
            })
    document["buffers"] = [{"byteLength": len(binary)}]
    encoded = json.dumps(document, separators=(",", ":"), allow_nan=False).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary += b"\0" * (-len(binary) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(encoded) + len(binary))
            + struct.pack("<I4s", len(encoded), b"JSON") + encoded
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)
