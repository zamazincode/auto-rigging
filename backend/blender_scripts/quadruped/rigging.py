"""
Quadruped Auto-Rigging Pipeline
=================================
4 bacaklı hayvan modelleri için otomatik rigging.
Template: quadruped_rig.blend (34 kemik)

Kemik yapısı:
  spine.004 (ROOT/kalça)
  ├── spine.003→.002→.001→spine  (kuyruk, Y+)
  └── spine.005→.006→.007→.008  (boyun, Y-)
      ├── spine.009→.010→.011    (baş)
      ├── shoulder.L/R → front_thigh → front_shin → front_foot → front_toe
      ├── thigh.L/R → shin → foot → toe
      └── pelvis.L/R
"""
import bpy, os, sys, math, importlib
from mathutils import Vector

script_dir = os.path.normpath(r"c:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\blender_scripts")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import quadruped.analyzer as quadruped_analyzer
importlib.reload(quadruped_analyzer)

from common.mesh_utils import get_mesh_dimensions, get_world_verts, lerp_vec
from common.blender_utils import pick_target_mesh, ensure_object_mode, select_only, append_custom_rig
from common.mesh_processing import preprocess_mesh, create_voxel_proxy, cleanup_proxy
from common.fitting_utils import solve_two_bone_ik, raycast_find_center, extract_chain_ratios
from quadruped.analyzer import detect_quadruped_landmarks

TEMPLATE_DIR = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\templates"
RIG_FILE = "quadruped_rig.blend"
RIG_OBJ_NAME = "metarig"

# ═══════════════════════════════════ BONE CONFIG ═══════════════════════════════

QUAD_CHAIN_CONFIG = {
    "front_legs": {"bones": ["front_thigh", "front_shin", "front_foot"], "sides": [".L", ".R"]},
    "rear_legs": {"bones": ["thigh", "shin", "foot"], "sides": [".L", ".R"]},
    "spine": ["spine.004", "spine.003", "spine.002", "spine.001", "spine",
              "spine.005", "spine.006", "spine.007", "spine.008",
              "spine.009", "spine.010", "spine.011"],
}

# ================= KEMIK İNCE AYAR (HEURISTIC) =================
# Bacakların mesh içinde dışa/içe genişliği (1.0 tam genişlik hesaplamasıdır)
HIP_WIDTH_MULTIPLIER = 1.0      # Arka kalça genişliği çarpanı
SHOULDER_WIDTH_MULTIPLIER = 1.0 # Ön omuz genişliği çarpanı

# Ayak ve Bilek (Hock) Yerleşimi
FOOT_Z_OFFSET_RATIO = 0.20      # Arka ayak bileğini (hock) zeminden yukarı taşıma
FRONT_FOOT_Z_OFFSET = 0.20      # Ön bacak ayak bileğini (knee) zeminden yukarı taşıma

# Diz Bükülme Offsetleri (Y ekseni öne / arkaya IK kilitleri için)
REAR_KNEE_BEND_RATIO = 0.08     # Arka dizin (stifle) öne bükülme miktarı
FRONT_KNEE_BEND_RATIO = 0.08    # Ön dizin geriye bükülme miktarı

# Sırt Dağılımı ve Kuyruk
SPINE_ROOT_Y_RATIO = 0.45       # 0.5 = Gövde Ortası. spine.004 buradan kalçaya bağlanır.
# ===============================================================

# Kuyruk zincirleri (spine.004 → spine): Y artan
TAIL_CHAIN = ["spine.003", "spine.002", "spine.001", "spine"]
# Boyun zincirleri (spine.004 → spine.008): Y azalan
NECK_CHAIN = ["spine.005", "spine.006", "spine.007", "spine.008"]
# Baş zincirleri
HEAD_CHAIN = ["spine.009", "spine.010", "spine.011"]


