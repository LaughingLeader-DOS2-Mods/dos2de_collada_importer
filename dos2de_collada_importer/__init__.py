bl_info = {
    "name": "Divinity Collada Importer",
    "author": "LaughingLeader",
    "blender": (2, 7, 9),
    "api": 38691,
    "location": "File > Import-Export",
    "description": ("Import DAE files."),
    "warning": "",
    "wiki_url": (""),
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export"}

import bpy

from bpy.path import display_name_from_filepath
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, IntProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

import os

def import_collada(operator, context, **args):
    filepath = args["filepath"]
    rename_actions = args["rename_actions"]
    fix_orientation = args["fix_orientation"]
    auto_connect = args["auto_connect"]
    find_chains = args["find_chains"]
    min_chain_length = args["min_chain_length"]
    import_units = args["import_units"]
    keep_bind_info = args["keep_bind_info"]

    name = os.path.split(filepath)[-1].split(".")[0]
    parts = os.path.splitext(filepath)
    ext = parts[1].lower()

    # Ignore current armatures when renaming actions
    ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    #print("[Divinity Collada Importer] Ignored Objects {}".format(len(ignored_objects)))
    if ext == ".dae":
        bpy.ops.wm.collada_import(filepath=filepath, fix_orientation=fix_orientation, import_units=import_units, 
            find_chains=find_chains, auto_connect=auto_connect, min_chain_length=min_chain_length, keep_bind_info=keep_bind_info)

        if rename_actions == True:
            new_objects = list(filter(lambda obj: obj.type == "ARMATURE" and obj.animation_data != None, context.scene.objects.values()))
            #print("[Divinity Collada Importer] New Armature Objects {}".format(len(new_objects)))

            if len(new_objects) > 0:
                for ob in new_objects:
                    if not ob in ignored_objects:
                        action_name = (ob.animation_data.action.name
                            if ob.animation_data is not None and
                            ob.animation_data.action is not None
                            else "")
                        
                        if action_name != "":
                            new_name = bpy.path.display_name_from_filepath(filepath)
                            operator.report({'INFO'}, "[Divinity Collada Importer] Renamed action '{}' to '{}'.".format(action_name, new_name))
                            ob.animation_data.action.name = new_name
            else:
                operator.report({'INFO'}, "[Divinity Collada Importer] No new actions to rename.")
    else:
        raise RuntimeError("[Divinity Collada Importer] Unknown extension: %s" % ext)

    return {"FINISHED"}

class ImportDivinityCollada(bpy.types.Operator, ImportHelper):
    """Load a Divinity .dae file"""
    bl_idname = "import_scene.divinitycollada"
    bl_label = "Import"
    bl_options = {"PRESET", "UNDO"}

    filename_ext = ".dae"
    filter_glob = StringProperty(
            default="*.dae",
            options={"HIDDEN"})

    rename_actions = BoolProperty(
            name="Rename Imported Actions",
            description="Rename actions to the name of the file",
            default=True)

    auto_connect = BoolProperty(
            name="Auto Connect",
            description="Set use_connect for parent bones which have exactly one child bone",
            default=True)

    find_chains = BoolProperty(
            name="Find Bone Chains",
            description="Find best matching Bone Chains and ensure bones in chain are connected",
            default=False)

    min_chain_length = IntProperty(
            name="Minimum Chain Length",
            description="When searching Bone Chains disregard chains of length below this value",
            default=0)

    fix_orientation = BoolProperty(
            name="Fix Leaf Bones",
            description="Fix Orientation of Leaf Bonese",
            default=False)

    import_units = BoolProperty(
            name="Import Units",
            description="If disabled match import to Blender’s current Unit settings, otherwise use the settings from the Imported scene",
            default=False)

    keep_bind_info = BoolProperty(
            name="Keep Bind Info",
            description="Store Bindpose information in custom bone properties for later use during Collada export",
            default=False)

    def execute(self, context):
        keywords = self.as_keywords()
        return import_collada(self, context, **keywords)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Import Data Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "import_units")
        row = box.row()
        row.prop(self, "rename_actions")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Armature Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "fix_orientation")
        row = box.row()
        row.prop(self, "find_chains")
        row = box.row()
        row.prop(self, "auto_connect")
        row = box.row()
        row.prop(self, "min_chain_length")

        box = layout.box()
        row = box.row(align=False)
        row.prop(self, "keep_bind_info")

import traceback

def menu_func_import(self, context):
    self.layout.operator(ImportDivinityCollada.bl_idname, text="Divinity Collada (.dae)")

def register():
    try: 
        bpy.utils.register_module(__name__)
        bpy.types.INFO_MT_file_import.append(menu_func_import)
    except: traceback.print_exc()

def unregister():
    try: 
        bpy.utils.unregister_module(__name__)
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
    except: traceback.print_exc()