"""
Fitting Yardımcıları
=====================
IK çözümleri, raycast merkezleme ve kemik oranı çıkarma.
Humanoid ve Quadruped pipeline'ları tarafından paylaşılır.
"""

import bpy
import math
from mathutils import Vector
from .blender_utils import select_only


# ═══════════════════════════════════════════════════════════════
# 2-BONE IK ANALİTİK ÇÖZÜM
# ═══════════════════════════════════════════════════════════════

def solve_two_bone_ik(start, end, len1, len2, pole_direction):
    """
    2-Bone IK analitik çözümü.

    İki kemik (len1, len2) ile start → end arası bağlantı kurar.
    Orta eklemin (dirsek/diz) pozisyonunu döndürür.

    Kosinüs teoremi:
        cos(A) = (len1² + dist² - len2²) / (2 × len1 × dist)

    Args:
        start: Başlangıç noktası (omuz/kalça)
        end: Bitiş noktası (bilek/ayak bileği)
        len1: İlk kemik uzunluğu
        len2: İkinci kemik uzunluğu
        pole_direction: Bükülme yönü (normalize Vector)

    Returns:
        Vector: Orta eklem pozisyonu
    """
    direction = end - start
    dist = direction.length

    if dist < 1e-6:
        return start + Vector((0, 0, len1))

    # Kemikler yetişmiyorsa → doğru çizgi
    if dist >= len1 + len2:
        t = len1 / (len1 + len2)
        return start + direction * t

    # Mesafe çok kısaysa → hafif bükülme
    if dist < abs(len1 - len2):
        t = len1 / (len1 + len2)
        mid = start + direction * t
        mid += pole_direction * len1 * 0.3
        return mid

    # Normal: kosinüs teoremi
    cos_angle = (len1**2 + dist**2 - len2**2) / (2 * len1 * dist)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    angle = math.acos(cos_angle)

    dir_n = direction.normalized()

    # Gram-Schmidt: pole'u kemik doğrultusuna dik yap
    pole_proj = pole_direction - dir_n * pole_direction.dot(dir_n)

    if pole_proj.length < 1e-6:
        if abs(dir_n.z) < 0.9:
            pole_proj = dir_n.cross(Vector((0, 0, 1)))
        else:
            pole_proj = dir_n.cross(Vector((1, 0, 0)))

    pole_proj.normalize()

    mid = (start
           + dir_n * (len1 * math.cos(angle))
           + pole_proj * (len1 * math.sin(angle)))

    return mid


# ═══════════════════════════════════════════════════════════════
# RAYCAST MERKEZLEMEİ
# ═══════════════════════════════════════════════════════════════

def raycast_world(obj, origin, direction):
    """Dünya koordinatında raycast. Dönüş: (hit, world_pos)."""
    matrix_inv = obj.matrix_world.inverted()
    origin_local = matrix_inv @ origin
    dir_local = (matrix_inv.to_3x3() @ direction).normalized()

    hit, loc_local, normal, face_idx = obj.ray_cast(origin_local, dir_local)

    if hit:
        return True, obj.matrix_world @ loc_local
    return False, None


def raycast_find_center(proxy, point, axis, dist=5.0):
    """İki yönlü raycast ile hacim merkezini bul."""
    hit_p, loc_p = raycast_world(proxy, point - axis * dist, axis)
    hit_n, loc_n = raycast_world(proxy, point + axis * dist, -axis)

    if hit_p and hit_n:
        return (loc_p + loc_n) / 2.0
    return None


