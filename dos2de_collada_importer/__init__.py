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
from bpy.types import Operator, OperatorFileListElement, AddonPreferences
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

import os
import subprocess

class DivinityImporterAddonPreferences(AddonPreferences):
    bl_idname = "dos2de_collada_importer"

    divine_path = StringProperty(
        name="Divine Path",
        description="The path to divine.exe, used to convert from gr2 to dae",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.label(text="General:", icon="OUTLINER_DATA_META")
        row = box.row()
        row.prop(self, "divine_path")

def import_collada(operator, context, load_filepath, **args):
    rename_actions = args["action_autorename"]
    fix_orientation = args["fix_orientation"]
    auto_connect = args["auto_connect"]
    find_chains = args["find_chains"]
    min_chain_length = args["min_chain_length"]
    import_units = args["import_units"]
    keep_bind_info = args["keep_bind_info"]

    bpy.ops.wm.collada_import(filepath=load_filepath, fix_orientation=fix_orientation, import_units=import_units, 
        find_chains=find_chains, auto_connect=auto_connect, min_chain_length=min_chain_length, keep_bind_info=keep_bind_info)

    if rename_actions == True:
        new_objects = list(filter(lambda obj: obj.type == "ARMATURE" and obj.animation_data != None, context.scene.objects.values()))
        #print("[DOS2DEImporter] New Armature Objects {}".format(len(new_objects)))

        if len(new_objects) > 0:
            for ob in new_objects:
                if not ob in ignored_objects:
                    action_name = (ob.animation_data.action.name
                        if ob.animation_data is not None and
                        ob.animation_data.action is not None
                        else "")
                    
                    if action_name != "":
                        new_name = bpy.path.display_name_from_filepath(load_filepath)
                        operator.report({'INFO'}, "[DOS2DEImporter] Renamed action '{}' to '{}'.".format(action_name, new_name))
                        ob.animation_data.action.name = new_name
        else:
            operator.report({'INFO'}, "[DOS2DEImporter] No new actions to rename.")

    return True

def import_granny(operator, context, load_filepath, divine_path, **args):
    conform_skeleton_path = args["conform_skeleton_path"]
    delete_dae = args["gr2_delete_dae"]

    divine_exe = '"{}"'.format(divine_path)
    dae_temp_path = str.replace(load_filepath, ".gr2", "-temp.dae")
    if conform_skeleton_path is not None and os.path.isfile(conform_skeleton_path):
        gr2_options_str = "-e conform conform-path \"{}\"".format(conform_skeleton_path)
    else:
        gr2_options_str = ""

    proccess_args = "{} --loglevel all -g dos2de -s \"{}\" -d \"{}\" -i gr2 -o dae -a convert-model {}".format(
        divine_exe, load_filepath, dae_temp_path, gr2_options_str)
    
    print("Starting GR2->DAE conversion using divine.exe.")
    print("Sending command: {}".format(proccess_args))

    process = subprocess.run(proccess_args, 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    print(process.stdout)
    
    if process.returncode != 0:
        #raise Exception("Error converting DAE to GR2: \"{}\"{}".format(process.stderr, process.stdout))
        error_message = "[DOS2DEImporter] [ERROR:{}] Error converting GR2 to DAE. {}".format(process.returncode, '\n'.join(process.stdout.splitlines()[-1:]))
        operator.report({"ERROR"}, error_message)
        print(error_message)
    else:
        #Deleta .dae
        if import_collada(operator, context, dae_temp_path, **args):
            if delete_dae:
                os.remove(dae_temp_path)
            return True
    
    return False

def import_start(operator, context, load_filepath, **args):
    divine_path = ""
    preferences = context.user_preferences.addons["dos2de_collada_importer"].preferences
    if preferences is not None:
        divine_path = preferences.divine_path

    name = os.path.split(load_filepath)[-1].split(".")[0]
    parts = os.path.splitext(load_filepath)
    ext = parts[1].lower()

    print("[DOS2DEImporter] Importing file: '{}'.".format(load_filepath))

    # Ignore current armatures when renaming actions
    ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    #print("[DOS2DEImporter] Ignored Objects {}".format(len(ignored_objects)))
    if ext == ".dae":
        return import_collada(operator, context, load_filepath, **args)
    elif ext == ".gr2":
        if divine_path != "" and os.path.isfile(divine_path):
            return import_granny(operator, context, load_filepath, divine_path, **args)
        else:
            operator.report({"ERROR"}, "[DOS2DEImporter] Failed to find divine.exe at path: '{}'. Canceling GR2 import.".format(divine_path))
    else:
        raise RuntimeError("[DOS2DEImporter] Unknown extension: %s" % ext)
        return False
    return True

class ImportDivinityCollada(bpy.types.Operator, ImportHelper):
    """Load a Divinity .dae file"""
    bl_idname = "import_scene.divinitycollada"
    bl_label = "Import"
    bl_options = {"PRESET", "UNDO"}

    filename_ext = ".dae"
    filter_glob = StringProperty(
            default="*.dae;*.gr2",
            options={"HIDDEN"})

    files = CollectionProperty(
            name="File Path",
            type=OperatorFileListElement
            )

    directory = StringProperty(
            subtype='DIR_PATH'
            )

    # Animation Options
    action_autorename = BoolProperty(
            name="Rename Imported Actions",
            description="Rename actions to the name of the file",
            default=True)

    action_set_fake_user = BoolProperty(
            name="Delete Animation Extras",
            description="Automatically delete armature/meshes provided with animation files",
            default=True)

    delete_animation_extras = BoolProperty(
            name="Delete Animation Extras",
            description="Automatically delete armature/meshes provided with animation files",
            default=False)

    # Default Collada Import Options
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

    # GR2 Options
    gr2_delete_dae = BoolProperty(
            name="Delete DAE",
            description="When importing from gr2, delete the temporary .dae file that gets created",
            default=True)

    conform_skeleton_path = StringProperty(
            name="Conform Skeleton Path",
            description="Conform the skeleton to the provided file",
            default="")

    def execute(self, context):
        keywords = self.as_keywords()

        directory = self.directory
        for file_elem in self.files:
            filepath = os.path.join(directory, file_elem.name)
            print("Selected file: {}".format(filepath))
            import_start(self, context, load_filepath=filepath, **keywords)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Import Data Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "import_units")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="GR2 Import Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "gr2_delete_dae")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Animation Options:", icon="ANIM_DATA")
        row = box.row()
        row.prop(self, "action_autorename")
        row = box.row()
        row.prop(self, "action_set_fake_user")
        row = box.row()
        row.prop(self, "delete_animation_extras")

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
        bpy.utils.register_module("dos2de_collada_importer")
        bpy.types.INFO_MT_file_import.append(menu_func_import)
    except: traceback.print_exc()

def unregister():
    try: 
        bpy.utils.unregister_module("dos2de_collada_importer")
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
    except: traceback.print_exc()