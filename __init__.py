# MIT License
#
# Copyright (c) 2023 aurycat
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


bl_info = {
    "name": "Vertex Color Utils",
    "description": "Adds vertex color channel masks, channel swizzling, and a vertex color sampler.",
    "author": "aurycat",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Vertex Paint > Paint",
    "warning": "",
    "doc_url": "",
    "tracker_url": "https://gitlab.com/aurycat/blender-vertex-color-utils",
    "support": "COMMUNITY",
    "category": "Mesh",
}

import bpy
import re
from bpy.types import Operator
from bpy_extras import view3d_utils
import mathutils


############
### Init ###
############

def main():
    # Invoke unregister op on an existing "install" of the plugin before
    # re-registering. Lets you press the "Run Script" button without having
    # to maually unregister or run Blender > Reload Scripts first.
    if ('vertex_color_utils' in dir(bpy.ops)) and ('unregister' in dir(bpy.ops.vertex_color_utils)):
        bpy.ops.vertex_color_utils.unregister()
    register()

def register():
    bpy.utils.register_class(VCU_OT_apply_mask)
    bpy.utils.register_class(VCU_OT_create_color_channel_mask)
    bpy.utils.register_class(VCU_OT_swizzle_channels)
    bpy.utils.register_class(VCU_OT_sample_vertex_color)
    bpy.utils.register_class(VCU_OT_unregister)
    bpy.types.VIEW3D_MT_paint_vertex.append(vcu_draw_menu)

def unregister():
    sample_vertex_color_end()
    bpy.types.VIEW3D_MT_paint_vertex.remove(vcu_draw_menu)
    bpy.utils.unregister_class(VCU_OT_apply_mask)
    bpy.utils.unregister_class(VCU_OT_create_color_channel_mask)
    bpy.utils.unregister_class(VCU_OT_swizzle_channels)
    bpy.utils.unregister_class(VCU_OT_sample_vertex_color)
    bpy.utils.unregister_class(VCU_OT_unregister)

class VCU_OT_unregister(Operator):
    bl_idname = "vertex_color_utils.unregister"
    bl_label = "Unregister"
    bl_options = {"REGISTER"}

    def execute(self, context):
        unregister()
        return {'FINISHED'}

def vcu_draw_menu(self, context):
    layout = self.layout
    ob = context.view_layer.objects.active
    if ob.type != 'MESH':
        return
    mesh = ob.data

    layout.separator()
    layout.operator("vertex_color_utils.sample_vertex_color", text="Sample Vertex Color")

    layout.separator()
    layout.operator("vertex_color_utils.swizzle_channels")
    if attr_name_is_mask(mesh.color_attributes.active_color_name):
        layout.operator("vertex_color_utils.apply_mask")
    else:
        r = layout.operator("vertex_color_utils.create_color_channel_mask", text="R Mask")
        r.channels = {'R'}
        g = layout.operator("vertex_color_utils.create_color_channel_mask", text="G Mask")
        g.channels = {'G'}
        b = layout.operator("vertex_color_utils.create_color_channel_mask", text="B Mask")
        b.channels = {'B'}
        a = layout.operator("vertex_color_utils.create_color_channel_mask", text="A Mask")
        a.channels = {'A'}

#    layout.separator()
#    layout.operator("vertex_color_utils.unregister")



##############
### Shared ###
##############

def shared_poll(self, context):
    if context.mode != 'PAINT_VERTEX':
        self.poll_message_set("failed, operator must be run in Vertex Paint mode")
        return False
    ob = context.active_object
    if ob == None or ob.type != 'MESH':
        self.poll_message_set("failed, no active (selected) MESH object")
        return False
    return True



#############################
### Color Channel Masking ###
#############################

in_update = False
def channels_prop_update(self, context):
    global in_update
    if not in_update:
        in_update = True
        try:
            if 'A' in self.channels and len(self.channels) > 1:
                self.channels = {'A'}
        finally:
            in_update = False

