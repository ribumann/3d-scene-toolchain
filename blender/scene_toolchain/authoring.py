"""Blender scene construction and lossless semantic JSON round-trip."""

import json
import math
import re
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from .coordinates import (
    blender_rotation_to_web, blender_size_to_web, blender_to_web,
    web_euler_matrix, web_matrix_to_euler, web_rotation_to_blender,
    web_size_to_blender, web_to_blender,
)

SCENE_KEY = "scene_toolchain_json"
ROLE = "scene_toolchain_role"
ID = "scene_toolchain_id"
SHAPES = {"box", "cylinder", "sphere", "cone", "plane"}


def _vector(value, name, positive=False):
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        or (positive and v <= 0) for v in value
    ):
        raise ValueError(f"{name} must contain three {'positive ' if positive else ''}finite numbers")


def validate_scene(data):
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("Expected a Scene with schema_version 1.0")
    if data.get("units") != "meters" or data.get("coordinates") != "right-handed-y-up":
        raise ValueError("Expected meters and right-handed-y-up coordinates")
    for key in ("nodes", "edges", "assets", "sources"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"Scene {key} must be an array")
    ids = set()
    for node in data["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise ValueError("Each node needs a nonempty string id")
        if node["id"] in ids:
            raise ValueError(f"Duplicate node id: {node['id']}")
        ids.add(node["id"])
        if node.get("shape") not in SHAPES:
            raise ValueError(f"Unsupported shape for {node['id']}")
        for key in ("position", "rotation", "size"):
            _vector(node.get(key), f"{node['id']}.{key}", key == "size")
        if not isinstance(node.get("visible"), bool):
            raise ValueError(f"{node['id']}.visible must be boolean")
        if not isinstance(node.get("evidence"), dict):
            raise ValueError(f"{node['id']}.evidence must be an object")
        _parse_color(node.get("color"))
    edge_ids = set()
    for edge in data["edges"]:
        if not isinstance(edge, dict) or not isinstance(edge.get("id"), str) or not edge["id"]:
            raise ValueError("Each edge needs a nonempty string id")
        if edge["id"] in edge_ids:
            raise ValueError(f"Duplicate edge id: {edge['id']}")
        edge_ids.add(edge["id"])
        if edge.get("source") not in ids or edge.get("target") not in ids:
            raise ValueError(f"Edge {edge['id']} references a missing node")
        if not isinstance(edge.get("points"), list):
            raise ValueError(f"Edge {edge['id']} points must be an array")
        for point in edge["points"]:
            _vector(point, f"{edge['id']}.points")


def _parse_color(value):
    if not isinstance(value, str) or not value.startswith("#") or len(value) not in (4, 5, 7, 9):
        raise ValueError(f"Color must be a CSS hex color: {value!r}")
    digits = value[1:]
    if len(digits) in (3, 4):
        digits = "".join(c * 2 for c in digits)
    if len(digits) == 6:
        digits += "ff"
    try:
        return tuple(int(digits[i:i + 2], 16) / 255 for i in range(0, 8, 2))
    except ValueError as exc:
        raise ValueError(f"Invalid color: {value!r}") from exc


def _linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _new_material(node):
    rgba = _parse_color(node["color"])
    linear = tuple(_linear(c) for c in rgba[:3]) + (rgba[3],)
    mat = bpy.data.materials.new(name=node["label"] + " material")
    mat.diffuse_color = linear
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = linear
    shader.inputs["Roughness"].default_value = 0.7
    if rgba[3] < 1:
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        elif hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
    return mat


def _make_node(node):
    shape = node["shape"]
    if shape in ("box", "plane"):
        # A thin solid retains all three specified dimensions, unlike a zero-thickness plane.
        bpy.ops.mesh.primitive_cube_add(size=1)
    elif shape == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.5, depth=1)
    elif shape == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.5, radius2=0, depth=1)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.5)
    obj = bpy.context.object
    obj.name = node["label"]
    obj[ROLE], obj[ID] = "node", node["id"]
    obj["scene_toolchain_evidence"] = json.dumps(node["evidence"], ensure_ascii=False)
    obj["scene_toolchain_asset_id"] = node.get("asset_id") or ""
    obj.location = web_to_blender(node["position"])
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Matrix(web_rotation_to_blender(web_euler_matrix(node["rotation"]))).to_quaternion()
    obj.scale = web_size_to_blender(node["size"])
    obj.hide_render = not node["visible"]
    obj.hide_set(not node["visible"])
    obj.data.materials.append(_new_material(node))
    return obj