def fit_quadruped_bones(mesh, rig, proxy_mesh=None):
    """Kemikleri quadruped anatomik noktalara oturtur."""
    print("[SİSTEM] Quadruped kemik oturtma başlatılıyor...")

    analysis_mesh = proxy_mesh if proxy_mesh else mesh
    lm = detect_quadruped_landmarks(analysis_mesh)
    if not lm:
        print("[UYARI] Landmark tespiti başarısız.")
        return False

    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    to_local = rig.matrix_world.inverted()

    center_x = lm["center_x"]
    ground_z = lm["ground_z"]
    spine_z = lm["spine_z"]
    body_h = lm["body_height"]
    body_l = lm["body_length"]
    body_w = lm["body_width"]

    hip_y = lm["hip_y"]
    chest_y = lm["chest_y"]
    waist_y = lm["waist_y"]
    neck_y = lm["neck_y"]
    head_y = lm["head_y"]
    tail_y = lm["tail_y"]

    # Sırt Z seviyesi (omurga hattı)
    spine_z_line = spine_z - (body_h * 0.08)  # Sırttan biraz içeride

    # Mesh'ten gerçek Z yüksekliklerini tahmin etme (Kuyruk ve Baş için daha doğru hedef)
    verts = get_world_verts(analysis_mesh)
    
    neck_verts = [v for v in verts if abs(v.y - neck_y) < body_l * 0.05]
    neck_z_max = max((v.z for v in neck_verts), default=spine_z_line + body_h * 0.20)
    neck_z = neck_z_max - body_h * 0.05

    head_verts = [v for v in verts if abs(v.y - head_y) < body_l * 0.05]
    head_z = (sum(v.z for v in head_verts) / len(head_verts)) if head_verts else neck_z

    tail_verts = [v for v in verts if abs(v.y - tail_y) < body_l * 0.05]
    tail_z = (sum(v.z for v in tail_verts) / len(tail_verts)) if tail_verts else spine_z_line - body_h * 0.10

    # ═══════ ROOT (spine.004) — kalça/gövde ortası ═══════
    root_y = lerp_vec(Vector((0, chest_y, 0)), Vector((0, hip_y, 0)), SPINE_ROOT_Y_RATIO).y
    root_pos = to_local @ Vector((center_x, root_y, spine_z_line))

    if "spine.004" in eb:
        eb["spine.004"].head = root_pos.copy()

    # ═══════ KUYRUK ZİNCİRİ (spine.003 → spine) ═══════
    # Root'tan kuyruk ucuna doğru (Y artıyor)
    tail_end = to_local @ Vector((center_x, tail_y, tail_z))
    n_tail = len(TAIL_CHAIN)

    # spine.004.tail = spine.003.head yönü
    tail_dir_start = to_local @ Vector((center_x, hip_y, spine_z_line))
    if "spine.004" in eb:
        eb["spine.004"].tail = tail_dir_start.copy()

    # Kuyruk segmentlerini dağıt
    for i, name in enumerate(TAIL_CHAIN):
        if name not in eb:
            continue
        t_start = (i) / n_tail
        t_end = (i + 1) / n_tail
        seg_head = lerp_vec(tail_dir_start, tail_end, t_start)
        seg_tail = lerp_vec(tail_dir_start, tail_end, t_end)
        eb[name].head = seg_head
        eb[name].tail = seg_tail

    # ═══════ GÖVDE (SPINE), BOYUN VE BAŞ ZİNCİRLERİ ═══════
    # Omurga: Root'tan (Kalça) Göğüs merkezine uzanır
    chest_pos = to_local @ Vector((center_x, chest_y, spine_z_line))
    neck_base_pos = to_local @ Vector((center_x, neck_y, neck_z))
    head_pos = to_local @ Vector((center_x, head_y, head_z))

    # Gövde kemikleri (Root'tan Göğüs hizasına)
    body_spine = ["spine.005", "spine.006", "spine.007"]
    for i, name in enumerate(body_spine):
        if name not in eb:
            continue
        t_s = i / len(body_spine)
        t_e = (i + 1) / len(body_spine)
        eb[name].head = lerp_vec(root_pos, chest_pos, t_s)
        eb[name].tail = lerp_vec(root_pos, chest_pos, t_e)

    # Omurga başlangıcını root'a bağla
    if "spine.005" in eb and "spine.004" in eb:
        eb["spine.005"].head = eb["spine.004"].head.copy()

    # Boyun kemikleri (Göğüsten enseye/boyun köküne)
    neck_bones = ["spine.008", "spine.009", "spine.010"]
    for i, name in enumerate(neck_bones):
        if name not in eb:
            continue
        t_s = i / len(neck_bones)
        t_e = (i + 1) / len(neck_bones)
        eb[name].head = lerp_vec(chest_pos, neck_base_pos, t_s)
        eb[name].tail = lerp_vec(chest_pos, neck_base_pos, t_e)

    # Baş kemiği (Enseden buruna)
    if "spine.011" in eb:
        eb["spine.011"].head = neck_base_pos
        eb["spine.011"].tail = head_pos

    # ═══════ ARKA BACAKLAR (thigh → shin → foot → toe) ═══════
    hip_half_w = (body_w * 0.18) * HIP_WIDTH_MULTIPLIER
    hip_z = spine_z_line - body_h * 0.05
    ankle_z = ground_z + body_h * FOOT_Z_OFFSET_RATIO

    for side, sign in [(".L", 1.0), (".R", -1.0)]:
        foot_lm = lm["rear_foot_l"] if sign > 0 else lm["rear_foot_r"]
        
        # Kalça eklemi (Femur) direkt kalça (hip_y) koordinatında yer alır.
        hip_pos = to_local @ Vector((center_x + sign * hip_half_w, hip_y, hip_z))
        
        # Ayak bileği (Hock) kalçadan biraz daha geride, ayağın üzerinde
        ankle_pos = to_local @ Vector((foot_lm.x, foot_lm.y + body_l * 0.05, ankle_z))
        toe_pos = to_local @ Vector((foot_lm.x, foot_lm.y - body_l * 0.08, ground_z))

        # Diz (Stifle) öne doğru bükülür (-Y)
        knee_pos = lerp_vec(hip_pos, ankle_pos, 0.50)
        knee_pos.y -= body_l * REAR_KNEE_BEND_RATIO

        if "thigh" + side in eb:
            eb["thigh" + side].head = hip_pos
            eb["thigh" + side].tail = knee_pos
        if "shin" + side in eb:
            eb["shin" + side].head = knee_pos
            eb["shin" + side].tail = ankle_pos
        if "foot" + side in eb:
            eb["foot" + side].head = ankle_pos
            eb["foot" + side].tail = toe_pos
        if "toe" + side in eb:
            eb["toe" + side].head = toe_pos
            eb["toe" + side].tail = to_local @ Vector((foot_lm.x, foot_lm.y - body_l * 0.10, ground_z))

    # ═══════ ÖN BACAKLAR (shoulder → front_thigh → front_shin → front_foot → front_toe) ═══════
    shoulder_z = spine_z_line + body_h * 0.05
    sh_bottom_z = spine_z_line - body_h * 0.35  # Omuz eklemi (humerus başı) aşağıda
    front_ankle_z = ground_z + body_h * FRONT_FOOT_Z_OFFSET

    for side, sign in [(".L", 1.0), (".R", -1.0)]:
        ft_lm = lm["front_foot_l"] if sign > 0 else lm["front_foot_r"]
        
        # Omuz (Scapula) göğüs (chest_y) koordinatını referans almalıdır.
        adjusted_shoulder_w = hip_half_w * 0.6 * SHOULDER_WIDTH_MULTIPLIER
        sh_pos = to_local @ Vector((center_x + sign * adjusted_shoulder_w, chest_y, shoulder_z))
        sh_bottom = to_local @ Vector((center_x + sign * adjusted_shoulder_w, chest_y - body_l * 0.05, sh_bottom_z))
        
        f_ankle = to_local @ Vector((ft_lm.x, ft_lm.y, front_ankle_z))
        f_toe = to_local @ Vector((ft_lm.x, ft_lm.y - body_l * 0.05, ground_z))

        # Dirsek (Humerus ve Radius arası) geriye doğru bükülür (+Y)
        f_knee = lerp_vec(sh_bottom, f_ankle, 0.50)
        f_knee.y += body_l * FRONT_KNEE_BEND_RATIO  # Ön diz/dirsek (elbow) GERİYE (+Y) bükülür

        if "shoulder" + side in eb:
            eb["shoulder" + side].head = sh_pos
            eb["shoulder" + side].tail = sh_bottom
        if "front_thigh" + side in eb:
            eb["front_thigh" + side].head = sh_bottom
            eb["front_thigh" + side].tail = f_knee
        if "front_shin" + side in eb:
            eb["front_shin" + side].head = f_knee
            eb["front_shin" + side].tail = f_ankle
        if "front_foot" + side in eb:
            eb["front_foot" + side].head = f_ankle
            eb["front_foot" + side].tail = f_toe
        if "front_toe" + side in eb:
            eb["front_toe" + side].head = f_toe
            eb["front_toe" + side].tail = to_local @ Vector((ft_lm.x, ft_lm.y - body_l * 0.10, ground_z))

    # ═══════ PELVIS ═══════
    for side, sign in [(".L", 1.0), (".R", -1.0)]:
        if "pelvis" + side in eb:
            eb["pelvis" + side].head = root_pos.copy()
            hip_bone = "thigh" + side
            if hip_bone in eb:
                eb["pelvis" + side].tail = eb[hip_bone].head.copy()

    # ═══════ BREAST ═══════
    for side, sign in [(".L", 1.0), (".R", -1.0)]:
        if "breast" + side in eb and "spine.006" in eb:
            b_head = eb["spine.006"].tail.copy()
            b_head.x += sign * (body_w * 0.12)
            b_tail = b_head.copy()
            b_tail.z -= body_h * 0.15
            b_tail.y += body_l * 0.1  # Point backwards and down
            eb["breast" + side].head = b_head
            eb["breast" + side].tail = b_tail
            eb["breast" + side].parent = eb["spine.006"]

    bpy.ops.object.mode_set(mode='OBJECT')
    print("[SİSTEM] Quadruped kemik fitting tamamlandı.")
    return True