class VCU_OT_create_color_channel_mask(Operator):
    bl_idname = "vertex_color_utils.create_color_channel_mask"
    bl_label = "Create Vertex Color Channel Mask"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Create a new color attribute layer which is only a subset of the color channels. That layer can then be re-applied after editing via clicking Paint > Apply Channel Mask"

    enum_items = (
        ('R', "R", "Include red channel in mask (can select multiple)"),
        ('G', "G", "Include green channel in mask (can select multiple)"),
        ('B', "B", "Include blue channel in mask (can select multiple)"),
        None,
        ('A', "A", "Create mask for alpha channel (cannot also include R/G/B)"),
    )
    channels: bpy.props.EnumProperty(name="Channels", items=enum_items, options={'ENUM_FLAG'}, update=channels_prop_update)

    @classmethod
    def poll(self, context):
        return shared_poll(self, context)

    def execute(self, context):
        ob = context.active_object
        mesh = ob.data
        color_attrs = mesh.color_attributes

        channel_str = make_channel_str(self.channels)
        if channel_str == '':
            # Return FINISHED not CANCELLED so blender still treats it as having
            # something to undo. That way if you are changing the parameters after
            # initiating the operator, and select no channels, it clears the mask
            # made previously.
            return {'FINISHED'}

        base_attr = color_attrs.active_color
        if attr_name_is_mask(base_attr.name):
            (base_name, _) = get_mask_name_parts(base_attr.name)
            if base_name in color_attrs:
                base_attr = color_attrs[base_name]
            else:
                self.report({'ERROR_INVALID_INPUT'}, "Active vertex color attribute '" + base_attr.name + "' appears to already be a mask, and no base color attribute '" + base_name + "' can be found.")
                return {'CANCELLED'}

        conflict = check_for_conflicting_mask(color_attrs, base_attr.name, self.channels)
        if conflict != None:
            (c, a) = conflict
            self.report({'WARNING'}, "There is already a mask '" + a.name + "' which includes channel '" + c + "'. Please apply it first before making a new mask which includes that channel.")
            color_attrs.active_color = a
            (_, ch) = get_mask_name_parts(a.name)
            chs = make_channel_set(ch)
            self.channels = chs # Update the popup menu thingy blender does after applying an operator with properties
            return {'FINISHED'}

        mask_attr = create_color_channel_mask(mesh, base_attr, channel_str)

        color_attrs.active_color = mask_attr
        return {'FINISHED'}


class VCU_OT_apply_mask(bpy.types.Operator):
    bl_idname = "vertex_color_utils.apply_mask"
    bl_label = "Apply Channel Mask"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Apply the active mask color attribute to the base color attribute, and delete the mask"

    @classmethod
    def poll(self, context):
        return shared_poll(self, context)

    def execute(self, context):
        ob = context.active_object
        mesh = ob.data
        color_attrs = mesh.color_attributes
        mask_attr = color_attrs.active_color

        if not attr_name_is_mask(mask_attr.name):
            self.report({'ERROR_INVALID_INPUT'}, "Active vertex color attribute '" + mask_attr.name + "' does not appear to be a mask.")
            return {'CANCELLED'}

        (base_name, channel_str) = get_mask_name_parts(mask_attr.name)
        if not (base_name in color_attrs):
            self.report({'ERROR_INVALID_INPUT'}, "No base color attribute '" + base_name + "' can be found to apply the mask to.")
            return {'CANCELLED'}

        base_attr = color_attrs[base_name]
        copy_from_mask(base_attr, mask_attr, channel_str)

        color_attrs.remove(mask_attr)
        return {'FINISHED'}


def copy_to_mask(base, mask, ch):
    """ `base` is a Byte/FloatColorAttribute(Attribute) to copy from
        `mask` is a Byte/FloatColorAttribute(Attribute) to copy to
        `ch` is a string approximately matching /[RGBA]+/ indicating which channels to copy
    """

    if len(base.data) != len(mask.data):
        raise RuntimeError("Mask color attribute '" + mask.name + "' does not have the same amount of vertex data (len=" + str(len(mask.data)) + ") as the color base attribute '" + base.name + "' (len=" + str(len(base.data)) + ")")
    n = len(base.data)

    if ch == 'R':
        for i in range(n):
            mask.data[i].color = [base.data[i].color[0], 0, 0, 1]
    elif ch == 'G':
        for i in range(n):
            mask.data[i].color = [0, base.data[i].color[1], 0, 1]
    elif ch == 'B':
        for i in range(n):
            mask.data[i].color = [0, 0, base.data[i].color[2], 1]
    elif ch == 'A':
        for i in range(n):
            mask.data[i].color = [base.data[i].color[3], base.data[i].color[3], base.data[i].color[3], 1]
    elif ch == 'RG':
        for i in range(n):
            mask.data[i].color = [base.data[i].color[0], base.data[i].color[1], 0, 1]
    elif ch == 'RB':
        for i in range(n):
            mask.data[i].color = [base.data[i].color[0], 0, base.data[i].color[2], 1]
    elif ch == 'GB':
        for i in range(n):
            mask.data[i].color = [0, base.data[i].color[1], base.data[i].color[2], 1]
    elif ch == 'RGB':
        for i in range(n):
            mask.data[i].color = [base.data[i].color[0], base.data[i].color[1], base.data[i].color[2], 1]
    else:
        raise RuntimeError("Invalid channel string '" + ch + "'")


