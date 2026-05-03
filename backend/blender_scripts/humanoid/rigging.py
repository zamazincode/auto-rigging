import bpy
import os
import sys
import math
from mathutils import Vector

# Sistem yollarını ekle (standalones için)
script_dir = os.path.normpath(r"c:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\blender_scripts")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from common.mesh_utils import get_world_bbox, get_mesh_dimensions, average_vec, lerp_vec, get_world_verts
from common.blender_utils import pick_target_mesh, ensure_object_mode, select_only, append_custom_rig
from common.mesh_processing import preprocess_mesh, create_voxel_proxy, cleanup_proxy
from common.fitting_utils import solve_two_bone_ik, refine_bones_with_raycast, extract_chain_ratios
from humanoid.analyzer import detect_humanoid_pose, detect_humanoid_landmarks

TEMPLATE_DIR = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\templates"
RIG_FILE_T = "human_rig_T.blend" 
RIG_FILE_A = "human_rig_A.blend" 
RIG_OBJECT_NAME = "Armature"

def apply_regional_scaling(rig, chain_ratios):
    """
    Bölgesel ölçekleme + IK solve.
    
    fit_bones_to_anatomy() SONRASINDA çağrılır.
    
    Her kemik zinciri için:
    1. Anchor noktalarını koru (omuz, el, kalça, ayak bileği)
    2. Template oranlarıyla zincir uzunluklarını dağıt
    3. 2-Bone IK ile orta eklemleri (dirsek, diz) çöz
    
    NEDEN FARKLI:
        fit_bones_to_anatomy dirsek için lerp(shoulder, wrist, 0.52)
        kullanıyor → sabit oran, her model için aynı.
        
        Bu fonksiyon template rig'deki GERÇEK upper_arm/forearm
        oranını koruyarak dirsek pozisyonunu MATEMATİKSEL olarak
        çözer (kosinüs teoremi + pole vector).
    """
    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    
    print("[HESAP] Bölgesel ölçekleme + IK solve başlatılıyor...")
    
    # ══════════════════════════════════════════════════
    # KOL ZİNCİRLERİ
    # ══════════════════════════════════════════════════
    for side in ['.L', '.R']:
        ua_name = 'upper_arm' + side
        fa_name = 'forearm' + side
        ha_name = 'hand' + side
        
        if not all(n in eb for n in [ua_name, fa_name, ha_name]):
            continue
        
        # Anchor'lar: omuz eklemi → el ucu (fit tarafından set edilmiş)
        arm_start = eb[ua_name].head.copy()
        arm_end = eb[ha_name].tail.copy()
        
        total_dist = (arm_end - arm_start).length
        if total_dist < 1e-6:
            continue
        
        # Template oranlarıyla kemik uzunluklarını hesapla
        r_upper = chain_ratios.get('arm_upper' + side, 0.40)
        r_fore = chain_ratios.get('arm_fore' + side, 0.35)
        r_hand = chain_ratios.get('arm_hand' + side, 0.25)
        
        len_upper = total_dist * r_upper
        len_fore = total_dist * r_fore
        len_hand = total_dist * r_hand
        
        # Bilek: el ucundan hand uzunluğu kadar geri
        wrist_pos = arm_end + (arm_start - arm_end).normalized() * len_hand
        
        # Dirsek: 2-Bone IK (omuz → bilek arası)
        side_sign = 1.0 if side == '.L' else -1.0
        pole_dir = Vector((side_sign * 0.1, 1.0, -0.3)).normalized()
        
        elbow_pos = solve_two_bone_ik(
            arm_start, wrist_pos, len_upper, len_fore, pole_dir
        )
        
        # Kemikleri yerleştir
        eb[ua_name].tail = elbow_pos
        eb[fa_name].head = elbow_pos
        eb[fa_name].tail = wrist_pos
        eb[ha_name].head = wrist_pos
        # hand.tail = arm_end (zaten doğru)
        
        print(f"   [OK] Kol{side}: üst={len_upper:.3f} ön={len_fore:.3f} "
              f"el={len_hand:.3f} (toplam={total_dist:.3f})")
    
    # ══════════════════════════════════════════════════
    # BACAK ZİNCİRLERİ
    # ══════════════════════════════════════════════════
    for side in ['.L', '.R']:
        th_name = 'thigh' + side
        sn_name = 'shin' + side
        ft_name = 'foot' + side
        
        if not all(n in eb for n in [th_name, sn_name]):
            continue
        
        # Anchor'lar: kalça eklemi → ayak bileği
        leg_start = eb[th_name].head.copy()
        leg_end = eb[sn_name].tail.copy()
        
        total_dist = (leg_end - leg_start).length
        if total_dist < 1e-6:
            continue
        
        # Template oranları
        r_thigh = chain_ratios.get('leg_thigh' + side, 0.52)
        r_shin = chain_ratios.get('leg_shin' + side, 0.48)
        
        len_thigh = total_dist * r_thigh
        len_shin = total_dist * r_shin
        
        # Diz: 2-Bone IK (kalça → ayak bileği arası)
        # Pole: diz ÖNE kırılır (Y-)
        pole_dir = Vector((0.0, -1.0, 0.0)).normalized()
        
        knee_pos = solve_two_bone_ik(
            leg_start, leg_end, len_thigh, len_shin, pole_dir
        )
        
        # Kemikleri yerleştir
        eb[th_name].tail = knee_pos
        eb[sn_name].head = knee_pos
        # shin.tail = leg_end (zaten doğru)
        
        # Foot bağlantısı
        if ft_name in eb:
            eb[ft_name].head = leg_end
        
        print(f"   [OK] Bacak{side}: üst={len_thigh:.3f} alt={len_shin:.3f} "
              f"(toplam={total_dist:.3f})")
    
    # ══════════════════════════════════════════════════
    # OMURGA ZİNCİRİ
    #
    # Mevcut fitting omurgayı eşit aralıkla dağıtıyor.
    # Template'te alt omurga kemikleri genelde daha uzun,
    # üst olanlar kısa olur. Bu oranları geri yüklüyoruz.
    # ══════════════════════════════════════════════════
    spine_names = ['spine', 'spine.001', 'spine.002', 'spine.003',
                   'spine.004', 'spine.005', 'spine.006']
    
    existing = [n for n in spine_names if n in eb]
    if len(existing) >= 2:
        spine_start = eb[existing[0]].head.copy()
        spine_end = eb[existing[-1]].tail.copy()
        
        # Spine X ve Y sabit tutulmalı, sadece Z dağılımı değişir
        cx = spine_start.x
        cy = spine_start.y
        z_start = spine_start.z
        z_end = spine_end.z
        total_z = z_end - z_start
        
        if abs(total_z) > 1e-6:
            # Template oranlarını oku
            total_ratio = 0.0
            seg_ratios = []
            for name in existing:
                r = chain_ratios.get('spine_' + name, 1.0 / len(existing))
                seg_ratios.append(r)
                total_ratio += r
            
            # Normalize et ve Z noktalarını hesapla
            cumulative = 0.0
            points = [z_start]
            for r in seg_ratios:
                cumulative += r / total_ratio
                points.append(z_start + total_z * cumulative)
            
            for i, name in enumerate(existing):
                eb[name].head = Vector((cx, cy, points[i]))
                eb[name].tail = Vector((cx, cy, points[i + 1]))
            
            print(f"   [OK] Omurga: {len(existing)} kemik template oranlarıyla dağıtıldı")
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("[HESAP] Bölgesel ölçekleme tamamlandı.")