def apply_quadruped_regional_scaling(rig, chain_ratios):
    """Bölgesel ölçekleme + IK solve (quadruped versiyonu)."""
    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    print("[HESAP] Quadruped bölgesel ölçekleme başlatılıyor...")

    # Arka bacaklar
    for side in ['.L', '.R']:
        th, sn = 'thigh' + side, 'shin' + side
        if th not in eb or sn not in eb:
            continue
        start = eb[th].head.copy()
        end = eb[sn].tail.copy()
        dist = (end - start).length
        if dist < 1e-6:
            continue
        r_th = chain_ratios.get(f'rear_legs_thigh{side}', 0.52)
        r_sn = chain_ratios.get(f'rear_legs_shin{side}', 0.48)
        l_th, l_sn = dist * r_th * 1.05, dist * r_sn * 1.05  # %5 bükülme payı
        pole = Vector((0.0, -1.0, 0.0))  # Arka diz (stifle) ÖNE (-Y) bükülür
        knee = solve_two_bone_ik(start, end, l_th, l_sn, pole)
        eb[th].tail = knee
        eb[sn].head = knee
        print(f"   [OK] Arka bacak{side}: üst={l_th:.3f} alt={l_sn:.3f}")

    # Ön bacaklar
    for side in ['.L', '.R']:
        ft, fs = 'front_thigh' + side, 'front_shin' + side
        if ft not in eb or fs not in eb:
            continue
        start = eb[ft].head.copy()
        end = eb[fs].tail.copy()
        dist = (end - start).length
        if dist < 1e-6:
            continue
        r_ft = chain_ratios.get(f'front_legs_front_thigh{side}', 0.52)
        r_fs = chain_ratios.get(f'front_legs_front_shin{side}', 0.48)
        l_ft, l_fs = dist * r_ft * 1.05, dist * r_fs * 1.05  # %5 bükülme payı
        pole = Vector((0.0, 1.0, 0.0))  # Ön diz/dirsek (elbow) GERİYE (+Y) bükülür
        knee = solve_two_bone_ik(start, end, l_ft, l_fs, pole)
        eb[ft].tail = knee
        eb[fs].head = knee
        print(f"   [OK] Ön bacak{side}: üst={l_ft:.3f} alt={l_fs:.3f}")

    bpy.ops.object.mode_set(mode='OBJECT')
    print("[HESAP] Quadruped bölgesel ölçekleme tamamlandı.")


