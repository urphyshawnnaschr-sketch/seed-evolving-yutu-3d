# -*- coding: utf-8 -*-
"""
中秋玉兔小摆件 V4 —— 成品摆件精修版（基于 V3 增量）
  主体：吻部/下巴/脸颊体积层次；耳朵姿态差；爪搭饼面“展示式”抱法
  月饼：心形花瓣 + 卷珠 + 绳纹 + 底衬“月”字（更强识别）
  灯笼：竖向瓜棱 + 交替链环（内含实心打印杆）+ 束扎流苏
  月环：向尖端收分；底座：深色桌面 + 前金绶带 + 如意云头大匾
  呈现：弧形无影背景、金/木微凹凸、大面积柔光
无头运行:
    blender -b --factory-startup -P yutu_v4.py
"""

import bpy
import math
import os
import sys
import traceback
from mathutils import Vector

OUT_DIR = r"D:\笨小丁\下载\yutu_v1"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

BLEND_PATH = os.path.join(OUT_DIR, "yutu_v4.blend")
GLB_PATH   = os.path.join(OUT_DIR, "yutu_v4.glb")
STL_PATH   = os.path.join(OUT_DIR, "yutu_v4.stl")
PNG_FRONT  = os.path.join(OUT_DIR, "preview_front_v4.png")
PNG_3Q     = os.path.join(OUT_DIR, "preview_3q_v4.png")

AIM = (0.0, -3.0, 37.0)
CAKE_Z = 31.5          # 月饼中心高（V3 下调，与笑嘴留缝）
CAKE_Y = -13.5         # 月饼中心纵深

def log(msg):
    print("[yutu4] %s" % msg, flush=True)


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
            setattr(scn.eevee, attr, 96)

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
    bg.inputs[0].default_value = (0.90, 0.85, 0.80, 1.0)
    bg.inputs[1].default_value = 0.8


