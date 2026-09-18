# -*- coding: utf-8 -*-
"""
中秋玉兔小摆件 V1 —— 块面验证版
只包含 4 个核心元素：玉兔主体 / 双手抱月饼 / 身后月环 / 圆形底座
尺寸单位：毫米（桌面小摆件，未锁死打印尺寸，等比放大缩小即可）

无头运行:
    blender -b --factory-startup -P yutu_v1.py
"""

import bpy
import math
import os
import sys
import traceback
from mathutils import Vector, Matrix

# ============================================================
# 0. 全局参数（所有尺寸 mm，V1 比例可调）
# ============================================================
OUT_DIR = r"D:\笨小丁\下载\yutu_v1"

BLEND_PATH = os.path.join(OUT_DIR, "yutu_v1.blend")
GLB_PATH   = os.path.join(OUT_DIR, "yutu_v1.glb")
STL_PATH   = os.path.join(OUT_DIR, "yutu_v1.stl")
PNG_FRONT  = os.path.join(OUT_DIR, "preview_front.png")
PNG_3Q     = os.path.join(OUT_DIR, "preview_3q.png")

# 相机公共注视点
AIM = (0.0, -2.0, 40.0)

def log(msg):
    print("[yutu] %s" % msg, flush=True)


# ============================================================
# 1. 场景初始化 & 单位 & 材质
# ============================================================
def reset_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                  bpy.data.cameras, bpy.data.lights, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    scn = bpy.context.scene
    us = scn.unit_settings
    us.system = 'METRIC'
    us.length_unit = 'MILLIMETERS'
    us.scale_length = 0.001

    # 渲染设置：EEVEE（5.x 为 EEVEE Next），失败则回退 CYCLES
    avail_engines = {e.identifier for e in
                     bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if eng in avail_engines:
            scn.render.engine = eng
            break
    else:
        scn.render.engine = "CYCLES"
        scn.cycles.samples = 32
    log("render engine: %s" % scn.render.engine)

    for attr, val in (("taa_render_samples", 64),
                      ("taa_samples", 64),
                      ("samples", 64)):
        if hasattr(scn.eevee, attr):
            setattr(scn.eevee, attr, val)

    scn.render.resolution_x = 800
    scn.render.resolution_y = 800
    scn.render.resolution_percentage = 100
    scn.render.image_settings.file_format = 'PNG'
    scn.render.image_settings.color_mode = 'RGB'

    # Q 版手办预览要颜色干净直接，不用 AgX 的高调胶片感
    try:
        scn.view_settings.view_transform = 'Standard'
        scn.view_settings.look = 'None'
    except TypeError:
        pass
    scn.view_settings.exposure = 0.0

    # 暖色世界背景（参考图米色）
    world = bpy.data.worlds.new("World")
    scn.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.93, 0.88, 0.84, 1.0)
    bg.inputs[1].default_value = 0.8