def refine_quadruped_with_raycast(proxy, rig):
    """Quadruped kemiklerini raycast ile yatayda (sadece X ekseninde) mesh merkezine hizala."""
    from common.fitting_utils import raycast_find_center
    
    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    
    dir_x = Vector((1.0, 0.0, 0.0))

    # 1. Bacakları X ekseninde ortalayarak mesh'in tam içine it
    for side in [".L", ".R"]:
        for bone in ["shoulder", "front_thigh", "front_shin", "front_foot", "thigh", "shin", "foot"]:
            bname = bone + side
            if bname in eb:
                bone_obj = eb[bname]
                
                # Head için X merkezleme
                center_head = raycast_find_center(proxy, bone_obj.head, dir_x)
                if center_head:
                    bone_obj.head.x = center_head.x
                
                # Tail için X merkezleme
                center_tail = raycast_find_center(proxy, bone_obj.tail, dir_x)
                if center_tail:
                    bone_obj.tail.x = center_tail.x

    # 2. Omurga ve boynu (center_x = 0 varsayımıyla veya Z-ray olmadan) tam simetriye çek
    spine_bones = QUAD_CHAIN_CONFIG["spine"] + TAIL_CHAIN + HEAD_CHAIN
    for bname in spine_bones:
        if bname in eb:
            bone_obj = eb[bname]
            # Hayvanlarda Z raycast'i karnı sırta ve omurgayı aşağı çekebilir. 
            # O yüzden sadec X'te merkeze kilitliyoruz. 
            bone_obj.head.x = 0.0
            bone_obj.tail.x = 0.0

    bpy.ops.object.mode_set(mode='OBJECT')
    print("[OK] Quadruped Raycast (X-Ekseni) ile bacaklar merkeze alındı.")