# ════════════════════════════════════════════════════════════════════════
#                      KEMİK OTURTMA (FITTING)
# ════════════════════════════════════════════════════════════════════════


def fit_bones_to_anatomy(mesh, rig, proxy_mesh=None):
    """
    Kemikleri Edit modunda anatomik noktalara çeker.
    
    HİBRİT YAKLAŞIM:
    - Z seviyeleri: Cross-section tespiti + anatomik min/max sınırları
    - X genişlikleri: Cross-section'dan (mesh genişliği)
    - Pelvis genişliği: Bel genişliğinden oransal
    
    Eğer proxy_mesh verilmişse, landmark tespiti proxy üzerinde yapılır.
    Bu sayede ekipman detayları yumuşatılmış mesh'ten ölçüm yapılır.
    """
    print("[SİSTEM] Cross-Section Kemik Oturtma (Fitting) başlatılıyor...")

    # Landmark tespiti: proxy varsa proxy'den, yoksa orijinal mesh'ten
    analysis_mesh = proxy_mesh if proxy_mesh else mesh
    lm = detect_humanoid_landmarks(analysis_mesh)
    if not lm:
        print("[UYARI] Landmark tespiti başarısız, kemik fitting atlandı.")
        return False

    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    to_local = rig.matrix_world.inverted()

    # === Landmark'lardan Gelen Ölçüler ===
    mesh_h = lm["total_height"]
    center_x = lm["center_x"]
    torso_y = lm["pelvis_center"].y
    
    # Cross-section Z seviyeleri
    cs_neck_z = lm["neck_z"]
    cs_shoulder_z = lm["shoulder_z"]
    cs_waist_z = lm["waist_z"]
    cs_hip_z = lm["hip_z"]
    cs_crotch_z = lm["crotch_z"]
    cs_knee_z = lm["knee_z"]
    
    # Cross-section genişlik verileri
    shoulder_inset = lm["shoulder_inset"]
    waist_width = lm["waist_width"]
    
    # Mesh sınırları (orijinal mesh'ten — proxy biraz farklı olabilir)
    verts = get_world_verts(mesh)
    z_min = min(v.z for v in verts)
    z_max = max(v.z for v in verts)
    
    # ================================================================
    # HİBRİT Z SEVİYELERİ
    #
    # Cross-section tespitlerini KULLAN ama anatomik sınırlarla 
    # KISITLA. Bu sayede:
    # - Normal modellerde cross-section'ın hassasiyetinden faydalanılır
    # - Ekipman/stilden bozulan modellerde güvenli sınıra düşülür
    # ================================================================
    
    def clamp_z(value, min_pct, max_pct, name):
        """Z değerini anatomik yüzde sınırları içine al."""
        lo = z_min + mesh_h * min_pct
        hi = z_min + mesh_h * max_pct
        clamped = max(lo, min(hi, value))
        if abs(clamped - value) > mesh_h * 0.01:
            pct_orig = (value - z_min) / mesh_h * 100
            pct_new = (clamped - z_min) / mesh_h * 100
            print(f"   🔧 {name}: cross-section %{pct_orig:.0f} → clamp %{pct_new:.0f}")
        return clamped
    
    shoulder_z = clamp_z(cs_shoulder_z, 0.78, 0.84, "Omuz")
    neck_z = clamp_z(cs_neck_z, 0.82, 0.90, "Boyun")
    
    # Spine root: bel ile kasık ortalaması → sacrum seviyesi
    cs_spine_root = (cs_waist_z + cs_crotch_z) / 2
    spine_root_z = clamp_z(cs_spine_root, 0.48, 0.56, "Spine root")
    
    # Kalça eklemi: spine root'un biraz altında
    cs_hip_joint = spine_root_z - mesh_h * 0.05
    hip_joint_z = clamp_z(cs_hip_joint, 0.44, 0.50, "Kalça eklemi")
    
    # Diz
    knee_z = clamp_z(cs_knee_z, 0.24, 0.32, "Diz")
    
    print(f"[ÖLÇÜM] Hibrit Z seviyeleri (cross-section + clamp):")
    print(f"   Omuz:   {shoulder_z:.4f} (%{(shoulder_z-z_min)/mesh_h*100:.0f})")
    print(f"   Boyun:  {neck_z:.4f} (%{(neck_z-z_min)/mesh_h*100:.0f})")
    print(f"   Spine:  {spine_root_z:.4f} (%{(spine_root_z-z_min)/mesh_h*100:.0f})")
    print(f"   Kalça:  {hip_joint_z:.4f} (%{(hip_joint_z-z_min)/mesh_h*100:.0f})")
    print(f"   Diz:    {knee_z:.4f} (%{(knee_z-z_min)/mesh_h*100:.0f})")

    # ================================================================
    # 1. OMUZ POZİSYONLARI
    # X: cross-section'dan (mesh genişliği), Z: hibrit
    # ================================================================
    shoulder_l_w = lm["shoulder_l"].copy()
    shoulder_r_w = lm["shoulder_r"].copy()
    shoulder_l_w.x = center_x + (shoulder_l_w.x - center_x) * shoulder_inset
    shoulder_r_w.x = center_x + (shoulder_r_w.x - center_x) * shoulder_inset
    shoulder_l_w.z = shoulder_z
    shoulder_r_w.z = shoulder_z
    shoulder_l_w.y = torso_y
    shoulder_r_w.y = torso_y

    # ================================================================
    # 2. EL POZİSYONLARI
    # ================================================================
    hand_l_w = lm["hand_l"].copy()
    hand_r_w = lm["hand_r"].copy()
    hand_l_w.y = torso_y
    hand_r_w.y = torso_y

    # ================================================================
    # 3. AYAK BİLEĞİ POZİSYONLARI
    # ================================================================
    ground_z = min(lm["foot_l"].z, lm["foot_r"].z)
    ankle_z = ground_z + (mesh_h * 0.035)
    foot_l_w = lm["foot_l"].copy()
    foot_r_w = lm["foot_r"].copy()
    foot_l_w.z = ankle_z
    foot_r_w.z = ankle_z

    # ================================================================
    # 4. KALÇA POZİSYONLARI
    #
    # Pelvis genişliği: bel genişliğinin %45'i (cross-section'dan).
    # Sınır: mesh yüksekliğinin %4-%8 arası.
    # ================================================================
    hip_half_width = waist_width * 0.45
    hip_half_width = max(mesh_h * 0.04, min(mesh_h * 0.08, hip_half_width))
    
    hip_l_w = Vector((center_x + hip_half_width, torso_y, hip_joint_z))
    hip_r_w = Vector((center_x - hip_half_width, torso_y, hip_joint_z))

    # ================================================================
    # 5. DİZ POZİSYONLARI
    # ================================================================
    knee_l_w = lm["knee_l"].copy()
    knee_r_w = lm["knee_r"].copy()
    knee_l_w.z = knee_z
    knee_l_w.x = hip_l_w.x
    knee_r_w.z = knee_z
    knee_r_w.x = hip_r_w.x

    # ================================================================
    # 6. DÜNYA → RIG LOKAL KOORDİNAT DÖNÜŞÜMÜ
    # ================================================================
    shoulder_l = to_local @ shoulder_l_w
    shoulder_r = to_local @ shoulder_r_w
    hand_l = to_local @ hand_l_w
    hand_r = to_local @ hand_r_w
    hip_l = to_local @ hip_l_w
    hip_r = to_local @ hip_r_w
    knee_l = to_local @ knee_l_w
    knee_r = to_local @ knee_r_w
    foot_l = to_local @ foot_l_w
    foot_r = to_local @ foot_r_w

    # Spine için Y ve X koordinat (lokal)
    spine_center_w = Vector((center_x, torso_y, 0.0))
    spine_center_local = to_local @ spine_center_w
    cx_local = spine_center_local.x
    cy_local = spine_center_local.y

    # ================================================================
    # 7. DİRSEK ve BİLEK HESAPLAMA
    # ================================================================
    wrist_l = lerp_vec(shoulder_l, hand_l, 0.82)
    wrist_r = lerp_vec(shoulder_r, hand_r, 0.82)
    elbow_l = lerp_vec(shoulder_l, wrist_l, 0.52)
    elbow_r = lerp_vec(shoulder_r, wrist_r, 0.52)

    elbow_l.x += abs(wrist_l.x - shoulder_l.x) * 0.08
    elbow_r.x -= abs(wrist_r.x - shoulder_r.x) * 0.08

    # ================================================================
    # 8. OMURGA ZİNCİRİ (spine → spine.006)
    #
    # spine.head = spine_root (sacrum, ~%48-%56)
    # spine — spine.004: 5 segment gövde
    # spine.005: boyun (kısa)
    # spine.006: baş (orta boy, saç ucuna değil %45'ine kadar)
    # ================================================================
    spine_root_local = (to_local @ Vector((0, 0, spine_root_z))).z
    shoulder_local_z = (to_local @ Vector((0, 0, shoulder_z))).z
    neck_local_z = (to_local @ Vector((0, 0, neck_z))).z
    head_center_z = (to_local @ Vector((0, 0, neck_z + (z_max - neck_z) * 0.45))).z
    
    spine_step = (shoulder_local_z - spine_root_local) / 5.0
    
    spine_z_points = []
    for i in range(6):
        spine_z_points.append(spine_root_local + i * spine_step)
    spine_z_points.append(neck_local_z)
    spine_z_points.append(head_center_z)
    
    spine_names = ["spine", "spine.001", "spine.002", "spine.003", 
                   "spine.004", "spine.005", "spine.006"]
    
    for i, name in enumerate(spine_names):
        if name in eb:
            eb[name].head = Vector((cx_local, cy_local, spine_z_points[i]))
            eb[name].tail = Vector((cx_local, cy_local, spine_z_points[i + 1]))

    # ================================================================
    # 9. PELVIS KEMİKLERİ
    # Spine root → kalça eklemi (aşağı ve yana)
    # ================================================================
    spine_root_vec = Vector((cx_local, cy_local, spine_root_local))
    
    if "pelvis.L" in eb:
        eb["pelvis.L"].head = spine_root_vec
        eb["pelvis.L"].tail = hip_l
    if "pelvis.R" in eb:
        eb["pelvis.R"].head = spine_root_vec
        eb["pelvis.R"].tail = hip_r

    # ================================================================
    # 10. OMUZ KEMİKLERİ
    # ================================================================
    shoulder_attach = Vector((cx_local, cy_local, spine_z_points[5]))
    
    if "shoulder.L" in eb:
        eb["shoulder.L"].head = shoulder_attach
        eb["shoulder.L"].tail = shoulder_l
    if "shoulder.R" in eb:
        eb["shoulder.R"].head = shoulder_attach
        eb["shoulder.R"].tail = shoulder_r

    # ================================================================
    # 11. KOL ZİNCİRİ
    # ================================================================
    if "upper_arm.L" in eb:
        eb["upper_arm.L"].head = shoulder_l
        eb["upper_arm.L"].tail = elbow_l
    if "forearm.L" in eb:
        eb["forearm.L"].head = elbow_l
        eb["forearm.L"].tail = wrist_l
    if "hand.L" in eb:
        eb["hand.L"].head = wrist_l
        eb["hand.L"].tail = hand_l

    if "upper_arm.R" in eb:
        eb["upper_arm.R"].head = shoulder_r
        eb["upper_arm.R"].tail = elbow_r
    if "forearm.R" in eb:
        eb["forearm.R"].head = elbow_r
        eb["forearm.R"].tail = wrist_r
    if "hand.R" in eb:
        eb["hand.R"].head = wrist_r
        eb["hand.R"].tail = hand_r

    # ================================================================
    # 12. BACAK ZİNCİRİ
    # ================================================================
    if "thigh.L" in eb:
        eb["thigh.L"].head = hip_l
        eb["thigh.L"].tail = knee_l
    if "shin.L" in eb:
        eb["shin.L"].head = knee_l
        eb["shin.L"].tail = foot_l
    
    if "thigh.R" in eb:
        eb["thigh.R"].head = hip_r
        eb["thigh.R"].tail = knee_r
    if "shin.R" in eb:
        eb["shin.R"].head = knee_r
        eb["shin.R"].tail = foot_r

    # ================================================================
    # 13. AYAK + PARMAK + TOPUK
    # ================================================================
    foot_forward_len = mesh_h * 0.04
    toe_len = mesh_h * 0.025
    
    for side, foot_pos in [(".L", foot_l), (".R", foot_r)]:
        foot_name = "foot" + side
        toe_name = "toe" + side
        heel_name = "heel.02" + side
        
        if foot_name in eb:
            foot_end = foot_pos.copy()
            foot_end.y -= foot_forward_len
            foot_end.z = foot_pos.z - mesh_h * 0.02
            eb[foot_name].head = foot_pos
            eb[foot_name].tail = foot_end
            
            if toe_name in eb:
                toe_end = foot_end.copy()
                toe_end.y -= toe_len
                eb[toe_name].head = foot_end
                eb[toe_name].tail = toe_end
            
            if heel_name in eb:
                heel_start = foot_pos.copy()
                heel_end = heel_start.copy()
                heel_end.y += mesh_h * 0.02
                heel_end.z = foot_pos.z - mesh_h * 0.03
                eb[heel_name].head = heel_start
                eb[heel_name].tail = heel_end

    # ================================================================
    # 14. GÖĞÜS KEMİKLERİ (breast.L/R)
    # ================================================================
    if "spine.003" in eb and len(spine_z_points) > 4:
        breast_z_local = spine_z_points[3] + spine_step * 0.5
        breast_len = mesh_h * 0.04
        
        for side_name, side_sign in [("breast.L", 1.0), ("breast.R", -1.0)]:
            if side_name in eb:
                b_head = Vector((cx_local + side_sign * mesh_h * 0.04, 
                                cy_local, breast_z_local))
                b_tail = Vector((cx_local + side_sign * mesh_h * 0.04, 
                                cy_local - breast_len, breast_z_local - breast_len * 0.3))
                eb[side_name].head = b_head
                eb[side_name].tail = b_tail

    # ================================================================
    # LOG
    # ================================================================
    print(
        f"[BİLGİ] Fitting: shoulder_inset={shoulder_inset:.3f}, "
        f"hip_width={hip_half_width*2:.4f}, "
        f"waist_width={waist_width:.4f}"
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    print("[SİSTEM] Kemikler yeni pozisyonlarına kilitlendi.")
    return True


# ════════════════════════════════════════════════════════════════════════
#                        ANA PIPELINE
# ════════════════════════════════════════════════════════════════════════

def auto_rig_advanced():
    """
    Ana rigging pipeline — tüm adımları sırayla çalıştırır.
    
    Akış:
    1. Hedef mesh'i bul
    2. Transform'ları uygula
    3. Mesh'i ön işle (preprocessing)
    4. Voxel proxy oluştur (ekipman yumuşatma)
    5. Pose algıla (T veya A)
    6. Template rig'i sahneye ekle
    7. Rig'i mesh boyutuna ölçekle
    8. Kemikleri anatomik noktalara otur (cross-section on proxy)
    9. Raycasting ile kemikleri hacim ortasına merkezle
    10. Voxel proxy'yi temizle
    11. Auto-weights ile skinning yap
    """
    ensure_object_mode()

    # === 1. Hedef Mesh ===
    target_mesh = pick_target_mesh()
    if not target_mesh:
        print("[HATA] Sahnede mesh bulunamadı.")
        return
    
    print(f"[OK] Hedef mesh: {target_mesh.name}")
    
    select_only(target_mesh)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    
    # === 2. Mesh Ön İşleme ===
    preprocess_mesh(target_mesh)
    
    # === 3. Ölçüler ve Pose Tespiti ===
    mesh_height, _ = get_mesh_dimensions(target_mesh)
    print(f"[HESAP] Mesh yüksekliği: {mesh_height:.4f}")
    
    # === 4. Voxel Proxy Oluştur ===
    print("[OK] Voxel proxy oluşturuluyor...")
    ensure_object_mode()
    voxel_proxy = create_voxel_proxy(target_mesh)
    ensure_object_mode()
    
    # Cross-section tabanlı pose tespiti
    pose_type = detect_humanoid_pose(target_mesh)
    
    selected_rig = RIG_FILE_A if pose_type == 'A_POSE' else RIG_FILE_T
    rig_path = os.path.join(TEMPLATE_DIR, selected_rig)
    print(f"[BİLGİ] Seçilen template rig: {selected_rig}")
    
    # === 5. Template Rig'i Sahneye Ekle ===
    custom_rig = append_custom_rig(rig_path, RIG_OBJECT_NAME)
    
    if not custom_rig:
        print("[HATA] Template rig sahneye eklenemedi.")
        cleanup_proxy(voxel_proxy)
        return
    custom_rig.location = (0, 0, 0)
    
    # === 6. Rig'i Mesh Boyutuna Ölçekle ===
    bpy.context.view_layer.update()
    rig_height, _ = get_mesh_dimensions(custom_rig)
    
    if rig_height <= 1e-6:
        print("[HATA] Rig yüksekliği hesaplanamadı.")
        cleanup_proxy(voxel_proxy)
        return

    scale_factor = (mesh_height / rig_height) * 0.92
    scale_factor = max(0.20, min(scale_factor, 8.00))
    custom_rig.scale = (scale_factor, scale_factor, scale_factor)
    print(f"[ÖLÇÜM] Ölçek faktörü: {scale_factor:.4f}")
    
    select_only(custom_rig)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # === 6.5. Template Oranlarını Çıkar (scale sonrası, fit öncesi) ===
    chain_ratios = extract_chain_ratios(custom_rig)

    # === 7. Kemikleri Anatomik Noktalara Otur (Proxy üzerinden) ===
    fit_ok = fit_bones_to_anatomy(target_mesh, custom_rig, proxy_mesh=voxel_proxy)
    if not fit_ok:
        print("[UYARI] Fitting atlandı, yalnızca template ölçeklenerek devam ediliyor.")
    
    # === 7.5. Bölgesel Ölçekleme + IK Solve ===
    if fit_ok:
        ensure_object_mode()
        apply_regional_scaling(custom_rig, chain_ratios)

    # === 8. Raycasting ile Kemikleri Hacim Ortasına Merkezle ===
    if fit_ok:
        ensure_object_mode()
        refine_bones_with_raycast(voxel_proxy, custom_rig)
    
    # === 9. Voxel Proxy Temizliği ===
    ensure_object_mode()
    cleanup_proxy(voxel_proxy)
    print("[BİLGİ] Voxel proxy temizlendi.")

    # === 10. Skinning (Deri Giydirme) ===
    ensure_object_mode()
    select_only(target_mesh)
    target_mesh.select_set(True)
    custom_rig.select_set(True)
    bpy.context.view_layer.objects.active = custom_rig
    
    print("[OK] Otomatik Ağırlıklandırma (Skinning) yapılıyor...")
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print("[BAŞARILI] Voxel+Raycast Auto-Rigging Başarıyla Tamamlandı!\n")
    except Exception as e:
        print(f"[UYARI] ARMATURE_AUTO başarısız: {e}")
        print("[OK] ARMATURE_NAME fallback deneniyor...")
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        custom_rig.select_set(True)
        bpy.context.view_layer.objects.active = custom_rig
        try:
            bpy.ops.object.parent_set(type='ARMATURE_NAME')
            print("[OK] Fallback ile parent kuruldu (weights manuel/sonradan düzeltilebilir).")
        except Exception as e2:
            print(f"[HATA] Fallback de başarısız: {e2}")

if __name__ == "__main__":
    auto_rig_advanced()