def make_mat(name, color, roughness=0.55, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return m


MAT = {}

def init_materials():
    MAT['rabbit'] = make_mat("玉兔白",   (0.985, 0.955, 0.925), 0.55)
    MAT['inner']  = make_mat("内耳粉",   (1.000, 0.760, 0.800), 0.60)
    MAT['pad']    = make_mat("肉垫粉",   (1.000, 0.620, 0.700), 0.55)
    MAT['nose']   = make_mat("鼻粉",     (1.000, 0.560, 0.660), 0.40)
    MAT['blush']  = make_mat("腮红",     (1.000, 0.600, 0.660), 0.75)
    MAT['eye']    = make_mat("眼黑",     (0.070, 0.045, 0.035), 0.15)
    MAT['hi']     = make_mat("眼神光",   (1.000, 1.000, 1.000), 0.05)
    MAT['mouth']  = make_mat("口腔红",   (0.520, 0.100, 0.120), 0.40)
    MAT['tongue'] = make_mat("舌粉",     (0.960, 0.400, 0.500), 0.45)
    MAT['gold']   = make_mat("哑光金",   (0.920, 0.640, 0.220), 0.32, metallic=1.0)
    MAT['wood']   = make_mat("深木座",   (0.250, 0.145, 0.085), 0.45)
    MAT['cake']   = make_mat("月饼金棕", (0.860, 0.500, 0.160), 0.60)
    MAT['floor']  = make_mat("地面米",   (0.875, 0.815, 0.760), 0.90)


# ============================================================
# 2. 通用建模工具
# ============================================================
def smooth_obj(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def add_sphere(name, location, scale=1.0, rotation=(0, 0, 0), mat=None, subdiv=2):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20,
                                         location=location)
    ob = bpy.context.object
    ob.name = name
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    ob.scale = scale
    ob.rotation_euler = rotation
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def add_capsule(name, location, radius=4.0, length=10.0, scale=(1, 1, 1),
                rotation=(0, 0, 0), mat=None):
    """5.x 自带胶囊体；老版本兜底用 圆柱+两球。"""
    try:
        bpy.ops.mesh.primitive_capsule_add(radius=radius, length=length,
                                           segments=16, location=location)
        ob = bpy.context.object
    except Exception:
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius,
                                            depth=length, location=location)
        cyl = bpy.context.object
        top = add_sphere("_cap_t", (0, 0, length / 2), radius)
        bot = add_sphere("_cap_b", (0, 0, -length / 2), radius)
        top.parent = cyl
        bot.parent = cyl
        bpy.ops.object.select_all(action='DESELECT')
        cyl.select_set(True)
        top.select_set(True)
        bot.select_set(True)
        bpy.context.view_layer.objects.active = cyl
        bpy.ops.object.join()
        ob = cyl
    ob.name = name
    ob.scale = scale
    ob.rotation_euler = rotation
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def apply_bevel(obj, amount, segments=3):
    mod = obj.modifiers.new("倒角", 'BEVEL')
    mod.width = amount
    mod.segments = segments
    mod.limit_method = 'NONE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def apply_all_transforms(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')


def join_and_remesh(name, objects, voxel):
    """融合多个相交球体为单一水密网格（体素重构）。"""
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    ob = bpy.context.object
    ob.name = name

    mod = ob.modifiers.new("体素融合", 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = voxel
    if hasattr(mod, "use_smooth_shade"):
        mod.use_smooth_shade = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    smooth_obj(ob)
    bpy.ops.object.select_all(action='DESELECT')
    return ob


# ============================================================
# 3. 底座（深色圆台 + 一圈金箍）
# ============================================================
def build_base():
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=36, depth=12,
                                        location=(0, 0, 6))
    base = bpy.context.object
    base.name = "底座"
    base.data.materials.append(MAT['wood'])
    apply_bevel(base, 1.2, 3)
    smooth_obj(base)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=35.4, minor_radius=0.8,
        major_segments=80, minor_segments=12,
        location=(0, 0, 12.2))
    rim = bpy.context.object
    rim.name = "底座金箍"
    rim.data.materials.append(MAT['gold'])
    smooth_obj(rim)
    return [base, rim]


