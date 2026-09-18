# -*- coding: utf-8 -*-
"""
中秋玉兔小摆件 V3 —— 参考图元素恢复版
四要素边界不变（玉兔 / 月饼 / 月环 / 底座），本轮恢复：
  P1 月饼：波浪花边 + 外圈花瓣 + 内圈卷珠 + 绳纹环 + “月”字浮雕
  P1 祥云：5 朵（右上贴环云 / 右中拖尾云 / 左右坐地云 + 右前小云），奶白+金包边+卷涡
  P2 灯笼：挂环 + 珠链（实心态，打印安全） + 灯肚 + 上下盖 + 流苏
  P2 牌匾：云头牌匾 + “中秋” + 菱形点 + 底座两侧金色小云
  小修：U 型笑嘴、棕眼、睫毛（仅渲染）、右耳再多外撇、手臂微弯、底座加底线脚

无头运行:
    blender -b --factory-startup -P yutu_v3.py
"""

import bpy
import math
import os
import sys
import traceback
from mathutils import Vector

OUT_DIR = r"D:\笨小丁\下载\yutu_v1"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

BLEND_PATH = os.path.join(OUT_DIR, "yutu_v3.blend")
GLB_PATH   = os.path.join(OUT_DIR, "yutu_v3.glb")
STL_PATH   = os.path.join(OUT_DIR, "yutu_v3.stl")
PNG_FRONT  = os.path.join(OUT_DIR, "preview_front_v3.png")
PNG_3Q     = os.path.join(OUT_DIR, "preview_3q_v3.png")

AIM = (0.0, -3.0, 37.0)
CAKE_Z = 31.5          # 月饼中心高（V3 下调，与笑嘴留缝）
CAKE_Y = -13.5         # 月饼中心纵深

def log(msg):
    print("[yutu3] %s" % msg, flush=True)


# ============================================================
# 场景 / 材质
# ============================================================
def reset_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                  bpy.data.cameras, bpy.data.lights, bpy.data.images,
                  bpy.data.fonts):
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

    for attr, val in (("use_shadows", True), ("use_gtao", True),
                      ("use_raytracing", True)):
        if hasattr(scn.eevee, attr):
            try:
                setattr(scn.eevee, attr, val)
            except TypeError:
                pass
    if hasattr(scn.eevee, "gtao_distance"):
        scn.eevee.gtao_distance = 6.0
    for attr in ("taa_render_samples", "taa_samples", "samples"):
        if hasattr(scn.eevee, attr):
            setattr(scn.eevee, attr, 64)

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
    MAT['rabbit']  = make_mat("玉兔白",   (0.985, 0.955, 0.925), 0.58)
    MAT['cloud']   = make_mat("祥云奶白", (0.970, 0.935, 0.880), 0.55)
    MAT['inner']   = make_mat("内耳粉",   (1.000, 0.740, 0.790), 0.60)
    MAT['pad']     = make_mat("肉垫粉",   (1.000, 0.600, 0.680), 0.55)
    MAT['nose']    = make_mat("鼻粉",     (1.000, 0.540, 0.640), 0.40)
    MAT['blush']   = make_mat("腮红",     (1.000, 0.520, 0.590), 0.75)
    MAT['eye']     = make_mat("眼棕黑",   (0.150, 0.085, 0.060), 0.16)
    MAT['lash']    = make_mat("睫毛深棕", (0.120, 0.070, 0.050), 0.30)
    MAT['hi']      = make_mat("眼神光",   (1.000, 1.000, 1.000), 0.05)
    MAT['mouth']   = make_mat("口腔红",   (0.500, 0.090, 0.110), 0.40)
    MAT['tongue']  = make_mat("舌粉",     (0.960, 0.380, 0.480), 0.45)
    MAT['gold']    = make_mat("暖金",     (0.960, 0.700, 0.260), 0.30, 0.70)
    MAT['wood']    = make_mat("木座",     (.330, .200, .120), 0.42)
    MAT['cake']    = make_mat("月饼棕",   (0.830, 0.470, 0.140), 0.60)
    MAT['cakehi']  = make_mat("月饼浮雕金",(0.940, 0.630, 0.220), 0.55)
    MAT['lantern'] = make_mat("灯肚金",   (0.870, 0.580, 0.200), 0.34, 0.60)
    MAT['plaque_dark'] = make_mat("刻字深", (0.110, 0.060, 0.030), 0.45)
    MAT['floor']   = make_mat("地面米",   (0.875, 0.815, 0.760), 0.90)