def copy_from_mask(base, mask, ch):
    """ `base` is a Byte/FloatColorAttribute(Attribute) to copy to
        `mask` is a Byte/FloatColorAttribute(Attribute) to copy from
        `ch` is a string approximately matching /[RGBA]+/ indicating which channels to copy
    """

    if len(base.data) != len(mask.data):
        raise RuntimeError("Mask color attribute '" + mask.name + "' does not have the same amount of vertex data (len=" + str(len(mask.data)) + ") as the color base attribute '" + base.name + "' (len=" + str(len(base.data)) + ")")
    n = len(base.data)

    if ch == 'R':
        for i in range(n):
            base.data[i].color[0] = mask.data[i].color[0]
    elif ch == 'G':
        for i in range(n):
            base.data[i].color[1] = mask.data[i].color[1]
    elif ch == 'B':
        for i in range(n):
            base.data[i].color[2] = mask.data[i].color[2]
    elif ch == 'A':
        for i in range(n):
            base.data[i].color[3] = mask.data[i].color[0]
    elif ch == 'RG':
        for i in range(n):
            base.data[i].color[0] = mask.data[i].color[0]
            base.data[i].color[1] = mask.data[i].color[1]
    elif ch == 'RB':
        for i in range(n):
            base.data[i].color[0] = mask.data[i].color[0]
            base.data[i].color[2] = mask.data[i].color[2]
    elif ch == 'GB':
        for i in range(n):
            base.data[i].color[1] = mask.data[i].color[1]
            base.data[i].color[2] = mask.data[i].color[2]
    elif ch == 'RGB':
        for i in range(n):
            base.data[i].color[0] = mask.data[i].color[0]
            base.data[i].color[1] = mask.data[i].color[1]
            base.data[i].color[2] = mask.data[i].color[2]
    else:
        raise RuntimeError("Invalid channel string '" + ch + "'")


def create_color_channel_mask(mesh, base_attr, channel_str):
    """ `mesh` is a Mesh(ID)
        `base_attr` is a Byte/FloatColorAttribute(Attribute) color attribute on the mesh to create a mask for
        `channel_str` is a string approximately matching /[RGBA]+/
    """

    color_attrs = mesh.color_attributes
    base_attr_name = base_attr.name

    mask_attr_name = base_attr_name + "__" + channel_str
    if mask_attr_name in color_attrs:
        return color_attrs[mask_attr_name]

    mask_attr = color_attrs.new(mask_attr_name, base_attr.data_type, base_attr.domain)

    # Re-get base_attr, making a new attribute seems to invalidate existing pointers
    base_attr = color_attrs[base_attr_name]

    copy_to_mask(base_attr, mask_attr, channel_str)
    return mask_attr


def make_channel_str(channels):
    """ `channels` is a set of characters in [RGBA] """
    if 'A' in channels:
        return 'A'
    str = ('R' if 'R' in channels else '')
    str += ('G' if 'G' in channels else '')
    str += ('B' if 'B' in channels else '')
    return str


def make_channel_set(channel_str):
    channels = set()
    if 'R' in channel_str: channels.add('R')
    if 'G' in channel_str: channels.add('G')
    if 'B' in channel_str: channels.add('B')
    if 'A' in channel_str: channels.add('A')
    return channels


def attr_name_is_mask(name):
    """ `name` is a color attribute name """
    return name.endswith('__R') or \
           name.endswith('__G') or \
           name.endswith('__B') or \
           name.endswith('__A') or \
           name.endswith('__RG') or \
           name.endswith('__RB') or \
           name.endswith('__GB') or \
           name.endswith('__RGB')


def get_mask_name_parts(name):
    """ `name` is a color attribute name
        Returns (base name, channel str)
    """
    if name.endswith('__R') or \
       name.endswith('__G') or \
       name.endswith('__B') or \
       name.endswith('__A'):
        return (name[:-3], name[-1:])
    if name.endswith('__RG') or \
       name.endswith('__RB') or \
       name.endswith('__GB'):
        return (name[:-4], name[-2:])
    if name.endswith('__RGB'):
        return (name[:-5], name[-3:])
    return (name, '')


def check_for_conflicting_mask(color_attrs, base_name, channels):
    for attr in color_attrs:
        if attr_name_is_mask(attr.name):
            (attr_base, attr_channel_str) = get_mask_name_parts(attr.name)
            if attr_base == base_name:
                for c in channels:
                    if c in attr_channel_str:
                        return (c, attr)
    return None



##################################
### Swizzle / Reorder Channels ###
##################################