def make_mat(name, color, roughness=0.55, metallic=0.0, bump=0.0,
             bump_scale=5.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if bump > 0:
        n1 = nt.nodes.new("ShaderNodeTexNoise")
        n1.inputs["Scale"].default_value = bump_scale
        n1.inputs["Detail"].default_value = 4.0
        n2 = nt.nodes.new("ShaderNodeBump")
        n2.inputs["Strength"].default_value = bump
        n2.inputs["Distance"].default_value = 0.25
        nt.links.new(n1.outputs["Fac"], n2.inputs["Height"])
        nt.links.new(n2.outputs["Normal"], bsdf.inputs["Normal"])
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
    MAT['gold']    = make_mat("暖金",     (0.960, 0.700, 0.260), 0.30, 0.75,
                              bump=0.10, bump_scale=4.0)
    MAT['wood']    = make_mat("木座",     (.300, .175, .100), 0.38,
                              bump=0.12, bump_scale=7.0)
    MAT['darktop'] = make_mat("桌面深木", (.130, .072, .042), 0.32,
                              bump=0.10, bump_scale=8.0)
    MAT['cake']    = make_mat("月饼棕",   (0.830, 0.470, 0.140), 0.60,
                              bump=0.08, bump_scale=9.0)
    MAT['cakehi']  = make_mat("月饼浮雕金",(0.940, 0.630, 0.220), 0.55)
    MAT['cakecen'] = make_mat("饼心深衬", (0.600, 0.330, 0.100), 0.55)
    MAT['lantern'] = make_mat("灯肚金",   (0.880, 0.590, 0.200), 0.32, 0.65,
                              bump=0.08, bump_scale=6.0)
    MAT['plaque_dark'] = make_mat("刻字深", (0.100, 0.055, 0.028), 0.45)
    MAT['floor']   = make_mat("背景米",   (0.90, 0.85, 0.80), 0.92)


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

    # 顶面金箍 + 深色桌面
    parts.append(add_torus("底座金箍", (0, 0, 10.1), 33.2, 0.7,
                           mat=MAT['gold']))
    top = add_cylinder("深色桌面", (0, 0, 10.35), 32.4, 0.7,
                       mat=MAT['darktop'], vertices=64)
    shade_smooth_by_angle(top)
    parts.append(top)

    # 底部细金线
    parts.append(add_torus("底金线", (0, 0, 2.5), 36.4, 0.4,
                           mat=MAT['gold']))

    # 正面金色绶带（仅前 150° 的弧段）
    band_pts = []
    RB = 35.9
    for i in range(36):
        a = math.radians(-60 + 120 * i / 35)
        band_pts.append((RB * math.sin(a), -RB * math.cos(a), 5.0))
    parts.append(add_poly_tube("前金绶带", band_pts, 0.55,
                               mat=MAT['gold'], resolution=3))

    # ---- 如意云头大匾 ----
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -34.9, 5.0))
    plate = bpy.context.object
    plate.name = "牌匾"
    plate.scale = (10.4, 1.35, 3.4)
    plate.data.materials.append(MAT['gold'])
    apply_bevel(plate, 0.9, 3)
    shade_smooth_by_angle(plate)

    ends = [plate]
    for sx in (-1, 1):
        ends.append(add_sphere("牌云头", (sx * 10.9, -34.9, 6.1),
                               scale=(1.7, 1.2, 1.4), mat=MAT['gold']))
        ends.append(add_sphere("牌云头", (sx * 10.9, -34.9, 3.9),
                               scale=(1.7, 1.2, 1.4), mat=MAT['gold']))
        ends.append(add_sphere("牌云尖", (sx * 12.6, -34.9, 5.0),
                               scale=(1.5, 1.1, 1.5), mat=MAT['gold']))
    plate = join_and_remesh("如意牌匾", ends, voxel=0.38)
    parts.append(plate)

    # 匾上 “中秋”
    txt = add_text("中秋字", "中  秋", 6.4, 0.55, (0, -36.9, 4.6),
                   (math.radians(90), 0, 0), MAT['plaque_dark'],
                   bevel=0.02)
    parts.append(txt)
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1.0,
                                        location=(sx * 8.0, -36.6, 5.0),
                                        rotation=(math.radians(90), 0,
                                                  math.radians(45)))
        dia = bpy.context.object
        dia.name = "匾菱点"
        dia.data.materials.append(MAT['plaque_dark'])
        parts.append(dia)

    # 绶带两端贴墙金色小云（沿弧面切线方向排开，不超出底座剪影）
    for sx in (-1, 1):
        cx = sx * 30.0
        puffs = [
            add_sphere("绶云", (cx, -19.6, 5.6),
                       scale=(2.1, 1.0, 1.6), mat=MAT['gold'], seg=20),
            add_sphere("绶云", (cx + sx * 1.6, -16.6, 5.3),
                       scale=(1.4, 0.85, 1.1), mat=MAT['gold'], seg=18),
            add_sphere("绶云", (cx - sx * 1.4, -17.8, 5.0),
                       scale=(1.2, 0.8, 1.0), mat=MAT['gold'], seg=18),
        ]
        parts.append(join_and_remesh("绶带云角", puffs, voxel=0.3))

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
    R, CZ, Y, TUBE = 32.0, 40.0, 9.0, 3.7
    A0 = math.radians(150)
    A1 = math.radians(-160)
    N = 200

    cu = bpy.data.curves.new("月环曲线", type='CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 2
    cu.bevel_depth = TUBE
    cu.bevel_resolution = 5
    cu.use_fill_caps = True

    # Taper：尖端收细，主体段保持等粗
    tc = bpy.data.curves.new("月环锥度", type='CURVE')
    tc.dimensions = '2D'
    tsp = tc.splines.new('POLY')
    profile = [(0.0, 0.62), (0.05, 0.9), (0.12, 1.0),
               (0.90, 1.0), (0.98, 0.92), (1.0, 0.82)]
    tsp.points.add(len(profile) - 1)
    for i, (px, py) in enumerate(profile):
        tsp.points[i].co = (px, py, 0, 1)
    taper_obj = bpy.data.objects.new("月环锥度物体", tc)
    bpy.context.collection.objects.link(taper_obj)
    cu.taper_object = taper_obj

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
    bpy.data.objects.remove(taper_obj, do_unlink=True)
    ring.data.materials.append(MAT['gold'])
    smooth_obj(ring)

    tips = [
        add_sphere("环端", (R * math.cos(A0), Y, CZ + R * math.sin(A0)),
                   scale=TUBE * 0.62, mat=MAT['gold']),
        add_sphere("环端", (R * math.cos(A1), Y, CZ + R * math.sin(A1)),
                   scale=TUBE * 0.82, mat=MAT['gold']),
    ]
    ring = join_and_remesh("月环", [ring] + tips, voxel=0.55)
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
    # 脸颊更鼓更前；吻部小鼓包 + 下巴，做出面部层次（不再是光滑单球）
    white.append(add_sphere("左颊", (-9.6, -10.8, 46.0),
                            scale=(5.9, 5.0, 5.4), mat=MAT['rabbit']))
    white.append(add_sphere("右颊", (9.6, -10.8, 46.0),
                            scale=(5.9, 5.0, 5.4), mat=MAT['rabbit']))
    white.append(add_sphere("吻部", (0, -14.2, 45.0),
                            scale=(4.6, 3.2, 3.4), mat=MAT['rabbit']))
    white.append(add_sphere("下巴", (0, -12.0, 41.6),
                            scale=(3.4, 2.6, 2.6), mat=MAT['rabbit']))

    # ---- 耳朵：左耳近直、右耳明显外撇 ----
    ears = [("左耳", -5.2, 67.5, -10, -6),
            ("右耳",  7.0, 66.8, -6, 21)]
    for name, ex, ez, tx, tz in ears:
        rot = (math.radians(tx), 0, math.radians(tz))
        outer = add_sphere(name, (ex, 4.0, ez),
                           scale=(3.9, 2.7, 15.2), rotation=rot,
                           mat=MAT['rabbit'])
        white.append(outer)
        inner = add_sphere(name + "内耳", (0, 0, 0),
                           scale=(2.2, 0.7, 11.2), mat=MAT['inner'])
        q = outer.rotation_euler.to_quaternion()
        inner.rotation_euler = outer.rotation_euler
        inner.location = outer.location + q @ Vector((0, -2.4, 1.0))
        decor.append(inner)

    # ---- 微弯的环抱手臂（曲管）+ 馒头爪 ----
    for sx in (-1, 1):
        white.append(add_poly_tube(
            "手臂",
            [(sx * 13.0, -3.0, 37.0),
             (sx * 11.2, -10.0, 35.8),
             (sx * 6.2, -16.2, 35.0)],
            radius=3.5, mat=MAT['rabbit']))
        # 馒头爪搭在饼面 10/2 点位，呈“抱住并展示”
        white.append(add_sphere("手爪", (sx * 5.9, -17.9, 34.6),
                                scale=(4.7, 3.0, 4.1),
                                rotation=(0, 0, math.radians(sx * 6)),
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
        decor.append(add_sphere("眼睛", (sx * 5.9, -14.2, 52.8),
                                scale=(3.15, 1.7, 3.55), mat=MAT['eye']))
        decor.append(add_sphere("眼神光", (sx * 6.9, -15.7, 54.0),
                                scale=(0.95, 0.5, 0.95), mat=MAT['hi']))
        decor.append(add_sphere("腮红", (sx * 9.8, -17.7, 46.0),
                                scale=(3.2, 0.8, 2.4), mat=MAT['blush']))
        # 睫毛（仅渲染，两根小弧线，不进 STL）
        decor.append(add_poly_tube(
            "睫毛",
            [(sx * 8.0, -14.8, 55.2),
             (sx * 9.5, -15.6, 56.4)],
            radius=0.22, mat=MAT['lash'], resolution=2))
        decor.append(add_poly_tube(
            "睫毛",
            [(sx * 8.3, -14.4, 54.8),
             (sx * 9.9, -14.9, 55.5)],
            radius=0.22, mat=MAT['lash'], resolution=2))

    decor.append(add_sphere("鼻子", (0, -16.8, 46.8),
                            scale=(1.95, 0.95, 1.25), mat=MAT['nose']))

    # U 型笑嘴 + 舌头 + 吻部白毛把开口“挤”成上翘 U
    decor.append(add_sphere("嘴", (0, -16.6, 44.0),
                            scale=(2.7, 1.2, 1.9), mat=MAT['mouth']))
    decor.append(add_sphere("舌头", (0, -17.3, 43.1),
                            scale=(1.9, 0.85, 1.15), mat=MAT['tongue']))
    white.append(add_sphere("嘴角白", (-2.7, -16.0, 44.8),
                            scale=(1.4, 1.1, 1.2), mat=MAT['rabbit']))
    white.append(add_sphere("嘴角白", (2.7, -16.0, 44.8),
                            scale=(1.4, 1.1, 1.2), mat=MAT['rabbit']))

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

    # 外圈心形花瓣：外圆瓣 + 向内收的瓣尖，14 枚
    petals = []
    for i in range(LOBES):
        a = 2 * math.pi * i / LOBES
        ca, sa = math.cos(a), math.sin(a)
        petals.append(add_sphere(
            "花瓣", (7.1 * ca, front_y - 0.35, CAKE_Z + 7.1 * sa),
            scale=(2.05, 0.6, 1.25),
            rotation=(0, a + math.pi / 2, 0),
            mat=MAT['cakehi'], seg=20))
        petals.append(add_sphere(
            "瓣尖", (5.7 * ca, front_y - 0.32, CAKE_Z + 5.7 * sa),
            scale=(1.0, 0.5, 0.85),
            rotation=(0, a + math.pi / 2, 0),
            mat=MAT['cakehi'], seg=16))
    parts.append(join_and_remesh("心形花瓣环", petals, voxel=0.3))

    # 内圈卷珠（12 个小圆鼓包）
    beads = []
    for i in range(12):
        a = 2 * math.pi * i / 12 + math.pi / 12
        x = 4.7 * math.cos(a)
        z = CAKE_Z + 4.7 * math.sin(a)
        beads.append(add_sphere("卷珠", (x, front_y - 0.3, z),
                                scale=(0.82, 0.45, 0.82),
                                mat=MAT['cakehi'], seg=16))
    parts.append(join_and_remesh("卷珠环", beads, voxel=0.25))

    # 两道绳纹环
    parts.append(add_torus("外绳环", (0, front_y - 0.25, CAKE_Z),
                           6.3, 0.4, rotation=(math.radians(90), 0, 0),
                           mat=MAT['cakehi']))
    parts.append(add_torus("内绳环", (0, front_y - 0.25, CAKE_Z),
                           3.2, 0.4, rotation=(math.radians(90), 0, 0),
                           mat=MAT['cakehi']))

    # 中央深色衬底圆 + 立体“月”，保证小图也读得清
    disk = add_cylinder("月衬底", (0, front_y - 0.4, CAKE_Z),
                        2.85, 0.35, rotation=(math.radians(90), 0, 0),
                        mat=MAT['cakecen'], vertices=40)
    shade_smooth_by_angle(disk)
    parts.append(disk)
    parts.append(add_text("月字", "月", 5.6, 1.0,
                          (0, front_y - 0.72, CAKE_Z - 0.15),
                          (math.radians(90), 0, 0), MAT['cakehi'],
                          bevel=0.12))
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
    x, y = tx, 5.5

    # 挂环（竖直面内）
    parts.append(add_torus("灯挂环", (x, y, tz - 1.6), 1.1, 0.35,
                           rotation=(0, math.radians(90), 0),
                           mat=MAT['gold']))

    # 链环：4 个交替 90° 的环 + 贯穿细杆（打印安全）
    parts.append(add_cylinder("灯链安全杆", (x, y, 51.0), 0.3, 7.2,
                              mat=MAT['gold'], vertices=10))
    for i, z in enumerate((53.2, 51.6, 50.0, 48.4)):
        rot = ((0, math.radians(90), 0) if i % 2 == 0
               else (math.radians(90), 0, 0))
        parts.append(add_torus("灯链环", (x, y, z), 0.75, 0.22,
                               rotation=rot, mat=MAT['gold']))

    # 上颈 + 上盖（两级）
    parts.append(add_cylinder("灯上颈", (x, y, 47.1), 1.1, 1.0,
                              mat=MAT['gold']))
    parts.append(add_cylinder("灯上盖", (x, y, 46.0), 1.9, 1.0,
                              mat=MAT['gold']))

    # 灯肚
    bz = 40.6
    rx, ry, rz = 4.0, 3.5, 4.7
    parts.append(add_sphere("灯肚", (x, y, bz),
                            scale=(rx, ry, rz), mat=MAT['lantern']))

    # 8 条竖向瓜棱（贴椭球表面的经线）
    for k in range(8):
        phi = 2 * math.pi * k / 8
        pts = []
        for j in range(25):
            th = math.radians(-72 + 144 * j / 24)
            pts.append((x + rx * math.cos(th) * math.sin(phi),
                        y - ry * math.cos(th) * math.cos(phi),
                        bz + rz * math.sin(th)))
        parts.append(add_poly_tube("灯瓜棱", pts, 0.3,
                                   mat=MAT['gold'], resolution=2))

    # 上下束环
    parts.append(add_torus("灯上环", (x, y, bz + 3.0), 2.6, 0.28,
                           rotation=(math.radians(90), 0, 0),
                           mat=MAT['gold']))
    parts.append(add_torus("灯下环", (x, y, bz - 3.0), 2.6, 0.28,
                           rotation=(math.radians(90), 0, 0),
                           mat=MAT['gold']))

    # 下盖 + 束扎流苏
    parts.append(add_cylinder("灯下盖", (x, y, 35.6), 1.5, 1.0,
                              mat=MAT['gold']))
    parts.append(add_cylinder("流苏束", (x, y, 34.2), 1.1, 1.2,
                              mat=MAT['gold']))
    for k in range(5):
        phi = 2 * math.pi * k / 5
        top = (x + 0.8 * math.sin(phi), y - 0.8 * math.cos(phi), 33.7)
        bot = (x + 1.1 * math.sin(phi), y - 1.1 * math.cos(phi), 29.6)
        parts.append(add_poly_tube("流苏穗", [top, bot], 0.38,
                                   mat=MAT['gold'], resolution=2))
        parts.append(add_sphere("流苏梢", bot, scale=0.55,
                                mat=MAT['gold'], seg=14))
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


def build_backdrop():
    """地面到背景墙一体的弧形无影墙（XZ 之外无接缝）。"""
    rows = 150
    xw = 900.0
    verts, faces = [], []
    for i in range(rows + 1):
        y = -260.0 + 960.0 * i / rows
        z = 0.0 if y < 120.0 else (y - 120.0) ** 2 * 0.0025
        verts.append((-xw, y, z - 0.15))
        verts.append((xw, y, z - 0.15))
    for i in range(rows):
        a, b = 2 * i, 2 * i + 1
        c, d = a + 2, b + 2
        faces.append((a, c, d, b))
    me = bpy.data.meshes.new("无影墙网格")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("无影背景墙", me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(MAT['floor'])
    smooth_obj(ob)
    return ob


def build_studio():
    add_area_light("主光", (40, -70, 110), 700, 110)
    add_area_light("补光", (-70, -30, 60), 220, 90)
    add_area_light("轮廓光", (55, 70, 95), 420, 70)
    add_area_light("顶部柔反", (0, 30, 140), 160, 140)

    backdrop = build_backdrop()

    tgt = bpy.data.objects.new("相机注视点", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = AIM

    cams = {}
    for name, loc, lens in (
        ("front", (0, -152, 56), 46),
        ("3q",    (92, -134, 60), 46),
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
    return cams, backdrop


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
    return join_and_remesh("打印一体实体", copies, voxel=0.3)


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
    cams, backdrop = build_studio()
    render_to(cams['front'], PNG_FRONT)
    render_to(cams['3q'], PNG_3Q)

    # 无影墙只是摄影棚，不进交付物
    bpy.data.objects.remove(backdrop, do_unlink=True)

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
