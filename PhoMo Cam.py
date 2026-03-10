bl_info = {
    "name": "PhoMo Camera",
    "author": "Morpholic",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > N-Panel > PhoMo",
    "description": "Photo mode camera controls inspired by video games.",
    "category": "Camera",
}

import bpy
import json
import os

_active_camera_cache = None

def _global_presets_path():
    """Return the path to the global presets JSON file in Blender's config dir."""
    return os.path.join(
        bpy.utils.user_resource('CONFIG'), 'phomo_global_presets.json'
    )

def _get_active_camera(context):
    return context.scene.camera


def _dof_visible(context):
    """Return True only if the current shading mode can display DoF."""
    space = context.space_data
    if not isinstance(space, bpy.types.SpaceView3D):
        return False
    return space.shading.type in {'MATERIAL', 'RENDERED'}

def _update_fstop(self, context):
    """Sync PhoMo F-Stop to the active camera and auto-enable DoF."""
    cam = _get_active_camera(context)
    if cam is None:
        return
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = self.fstop


def _update_camera_exposure(self, context):
    """
    self = Camera data block.
    Sync this camera's per-camera exposure to the scene only when it is
    the currently active camera.
    """
    scene = context.scene
    if scene.camera and scene.camera.data == self:
        scene.view_settings.exposure = self.phomo_exposure

@bpy.app.handlers.persistent
def _on_depsgraph_update(scene, depsgraph):
    """
    Detect active camera switches and sync the incoming camera's stored
    exposure value to scene.view_settings.exposure.
    """
    global _active_camera_cache
    cam = scene.camera
    if cam != _active_camera_cache:
        _active_camera_cache = cam
        if cam is not None:
            scene.view_settings.exposure = cam.data.phomo_exposure

def _read_global_presets():
    path = _global_presets_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def _write_global_presets(presets_list):
    path = _global_presets_path()
    try:
        with open(path, 'w') as f:
            json.dump(presets_list, f, indent=2)
        return True
    except Exception:
        return False

class PhoMoPresetItem(bpy.types.PropertyGroup):
    """Represents one saved preset stored in the .blend file (scene scope)."""

    focal_length: bpy.props.FloatProperty(default=50.0)
    fstop: bpy.props.FloatProperty(default=2.8)
    exposure: bpy.props.FloatProperty(default=0.0)
    res_x: bpy.props.IntProperty(default=1920)
    res_y: bpy.props.IntProperty(default=1080)

    has_focal_length: bpy.props.BoolProperty(default=False)
    has_fstop: bpy.props.BoolProperty(default=False)
    has_exposure: bpy.props.BoolProperty(default=False)
    has_dimensions: bpy.props.BoolProperty(default=False)


class PhoMoProperties(bpy.types.PropertyGroup):
    """Scene-level PhoMo state."""

    fstop: bpy.props.FloatProperty(
        name="F-Stop",
        description=(
            "Aperture f-stop value. "
            "Automatically enables Depth of Field on the active camera"
        ),
        min=0.1, max=64.0, default=2.8,
        step=10, precision=1,
        update=_update_fstop,
    )

    cinematic_active: bpy.props.BoolProperty(
        name="Cinematic View Active",
        default=False,
    )

    custom_res_x: bpy.props.IntProperty(
        name="Width",
        description="Custom render width in pixels",
        default=1920, min=1, max=32768,
    )

    custom_res_y: bpy.props.IntProperty(
        name="Height",
        description="Custom render height in pixels",
        default=1080, min=1, max=32768,
    )

    show_global_presets: bpy.props.BoolProperty(
        name="Show Global Presets",
        description="Switch between scene presets (saved in .blend) and global presets (saved to disk)",
        default=False,
    )