# ============================================================
# 4. 月环（圆管弯成的月牙弧，下端埋入底座锚固）
# ============================================================
def build_moon_ring():
    R = 35.0          # 环半径
    CZ = 39.0         # 环心高度（保证最低管段藏在底座 0~12 内）
    Y = 9.0           # 位于兔子身后
    TUBE = 4.0        # 圆管粗
    A0 = math.radians(150)    # 左上尖端（10 点钟，将来挂灯笼）
    A1 = math.radians(-150)   # 左下尖端（8 点钟悬空小尖；环道经底座内锚固）
    N = 200

    cu = bpy.data.curves.new("月环曲线", type='CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 2
    cu.bevel_depth = TUBE
    cu.bevel_resolution = 5
    cu.use_fill_caps = True

    sp = cu.splines.new('POLY')
    sp.points.add(N - 1)
    for i in range(N):
        a = A0 + (A1 - A0) * i / (N - 1)
        x = R * math.cos(a)
        z = CZ + R * math.sin(a)
        sp.points[i].co = (x, Y, z, 1.0)

    ring = bpy.data.objects.new("月环", cu)
    bpy.context.collection.objects.link(ring)

    # 曲线转网格，方便后续导出/融合
    bpy.ops.object.select_all(action='DESELECT')
    ring.select_set(True)
    bpy.context.view_layer.objects.active = ring
    bpy.ops.object.convert(target='MESH')
    ring = bpy.context.object
    ring.data.materials.append(MAT['gold'])
    smooth_obj(ring)
    return ring


# ============================================================
# 5. 玉兔（头/身/耳/四肢/尾，白色部分最后体素融合为一体）
# ============================================================
def build_rabbit():
    white = []  # 参与白色主体融合的部件
    decor = []  # 粉色/黑色装饰贴片（单独保留，供渲染与 GLB）

    # ---- 身体（坐姿梨形：球+球叠压）----
    white.append(add_sphere("身体", (0, 1, 26.5),
                            scale=(14, 12, 15), mat=MAT['rabbit']))

    # ---- 头（Q 版大头）----
    white.append(add_sphere("头", (0, 0.5, 49),
                            scale=(17.2, 16.0, 17.5), mat=MAT['rabbit']))
    # 两颊
    white.append(add_sphere("左颊", (-9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))
    white.append(add_sphere("右颊", (9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))

    # ---- 长耳朵（外白内粉，略外八、略前倾）----
    for sx, name in ((-1, "左耳"), (1, "右耳")):
        rot = (math.radians(-10), math.radians(sx * 13), 0)
        outer = add_capsule(name, (sx * 6.5, 3.5, 64),
                            radius=4.2, length=13,
                            scale=(1, 0.72, 1), rotation=rot,
                            mat=MAT['rabbit'])
        white.append(outer)

        inner = add_capsule(name + "内耳", (0, 0, 0),
                            radius=2.5, length=8,
                            scale=(1, 0.5, 1), mat=MAT['inner'])
        M = outer.matrix_world @ Matrix.Translation((0, -3.1, -0.5))
        inner.matrix_world = M
        decor.append(inner)

    # ---- 前肢 + 抱月饼的小手 ----
    for sx in (-1, 1):
        shoulder = Vector((sx * 12, -4, 38.5))
        paw = Vector((sx * 10.8, -14.0, 33.5))
        d = paw - shoulder
        quat = d.normalized().to_track_quat('Z', 'Y')
        arm = add_capsule("手臂", (shoulder + paw) / 2,
                          radius=3.8, length=3.2,
                          scale=(1, 1, 1), mat=MAT['rabbit'])
        arm.rotation_euler = quat.to_euler()
        white.append(arm)
        white.append(add_sphere("手", paw,
                                scale=(5.2, 5.2, 4.8), mat=MAT['rabbit']))

    # ---- 朝前坐的两只后脚 + 粉色脚掌垫 ----
    for sx in (-1, 1):
        foot = add_sphere("脚", (sx * 10.5, -6.5, 17.8),
                          scale=(8.5, 9.8, 7.0),
                          rotation=(0, 0, math.radians(sx * 6)),
                          mat=MAT['rabbit'])
        white.append(foot)

        decor.append(add_sphere("脚掌大垫", (sx * 10.5, -15.8, 16.0),
                                scale=(3.0, 0.9, 3.6), mat=MAT['pad']))
        for k, dx in enumerate((-2.3, 0, 2.3)):
            decor.append(add_sphere(
                "脚趾垫", (sx * 10.5 + dx, -15.3, 19.6),
                scale=(1.0, 0.45, 1.0), mat=MAT['pad']))

    # ---- 小尾巴 ----
    white.append(add_sphere("尾巴", (0, 11, 23),
                            scale=(5, 5, 5), mat=MAT['rabbit']))

    # ---- 五官 ----
    for sx in (-1, 1):
        decor.append(add_sphere("眼睛", (sx * 6.3, -13.8, 52.5),
                                scale=(3.2, 1.9, 3.6), mat=MAT['eye']))
        decor.append(add_sphere("眼神光", (sx * 7.4, -15.6, 53.7),
                                scale=(0.95, 0.6, 0.95), mat=MAT['hi']))
        decor.append(add_sphere("腮红", (sx * 10.6, -11.6, 45.5),
                                scale=(2.6, 0.9, 2.1), mat=MAT['blush']))

    decor.append(add_sphere("鼻子", (0, -15.3, 46.3),
                            scale=(2.0, 1.0, 1.3), mat=MAT['nose']))
    decor.append(add_sphere("口腔", (0, -14.6, 43.4),
                            scale=(3.1, 2.0, 3.4), mat=MAT['mouth']))
    decor.append(add_sphere("舌头", (0, -16.0, 42.7),
                            scale=(1.5, 0.9, 1.1), mat=MAT['tongue']))

    return white, decor


# ============================================================
# 6. 月饼（V1 仅为带倒角的短圆柱，不做花纹与文字）
# ============================================================
def build_mooncake():
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=10.0, depth=7,
                                        location=(0, -13.5, 33.5),
                                        rotation=(math.radians(90), 0, 0))
    cake = bpy.context.object
    cake.name = "月饼"
    cake.data.materials.append(MAT['cake'])
    apply_bevel(cake, 0.9, 3)
    smooth_obj(cake)
    return cake


# ============================================================
# 7. 灯光 / 地面 / 相机
# ============================================================
def add_area_light(name, loc, energy, size):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    return ob


def build_studio():
    add_area_light("主光", (0, -70, 110), 500, 60)
    add_area_light("补光", (-60, -20, 60), 150, 50)
    add_area_light("轮廓光", (50, 60, 80), 300, 50)

    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.15))
    floor = bpy.context.object
    floor.name = "地面"
    floor.data.materials.append(MAT['floor'])

    tgt = bpy.data.objects.new("相机注视点", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = AIM

    cams = {}
    for name, loc, lens in (
        ("front", (0, -128, 52), 50),
        ("3q",    (82, -100, 55), 50),
    ):
        cd = bpy.data.cameras.new("cam_" + name)
        cd.lens = lens
        cam = bpy.data.objects.new("cam_" + name, cd)
        bpy.context.collection.objects.link(cam)
        cam.location = loc
        con = cam.constraints.new('TRACK_TO')
        con.target = tgt
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        cams[name] = cam
    return cams


def render_to(cam, path):
    scn = bpy.context.scene
    scn.camera = cam
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("rendered -> %s" % path)


# ============================================================
# 8. 导出
# ============================================================
def export_glb():
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format='GLB',
        export_apply=True,
    )
    log("exported -> %s" % GLB_PATH)


