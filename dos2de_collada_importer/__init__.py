bl_info = {
    "name": "Divinity Collada Importer",
    "author": "LaughingLeader",
    "blender": (2, 7, 9),
    "api": 38691,
    "location": "File > Import-Export",
    "description": ("Import Collada/Granny files for Divinity: Original Sin 2 - Definitive Edition."),
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

def transform_apply(self, context, obj, location=False, rotation=False, scale=False, children=False):
    last_active = getattr(bpy.context.scene.objects, "active", None)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.scene.objects.active = obj
    obj.select = True
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)

    recurse_targets = []
    if children:
        for childobj in obj.children:
            childobj.select = True
            if childobj.children is not None:
                recurse_targets.append(childobj)
        bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
        bpy.ops.object.select_all(action='DESELECT')
    obj.select = False
    bpy.context.scene.objects.active = last_active

    if len(recurse_targets) > 0:
        for recobj in recurse_targets:
            transform_apply(self, context, recobj, location, rotation, scale, children)

def import_collada(operator, context, load_filepath, rename_temp=False, **args):
    rename_actions = args["action_autorename"]
    action_set_fake_user = args["action_set_fake_user"]
    gr2_conform_delete_armatures = args["gr2_conform_delete_armatures"]
    gr2_conform_delete_meshes = args["gr2_conform_delete_meshes"]

    fix_orientation = args["fix_orientation"]
    auto_connect = args["auto_connect"]
    find_chains = args["find_chains"]
    min_chain_length = args["min_chain_length"]
    import_units = args["import_units"]
    apply_transformation = args["apply_transformation"]
    keep_bind_info = args["keep_bind_info"]

    #ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    ignored_objects = context.scene.objects.values()

    print("[DOS2DE-Importer] Importing collada file: '{}'".format(load_filepath))

    bpy.ops.wm.collada_import(filepath=load_filepath, fix_orientation=fix_orientation, import_units=import_units, 
        find_chains=find_chains, auto_connect=auto_connect, min_chain_length=min_chain_length, keep_bind_info=keep_bind_info)

    if rename_actions or action_set_fake_user:
        new_objects = list(filter(lambda obj: obj.type == "ARMATURE" and obj.animation_data != None and not obj in ignored_objects, context.scene.objects.values()))
        print("[DOS2DE-Importer] New Armature Objects {}".format(len(new_objects)))
        if len(new_objects) > 0:
            for ob in new_objects:
                action = (ob.animation_data.action
                    if ob.animation_data is not None and
                    ob.animation_data.action is not None
                    else None)

                if action is not None:
                    action_name = action.name

                    if rename_actions:
                        new_name = bpy.path.display_name_from_filepath(load_filepath)
                        if rename_temp:
                            new_name = str.replace(new_name, "-temp", "")
                        operator.report({'INFO'}, "[DOS2DE-Importer] Renamed action '{}' to '{}'.".format(action_name, new_name))
                        ob.animation_data.action.name = new_name
                        action_name = new_name

                    if action_set_fake_user:
                        action.use_fake_user = True
                        print("[DOS2DE-Importer] Enabled fake user for action '{}'.".format(action_name))
        else:
            #operator.report({'INFO'}, "[DOS2DE-Importer] No new actions to rename.")
            pass

        if apply_transformation:
            new_objects = list(filter(lambda obj: not obj in ignored_objects, context.scene.objects.values()))
            for obj in new_objects:
                print("[DOS2DE-Importer] Applying transformation for object '{}:{}' and children.".format(obj.name, obj.type))
                transform_apply(operator, context, obj, location=True, rotation=True, scale=True, children=True)

        if gr2_conform_delete_armatures or gr2_conform_delete_meshes:
            delete_objects = list(filter(lambda obj: not obj in ignored_objects, context.scene.objects.values()))
            print("[DOS2DE-Importer] Deleting '{}' new objects after import.".format(len(delete_objects)))
            for obj in delete_objects:
                if gr2_conform_delete_armatures and obj.type == "ARMATURE" or gr2_conform_delete_meshes and obj.type == "MESH":
                    index = bpy.data.objects.find(obj.name)
                    if index > -1:
                        obj_data = bpy.data.objects[index]
                        print("[DOS2DE-Importer] Deleting object '{}:{}'.".format(obj.name, obj.type))
                        bpy.data.objects.remove(obj_data)

    return True

def import_granny(operator, context, load_filepath, divine_path, **args):
    gr2_conform = args["gr2_conform"]
    if gr2_conform:
        conform_skeleton_path = context.scene.dos2de_conform_skeleton_path
    else:
        conform_skeleton_path = ""
    delete_dae = args["gr2_delete_dae"]

    divine_exe = '"{}"'.format(divine_path)

    from pathlib import Path
    path_start = Path(load_filepath)
    dae_temp_path = str(Path(str(path_start.with_suffix("")) + "-temp.dae"))
    if gr2_conform and conform_skeleton_path is not None and os.path.isfile(conform_skeleton_path):
        gr2_options_str = "-e conform -e conform-copy --conform-path \"{}\"".format(conform_skeleton_path)
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
        error_message = "[DOS2DE-Importer] [ERROR:{}] Error converting GR2 to DAE. {}".format(process.returncode, '\n'.join(process.stdout.splitlines()[-1:]))
        operator.report({"ERROR"}, error_message)
        print(error_message)
    else:
        #Deleta .dae
        print("[DOS2DE-Importer] Importing temp dae file: '{}'.".format(dae_temp_path))
        if import_collada(operator, context, load_filepath=dae_temp_path, rename_temp=True, **args):
            if delete_dae:
                print("[DOS2DE-Importer] Deleting temp file: '{}'.".format(dae_temp_path))
                if os.path.isfile(dae_temp_path):
                    os.remove(dae_temp_path)
            return True
        else:
            print("Failed?")
    return False