class VCU_OT_swizzle_channels(Operator):
    bl_idname = "vertex_color_utils.swizzle_channels"
    bl_label = "Swizzle / Reorder Channels"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Reorder or copy the contents of the R, G, B, and A channels. For example, if the swizzle string is 'BGRR', B moves to R, G is unchanged, R moves to B, and R is also copied into A. The swizzle characters may also be 0 or 1 to indicate clearing that channel to solid 0 or 1."

    swizzle_str: bpy.props.StringProperty(name="Swizzle String", default="RGBA")

    @classmethod
    def poll(self, context):
        return shared_poll(self, context)

    def execute(self, context):
        ob = context.active_object
        mesh = ob.data
        color_attrs = mesh.color_attributes

        str = self.swizzle_str
        invalid_input_err_msg = "Swizzle string must be 4 characters long and only contain R, G, B, A, 0, or 1."
        if len(str) != 4:
            self.report({'ERROR_INVALID_INPUT'}, invalid_input_err_msg)
            return {'CANCELLED'}
        str = str.upper()
        for x in str:
            if not x in 'RGBA01':
                self.report({'ERROR_INVALID_INPUT'}, invalid_input_err_msg)
                return {'CANCELLED'}

        if not (('R' in str) and ('G' in str) and ('B' in str) and ('A' in str)):
            self.report({'WARNING'}, "One or more channels will be lost in this swizzle operation.")

        swizzle_channels(color_attrs.active_color, str)
        return {'FINISHED'}


def swizzle_channels(attr, swizzle_str):
    m = {'R':0, 'G':1, 'B':2, 'A':3, '0':4, '1':5}
    new_r = m[swizzle_str[0]]
    new_g = m[swizzle_str[1]]
    new_b = m[swizzle_str[2]]
    new_a = m[swizzle_str[3]]

    for i in range(len(attr.data)):
        col = [attr.data[i].color[0], attr.data[i].color[1], attr.data[i].color[2], attr.data[i].color[3], 0, 1]
        attr.data[i].color = [col[new_r], col[new_g], col[new_b], col[new_a]]



###########################
### Sample Vertex Color ###
###########################

sample_vertex_color_timer = None
prev_show_brush = True

def sample_vertex_color_end(context=bpy.context):
    global sample_vertex_color_timer
    global prev_show_brush

    try: context.window.cursor_modal_restore()
    except: pass

    try: context.area.header_text_set(None)
    except: pass

    try:
        if sample_vertex_color_timer != None:
            context.window_manager.event_timer_remove(sample_vertex_color_timer)
        sample_vertex_color_timer = None
    except: pass

    try: context.tool_settings.vertex_paint.show_brush = prev_show_brush
    except: pass

    try: context.workspace.status_text_set(None)
    except: pass