# ============================================================
# 通用工具
# ============================================================
def smooth_obj(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def add_sphere(name, location, scale=1.0, rotation=(0, 0, 0), mat=None,
               seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2 + 4,
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


def add_cylinder(name, location, radius, depth, rotation=(0, 0, 0),
                 mat=None, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=depth, location=location,
                                        rotation=rotation)
    ob = bpy.context.object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def add_torus(name, location, major, minor, rotation=(0, 0, 0), mat=None,
              major_seg=64):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor,
        major_segments=major_seg, minor_segments=10,
        location=location, rotation=rotation)
    ob = bpy.context.object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def add_poly_tube(name, pts, radius, mat=None, resolution=4):
    """多点折线圆管（圆头端）。pts: list[(x,y,z)]"""
    cu = bpy.data.curves.new(name + "曲线", type='CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 2
    cu.bevel_depth = radius
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.object
    if mat:
        ob.data.materials.append(mat)
    smooth_obj(ob)
    return ob


def shade_smooth_by_angle(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.object, "shade_smooth_by_angle"):
        bpy.ops.object.shade_smooth_by_angle()
    else:
        smooth_obj(obj)


def apply_bevel(obj, amount, segments=3, angle=None):
    mod = obj.modifiers.new("倒角", 'BEVEL')
    mod.width = amount
    mod.segments = segments
    if angle is not None:
        mod.limit_method = 'ANGLE'
        mod.angle_limit = angle
    else:
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


def move_to_collection(ob, coll):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)


# ============================================================
# 底座：收分主体 + 底部线脚 + 金箍 + 云头牌匾
# ============================================================
def build_base():
    parts = []

    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=36, radius2=34,
                                    depth=10, end_fill_type='NGON',
                                    location=(0, 0, 5))
    body = bpy.context.object
    body.name = "底座"
    body.data.materials.append(MAT['wood'])
    apply_bevel(body, 1.1, 3)
    shade_smooth_by_angle(body)
    parts.append(body)

    # 底部外扩线脚
    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=37, radius2=36.2,
                                    depth=2.6, end_fill_type='NGON',
                                    location=(0, 0, 1.3))
    flare = bpy.context.object
    flare.name = "底线脚"
    flare.data.materials.append(MAT['wood'])
    apply_bevel(flare, 0.5, 2)
    shade_smooth_by_angle(flare)
    parts.append(flare)

    parts.append(add_torus("底座金箍", (0, 0, 10.1), 33.2, 0.7,
                           mat=MAT['gold']))

    # ---- 云头牌匾（长圆牌 + 两端云头鼓包）----
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -34.8, 5.2))
    plate = bpy.context.object
    plate.name = "牌匾"
    plate.scale = (9.6, 1.3, 3.3)
    plate.data.materials.append(MAT['gold'])
    apply_bevel(plate, 0.9, 3)
    shade_smooth_by_angle(plate)

    cap_l = add_sphere("牌端", (-10.1, -34.8, 5.2), scale=(2.2, 1.2, 2.1),
                       mat=MAT['gold'])
    cap_r = add_sphere("牌端", (10.1, -34.8, 5.2), scale=(2.2, 1.2, 2.1),
                       mat=MAT['gold'])
    plate = join_and_remesh("云头牌匾", [plate, cap_l, cap_r], voxel=0.4)
    parts.append(plate)

    # 匾上 “中秋”
    txt = add_text("中秋字", "中  秋", 4.7, 0.5, (0, -36.6, 4.8),
                   (math.radians(90), 0, 0), MAT['plaque_dark'],
                   bevel=0.06)
    parts.append(txt)
    # 两侧菱形点
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=0.9,
                                        location=(sx * 7.3, -36.4, 5.2),
                                        rotation=(math.radians(90), 0,
                                                  math.radians(45)))
        dia = bpy.context.object
        dia.name = "匾菱点"
        dia.data.materials.append(MAT['plaque_dark'])
        parts.append(dia)

    # 底座两侧金色小云
    for sx in (-1, 1):
        puffs = [
            add_sphere("座云", (sx * 18.5, -30.6, 10.6),
                       scale=(2.0, 1.0, 1.3), mat=MAT['gold'], seg=20),
            add_sphere("座云", (sx * 21.0, -30.2, 10.5),
                       scale=(1.5, 0.9, 1.0), mat=MAT['gold'], seg=20),
            add_sphere("座云", (sx * 16.6, -30.9, 10.3),
                       scale=(1.2, 0.8, 0.9), mat=MAT['gold'], seg=20),
        ]
        parts.append(join_and_remesh("座侧金云", puffs, voxel=0.35))

    return parts