def import_start(operator, context, load_filepath, **args):
    divine_path = ""
    preferences = context.user_preferences.addons["dos2de_collada_importer"].preferences
    if preferences is not None:
        divine_path = preferences.divine_path

    name = os.path.split(load_filepath)[-1].split(".")[0]
    parts = os.path.splitext(load_filepath)
    ext = parts[1].lower()

    print("[DOS2DE-Importer] Importing file: '{}'.".format(load_filepath))

    # Ignore current armatures when renaming actions
    ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    #print("[DOS2DE-Importer] Ignored Objects {}".format(len(ignored_objects)))
    if ext == ".dae":
        return import_collada(operator, context, load_filepath, **args)
    elif ext == ".gr2":
        if divine_path != "" and os.path.isfile(divine_path):
            return import_granny(operator, context, load_filepath, divine_path, **args)
        else:
            operator.report({"ERROR"}, "[DOS2DE-Importer] Failed to find divine.exe at path: '{}'. Canceling GR2 import.".format(divine_path))
    else:
        raise RuntimeError("[DOS2DE-Importer] Unknown extension: %s" % ext)
        return False
    return True

class DOS2DEImporter_FileSelectorOperator(bpy.types.Operator):
    bl_idname = "dos2deimporter.op_fileselector"
    bl_label = "Select File"

    filename_ext = ".gr2"

    filepath = bpy.props.StringProperty(subtype="FILE_PATH") 

    def execute(self, context):
        display = "filepath= "+self.filepath  
        return {'FINISHED'}

    def invoke(self, context, event): 
        context.window_manager.invoke_popup(self) 
        return {'RUNNING_MODAL'} 

class DOS2DEImporter_GR2_AddConformPath(Operator):
    """Use the selected file as the skeleton to conform to"""
    bl_idname = "dos2deimporter.op_gr2_addconformpath"
    bl_label = ""

    filepath = StringProperty(default="", subtype="FILE_PATH")
    updated = BoolProperty(default=False, options={'HIDDEN'})
    file_ext = ".gr2"

    def execute(self, context):
        if self.filepath != "":
            context.scene.dos2de_conform_skeleton_path = self.filepath
            print("[DOS2DE-Importer] Set pathway to '{}.'".format(self.filepath))
            updated = True
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)
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
            name="Set Fake User",
            description="Set a fake user on newly imported actions",
            default=True)

    # Default Collada Import Options
    apply_transformation = BoolProperty(
            name="Apply Transformations",
            description="Apply all object transformations on imported objects. Useful if the model is y-up, which comes with a X 90 rotation",
            default=True)

    auto_connect = BoolProperty(
            name="Auto Connect",
            description="Set use_connect for parent bones which have exactly one child bone",
            default=False)

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

    gr2_conform = BoolProperty(
            name="Conform",
            description="When importing from gr2, conform the file to a specific skeleton",
            default=False)

    gr2_conform_delete_armatures = BoolProperty(
            name="Delete Extra Armatures",
            description="When conforming, delete extra armatures that get created",
            default=False)

    gr2_conform_delete_meshes = BoolProperty(
            name="Delete Extra Meshes",
            description="When conforming, delete extra meshes that get created",
            default=False)

    debug_mode = BoolProperty(default=False, options={"HIDDEN"})
    
    def invoke(self, context, event):
        if context.scene.dos2de_conform_skeleton_path is not None and os.path.isfile(context.scene.dos2de_conform_skeleton_path):
            self.gr2_conform = True
        else:
            self.gr2_conform = False

        if "laughingleader_blender_helpers" in context.user_preferences.addons:
            helper_preferences = context.user_preferences.addons["laughingleader_blender_helpers"].preferences
            if helper_preferences is not None:
                self.debug_mode = getattr(helper_preferences, "debug_mode", False)
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

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
        row = box.row()
        row.prop(self, "apply_transformation")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="GR2 Import Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "gr2_delete_dae")

        row = box.row()
        box = row.box()
        row = box.row()
        row.label("Conform Options: ", icon="MOD_ARMATURE")
        row = box.row()
        row.prop(self, "gr2_conform", text="Enable Conforming")
        row = box.row()
        row.label("Skeleton: ")
        row = box.row()
        row.prop(context.scene, "dos2de_conform_skeleton_path", text="")
        op = row.operator(DOS2DEImporter_GR2_AddConformPath.bl_idname, icon="IMPORT", text="")
        op.filepath = self.filepath
        row = box.row()
        row.prop(self, "gr2_conform_delete_armatures")
        row = box.row()
        row.prop(self, "gr2_conform_delete_meshes")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Animation Options:", icon="ANIM_DATA")
        row = box.row()
        row.prop(self, "action_autorename")
        row = box.row()
        row.prop(self, "action_set_fake_user")

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
    self.layout.operator(ImportDivinityCollada.bl_idname, text="Divinity Collada (.dae, .gr2)")

def register():
    try: 
        bpy.utils.register_module("dos2de_collada_importer")
        bpy.types.INFO_MT_file_import.append(menu_func_import)

        bpy.types.Scene.dos2de_conform_skeleton_path = StringProperty(
            name="Skeleton",
            description="Conform the imported armature to this skeleton",
            default="")
    except: traceback.print_exc()

def unregister():
    try: 
        bpy.utils.unregister_module("dos2de_collada_importer")
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
        #del bpy.types.Scene.dos2de_conform_skeleton_path
    except: traceback.print_exc()