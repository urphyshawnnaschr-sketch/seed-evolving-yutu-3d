# -*- coding: utf-8 -*-
"""
中秋玉兔小摆件 V2 —— 姿态/比例/呈现修正版
仍只含 4 元素：玉兔 / 月饼 / 月环 / 底座（无灯笼、祥云、牌匾、花纹）

V2 相对 V1：
  1) 前爪从“两侧夹饼”改为“搭在饼正面 10/2 点”的真怀抱；
  2) 月饼略缩小、降低，下巴与饼之间留缝；胯部+肚皮体积补齐坐姿；
  3) 耳朵改长椭球（自然收尖），左耳直、右耳外撇，不对称；
  4) 笑嘴下移与饼脱离、舌头做出来；腮红加大加深；眼睛内收防侧脸穿出；
  5) 月环收半径贴近头侧、端部加圆头；底座减厚做收分；
     灯光加 AO/软阴影，金色降金属度，整体去“平面贴纸感”。

无头运行:
    blender -b --factory-startup -P yutu_v2.py
"""

import bpy
import math
import os
import sys
import traceback
from mathutils import Vector, Matrix

# ============================================================
# 0. 全局参数（mm）
# ============================================================
OUT_DIR = r"D:\笨小丁\下载\yutu_v1"

BLEND_PATH = os.path.join(OUT_DIR, "yutu_v2.blend")
GLB_PATH   = os.path.join(OUT_DIR, "yutu_v2.glb")
STL_PATH   = os.path.join(OUT_DIR, "yutu_v2.stl")
PNG_FRONT  = os.path.join(OUT_DIR, "preview_front_v2.png")
PNG_3Q     = os.path.join(OUT_DIR, "preview_3q_v2.png")

AIM = (0.0, -3.0, 38.0)

def log(msg):
    print("[yutu2] %s" % msg, flush=True)


# ============================================================
# 1. 场景初始化
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

    avail = {e.identifier for e in
             bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if eng in avail:
            scn.render.engine = eng
            break
    else:
        scn.render.engine = "CYCLES"
        scn.cycles.samples = 48
    log("render engine: %s" % scn.render.engine)

    # EEVEE：阴影 + 环境光遮蔽（存在才开）
    for attr, val in (("use_shadows", True),
                      ("use_gtao", True),
                      ("use_raytracing", True)):
        if hasattr(scn.eevee, attr):
            try:
                setattr(scn.eevee, attr, val)
            except TypeError:
                pass
    if hasattr(scn.eevee, "gtao_distance"):
        scn.eevee.gtao_distance = 6.0

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

    try:
        scn.view_settings.view_transform = 'Standard'
        scn.view_settings.look = 'None'
    except TypeError:
        pass
    scn.view_settings.exposure = 0.0

    # 暖色世界
    world = bpy.data.worlds.new("World")
    scn.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.93, 0.88, 0.84, 1.0)
    bg.inputs[1].default_value = 0.75


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
    MAT['rabbit'] = make_mat("玉兔白",   (0.985, 0.955, 0.925), 0.58)
    MAT['inner']  = make_mat("内耳粉",   (1.000, 0.740, 0.790), 0.60)
    MAT['pad']    = make_mat("肉垫粉",   (1.000, 0.600, 0.680), 0.55)
    MAT['nose']   = make_mat("鼻粉",     (1.000, 0.540, 0.640), 0.40)
    MAT['blush']  = make_mat("腮红",     (1.000, 0.520, 0.590), 0.75)
    MAT['eye']    = make_mat("眼黑",     (0.070, 0.045, 0.035), 0.18)
    MAT['hi']     = make_mat("眼神光",   (1.000, 1.000, 1.000), 0.05)
    MAT['mouth']  = make_mat("口腔红",   (0.500, 0.090, 0.110), 0.40)
    MAT['tongue'] = make_mat("舌粉",     (0.960, 0.380, 0.480), 0.45)
    # 半哑光金：无 HDRI 环境时也不显脏黑
    MAT['gold']   = make_mat("暖金",     (0.950, 0.680, 0.250), 0.38, metallic=0.55)
    MAT['wood']   = make_mat("木座",     (.330, .200, .120), 0.42)
    MAT['cake']   = make_mat("月饼金棕", (0.860, 0.500, 0.160), 0.60)
    MAT['floor']  = make_mat("地面米",   (0.875, 0.815, 0.760), 0.90)