def refine_bones_with_raycast(proxy, rig, bone_config=None):
    """
    Raycasting ile kemikleri mesh hacminin ortasına hizalar.

    Args:
        proxy: Voxel proxy mesh
        rig: Armature objesi
        bone_config: dict — kemik isimlerini ve hangi eksende
                     merkezleneceğini belirler. None ise humanoid
                     varsayılanı kullanılır.

    bone_config formatı:
        {
            "spine_bones": ["spine", "spine.001", ...],
            "spine_last": "spine.006",
            "limb_chains": {
                "shoulder": {"parts": ["upper_arm","forearm","hand"], "sides": [".L",".R"]},
                "leg": {"parts": ["thigh","shin"], "sides": [".L",".R"]},
            },
            "pelvis_sides": [".L", ".R"],
            "chain_connections": [
                ("shoulder.L", "tail", "upper_arm.L", "head"),
                ...
            ],
        }
    """
    if bone_config is None:
        bone_config = _humanoid_bone_config()

    print("[BİLGİ] Raycast ile kemik merkezleme başlatılıyor...")

    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    world = rig.matrix_world
    world_inv = world.inverted()

    axis_x = Vector((1, 0, 0))
    axis_y = Vector((0, 1, 0))

    refined_count = 0

    def center_point(bone_name, point_type, axis):
        nonlocal refined_count
        if bone_name not in eb:
            return
        bone = eb[bone_name]
        point = bone.head if point_type == 'head' else bone.tail
        point_world = world @ point
        center = raycast_find_center(proxy, point_world, axis)
        if center:
            center_local = world_inv @ center
            if axis == axis_y:
                point.y = center_local.y
            elif axis == axis_x:
                point.x = center_local.x
            refined_count += 1

    # ── Omurga: Y merkezle ──
    for name in bone_config.get("spine_bones", []):
        center_point(name, 'head', axis_y)
    spine_last = bone_config.get("spine_last")
    if spine_last:
        center_point(spine_last, 'tail', axis_y)

    # Spine zinciri senkronizasyonu
    spine_bones = bone_config.get("spine_bones", [])
    for i in range(len(spine_bones) - 1):
        curr, nxt = spine_bones[i], spine_bones[i + 1]
        if curr in eb and nxt in eb:
            avg_y = (eb[curr].tail.y + eb[nxt].head.y) / 2
            eb[curr].tail.y = avg_y
            eb[nxt].head.y = avg_y

    # ── Uzuv zincirleri: Y merkezle ──
    for chain_name, chain_info in bone_config.get("limb_chains", {}).items():
        for side in chain_info.get("sides", [".L", ".R"]):
            # Shoulder/pelvis gibi kök kemik
            if "root" in chain_info:
                center_point(chain_info["root"] + side, 'tail', axis_y)
            for part in chain_info.get("parts", []):
                center_point(part + side, 'head', axis_y)
                center_point(part + side, 'tail', axis_y)

    # ── Pelvis ──
    for side in bone_config.get("pelvis_sides", [".L", ".R"]):
        center_point("pelvis" + side, 'tail', axis_y)

    # ── Bağlantı tutarlılığı ──
    for conn in bone_config.get("chain_connections", []):
        src_name, src_pt, dst_name, dst_pt = conn
        if src_name in eb and dst_name in eb:
            src_bone = eb[src_name]
            dst_bone = eb[dst_name]
            val = src_bone.tail.copy() if src_pt == 'tail' else src_bone.head.copy()
            if dst_pt == 'head':
                dst_bone.head = val
            else:
                dst_bone.tail = val

    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"   [OK] Raycast: {refined_count} nokta merkezlendi")


def _humanoid_bone_config():
    """Humanoid pipeline için varsayılan kemik konfigürasyonu."""
    connections = []
    for side in [".L", ".R"]:
        connections.extend([
            ("shoulder" + side, "tail", "upper_arm" + side, "head"),
            ("upper_arm" + side, "tail", "forearm" + side, "head"),
            ("thigh" + side, "tail", "shin" + side, "head"),
        ])

    return {
        "spine_bones": ["spine", "spine.001", "spine.002", "spine.003",
                        "spine.004", "spine.005", "spine.006"],
        "spine_last": "spine.006",
        "limb_chains": {
            "arm": {
                "root": "shoulder",
                "parts": ["upper_arm", "forearm", "hand"],
                "sides": [".L", ".R"],
            },
            "leg": {
                "parts": ["thigh", "shin"],
                "sides": [".L", ".R"],
            },
        },
        "pelvis_sides": [".L", ".R"],
        "chain_connections": connections,
    }


def extract_chain_ratios(rig, chain_config=None):
    """
    Template rig'den kemik zinciri uzunluk oranlarını çıkar.

    Args:
        rig: Armature objesi
        chain_config: dict — zincir isimleri ve kemik listeleri.
                      None ise humanoid varsayılan.

    chain_config formatı:
        {
            "arms": {"bones": ["upper_arm","forearm","hand"], "sides": [".L",".R"]},
            "legs": {"bones": ["thigh","shin"], "sides": [".L",".R"]},
            "spine": ["spine","spine.001",...],
        }
    """
    if chain_config is None:
        chain_config = {
            "arms": {"bones": ["upper_arm", "forearm", "hand"],
                     "sides": [".L", ".R"]},
            "legs": {"bones": ["thigh", "shin"],
                     "sides": [".L", ".R"]},
            "spine": ["spine", "spine.001", "spine.002", "spine.003",
                      "spine.004", "spine.005", "spine.006"],
        }

    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    world = rig.matrix_world

    def bone_len(name):
        if name not in eb:
            return 0.0
        b = eb[name]
        return (world @ b.tail - world @ b.head).length

    ratios = {}

    # Uzuv zincirleri
    for chain_type in ["arms", "legs", "front_legs", "rear_legs"]:
        if chain_type not in chain_config:
            continue
        info = chain_config[chain_type]
        bones = info["bones"]
        for side in info.get("sides", [".L", ".R"]):
            lengths = [bone_len(b + side) for b in bones]
            total = sum(lengths)
            if total > 1e-6:
                for i, b in enumerate(bones):
                    ratios[f"{chain_type}_{b}{side}"] = lengths[i] / total

    # Omurga zinciri
    if "spine" in chain_config:
        spine_names = chain_config["spine"]
        spine_lens = [bone_len(n) for n in spine_names]
        total_spine = sum(spine_lens)
        if total_spine > 1e-6:
            for i, name in enumerate(spine_names):
                ratios[f"spine_{name}"] = spine_lens[i] / total_spine

    bpy.ops.object.mode_set(mode='OBJECT')

    print("[BİLGİ] Template oranları çıkarıldı.")
    return ratios