def build_print_solid(structural):
    """把所有结构件深拷贝后体素融合成一个水密实体，专供 STL。"""
    copies = []
    for ob in structural:
        n = ob.copy()
        n.data = ob.data.copy()
        bpy.context.collection.objects.link(n)
        copies.append(n)

    solid = join_and_remesh("打印一体实体", copies, voxel=0.7)
    return solid


def export_stl(solid):
    bpy.ops.object.select_all(action='DESELECT')
    solid.select_set(True)
    bpy.context.view_layer.objects.active = solid

    # Blender 4.5+/5.x：bpy.ops.wm.stl_export；旧版：bpy.ops.export_mesh.stl
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(
            filepath=STL_PATH,
            export_selected_objects=True,
            ascii_format=False,
            global_scale=1.0,
            apply_modifiers=True,
        )
    else:
        op_props = {p.identifier for p in
                    bpy.ops.export_mesh.stl.get_rna_type().properties}
        kwargs = {"filepath": STL_PATH, "global_scale": 1.0}
        if "as_binary" in op_props:
            kwargs["as_binary"] = True
        if "use_selection" in op_props:
            kwargs["use_selection"] = True
        bpy.ops.export_mesh.stl(**kwargs)
    log("exported -> %s" % STL_PATH)


# ============================================================
# main
# ============================================================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    reset_scene()
    init_materials()

    log("building base ...")
    base_parts = build_base()

    log("building moon ring ...")
    ring = build_moon_ring()

    log("building rabbit ...")
    white_parts, decor_parts = build_rabbit()

    log("building mooncake ...")
    cake = build_mooncake()

    # 统一应用旋转/缩放后，再把白色部件融合
    all_meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    apply_all_transforms(all_meshes)

    rabbit = join_and_remesh("玉兔主体", white_parts, voxel=0.55)
    structural = base_parts + [ring, rabbit, cake]

    log("building studio & rendering ...")
    cams = build_studio()
    render_to(cams['front'], PNG_FRONT)
    render_to(cams['3q'], PNG_3Q)

    log("exporting glb ...")
    export_glb()

    log("building watertight solid & exporting stl ...")
    solid = build_print_solid(structural)
    export_stl(solid)
    # STL 实体不参与渲染，只保留在 blend 里备用
    solid.hide_set(True)
    solid.hide_render = True

    log("saving blend ...")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    log("DONE")


try:
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