def add_text(name, text, size, extrude, location, rotation, mat,
             bevel=0.12):
    bpy.ops.object.text_add(location=location, rotation=rotation)
    ob = bpy.context.object
    ob.name = name
    d = ob.data
    d.body = text
    d.size = size
    d.extrude = extrude
    d.bevel_depth = bevel
    d.bevel_resolution = 2
    d.align_x = 'CENTER'
    d.align_y = 'CENTER'
    if os.path.exists(FONT_PATH):
        d.font = bpy.data.fonts.load(FONT_PATH)
    d.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.object
    shade_smooth_by_angle(ob)
    return ob


# ============================================================
# 月环（左下尖改为从左祥云后探出的月牙角）
# ============================================================
def build_moon_ring():
    R, CZ, Y, TUBE = 32.0, 40.0, 9.0, 4.0
    A0 = math.radians(150)
    A1 = math.radians(-160)
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
        sp.points[i].co = (R * math.cos(a), Y, CZ + R * math.sin(a), 1.0)

    ring = bpy.data.objects.new("月环", cu)
    bpy.context.collection.objects.link(ring)
    bpy.ops.object.select_all(action='DESELECT')
    ring.select_set(True)
    bpy.context.view_layer.objects.active = ring
    bpy.ops.object.convert(target='MESH')
    ring = bpy.context.object
    ring.data.materials.append(MAT['gold'])
    smooth_obj(ring)

    tips = []
    for a in (A0, A1):
        tips.append(add_sphere("环端",
            (R * math.cos(a), Y, CZ + R * math.sin(a)),
            scale=TUBE, mat=MAT['gold']))
    ring = join_and_remesh("月环", [ring] + tips, voxel=0.6)
    return ring, (R * math.cos(A0), Y, CZ + R * math.sin(A0))