def _make_edge(edge):
    curve = bpy.data.curves.new(edge["label"] or edge["id"], "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = 0.025
    curve.bevel_resolution = 2
    # Empty paths remain empty rather than fabricating points.
    if edge["points"]:
        spline = curve.splines.new("POLY")
        spline.points.add(len(edge["points"]) - 1)
        for point, co in zip(spline.points, edge["points"]):
            point.co = (*web_to_blender(co), 1)
    obj = bpy.data.objects.new(edge["label"] or edge["id"], curve)
    bpy.context.scene.collection.objects.link(obj)
    obj[ROLE], obj[ID] = "edge", edge["id"]
    return obj


def _helper(obj):
    obj[ROLE] = "helper"
    return obj


def add_studio(scene, nodes):
    visible = [obj for obj in nodes if not obj.hide_render]
    points = [obj.matrix_world @ Vector(corner) for obj in visible for corner in obj.bound_box]
    if points:
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        center = (low + high) / 2
        extent = max((high - low).length, 1)
        floor = low.z
    else:
        center, extent, floor = Vector((0, 0, 0)), 4, 0
    bpy.ops.mesh.primitive_plane_add(size=extent * 4, location=(center.x, center.y, floor - 0.01))
    ground = _helper(bpy.context.object)
    ground.name = "Studio ground"
    ground["scene_toolchain_ground"] = True
    ground.data.materials.append(_new_material({"label": "Ground", "color": "#dddddd"}))
    bpy.ops.object.camera_add()
    camera = _helper(bpy.context.object)
    camera.name = "Studio camera"
    camera.location = center + Vector((1, -2, 1.5)).normalized() * extent * 2
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 1.4
    camera.data.clip_start = max(extent / 10000, 0.0001)
    camera.data.clip_end = max(extent * 10, 100)
    scene.camera = camera
    for name, direction, power in (("Key", (1, -1, 2), 900), ("Fill", (-1, 1, 1.5), 500)):
        bpy.ops.object.light_add(type="AREA", location=center + Vector(direction) * extent)
        light = _helper(bpy.context.object)
        light.name = name
        light["scene_toolchain_studio_light"] = name
        light.data.energy = power * extent * extent / 16
        light.data.shape = "DISK"
        light.data.size = extent
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()


def import_scene(data):
    validate_scene(data)
    scene = bpy.context.scene
    if SCENE_KEY in scene or any(ROLE in obj for obj in scene.objects):
        raise ValueError("This Blender scene already contains an imported Scene; create a new scene first")
    scene[SCENE_KEY] = json.dumps(data, ensure_ascii=False)
    nodes = [_make_node(node) for node in data["nodes"]]
    for edge in data["edges"]:
        _make_edge(edge)
    bpy.context.view_layer.update()
    add_studio(scene, nodes)
    return nodes


def _objects_by_id(scene, role):
    result = {}
    for obj in scene.objects:
        if obj.get(ROLE) == role:
            identifier = obj.get(ID)
            if not identifier or identifier in result:
                raise ValueError(f"Missing or duplicate {role} semantic ID: {identifier!r}")
            result[identifier] = obj
    return result


def _object_color(obj, original):
    if not obj.data.materials or obj.data.materials[0] is None:
        raise ValueError(f"Node {obj.get(ID)} has no material")
    mat = obj.data.materials[0]
    shader = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
    rgba = shader.inputs["Base Color"].default_value if shader else mat.diffuse_color
    channels = [round(_srgb(c) * 255) for c in rgba[:3]] + [round(max(0, min(1, rgba[3])) * 255)]
    previous = _parse_color(original)
    if all(abs(channels[i] / 255 - previous[i]) < 0.5 / 255 + 1e-8 for i in range(4)):
        return original
    return "#" + "".join(f"{c:02x}" for c in (channels if channels[3] < 255 else channels[:3]))


def _edge_points(obj):
    curve = obj.data
    if obj.type != "CURVE" or len(curve.splines) > 1:
        raise ValueError(f"Route {obj.get(ID)} must be a single curve spline")
    if not curve.splines:
        return []
    spline = curve.splines[0]
    if spline.type != "POLY":
        raise ValueError(f"Route {obj.get(ID)} must use a poly spline")
    return [list(blender_to_web(obj.matrix_world @ Vector(p.co[:3]))) for p in spline.points]


def scene_data(scene):
    if SCENE_KEY not in scene:
        raise ValueError("Import a Scene JSON before exporting")
    data = json.loads(scene[SCENE_KEY])
    node_objects = _objects_by_id(scene, "node")
    edge_objects = _objects_by_id(scene, "edge")
    if set(node_objects) != {node["id"] for node in data["nodes"]}:
        raise ValueError("Node IDs were added, removed, or changed; restore them before export")
    if set(edge_objects) != {edge["id"] for edge in data["edges"]}:
        raise ValueError("Route IDs were added, removed, or changed; restore them before export")
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    for node in data["nodes"]:
        obj = node_objects[node["id"]]
        if obj.type != "MESH":
            raise ValueError(f"Node {node['id']} must remain a mesh")
        columns = [obj.matrix_world.to_3x3().col[i].copy() for i in range(3)]
        if (any(c.length <= 1e-12 for c in columns)
                or any(abs(columns[i].normalized().dot(columns[j].normalized())) > 1e-5
                       for i in range(3) for j in range(i + 1, 3))):
            raise ValueError(f"Node {node['id']} has a sheared or degenerate transform")
        location, rotation, scale = obj.matrix_world.decompose()
        if any(s <= 0 for s in scale):
            raise ValueError(f"Node {node['id']} must have positive scale")
        # The local bounding box captures edit-mode geometry changes as well as object scaling.
        bounds = obj.bound_box
        extents = [max(p[i] for p in bounds) - min(p[i] for p in bounds) for i in range(3)]
        dims = [extents[i] * scale[i] for i in range(3)]
        if any(d <= 0 for d in dims):
            raise ValueError(f"Node {node['id']} must have positive dimensions")
        node["position"] = list(blender_to_web(location))
        node["rotation"] = list(web_matrix_to_euler(blender_rotation_to_web(rotation.to_matrix())))
        node["size"] = list(blender_size_to_web(dims))
        node["visible"] = not obj.hide_render
        node["color"] = _object_color(obj, node["color"])
    for edge in data["edges"]:
        edge["points"] = _edge_points(edge_objects[edge["id"]])
    validate_scene(data)
    return data


def export_glb(filepath, scene):
    layer = bpy.context.view_layer
    active = layer.objects.active
    selected = list(bpy.context.selected_objects)
    hidden = {obj: obj.hide_get() for obj in layer.objects}
    try:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in scene.objects:
            if obj.get(ROLE) in ("node", "edge") and not obj.hide_render:
                obj.hide_set(False)
                obj.select_set(True)
        result = bpy.ops.export_scene.gltf(filepath=str(filepath), export_format="GLB",
                                           use_selection=True, export_yup=True, export_extras=True)
        if "FINISHED" not in result:
            raise RuntimeError("Blender glTF export did not finish")
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in selected:
            obj.select_set(True)
        for obj, was_hidden in hidden.items():
            obj.hide_set(was_hidden)
        layer.objects.active = active


def export_json_and_glb(filepath):
    path = Path(filepath)
    data = scene_data(bpy.context.scene)
    path.parent.mkdir(parents=True, exist_ok=True)
    export_glb(path.with_suffix(".glb"), bpy.context.scene)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def render_references(outdir, ids):
    scene = bpy.context.scene
    objects = _objects_by_id(scene, "node")
    if len(ids) > 16:
        raise ValueError("At most 16 reference renders may be requested")
    if len(set(ids)) != len(ids):
        raise ValueError("Reference node IDs must be unique")
    for identifier in ids:
        if identifier not in objects or objects[identifier].hide_render:
            raise ValueError(f"Reference node not found or hidden: {identifier}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", identifier):
            raise ValueError(f"Reference node ID is not a safe filename: {identifier!r}")
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    saved_visibility = {obj: obj.hide_render for obj in scene.objects}
    old_matrix = scene.camera.matrix_world.copy()
    old_scale = scene.camera.data.ortho_scale
    old_clip = (scene.camera.data.clip_start, scene.camera.data.clip_end)
    old_path = scene.render.filepath
    old_film = scene.render.film_transparent
    old_res = (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage)
    lights = [obj for obj in scene.objects if obj.get("scene_toolchain_studio_light")]
    old_lights = [(obj, obj.matrix_world.copy(), obj.data.energy, obj.data.size) for obj in lights]
    manifest = []
    try:
        for obj in scene.objects:
            if obj.get(ROLE) in ("node", "edge") or obj.get("scene_toolchain_ground"):
                obj.hide_render = True
        scene.render.resolution_x = scene.render.resolution_y = 256
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.film_transparent = True
        for identifier in ids:
            obj = objects[identifier]
            obj.hide_render = False
            points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
            high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
            center = (low + high) / 2
            extent = max((high - low).length, 0.01)
            scene.camera.location = center + Vector((1, -2, 1.5)).normalized() * extent * 2
            scene.camera.rotation_euler = (center - scene.camera.location).to_track_quat("-Z", "Y").to_euler()
            scene.camera.data.ortho_scale = extent * 1.2
            scene.camera.data.clip_start = max(extent / 10000, 0.0001)
            scene.camera.data.clip_end = max(extent * 10, 100)
            for light in lights:
                direction = (Vector((1, -1, 2)) if light["scene_toolchain_studio_light"] == "Key"
                             else Vector((-1, 1, 1.5)))
                light.location = center + direction * extent
                light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
                light.data.energy = (900 if light["scene_toolchain_studio_light"] == "Key" else 500) * extent * extent / 16
                light.data.size = extent
            filename = f"{identifier}.png"
            image_path = outdir / filename
            if image_path.is_symlink():
                raise ValueError(f"Reference output must not be a symlink: {image_path}")
            scene.render.filepath = str(image_path)
            bpy.ops.render.render(write_still=True)
            manifest.append({"node_id": identifier, "image": filename})
            obj.hide_render = True
    finally:
        for obj, hidden in saved_visibility.items():
            obj.hide_render = hidden
        scene.camera.matrix_world = old_matrix
        scene.camera.data.ortho_scale = old_scale
        scene.camera.data.clip_start, scene.camera.data.clip_end = old_clip
        for obj, matrix, energy, size in old_lights:
            obj.matrix_world = matrix
            obj.data.energy = energy
            obj.data.size = size
        scene.render.filepath = old_path
        scene.render.film_transparent = old_film
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = old_res
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