# ═══════════════════════════════════ ANA PİPELİNE ═══════════════════════════════

def auto_rig_quadruped():
    """Quadruped auto-rigging pipeline."""
    ensure_object_mode()

    # 1. Hedef mesh
    target = pick_target_mesh()
    if not target:
        print("[HATA] Sahnede mesh bulunamadı.")
        return
    print(f"[OK] Hedef mesh: {target.name}")

    select_only(target)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # 2. Preprocessing
    preprocess_mesh(target)
    mesh_height, mesh_dims = get_mesh_dimensions(target)
    print(f"[HESAP] Mesh yüksekliği: {mesh_height:.4f}, uzunluğu: {mesh_dims.y:.4f}")

    # 3. Voxel proxy
    print("[OK] Voxel proxy oluşturuluyor...")
    ensure_object_mode()
    voxel_proxy = create_voxel_proxy(target)
    ensure_object_mode()

    # 4. Template rig yükle
    rig_path = os.path.join(TEMPLATE_DIR, RIG_FILE)
    print(f"[BİLGİ] Template rig: {RIG_FILE}")
    custom_rig = append_custom_rig(rig_path, RIG_OBJ_NAME)

    if not custom_rig:
        print("[HATA] Template rig yüklenemedi.")
        cleanup_proxy(voxel_proxy)
        return
    custom_rig.location = (0, 0, 0)

    # 5. Uniform scale
    bpy.context.view_layer.update()
    rig_height, rig_dims = get_mesh_dimensions(custom_rig)
    if rig_height <= 1e-6:
        print("[HATA] Rig yüksekliği hesaplanamadı.")
        cleanup_proxy(voxel_proxy)
        return

    # Quadruped için Y (uzunluk) bazlı scale
    scale_factor = (mesh_dims.y / rig_dims.y) * 0.92 if rig_dims.y > 1e-6 else 1.0
    scale_factor = max(0.20, min(scale_factor, 8.00))
    custom_rig.scale = (scale_factor, scale_factor, scale_factor)
    print(f"[ÖLÇÜM] Ölçek faktörü: {scale_factor:.4f}")

    select_only(custom_rig)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # 6. Template oranlarını çıkar
    chain_ratios = extract_chain_ratios(custom_rig, chain_config=QUAD_CHAIN_CONFIG)

    # 7. Kemikleri otur
    fit_ok = fit_quadruped_bones(target, custom_rig, proxy_mesh=voxel_proxy)
    if not fit_ok:
        print("[UYARI] Fitting başarısız.")

    # 7.5. Bölgesel ölçekleme + IK
    if fit_ok:
        ensure_object_mode()
        apply_quadruped_regional_scaling(custom_rig, chain_ratios)

    # 8. Raycast merkezleme (Sadece X ekseni ile bacakların mesh içine oturtulması)
    if fit_ok:
        ensure_object_mode()
        refine_quadruped_with_raycast(voxel_proxy, custom_rig)

    # 9. Proxy temizlik
    ensure_object_mode()
    cleanup_proxy(voxel_proxy)
    print("[BİLGİ] Voxel proxy temizlendi.")

    # 10. Mesh Cleanup & Skinning
    ensure_object_mode()
    select_only(target)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    select_only(target)
    target.select_set(True)
    custom_rig.select_set(True)
    bpy.context.view_layer.objects.active = custom_rig

    print("[OK] Skinning yapılıyor...")
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print("[BAŞARILI] Quadruped Auto-Rigging Tamamlandı!")
    except Exception as e:
        print(f"[UYARI] ARMATURE_AUTO başarısız: {e}")
        print("[OK] ARMATURE_NAME fallback...")
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        custom_rig.select_set(True)
        bpy.context.view_layer.objects.active = custom_rig
        try:
            bpy.ops.object.parent_set(type='ARMATURE_NAME')
            print("[OK] Fallback başarılı.")
        except Exception as e2:
            print(f"[HATA] Fallback de başarısız: {e2}")


if __name__ == "__main__":
    auto_rig_quadruped()
