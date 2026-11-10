"""Install this directory as a Blender add-on."""

bl_info = {
    "name": "Scene Toolchain",
    "author": "Scene Toolchain contributors",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Scene Twin",
    "description": "Import and export semantic digital-twin scenes",
    "category": "Import-Export",
}

# Keep coordinate helpers importable in a regular Python interpreter.
try:
    import bpy
except ModuleNotFoundError:
    bpy = None

if bpy is not None:
    import json
    from bpy.props import StringProperty
    from bpy_extras.io_utils import ExportHelper, ImportHelper
    from . import authoring

    class SCENE_TOOLCHAIN_OT_import(bpy.types.Operator, ImportHelper):
        bl_idname = "scene_toolchain.import_scene"
        bl_label = "Import Scene JSON"
        bl_description = "Import into the current Blender scene"
        filename_ext = ".json"
        filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

        def execute(self, context):
            try:
                with open(self.filepath, encoding="utf-8") as file:
                    data = json.load(file)
                authoring.import_scene(data)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, "Scene imported")
            return {"FINISHED"}

    class SCENE_TOOLCHAIN_OT_export(bpy.types.Operator, ExportHelper):
        bl_idname = "scene_toolchain.export_scene"
        bl_label = "Export Scene JSON and GLB"
        bl_description = "Export semantic JSON and a GLB alongside it"
        filename_ext = ".json"
        filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

        def execute(self, context):
            try:
                authoring.export_json_and_glb(self.filepath)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, "Scene JSON and GLB exported")
            return {"FINISHED"}

    class SCENE_TOOLCHAIN_PT_panel(bpy.types.Panel):
        bl_label = "Scene Twin"
        bl_idname = "SCENE_TOOLCHAIN_PT_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Scene Twin"

        def draw(self, context):
            layout = self.layout
            layout.operator(SCENE_TOOLCHAIN_OT_import.bl_idname)
            layout.operator(SCENE_TOOLCHAIN_OT_export.bl_idname)
            obj = context.object
            if obj and obj.get(authoring.ROLE) == "node":
                layout.label(text="Node ID: " + obj.get(authoring.ID, ""))
                try:
                    evidence = json.loads(obj.get("scene_toolchain_evidence", "{}"))
                except (ValueError, TypeError):
                    evidence = {}
                layout.label(text="Evidence: " + str(evidence.get("origin", "unknown")))
                layout.label(text="Source: " + str(evidence.get("source_id") or "none"))
                try:
                    scene_data = json.loads(context.scene.get(authoring.SCENE_KEY, "{}"))
                    source = next((s for s in scene_data.get("sources", [])
                                   if s.get("id") == evidence.get("source_id")), None)
                except (ValueError, TypeError):
                    source = None
                if source:
                    layout.label(text="File: " + str(source.get("filename", "")))
                    layout.label(text="Source kind: " + str(source.get("kind", "")))
                layout.label(text="Reviewed: " + str(evidence.get("reviewed", False)))
                layout.label(text="Confidence: " + str(evidence.get("confidence", "")))
                if evidence.get("note"):
                    layout.label(text="Note: " + str(evidence["note"]))
                if obj.get("scene_toolchain_asset_id"):
                    layout.label(text="Asset: " + obj["scene_toolchain_asset_id"])
            elif obj and obj.get(authoring.ROLE) == "edge":
                layout.label(text="Route ID: " + obj.get(authoring.ID, ""))

    _CLASSES = (SCENE_TOOLCHAIN_OT_import, SCENE_TOOLCHAIN_OT_export, SCENE_TOOLCHAIN_PT_panel)


def register():
    if bpy is None:
        raise RuntimeError("The Scene Toolchain add-on requires Blender")
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    if bpy is not None:
        for cls in reversed(_CLASSES):
            bpy.utils.unregister_class(cls)