# Derived from https://devtalk.blender.org/t/pick-material-under-mouse-cursor/6978/4
class VCU_OT_sample_vertex_color(bpy.types.Operator):
    bl_idname = "vertex_color_utils.sample_vertex_color"
    bl_label = "Sample Vertex Color"
    bl_options = {"REGISTER"}
    bl_description = "Use the mouse to sample the attribute color of a particular vertex"

    first_modal = False

    @classmethod
    def poll(self, context):
        if context.space_data.type != 'VIEW_3D':
            self.poll_message_set("failed, operator must be run from the 3D Viewport space")
            return False
        return shared_poll(self, context)

    def modal(self, context, event):
        if self.first_modal or event.type == 'TIMER' or (event.type == 'LEFTMOUSE' and event.value == 'PRESS'):
            self.first_modal = False

            try:
                self.do_sample(context, event)
            except Exception as e:
                sample_vertex_color_end(context)
                raise e from None

            if event.type == 'LEFTMOUSE' and not event.ctrl:
                sample_vertex_color_end(context)
                return {'CANCELLED'}

            return {'RUNNING_MODAL'}

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            sample_vertex_color_end(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        global sample_vertex_color_timer
        global prev_show_brush
        try:
            self.first_modal = True

            # Showing the brush cursor while also doing header_text_set
            # in a modal operator makes Blender/the brush cursor behave
            # quite weirdly. Hide it while the operator is running.
            prev_show_brush = context.tool_settings.vertex_paint.show_brush
            context.tool_settings.vertex_paint.show_brush = False

            wm = context.window_manager
            if sample_vertex_color_timer != None:
                wm.event_timer_remove(sample_vertex_color_timer)
            sample_vertex_color_timer = wm.event_timer_add(0.3, window=context.window)

            wm.modal_handler_add(self)

            context.window.cursor_modal_set("EYEDROPPER")

            # No way to make a custom modal keymap afaik :(
            # The best alternative is just to set some text
            context.workspace.status_text_set("Mouse-over: Show color in header.    Ctrl-LeftClick: Write color to info log for copying.    LeftClick: Set brush color & exit.    ESC: Exit.")
        except Exception as e:
            sample_vertex_color_end(context)
            raise e from None

        return {'RUNNING_MODAL'}

    def do_sample(self, context, event):
        coord = mathutils.Vector((event.mouse_region_x, event.mouse_region_y))
        ob = context.active_object

        col_attr_val = pick_vertex_color_from_mouse_coord(ob, coord, context)

        if col_attr_val == None:
            context.area.header_text_set("Active object not under mouse cursor")
            return

        col_lin = col_attr_val.color[:]
        col_srgb = col_attr_val.color_srgb[:]

        col_lin_str = ", ".join([f2s(v) for v in col_lin])
        col_srgb_str = ", ".join([f2s(v) for v in col_srgb])
        col_lin_hex_str = col_to_hex(col_lin)
        col_srgb_hex_str = col_to_hex(col_srgb)

        if col_lin_str == col_srgb_str: # All 1s or 0s
            report_str = f"Color is  {col_lin_hex_str} ({col_lin_str})"
        else:
            report_str = f"Linear color is  {col_lin_hex_str} ({col_lin_str})  |  SRGB color is {col_srgb_hex_str} ({col_srgb_str})"

        if event.type == 'LEFTMOUSE':
            self.report({'INFO'}, report_str)

        context.area.header_text_set(report_str)

        if event.type == 'LEFTMOUSE' and not event.ctrl:
            # I'm not sure if this will always work (e.g. context doesn't have a
            # brush?) so just put it in a try/except since it's not super important
            mu_col = mathutils.Color((col_srgb[0], col_srgb[1], col_srgb[2]))
            try:
                context.tool_settings.vertex_paint.brush.color = mu_col
            except:
                pass


def col_to_hex(col):
    b = [round(c*255) for c in col]
    str = f"#{b[0]:02X}{b[1]:02X}{b[2]:02X}"
    if len(b) == 4 and b[3] != 255:
        str += f"{b[3]:02X}"
    return str


def f2s(f):
    return str(int(f)) if f.is_integer() else "{:.3f}".format(f)


def pick_vertex_color_from_mouse_coord(ob, coord, context=bpy.context):
    region = context.region
    rv3d = context.region_data
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    hit = ob.ray_cast(ray_origin, view_vector, depsgraph=context.evaluated_depsgraph_get())

    (hit_ok, location, _, face_index) = hit
    if not hit_ok:
        return None

    return pick_vertex_color_from_rayhit(ob, location, face_index, context)


def pick_vertex_color_from_rayhit(ob, hit_loc, hit_face_index, context):
    mesh = ob.data
    color_attr = mesh.color_attributes.active_color
    vert_colors = color_attr.data
    face = mesh.polygons[hit_face_index]

    if len(face.vertices) == 0:
        return None

    min_dist = float("inf")
    closest_face_vertex_index = -1

    # Find closest vertex of the face to hit location
    for i, v_idx in enumerate(face.vertices):
        v_loc = mesh.vertices[v_idx].co
        dist = (v_loc - hit_loc).magnitude
        if dist < min_dist:
            min_dist = dist
            closest_face_vertex_index = i

    if color_attr.domain == 'POINT':
        # Vertex colors are per-vertex, so len(vert_colors)
        # should equal the logical number of vertices in the
        # mesh, and should correspond with the vertex indices.
        if len(vert_colors) != len(mesh.vertices):
            raise Exception("Unexpected number of vertex color datapoints for POINT domain (got " + str(len(vert_colors)) + ", expected " + str(len(mesh.vertices)) + ")")

        closest_vertex_index = face.vertices[closest_face_vertex_index]

        return vert_colors[closest_vertex_index]

    elif color_attr.domain == 'CORNER':
        # Vertex colors are per-vertex-per-face, i.e. per-loop.
        # So len(vert_colors) should equal len(mesh.loops)
        if len(vert_colors) != len(mesh.loops):
            raise Exception("Unexpected number of vertex color datapoints for CORNER domain (got " + str(len(vert_colors)) + ", expected " + str(len(mesh.loops)) + ")")

        # face.vertices correspond to face.loop_indices,
        # so closest_face_vertex_index still works here
        closest_loop_index = face.loop_indices[closest_face_vertex_index]

        return vert_colors[closest_loop_index]

    else:
        raise Exception("Unknown domain '" + color_attr.domain + "' on active color attribute.")



if __name__ == "__main__":
    main()