class PHOMO_OT_focus_on_selection(bpy.types.Operator):
    bl_idname = "phomo.focus_on_selection"
    bl_label = "Focus on Selection"
    bl_description = (
        "Set the active camera's DoF focus object to the active selected object. "
        "Automatically enables Depth of Field"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cam = _get_active_camera(context)
        active = context.active_object
        return (
            cam is not None
            and active is not None
            and active != cam
            and active in context.selected_objects
        )

    def execute(self, context):
        cam = _get_active_camera(context)
        target = context.active_object
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = target
        self.report({'INFO'}, f"PhoMo: Focus locked to \"{target.name}\"")
        return {'FINISHED'}

class PHOMO_OT_toggle_cinematic(bpy.types.Operator):
    bl_idname = "phomo.toggle_cinematic"
    bl_label = "Toggle Cinematic View"
    bl_description = "Toggle all viewport overlays and gizmos for a clean cinematic view"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return isinstance(context.space_data, bpy.types.SpaceView3D)

    def execute(self, context):
        props = context.scene.phomo
        space = context.space_data
        props.cinematic_active = not props.cinematic_active
        is_cinematic = props.cinematic_active
        space.overlay.show_overlays = not is_cinematic
        space.show_gizmo = not is_cinematic
        self.report({'INFO'}, f"PhoMo: Cinematic View {'ON' if is_cinematic else 'OFF'}")
        return {'FINISHED'}

class PHOMO_OT_set_portrait(bpy.types.Operator):
    bl_idname = "phomo.set_portrait"
    bl_label = "Portrait"
    bl_description = "Swap render resolution to portrait orientation (taller than wide)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        render = context.scene.render
        w, h = render.resolution_x, render.resolution_y
        if w > h:
            render.resolution_x, render.resolution_y = h, w
        self.report({'INFO'}, f"PhoMo: Portrait {render.resolution_x}×{render.resolution_y}")
        return {'FINISHED'}


class PHOMO_OT_set_landscape(bpy.types.Operator):
    bl_idname = "phomo.set_landscape"
    bl_label = "Landscape"
    bl_description = "Swap render resolution to landscape orientation (wider than tall)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        render = context.scene.render
        w, h = render.resolution_x, render.resolution_y
        if h > w:
            render.resolution_x, render.resolution_y = h, w
        self.report({'INFO'}, f"PhoMo: Landscape {render.resolution_x}×{render.resolution_y}")
        return {'FINISHED'}


class PHOMO_OT_apply_custom_res(bpy.types.Operator):
    bl_idname = "phomo.apply_custom_res"
    bl_label = "Apply Custom Resolution"
    bl_description = "Apply the custom W×H values to the render output"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.phomo
        render = context.scene.render
        render.resolution_x = props.custom_res_x
        render.resolution_y = props.custom_res_y
        self.report(
            {'INFO'},
            f"PhoMo: Resolution set to {props.custom_res_x}×{props.custom_res_y}"
        )
        return {'FINISHED'}

class PHOMO_OT_save_preset(bpy.types.Operator):
    bl_idname = "phomo.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save current camera settings as a named preset"
    bl_options = {'REGISTER'}

    preset_name: bpy.props.StringProperty(
        name="Name",
        default="My Preset",
    )

    save_globally: bpy.props.BoolProperty(
        name="Save Globally",
        description=(
            "Save to disk so this preset is available across all .blend files. "
            "When off, preset is saved inside the current .blend file only"
        ),
        default=False,
    )

    capture_focal_length: bpy.props.BoolProperty(name="Focal Length", default=True)
    capture_fstop: bpy.props.BoolProperty(name="F-Stop", default=True)
    capture_exposure: bpy.props.BoolProperty(name="Exposure", default=True)
    capture_dimensions: bpy.props.BoolProperty(name="Dimensions", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.prop(self, "save_globally")
        layout.separator()
        layout.label(text="Capture:")
        col = layout.column(align=True)
        col.prop(self, "capture_focal_length")
        col.prop(self, "capture_fstop")
        col.prop(self, "capture_exposure")
        col.prop(self, "capture_dimensions")

    def execute(self, context):
        cam = _get_active_camera(context)
        scene = context.scene
        render = scene.render

        if not self.preset_name.strip():
            self.report({'ERROR'}, "PhoMo: Preset name cannot be empty")
            return {'CANCELLED'}

        data = {'name': self.preset_name.strip()}
        if self.capture_focal_length and cam:
            data['focal_length'] = cam.data.lens
        if self.capture_fstop and cam:
            data['fstop'] = scene.phomo.fstop
        if self.capture_exposure and cam:
            data['exposure'] = cam.data.phomo_exposure
        if self.capture_dimensions:
            data['res_x'] = render.resolution_x
            data['res_y'] = render.resolution_y

        if self.save_globally:
            presets = _read_global_presets()
            presets.append(data)
            if _write_global_presets(presets):
                self.report({'INFO'}, f"PhoMo: Preset \"{data['name']}\" saved globally")
            else:
                self.report({'ERROR'}, "PhoMo: Failed to write global presets file")
            return {'FINISHED'}

        item = scene.phomo_presets.add()
        item.name = data['name']
        if 'focal_length' in data:
            item.focal_length = data['focal_length']
            item.has_focal_length = True
        if 'fstop' in data:
            item.fstop = data['fstop']
            item.has_fstop = True
        if 'exposure' in data:
            item.exposure = data['exposure']
            item.has_exposure = True
        if 'res_x' in data:
            item.res_x = data['res_x']
            item.res_y = data['res_y']
            item.has_dimensions = True

        self.report({'INFO'}, f"PhoMo: Preset \"{item.name}\" saved to scene")
        return {'FINISHED'}


class PHOMO_OT_load_preset(bpy.types.Operator):
    bl_idname = "phomo.load_preset"
    bl_label = "Load Preset"
    bl_description = "Apply this preset to the active camera"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()
    is_global: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        cam = _get_active_camera(context)
        scene = context.scene
        render = scene.render

        if self.is_global:
            presets = _read_global_presets()
            if self.index >= len(presets):
                self.report({'ERROR'}, "PhoMo: Global preset index out of range")
                return {'CANCELLED'}
            data = presets[self.index]
            if 'focal_length' in data and cam:
                cam.data.lens = data['focal_length']
            if 'fstop' in data:
                scene.phomo.fstop = data['fstop']
            if 'exposure' in data and cam:
                cam.data.phomo_exposure = data['exposure']
            if 'res_x' in data:
                render.resolution_x = data['res_x']
                render.resolution_y = data['res_y']
            self.report({'INFO'}, f"PhoMo: Loaded global preset \"{data['name']}\"")
            return {'FINISHED'}

        if self.index >= len(scene.phomo_presets):
            self.report({'ERROR'}, "PhoMo: Scene preset index out of range")
            return {'CANCELLED'}
        item = scene.phomo_presets[self.index]
        if item.has_focal_length and cam:
            cam.data.lens = item.focal_length
        if item.has_fstop:
            scene.phomo.fstop = item.fstop
        if item.has_exposure and cam:
            cam.data.phomo_exposure = item.exposure
        if item.has_dimensions:
            render.resolution_x = item.res_x
            render.resolution_y = item.res_y
        self.report({'INFO'}, f"PhoMo: Loaded preset \"{item.name}\"")
        return {'FINISHED'}


class PHOMO_OT_delete_preset(bpy.types.Operator):
    bl_idname = "phomo.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Permanently delete this preset"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()
    is_global: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene

        if self.is_global:
            presets = _read_global_presets()
            if self.index >= len(presets):
                return {'CANCELLED'}
            name = presets[self.index].get('name', 'Unnamed')
            presets.pop(self.index)
            _write_global_presets(presets)
            self.report({'INFO'}, f"PhoMo: Deleted global preset \"{name}\"")
            return {'FINISHED'}

        if self.index >= len(scene.phomo_presets):
            return {'CANCELLED'}
        name = scene.phomo_presets[self.index].name
        scene.phomo_presets.remove(self.index)
        self.report({'INFO'}, f"PhoMo: Deleted preset \"{name}\"")
        return {'FINISHED'}

class VIEW3D_PT_phomo(bpy.types.Panel):
    """Root panel — shows active camera name, hosts all subpanels."""
    bl_label = "PhoMo Camera"
    bl_idname = "VIEW3D_PT_phomo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"

    def draw(self, context):
        layout = self.layout
        cam = _get_active_camera(context)

        if cam is None:
            col = layout.column(align=True)
            col.label(text="No active camera.", icon='ERROR')
            col.label(text="Set one in Scene Properties.")
            return

        row = layout.row()
        row.label(text=cam.name, icon='CAMERA_DATA')

class VIEW3D_PT_phomo_lens(bpy.types.Panel):
    bl_label = "Lens"
    bl_idname = "VIEW3D_PT_phomo_lens"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"
    bl_parent_id = "VIEW3D_PT_phomo"

    @classmethod
    def poll(cls, context):
        return _get_active_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.phomo
        cam = _get_active_camera(context)

        col = layout.column(align=True)
        col.prop(cam.data, "lens", text="Focal Length")
        col.prop(props, "fstop", text="F-Stop")

        if not _dof_visible(context):
            row = col.row()
            row.alert = True
            row.label(
                text="Switch to Material Preview or Rendered to see DoF",
                icon='ERROR',
            )
        elif cam.data.dof.use_dof:
            row = col.row()
            row.enabled = False
            row.label(text="Depth of Field active", icon='CHECKMARK')

        layout.separator(factor=0.5)

        col = layout.column(align=True)
        col.label(text="Focus", icon='EYEDROPPER')
        focus_obj = cam.data.dof.focus_object
        if focus_obj is not None:
            row = col.row()
            row.enabled = False
            row.label(text=focus_obj.name, icon='OBJECT_DATA')

        row = col.row()
        row.scale_y = 1.2
        row.operator("phomo.focus_on_selection", text="Focus on Selection", icon='CURSOR')

class VIEW3D_PT_phomo_frame(bpy.types.Panel):
    bl_label = "Frame"
    bl_idname = "VIEW3D_PT_phomo_frame"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"
    bl_parent_id = "VIEW3D_PT_phomo"

    @classmethod
    def poll(cls, context):
        return _get_active_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.phomo
        render = context.scene.render

        row = layout.row()
        row.enabled = False
        row.label(
            text=f"{render.resolution_x} \u00d7 {render.resolution_y}",
            icon='IMAGE_DATA',
        )

        layout.separator(factor=0.3)

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("phomo.set_landscape", text="Landscape")
        row.operator("phomo.set_portrait", text="Portrait")

        layout.separator(factor=0.3)

        col = layout.column(align=True)
        col.label(text="Custom")
        row = col.row(align=True)
        row.prop(props, "custom_res_x", text="W")
        row.prop(props, "custom_res_y", text="H")
        col.operator("phomo.apply_custom_res", text="Apply", icon='CHECKMARK')

class VIEW3D_PT_phomo_exposure(bpy.types.Panel):
    bl_label = "Exposure"
    bl_idname = "VIEW3D_PT_phomo_exposure"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"
    bl_parent_id = "VIEW3D_PT_phomo"

    @classmethod
    def poll(cls, context):
        return _get_active_camera(context) is not None

    def draw(self, context):
        layout = self.layout
        cam = _get_active_camera(context)

        col = layout.column(align=True)
        col.prop(cam.data, "phomo_exposure", text="Exposure (EV)", slider=True)

        row = col.row()
        row.enabled = False
        row.label(text="Per-camera. Synced on camera switch.", icon='INFO')

class VIEW3D_PT_phomo_view(bpy.types.Panel):
    bl_label = "View"
    bl_idname = "VIEW3D_PT_phomo_view"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"
    bl_parent_id = "VIEW3D_PT_phomo"

    def draw(self, context):
        layout = self.layout
        props = context.scene.phomo
        is_cinematic = props.cinematic_active

        row = layout.row()
        row.scale_y = 1.4
        row.operator(
            "phomo.toggle_cinematic",
            text="Exit Cinematic" if is_cinematic else "Cinematic View",
            icon='CHECKMARK' if is_cinematic else 'PLAY',
            depress=is_cinematic,
        )

class VIEW3D_PT_phomo_presets(bpy.types.Panel):
    bl_label = "Presets"
    bl_idname = "VIEW3D_PT_phomo_presets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PhoMo"
    bl_parent_id = "VIEW3D_PT_phomo"

    def draw(self, context):
        layout = self.layout
        props = context.scene.phomo
        scene = context.scene

        row = layout.row()
        row.scale_y = 1.2
        row.operator("phomo.save_preset", text="Save Preset", icon='ADD')

        layout.separator(factor=0.3)

        row = layout.row(align=True)
        row.prop(
            props, "show_global_presets",
            text="Global" if props.show_global_presets else "Scene",
            toggle=True,
            icon='WORLD' if props.show_global_presets else 'SCENE_DATA',
        )

        layout.separator(factor=0.3)

        if props.show_global_presets:
            self._draw_global_presets(layout)
        else:
            self._draw_scene_presets(layout, scene)

    @staticmethod
    def _preset_tag_string(has_fl, has_fs, has_ev, has_dim, res_x=0, res_y=0):
        tags = []
        if has_fl: tags.append("FL")
        if has_fs: tags.append("f/")
        if has_ev: tags.append("EV")
        if has_dim: tags.append(f"{res_x}\u00d7{res_y}")
        return " ".join(tags)

    def _draw_scene_presets(self, layout, scene):
        if not scene.phomo_presets:
            layout.label(text="No scene presets saved.", icon='INFO')
            return

        for i, item in enumerate(scene.phomo_presets):
            box = layout.box()
            row = box.row(align=True)
            row.label(text=item.name, icon='BOOKMARKS')
            op = row.operator("phomo.load_preset", text="", icon='IMPORT')
            op.index = i; op.is_global = False
            op = row.operator("phomo.delete_preset", text="", icon='TRASH')
            op.index = i; op.is_global = False

            tag_str = self._preset_tag_string(
                item.has_focal_length, item.has_fstop,
                item.has_exposure, item.has_dimensions,
                item.res_x, item.res_y,
            )
            if tag_str:
                sub = box.row()
                sub.enabled = False
                sub.label(text=tag_str)

    def _draw_global_presets(self, layout):
        presets = _read_global_presets()
        if not presets:
            layout.label(text="No global presets saved.", icon='INFO')
            return

        for i, data in enumerate(presets):
            box = layout.box()
            row = box.row(align=True)
            row.label(text=data.get('name', 'Unnamed'), icon='WORLD')
            op = row.operator("phomo.load_preset", text="", icon='IMPORT')
            op.index = i; op.is_global = True
            op = row.operator("phomo.delete_preset", text="", icon='TRASH')
            op.index = i; op.is_global = True

            tag_str = self._preset_tag_string(
                'focal_length' in data, 'fstop' in data,
                'exposure' in data, 'res_x' in data,
                data.get('res_x', 0), data.get('res_y', 0),
            )
            if tag_str:
                sub = box.row()
                sub.enabled = False
                sub.label(text=tag_str)

_classes = (
    PhoMoPresetItem,
    PhoMoProperties,
    PHOMO_OT_focus_on_selection,
    PHOMO_OT_toggle_cinematic,
    PHOMO_OT_set_portrait,
    PHOMO_OT_set_landscape,
    PHOMO_OT_apply_custom_res,
    PHOMO_OT_save_preset,
    PHOMO_OT_load_preset,
    PHOMO_OT_delete_preset,
    VIEW3D_PT_phomo,
    VIEW3D_PT_phomo_lens,
    VIEW3D_PT_phomo_frame,
    VIEW3D_PT_phomo_exposure,
    VIEW3D_PT_phomo_view,
    VIEW3D_PT_phomo_presets,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.phomo = bpy.props.PointerProperty(type=PhoMoProperties)
    bpy.types.Scene.phomo_presets = bpy.props.CollectionProperty(type=PhoMoPresetItem)

    bpy.types.Camera.phomo_exposure = bpy.props.FloatProperty(
        name="PhoMo Exposure",
        description=(
            "Per-camera exposure (EV). PhoMo syncs this to scene "
            "Color Management exposure whenever the active camera changes"
        ),
        min=-10.0, max=10.0, default=0.0,
        update=_update_camera_exposure,
    )

    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)

    del bpy.types.Camera.phomo_exposure
    del bpy.types.Scene.phomo_presets
    del bpy.types.Scene.phomo

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()