# ============================================================
# 玉兔 V3：微弯手臂 / U 型笑嘴 / 棕眼睫毛 / 耳角微调
# ============================================================
def build_rabbit():
    white, decor = [], []

    white.append(add_sphere("上身", (0, 1.0, 26.5),
                            scale=(14, 12, 14.5), mat=MAT['rabbit']))
    white.append(add_sphere("胯部", (0, 2.5, 20.0),
                            scale=(15, 12.5, 9.0), mat=MAT['rabbit']))
    white.append(add_sphere("肚皮", (0, -7.0, 25.0),
                            scale=(10.5, 7.0, 6.5), mat=MAT['rabbit']))
    white.append(add_sphere("头", (0, 0.5, 49),
                            scale=(17.2, 16.0, 17.5), mat=MAT['rabbit']))
    white.append(add_sphere("左颊", (-9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))
    white.append(add_sphere("右颊", (9, -10.5, 45),
                            scale=(6.2, 5.5, 5.6), mat=MAT['rabbit']))

    # ---- 耳朵：左耳近直、右耳明显外撇 ----
    ears = [("左耳", -5.5, 67.0, -8, -5),
            ("右耳",  6.5, 66.5, -8, 18)]
    for name, ex, ez, tx, tz in ears:
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

    # ---- 微弯的环抱手臂（曲管）+ 馒头爪 ----
    for sx in (-1, 1):
        white.append(add_poly_tube(
            "手臂",
            [(sx * 13.0, -3.0, 37.5),
             (sx * 11.4, -9.5, 36.0),
             (sx * 7.6, -15.6, 34.8)],
            radius=3.5, mat=MAT['rabbit']))
        white.append(add_sphere("手爪", (sx * 7.3, -17.0, 34.4),
                                scale=(4.0, 2.8, 3.7),
                                rotation=(math.radians(sx * 8), 0, 0),
                                mat=MAT['rabbit']))

    # ---- 后脚 + 肉垫 ----
    for sx in (-1, 1):
        white.append(add_sphere("脚", (sx * 10.8, -7.5, 15.5),
                                scale=(8.0, 9.2, 6.2),
                                rotation=(0, 0, math.radians(sx * 10)),
                                mat=MAT['rabbit']))
        decor.append(add_sphere("脚掌大垫", (sx * 10.8, -15.8, 14.2),
                                scale=(2.7, 0.8, 3.2), mat=MAT['pad']))
        for dx in (-2.2, 0.0, 2.2):
            decor.append(add_sphere("脚趾垫",
                                    (sx * 10.8 + dx, -16.0, 17.5),
                                    scale=(0.95, 0.4, 0.95),
                                    mat=MAT['pad']))

    white.append(add_sphere("尾巴", (0, 11, 22.5),
                            scale=(5, 5, 5), mat=MAT['rabbit']))

    # ---- 五官 ----
    for sx in (-1, 1):
        decor.append(add_sphere("眼睛", (sx * 5.9, -13.3, 52.6),
                                scale=(3.0, 1.65, 3.4), mat=MAT['eye']))
        decor.append(add_sphere("眼神光", (sx * 6.8, -14.7, 53.7),
                                scale=(0.9, 0.5, 0.9), mat=MAT['hi']))
        decor.append(add_sphere("腮红", (sx * 9.5, -15.2, 45.4),
                                scale=(3.3, 0.9, 2.4), mat=MAT['blush']))
        # 睫毛（仅渲染，两根小弧线，不进 STL）
        decor.append(add_poly_tube(
            "睫毛",
            [(sx * 8.0, -14.0, 55.0),
             (sx * 9.4, -14.6, 56.2)],
            radius=0.22, mat=MAT['lash'], resolution=2))
        decor.append(add_poly_tube(
            "睫毛",
            [(sx * 8.3, -13.6, 54.6),
             (sx * 9.8, -14.0, 55.2)],
            radius=0.22, mat=MAT['lash'], resolution=2))

    decor.append(add_sphere("鼻子", (0, -15.0, 46.6),
                            scale=(2.0, 1.0, 1.3), mat=MAT['nose']))

    # U 型笑嘴：红球 + 舌头 + 两团白色嘴角（并入主体）把开口“挤”成上翘 U
    decor.append(add_sphere("嘴", (0, -14.7, 43.7),
                            scale=(3.2, 1.5, 2.1), mat=MAT['mouth']))
    decor.append(add_sphere("舌头", (0, -15.7, 42.8),
                            scale=(2.1, 1.0, 1.3), mat=MAT['tongue']))
    white.append(add_sphere("嘴角白", (-2.9, -14.2, 44.9),
                            scale=(1.5, 1.2, 1.1), mat=MAT['rabbit']))
    white.append(add_sphere("嘴角白", (2.9, -14.2, 44.9),
                            scale=(1.5, 1.2, 1.1), mat=MAT['rabbit']))

    return white, decor


# ============================================================
# 月饼：波浪花边 + 花瓣 + 卷珠 + 绳纹环 + “月”字
# ============================================================
def build_mooncake():
    parts = []
    R_BODY = 9.2
    HF = 3.1
    LOBES = 14
    N = LOBES * 10
    AMP = 0.9

    verts, faces = [], []
    ring_f, ring_b = [], []
    for i in range(N):
        a = 2 * math.pi * i / N
        # 圆润花瓣边（只有外凸的圆弧，不做齿轮状内凹）
        r = R_BODY + AMP * 0.5 * (1.0 + math.cos(LOBES * a))
        zf, zb = 0.0, 0.0
        ring_f.append(len(verts))
        verts.append((r * math.cos(a), -HF, r * math.sin(a)))
        ring_b.append(len(verts))
        verts.append((r * math.cos(a), HF, r * math.sin(a)))
    cf = len(verts); verts.append((0, -HF, 0))
    cb = len(verts); verts.append((0, HF, 0))

    for i in range(N):
        j = (i + 1) % N
        fi, fj = ring_f[i], ring_f[j]
        bi, bj = ring_b[i], ring_b[j]
        faces.append((cf, fj, fi))
        faces.append((cb, bi, bj))
        faces.append((fi, fj, bj, bi))

    me = bpy.data.meshes.new("月饼花边网格")
    me.from_pydata(verts, [], faces)
    me.update()
    body = bpy.data.objects.new("月饼", me)
    bpy.context.collection.objects.link(body)
    body.location = (0, CAKE_Y, CAKE_Z)
    body.data.materials.append(MAT['cake'])
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    apply_bevel(body, 0.5, 2, angle=math.radians(35))
    shade_smooth_by_angle(body)
    parts.append(body)

    front_y = CAKE_Y - HF - 0.15

    # 外圈花瓣（14 枚切向拉长的鼓包）
    petals = []
    for i in range(LOBES):
        a = 2 * math.pi * i / LOBES
        x = 7.3 * math.cos(a)
        z = CAKE_Z + 7.3 * math.sin(a)
        petals.append(add_sphere(
            "花瓣", (x, front_y - 0.35, z),
            scale=(1.9, 0.6, 1.0),
            rotation=(0, a + math.pi / 2, 0),
            mat=MAT['cakehi'], seg=20))
    parts.append(join_and_remesh("花瓣环", petals, voxel=0.3))

    # 内圈卷珠（12 个小圆鼓包）
    beads = []
    for i in range(12):
        a = 2 * math.pi * i / 12 + math.pi / 12
        x = 4.7 * math.cos(a)
        z = CAKE_Z + 4.7 * math.sin(a)
        beads.append(add_sphere("卷珠", (x, front_y - 0.3, z),
                                scale=(0.95, 0.5, 0.95),
                                mat=MAT['cakehi'], seg=16))
    parts.append(join_and_remesh("卷珠环", beads, voxel=0.25))

    # 两道绳纹环
    parts.append(add_torus("外绳环", (0, front_y - 0.25, CAKE_Z),
                           6.3, 0.4, rotation=(math.radians(90), 0, 0),
                           mat=MAT['cakehi']))
    parts.append(add_torus("内绳环", (0, front_y - 0.25, CAKE_Z),
                           3.2, 0.4, rotation=(math.radians(90), 0, 0),
                           mat=MAT['cakehi']))

    # 中央 “月”
    parts.append(add_text("月字", "月", 5.4, 0.9,
                          (0, front_y - 0.55, CAKE_Z - 0.2),
                          (math.radians(90), 0, 0), MAT['cakehi'],
                          bevel=0.15))
    return parts


# ============================================================
# 祥云工厂：奶白球簇 + 放大后移的金色包边 + 金色卷涡
# ============================================================
CLOUD_SPECS = [
    # (名称, 中心, [(dx,dy,dz,r)...], 卷涡(局部x,z,半径), 是否贴环云)
    ("右上贴环云", (25.0, 3.0, 62.0),
     [(-3.6, 0, 0, 3.6), (0, 0.5, 1.6, 3.2), (3.6, 0, 0.4, 3.3),
      (1.4, 0, -2.2, 2.8), (-1.6, 0, -2.0, 2.6)],
     (-1.6, -0.8, 1.7), True),
    ("右中拖尾云", (28.2, 4.8, 37.6),
     [(-3.0, 0, 0, 3.3), (0.3, 0.2, 0.6, 2.9), (3.0, -0.2, 0.2, 2.5)],
     (-2.2, 0.4, 1.4), True),
    ("左坐地云", (-23.0, -5.0, 14.5),
     [(-4.2, 0, 0, 4.4), (1.0, 0.5, 1.6, 4.1), (5.0, 0, -0.3, 3.7),
      (0.6, 0, -3.0, 3.1), (-3.0, 0, -2.6, 3.0)],
     (-2.2, 1.6, 2.1), False),
    ("右坐地云", (21.0, -5.0, 14.0),
     [(-3.6, 0, 0, 4.1), (1.0, 0.5, 1.0, 3.8), (4.8, 0, -0.4, 3.4),
      (0.0, 0, -2.8, 2.7)],
     None, False),
    ("右前小云", (27.5, -11.0, 12.0),
     [(-1.8, 0, 0, 2.5), (1.5, 0, 0.3, 2.3), (0, 0, -1.6, 1.9)],
     (-0.4, -0.6, 1.1), False),
]


def add_swirl(name, cx, cy, cz, r, mat):
    """如意卷涡：1.4 圈收束螺旋 + 中心小圆珠，位于 XZ 平面。"""
    pts = []
    a0 = math.radians(110)
    total = math.radians(504)
    n = 40
    for i in range(n):
        t = i / (n - 1)
        a = a0 - total * t
        rr = r * (1.0 - 0.78 * t) + 0.12
        pts.append((cx + rr * math.cos(a), cy, cz + rr * math.sin(a)))
    tube = add_poly_tube(name, pts, 0.4, mat=mat, resolution=3)
    end = pts[-1]
    bead = add_sphere(name + "心珠", end, scale=0.5, mat=mat, seg=14)
    return [tube, bead]


def build_clouds():
    parts = []
    for name, center, puffs, swirl, ring_cloud in CLOUD_SPECS:
        cx, cy, cz = center
        white_obs, gold_obs = [], []
        for dx, dy, dz, r in puffs:
            white_obs.append(add_sphere(
                name + "白", (cx + dx, cy + dy, cz + dz),
                scale=r, mat=MAT['cloud'], seg=24))
            # 金色包边：同样的球簇放大 14%，向环/后方偏移
            g = add_sphere(
                name + "金", (cx + dx * 1.14, cy + dy + 1.6,
                              cz + dz * 1.14),
                scale=r * 1.14, mat=MAT['gold'], seg=24)
            gold_obs.append(g)

        # 拖尾云：加一截拉长的云尾（奶白 + 金包边）
        if name == "右中拖尾云":
            white_obs.append(add_sphere(
                name + "白尾", (cx + 6.4, cy - 0.6, cz - 0.5),
                scale=(3.0, 0.9, 0.85), mat=MAT['cloud'], seg=20))
            gold_obs.append(add_sphere(
                name + "金尾", (cx + 6.4, cy + 1.2, cz - 0.5),
                scale=(3.3, 1.0, 0.95), mat=MAT['gold'], seg=20))

        w = join_and_remesh(name + "_白身", white_obs, voxel=0.42)
        gld = join_and_remesh(name + "_金边", gold_obs, voxel=0.48)
        parts += [gld, w]

        if swirl is not None:
            sx, sz, sr = swirl
            parts += add_swirl(name + "卷涡",
                               cx + sx, cy - 4.3, cz + sz,
                               sr, MAT['gold'])
    return parts


# ============================================================
# 灯笼：挂环 + 珠链 + 灯肚 + 盖 + 流苏（全部实心相连）
# ============================================================
def build_lantern(tip):
    parts = []
    tx, ty, tz = tip
    x = tx
    y = 5.5

    # 挂环（竖直面内）
    parts.append(add_torus("灯挂环", (x, y, tz - 1.6), 1.1, 0.35,
                           rotation=(0, math.radians(90), 0),
                           mat=MAT['gold']))
    # 珠链：细杆 + 串珠
    parts.append(add_cylinder("灯链杆", (x, y, 49.8), 0.5, 7.4,
                              mat=MAT['gold'], vertices=12))
    for i, z in enumerate((52.8, 50.8, 48.8, 46.9)):
        parts.append(add_sphere("灯链珠", (x, y, z), scale=0.85,
                                mat=MAT['gold'], seg=16))

    # 上盖（两级）
    parts.append(add_cylinder("灯上盖", (x, y, 46.0), 1.9, 1.0,
                              mat=MAT['gold']))
    parts.append(add_cylinder("灯上颈", (x, y, 47.1), 1.1, 1.0,
                              mat=MAT['gold']))
    # 灯肚：竖向鼓球（略深金）+ 赤道束环（亮金）
    belly = add_sphere("灯肚", (x, y, 40.6),
                       scale=(4.0, 3.5, 4.7), mat=MAT['lantern'])
    parts.append(belly)
    parts.append(add_torus("灯肚束环", (x, y, 40.6), 3.5, 0.3,
                           rotation=(math.radians(90), 0, 0),
                           mat=MAT['gold']))
    parts.append(add_torus("灯上环", (x, y, 43.6), 2.6, 0.28,
                           rotation=(math.radians(90), 0, 0),
                           mat=MAT['gold']))
    parts.append(add_torus("灯下环", (x, y, 37.6), 2.6, 0.28,
                           rotation=(math.radians(90), 0, 0),
                           mat=MAT['gold']))
    # 下盖 + 坠珠 + 流苏穗（三股加粗锥）
    parts.append(add_cylinder("灯下盖", (x, y, 35.6), 1.5, 1.0,
                              mat=MAT['gold']))
    parts.append(add_sphere("灯坠珠", (x, y, 34.4), scale=0.9,
                            mat=MAT['gold'], seg=16))
    for k, ang in enumerate((0, 25, -25)):
        dx = math.sin(math.radians(ang)) * 0.9
        parts.append(add_poly_tube(
            "灯流苏",
            [(x, y, 33.8), (x + dx, y + 0.3, 29.6)],
            0.55, mat=MAT['gold'], resolution=2))
    return parts


# ============================================================
# 灯光 / 地面 / 相机
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
    add_area_light("主光", (35, -65, 105), 750, 35)
    add_area_light("补光", (-55, -25, 60), 160, 55)
    add_area_light("轮廓光", (45, 65, 85), 420, 50)
    add_area_light("顶反射", (0, -10, 130), 220, 80)
    add_area_light("左前点金", (-50, -60, 45), 120, 30)

    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.15))
    floor = bpy.context.object
    floor.name = "地面"
    floor.data.materials.append(MAT['floor'])

    tgt = bpy.data.objects.new("相机注视点", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = AIM

    cams = {}
    for name, loc, lens in (
        ("front", (0, -150, 55), 48),
        ("3q",    (96, -136, 58), 48),
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
    return cams, floor


def render_to(cam, path):
    scn = bpy.context.scene
    scn.camera = cam
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    log("rendered -> %s" % path)


# ============================================================
# 导出
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
    return join_and_remesh("打印一体实体", copies, voxel=0.5)


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
    ring, ring_tip = build_moon_ring()

    log("building rabbit ...")
    white_parts, decor_parts = build_rabbit()

    log("building mooncake ...")
    cake_parts = build_mooncake()

    log("building clouds ...")
    cloud_parts = build_clouds()

    log("building lantern ...")
    lantern_parts = build_lantern(ring_tip)

    all_meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    apply_all_transforms(all_meshes)

    rabbit = join_and_remesh("玉兔主体", white_parts, voxel=0.55)

    structural = (base_parts + [ring, rabbit] + cake_parts +
                  cloud_parts + lantern_parts)

    log("studio & render ...")
    cams, floor = build_studio()
    render_to(cams['front'], PNG_FRONT)
    render_to(cams['3q'], PNG_3Q)

    # 地面只是摄影棚，不进交付物
    bpy.data.objects.remove(floor, do_unlink=True)

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