# ============================================================
# 2. 通用工具
# ============================================================
def smooth_obj(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def add_sphere(name, location, scale=1.0, rotation=(0, 0, 0), mat=None):
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


def add_capsule_between(name, p1, p2, radius=3.5, mat=None):
    """沿 p1→p2 放置胶囊手臂。"""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    length = max(d.length - 2 * radius, 0.5)
    try:
        bpy.ops.mesh.primitive_capsule_add(radius=radius, length=length,
                                           segments=16, location=(p1 + p2) / 2)
        ob = bpy.context.object
    except Exception:
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius,
                                            depth=d.length,
                                            location=(p1 + p2) / 2)
        ob = bpy.context.object
    ob.name = name
    ob.rotation_euler = d.normalized().to_track_quat('Z', 'Y').to_euler()
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def shade_smooth_by_angle(obj):
    """硬表面（底座/饼）按角度平滑：顶面保持平、倒角处圆、底边不花。"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.object, "shade_smooth_by_angle"):
        bpy.ops.object.shade_smooth_by_angle()
    else:
        smooth_obj(obj)


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
# 3. 底座（收分圆台 + 金箍），高度 10
# ============================================================
def build_base():
    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=36, radius2=34,
                                    depth=10, end_fill_type='NGON',
                                    location=(0, 0, 5))
    base = bpy.context.object
    base.name = "底座"
    base.data.materials.append(MAT['wood'])
    apply_bevel(base, 1.1, 3)
    shade_smooth_by_angle(base)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=33.2, minor_radius=0.7,
        major_segments=80, minor_segments=12,
        location=(0, 0, 10.1))
    rim = bpy.context.object
    rim.name = "底座金箍"
    rim.data.materials.append(MAT['gold'])
    smooth_obj(rim)
    return [base, rim]


# ============================================================
# 4. 月环（R32，贴头侧；两端加圆球封头）
# ============================================================
def build_moon_ring():
    R = 32.0
    CZ = 40.0          # 环心高：最低管段 z = 40-32-4 = 4，藏在底座内
    Y = 9.0
    TUBE = 4.0
    A0 = math.radians(150)     # 左上尖端（将来挂灯笼）
    A1 = math.radians(-132)    # 左下月牙尖（收到左脚后方，仅露月牙边）
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
        sp.points[i].co = (R * math.cos(a), Y,
                           CZ + R * math.sin(a), 1.0)

    ring = bpy.data.objects.new("月环", cu)
    bpy.context.collection.objects.link(ring)
    bpy.ops.object.select_all(action='DESELECT')
    ring.select_set(True)
    bpy.context.view_layer.objects.active = ring
    bpy.ops.object.convert(target='MESH')
    ring = bpy.context.object
    ring.data.materials.append(MAT['gold'])
    smooth_obj(ring)

    # 圆头封端，避免“平切管”既视感
    tips = []
    for a in (A0, A1):
        tips.append(add_sphere("环端",
            (R * math.cos(a), Y, CZ + R * math.sin(a)),
            scale=TUBE, mat=MAT['gold']))
    ring = join_and_remesh("月环", [ring] + tips, voxel=0.6)
    return ring


# ============================================================
# 5. 玉兔 V2
# ============================================================
def build_rabbit():
    white = []
    decor = []

    # ---- 躯干：上身球 + 胯部球 + 前凸肚皮，合成坐姿梨形 ----
    white.append(add_sphere("上身", (0, 1.0, 26.5),
                            scale=(14, 12, 14.5), mat=MAT['rabbit']))
    white.append(add_sphere("胯部", (0, 2.5, 20.0),
                            scale=(15, 12.5, 9.0), mat=MAT['rabbit']))
    white.append(add_sphere("肚皮", (0, -7.0, 25.0),
                            scale=(10.5, 7.0, 6.5), mat=MAT['rabbit']))

    # ---- 头 ----
    white.append(add_sphere("头", (0, 0.5, 49),
                            scale=(17.2, 16.0, 17.5), mat=MAT['rabbit']))
    white.append(add_sphere("左颊", (-9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))
    white.append(add_sphere("右颊", (9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))

    # ---- 耳朵：长椭球自然收尖，左耳直、右耳外撇 ----
    ears = [
        # name, x, z, 绕X前倾角, 绕Z外撇角
        ("左耳", -5.5, 67.0, -8, -3),
        ("右耳",  6.5, 66.5, -8, 15),
    ]
    for name, ex, ez, tx, tz in ears:
        sx = -1 if ex < 0 else 1
        rot = (math.radians(tx), 0, math.radians(tz))
        outer = add_sphere(name, (ex, 4.0, ez),
                           scale=(3.9, 2.7, 14.5), rotation=rot,
                           mat=MAT['rabbit'])
        white.append(outer)

        inner = add_sphere(name + "内耳", (0, 0, 0),
                           scale=(2.2, 0.7, 10.5), mat=MAT['inner'])
        q = outer.rotation_euler.to_quaternion()
        inner.rotation_euler = outer.rotation_euler
        inner.location = outer.location + q @ Vector((0, -2.4, 1.0))
        decor.append(inner)

    # ---- 手臂：单根胶囊从肩侧斜插到饼正面（无肘折，侧面看是自然弧线）----
    for sx in (-1, 1):
        shoulder = (sx * 13.0, -3.0, 38.5)
        paw_pos  = (sx * 7.3, -17.0, 35.5)
        white.append(add_capsule_between("手臂", shoulder, paw_pos,
                                         radius=3.6, mat=MAT['rabbit']))
        white.append(add_sphere("手爪", paw_pos,
                                scale=(4.0, 2.8, 3.7),
                                rotation=(math.radians(sx * 8), 0, 0),
                                mat=MAT['rabbit']))

    # ---- 后脚（外撇、略小）+ 肉垫 ----
    for sx in (-1, 1):
        rz = math.radians(sx * 10)
        white.append(add_sphere("脚", (sx * 10.8, -7.5, 15.5),
                                scale=(8.0, 9.2, 6.2),
                                rotation=(0, 0, rz), mat=MAT['rabbit']))
        decor.append(add_sphere("脚掌大垫", (sx * 10.8, -15.8, 14.2),
                                scale=(2.7, 0.8, 3.2), mat=MAT['pad']))
        for dx in (-2.2, 0.0, 2.2):
            decor.append(add_sphere("脚趾垫",
                                    (sx * 10.8 + dx, -16.0, 17.5),
                                    scale=(0.95, 0.4, 0.95),
                                    mat=MAT['pad']))

    # ---- 尾巴 ----
    white.append(add_sphere("尾巴", (0, 11, 22.5),
                            scale=(5, 5, 5), mat=MAT['rabbit']))

    # ---- 五官（眼睛内收；嘴与饼脱开；腮红加大）----
    for sx in (-1, 1):
        decor.append(add_sphere("眼睛", (sx * 5.9, -13.3, 52.6),
                                scale=(3.0, 1.65, 3.4), mat=MAT['eye']))
        decor.append(add_sphere("眼神光", (sx * 6.8, -14.7, 53.7),
                                scale=(0.9, 0.5, 0.9), mat=MAT['hi']))
        decor.append(add_sphere("腮红", (sx * 8.8, -16.0, 45.3),
                                scale=(2.6, 1.2, 2.0), mat=MAT['blush']))

    decor.append(add_sphere("鼻子", (0, -15.0, 46.6),
                            scale=(2.0, 1.0, 1.3), mat=MAT['nose']))
    # 笑嘴：小的宽扁开口 + 下沿露出一点舌头（不做嘴角球，避免红胡子感）
    decor.append(add_sphere("嘴", (0, -14.3, 44.2),
                            scale=(3.0, 1.6, 1.9), mat=MAT['mouth']))
    decor.append(add_sphere("舌头", (0, -15.0, 43.4),
                            scale=(1.6, 0.75, 0.85), mat=MAT['tongue']))

    return white, decor


# ============================================================
# 6. 月饼（V2：半径 9，厚 6.5，中心 z33；仍为光板）
# ============================================================
def build_mooncake():
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=9.0, depth=6.5,
                                        location=(0, -13.5, 33.0),
                                        rotation=(math.radians(90), 0, 0))
    cake = bpy.context.object
    cake.name = "月饼"
    cake.data.materials.append(MAT['cake'])
    apply_bevel(cake, 0.8, 3)
    shade_smooth_by_angle(cake)
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
    # 主光偏右前，打出体积与软投影
    add_area_light("主光", (35, -65, 105), 750, 35)
    add_area_light("补光", (-55, -25, 60), 160, 55)
    add_area_light("轮廓光", (45, 65, 85), 380, 50)

    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.15))
    floor = bpy.context.object
    floor.name = "地面"
    floor.data.materials.append(MAT['floor'])

    # 头顶一块大白反光板（给金环出高光带）
    add_area_light("顶反射", (0, -10, 130), 200, 80)

    tgt = bpy.data.objects.new("相机注视点", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = AIM

    cams = {}
    for name, loc, lens in (
        ("front", (0, -132, 50), 50),
        ("3q",    (72, -108, 52), 50),
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
    bpy.ops.export_scene.gltf(filepath=GLB_PATH, export_format='GLB',
                              export_apply=True)
    log("exported -> %s" % GLB_PATH)


def build_print_solid(structural):
    copies = []
    for ob in structural:
        n = ob.copy()
        n.data = ob.data.copy()
        bpy.context.collection.objects.link(n)
        copies.append(n)
    return join_and_remesh("打印一体实体", copies, voxel=0.7)


def export_stl(solid):
    bpy.ops.object.select_all(action='DESELECT')
    solid.select_set(True)
    bpy.context.view_layer.objects.active = solid
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(
            filepath=STL_PATH, export_selected_objects=True,
            ascii_format=False, global_scale=1.0, apply_modifiers=True)
    else:
        bpy.ops.export_mesh.stl(filepath=STL_PATH, use_selection=True,
                                as_binary=True, global_scale=1.0)
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

    all_meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    apply_all_transforms(all_meshes)

    rabbit = join_and_remesh("玉兔主体", white_parts, voxel=0.55)
    structural = base_parts + [ring, rabbit, cake]

    log("studio & render ...")
    cams = build_studio()
    render_to(cams['front'], PNG_FRONT)
    render_to(cams['3q'], PNG_3Q)

    log("exporting glb ...")
    export_glb()

    log("watertight solid + stl ...")
    solid = build_print_solid(structural)
    export_stl(solid)
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
