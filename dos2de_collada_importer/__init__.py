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
from bpy.types import Operator, OperatorFileListElement, AddonPreferences, PropertyGroup
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty, PointerProperty
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

    extracted_assets_dir = StringProperty(
        name="Shared Assets",
        description="The path to extracted assets from Shared.pak. This should be Public/Shared/Assets.\nThis is used to automatically fetch conforming skeletons",
        subtype='DIR_PATH',
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.label(text="General:", icon="OUTLINER_DATA_META")
        row = box.row()
        row.prop(self, "divine_path")
        row.prop(self, "extracted_assets_dir")


base_skeleton_directories = ["Dwarves", "Elves", "Humans", "Lizards"]
base_skeleton_dict = {}

def get_base_skeletons(scene, context):
    assets_dir = ""
    if "dos2de_collada_importer" in context.user_preferences.addons:
        preferences = context.user_preferences.addons["dos2de_collada_importer"].preferences
        if preferences is not None:
            if "extracted_assets_dir" in preferences:
                assets_dir = preferences.extracted_assets_dir
    
    skeletons = [("DISABLED", "Disabled", "")]
    skeletons.append(("AUTO", "Auto", "Auto-select a base skeleton to conform to, based on the file name.\nThis happens when importing, to support multiple imports"))

    if assets_dir != "" and os.path.isdir(assets_dir):
        characters_dir = os.path.join(assets_dir, "Characters")
        if os.path.isdir(characters_dir):
            for race in base_skeleton_directories:
                race_dir = os.path.join(characters_dir, race)
                if os.path.isdir(race_dir):
                    base_skeleton_f = os.path.join(race_dir, race + "_Female_Base.gr2")
                    base_skeleton_m = os.path.join(race_dir, race + "_Male_Base.gr2")

                    global base_skeleton_dict

                    if os.path.isfile(base_skeleton_f):
                        key = race + "_Female"
                        display = race + " Female"
                        skeletons.append((key, display, base_skeleton_f))
                        base_skeleton_dict[key] = (base_skeleton_f, race, "Female")

                    if os.path.isfile(base_skeleton_m):
                        key = race + "_Male"
                        display = race + " Male"
                        skeletons.append((key, display, base_skeleton_m))
                        base_skeleton_dict[key] = (base_skeleton_m, race, "Male")

    return skeletons

class DOS2DEImporterSettings(PropertyGroup):

    apply_transformation = BoolProperty(
        name="Apply Transformations",
        description="Apply all object transformations on imported objects. Useful if the model is y-up, which comes with a X 90 rotation",
        default=True)
    
    gr2_conform_enabled = BoolProperty(
        name="Conform",
        description="When importing from gr2, conform the file to a specific skeleton",
        default=False)

    gr2_base_skeleton = EnumProperty(
        name="Base Skeletons",
        description="Auto-detected skeletons that can be used when conforming.\nThis setting will override the conform path set",
        items=get_base_skeletons
    )

    dos2de_conform_skeleton_path = StringProperty(
        name="Skeleton",
        description="Conform the imported armature to this skeleton",
        default="")

    gr2_conform_delete_armatures = BoolProperty(
            name="Delete Extra Armatures",
            description="When conforming, delete extra armatures that get created",
            default=False)

    gr2_conform_delete_meshes = BoolProperty(
            name="Delete Extra Meshes",
            description="When conforming, delete extra meshes that get created",
            default=False)

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

    if last_active is not None:
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
    gr2_conform_enabled = args["gr2_conform_enabled"]
    if gr2_conform_enabled == True:
        conform_skeleton_path = args["dos2de_conform_skeleton_path"]

        base_skeleton = args["gr2_base_skeleton"]
        autoselect = base_skeleton != None and base_skeleton == "AUTO"

        if base_skeleton is not None and base_skeleton != "DISABLED":
            if autoselect == True:
                filename = os.path.basename(load_filepath)
                print("  [DOS2DE-Importer] Auto-select base skeleton set. Looking for match in name {}".format(load_filepath))

                auto_skeleton = None
                for key,entry in base_skeleton_dict.items():
                    base_file = entry[0]
                    if filename.count(key) > 0:
                        auto_skeleton = base_file
                        break
                    else:
                        race = entry[1]
                        gender = entry[2]
                        if filename.count(race + "_Hero_"+gender) > 0:
                            auto_skeleton = base_file
                            break

                if auto_skeleton is not None and os.path.isfile(auto_skeleton):
                    conform_skeleton_path = auto_skeleton
                    print("    [DOS2DE-Importer] Auto-selected skeleton {}".format(auto_skeleton))
                else:
                    print("    [DOS2DE-Importer] No auto base skeleton found.")

            else:
                check_path = base_skeleton_dict[base_skeleton]
                if os.path.isfile(check_path):
                    conform_skeleton_path = check_path
                    print("[DOS2DE-Importer] Using base skeleton '{}'.".format(conform_skeleton_path))
        else:
            print("[DOS2DE-Importer] No base skeleton set. Using conform path.")
    else:
        conform_skeleton_path = ""
    delete_dae = args["gr2_delete_dae"]

    divine_exe = '"{}"'.format(divine_path)
    
    from pathlib import Path
    path_start = Path(load_filepath)
    dae_temp_path = str(Path(str(path_start.with_suffix("")) + "-temp.dae"))

    if gr2_conform_enabled and conform_skeleton_path is not None and os.path.isfile(conform_skeleton_path):
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

def import_start(operator, context, load_filepath, divine_path, **args):
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

    gr2_conform_enabled = BoolProperty(
        name="Conform",
        description="When importing from gr2, conform the file to a specific skeleton",
        default=False)

    gr2_base_skeleton = EnumProperty(
        name="Base Skeletons",
        description="Auto-detected skeletons that can be used when conforming.\nThis setting will override the conform path set",
    )

    dos2de_conform_skeleton_path = StringProperty(
        name="Skeleton",
        description="Conform the imported armature to this skeleton",
        default="")

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
        dos2de_importer_settings = getattr(context.scene, "dos2de_importer_settings", None)
        if dos2de_importer_settings is not None:
            self.apply_transformation = dos2de_importer_settings.apply_transformation
            self.gr2_conform_enabled = dos2de_importer_settings.gr2_conform_enabled
            self.gr2_base_skeleton = dos2de_importer_settings.gr2_base_skeleton
            self.gr2_conform_delete_armatures = dos2de_importer_settings.gr2_conform_delete_armatures
            self.gr2_conform_delete_meshes = dos2de_importer_settings.gr2_conform_delete_meshes
            self.gr2_delete_dae = dos2de_importer_settings.gr2_delete_dae

        if context.scene.dos2de_conform_skeleton_path is not None and os.path.isfile(context.scene.dos2de_conform_skeleton_path):
            pass
        else:
            context.scene.gr2_conform_enabled = False

        if "laughingleader_blender_helpers" in context.user_preferences.addons:
            helper_preferences = context.user_preferences.addons["laughingleader_blender_helpers"].preferences
            if helper_preferences is not None:
                self.debug_mode = getattr(helper_preferences, "debug_mode", False)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        dos2de_importer_settings = getattr(context.scene, "dos2de_importer_settings", None)
        if dos2de_importer_settings is not None:
            dos2de_importer_settings.apply_transformation = self.apply_transformation
            dos2de_importer_settings.gr2_conform_enabled = self.gr2_conform_enabled
            dos2de_importer_settings.gr2_base_skeleton = self.gr2_base_skeleton
            dos2de_importer_settings.gr2_conform_delete_armatures = self.gr2_conform_delete_armatures
            dos2de_importer_settings.gr2_conform_delete_meshes = self.gr2_conform_delete_meshes
            dos2de_importer_settings.gr2_delete_dae = self.gr2_delete_dae
            print("[DOS2DE-Importer] Saved importer settings to scene.")

        keywords = self.as_keywords()

        selection = bpy.context.selected_objects
        last_active = getattr(bpy.context.scene.objects, "active", None)

        directory = self.directory

        divine_path = ""

        if "dos2de_collada_importer" in context.user_preferences.addons:
            preferences = context.user_preferences.addons["dos2de_collada_importer"].preferences
            if preferences is not None and "divine_path" in preferences:
                divine_path = preferences.divine_path

        for file_elem in self.files:
            filepath = os.path.join(directory, file_elem.name)
            #print("Selected file: {}".format(filepath))
            import_start(self, context, filepath, divine_path, **keywords)

        if(len(selection) > 0):
            for obj in selection:
                obj.select = True

        if last_active is not None:
            bpy.context.scene.objects.active = last_active

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
        row.prop(self, "gr2_conform_enabled", text="Enable Conforming")
        row = box.row()
        row.label("Skeleton: ")
        row = box.row()
        row.prop(self, "gr2_base_skeleton")
        row = box.row()
        row.prop(self, "dos2de_conform_skeleton_path", text="")
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

        bpy.types.Scene.dos2de_importer_settings = PointerProperty(type=DOS2DEImporterSettings, 
            name="DOS2DE Import Settings",
            description="Persistent settings saved between imports for this specific scene"
        )

    except: traceback.print_exc()

def unregister():
    try: 
        bpy.utils.unregister_module("dos2de_collada_importer")
        bpy.types.INFO_MT_file_import.remove(menu_func_import)
        #del bpy.types.Scene.dos2de_conform_skeleton_path
    except: traceback.print_exc()