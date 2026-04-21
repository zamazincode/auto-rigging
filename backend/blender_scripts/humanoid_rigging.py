import bpy
import os
import sys
import math
from mathutils import Vector

####################################################################################
# Blender script olarak çalıştırıldığında veya GUI (Text Editor) içinden tetiklendiğinde 
# aynı dizindeki modülleri bulabilmesi için dizini Python path'ine dahil ediyoruz.
import os
import sys
import importlib

script_dir = os.path.normpath(r"c:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\blender_scripts")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    import cross_section_analyzer
    importlib.reload(cross_section_analyzer)  # Blender hafızasındaki önbelleği temizler
except ModuleNotFoundError as e:
    print("SİSTEM YOLU (sys.path):", sys.path)
    raise e
####################################################################################

from cross_section_analyzer import (
    get_world_bbox,
    get_mesh_dimensions,
    average_vec,
    lerp_vec,
    get_world_verts,
    detect_humanoid_pose,
    detect_humanoid_landmarks,
)

TEMPLATE_DIR = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\templates"

RIG_FILE_T = "human_rig_T.blend" 
RIG_FILE_A = "human_rig_A.blend" 

RIG_OBJECT_NAME = "Armature"


# ════════════════════════════════════════════════════════════════════════
#                        YARDIMCI FONKSİYONLAR
# ════════════════════════════════════════════════════════════════════════

def pick_target_mesh():
    """
    Sahnedeki riglenmesi gereken mesh'i seç.
    
    Tercih sırası:
    1. Eğer aktif obje mesh ise, onu kullan.
    2. Değilse, sahnedeki en büyük hacimli mesh'i seç.
    3. Hiç mesh yoksa None dön.
    """
    active = bpy.context.view_layer.objects.active
    
    if active and active.type == 'MESH':
        return active

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        return None

    def mesh_volume_world(obj):
        _, dims = get_mesh_dimensions(obj)
        return dims.x * dims.y * dims.z

    return max(meshes, key=mesh_volume_world)



def ensure_object_mode():
    """Blender'in Object Mode olmasını sağla."""
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def select_only(obj):
    """Tüm seçimleri kaldır ve yalnızca verilen objeyi seç."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def append_custom_rig(filepath, obj_name):
    """Harici .blend dosyasından iskelet objesini mevcut sahneye ekle."""
    if not os.path.exists(filepath):
        return None
    bpy.ops.object.select_all(action='DESELECT')
    existing_objects = set(obj.name for obj in bpy.context.scene.objects)
    
    inner_path = "Object"
    bpy.ops.wm.append(
        filepath=os.path.join(filepath, inner_path, obj_name),
        directory=os.path.join(filepath, inner_path),
        filename=obj_name
    )
    
    new_objects = [obj for obj in bpy.context.scene.objects if obj.name not in existing_objects]
    if new_objects:
        rig = new_objects[0]
        select_only(rig)
        return rig
    return None


def preprocess_mesh(obj):
    """
    Mesh'i auto-weights öncesi temizle.
    
    Non-manifold kenarlar, çift vertexler ve tutarsız normaller
    ARMATURE_AUTO (Heat Diffusion) algoritmasının başarısız olmasına
    veya kötü ağırlıklar üretmesine neden olabilir.
    """
    print("🧹 Mesh ön işleme (preprocessing) yapılıyor...")
    
    select_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    # 1. Çift vertexleri birleştir — çok yakın vertexler heat diffusion'ı bozabilir
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    
    # 2. Normalleri tutarlı yap — ters normaller ağırlık hesabını yanlış yapar
    bpy.ops.mesh.normals_make_consistent(inside=False)
    
    # 3. Degenerate yüzeyleri temizle — sıfır alanlı üçgenler sorun yaratır
    bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("🧹 Mesh ön işleme tamamlandı.")


# ════════════════════════════════════════════════════════════════════════
#                  VOXEL PROXY + RAYCASTING SİSTEMİ
#
# Neden gerekli?
# - Oyun modelleri genellikle zırh, silah, kemer gibi çıkıntılara sahip
# - Cross-section analizi bu çıkıntıları vücut olarak algılıyor
# - Voxel remesh bu detayları yumuşatıp temiz bir siluet üretir
# - Raycasting ile kemikler hacmin tam merkezine oturtulur
#
# Pipeline:
# 1. create_voxel_proxy()   → Temiz, katı mesh kopyası
# 2. Cross-section analiz   → Proxy üzerinde (daha doğru Z ve genişlik)
# 3. Kemik yerleştirme       → Hibrit Z + cross-section genişlik
# 4. refine_bones_raycast() → Raycasting ile Y ve X merkezleme
# 5. cleanup_proxy()        → Proxy'yi sahneden sil
# ════════════════════════════════════════════════════════════════════════

def create_voxel_proxy(target_mesh, voxel_size=None):
    """
    Modelin katı, basitleştirilmiş Voxel kopyasını oluşturur.
    
    Voxel remesh:
    - Açık kenarları kapatır (watertight mesh)
    - Ekipman/aksesuar detaylarını yumuşatır
    - Düz, uniform topoloji üretir → raycasting güvenilir olur
    
    Argümanlar:
    - voxel_size: Voxel çözünürlüğü (metre). None ise mesh yüksekliğine
      oransal otomatik hesap. Küçük = detaylı, büyük = yumuşak.
    """
    mesh_h, _ = get_mesh_dimensions(target_mesh)
    if voxel_size is None:
        # ~55-60 voxel yükseklik → ekipman yumuşar, kol ayrımı korunur
        voxel_size = max(0.02, mesh_h * 0.018)
    
    bpy.ops.object.select_all(action='DESELECT')
    target_mesh.select_set(True)
    bpy.context.view_layer.objects.active = target_mesh
    
    bpy.ops.object.duplicate()
    proxy = bpy.context.active_object
    proxy.name = target_mesh.name + "_VOXEL_PROXY"
    
    remesh = proxy.modifiers.new(name="VoxelRemesh", type='REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = voxel_size
    bpy.ops.object.modifier_apply(modifier="VoxelRemesh")
    
    print(f"   📦 Voxel proxy oluşturuldu (voxel_size={voxel_size:.3f}, "
          f"verts: {len(proxy.data.vertices)})")
    return proxy


def cleanup_proxy(proxy):
    """Voxel proxy objesini sahneden sil."""
    bpy.data.objects.remove(proxy, do_unlink=True)


def raycast_world(obj, origin, direction):
    """
    Dünya koordinatlarında bir objeye raycast fırlatır.
    
    Argümanlar:
    - obj: Hedef mesh objesi
    - origin: Işının başlangıç noktası (Vector, dünya koordinatı)
    - direction: Işın yönü (Vector, normalize edilecek)
    
    Dönüş:
    - (True, hit_world_pos) veya (False, None)
    """
    matrix_inv = obj.matrix_world.inverted()
    origin_local = matrix_inv @ origin
    dir_local = (matrix_inv.to_3x3() @ direction).normalized()
    
    hit, loc_local, normal, face_idx = obj.ray_cast(origin_local, dir_local)
    
    if hit:
        return True, obj.matrix_world @ loc_local
    return False, None


def raycast_find_center(proxy, point, axis, dist=5.0):
    """
    İki yönlü raycast ile bir noktanın belirli eksendeki hacim merkezini bulur.
    
    Yöntem:
    - Meshin dışından iki karşıt yönde raycast at
    - İki yüzey noktasının ortası = hacim merkezi
    
    Argümanlar:
    - proxy: Voxel proxy mesh
    - point: Merkezlenecek nokta (dünya koordinatı)
    - axis: Eksen vektörü (örn. Vector((0,1,0)) = Y ekseni)
    - dist: Raycast başlangıç uzaklığı (mesh dışına çıkmak için)
    """
    # + yönde: dışarıdan merkeze
    hit_p, loc_p = raycast_world(proxy, point - axis * dist, axis)
    # - yönde: dışarıdan merkeze
    hit_n, loc_n = raycast_world(proxy, point + axis * dist, -axis)
    
    if hit_p and hit_n:
        return (loc_p + loc_n) / 2.0
    return None


def refine_bones_with_raycast(proxy, rig):
    """
    Raycasting ile kemikleri mesh hacminin ortasına hizalar.
    
    Neden gerekli:
    - Cross-section sadece X ekseninde genişlik ölçer
    - Y ekseni (ön-arka) için sabit torso_y kullanılıyor → yanlış
    - Raycasting ile her kemik gerçek hacim merkezine çekilir
    
    Her kemik noktası (head/tail) için:
    1. Y ekseni (ön-arka): Her zaman merkezle
    2. X ekseni (sağ-sol): Sadece uzuv kemikleri için (spine hariç)
    """
    print("🎯 Raycast ile kemik merkezleme başlatılıyor...")
    
    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    world = rig.matrix_world
    world_inv = world.inverted()
    
    axis_x = Vector((1, 0, 0))
    axis_y = Vector((0, 1, 0))
    
    refined_count = 0
    
    def center_point_on_axis(bone_name, point_type, axis):
        """Tek bir kemik noktasını belirtilen eksende mesh ortasına çeker."""
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
    
    # ── SPINE: Y merkezle (ön-arka hizalama) ──
    # Omurga kemikleri gövdenin ön-arka ortasında olmalı
    spine_names = ["spine", "spine.001", "spine.002", "spine.003", 
                   "spine.004", "spine.005", "spine.006"]
    for name in spine_names:
        center_point_on_axis(name, 'head', axis_y)
    # Son spine'ın tail'ini de merkezle
    center_point_on_axis("spine.006", 'tail', axis_y)
    
    # Spine zincirini senkronize et (tail.y = sonraki head.y)
    for i in range(len(spine_names) - 1):
        curr = spine_names[i]
        nxt = spine_names[i + 1]
        if curr in eb and nxt in eb:
            avg_y = (eb[curr].tail.y + eb[nxt].head.y) / 2
            eb[curr].tail.y = avg_y
            eb[nxt].head.y = avg_y
    
    # ── OMUZ: tail Y merkezle ──
    for side in [".L", ".R"]:
        center_point_on_axis("shoulder" + side, 'tail', axis_y)
    
    # ── KOL ZİNCİRİ: Y merkezle ──
    for side in [".L", ".R"]:
        for part in ["upper_arm", "forearm", "hand"]:
            center_point_on_axis(part + side, 'head', axis_y)
            center_point_on_axis(part + side, 'tail', axis_y)
    
    # ── BACAK ZİNCİRİ: Y merkezle ──
    for side in [".L", ".R"]:
        for part in ["thigh", "shin"]:
            center_point_on_axis(part + side, 'head', axis_y)
            center_point_on_axis(part + side, 'tail', axis_y)
    
    # ── PELVIS: tail Y merkezle ──
    for side in [".L", ".R"]:
        center_point_on_axis("pelvis" + side, 'tail', axis_y)
    
    # Bağlantı tutarlılığı: upper_arm.head = shoulder.tail
    for side in [".L", ".R"]:
        sh = "shoulder" + side
        ua = "upper_arm" + side
        if sh in eb and ua in eb:
            eb[ua].head = eb[sh].tail.copy()
        
        # forearm.head = upper_arm.tail
        fa = "forearm" + side
        if ua in eb and fa in eb:
            eb[fa].head = eb[ua].tail.copy()
        
        # shin.head = thigh.tail
        th = "thigh" + side
        sn = "shin" + side
        if th in eb and sn in eb:
            eb[sn].head = eb[th].tail.copy()
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"   🎯 Raycast: {refined_count} nokta merkezlendi")


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
    print("🦴 Cross-Section Kemik Oturtma (Fitting) başlatılıyor...")

    # Landmark tespiti: proxy varsa proxy'den, yoksa orijinal mesh'ten
    analysis_mesh = proxy_mesh if proxy_mesh else mesh
    lm = detect_humanoid_landmarks(analysis_mesh)
    if not lm:
        print("⚠️ Landmark tespiti başarısız, kemik fitting atlandı.")
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
    
    print(f"📐 Hibrit Z seviyeleri (cross-section + clamp):")
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
        f"ℹ️ Fitting: shoulder_inset={shoulder_inset:.3f}, "
        f"hip_width={hip_half_width*2:.4f}, "
        f"waist_width={waist_width:.4f}"
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    print("🦴 Kemikler yeni pozisyonlarına kilitlendi.")
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
        print("❌ Sahnede mesh bulunamadı.")
        return
    
    print(f"🎯 Hedef mesh: {target_mesh.name}")
    
    select_only(target_mesh)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    
    # === 2. Mesh Ön İşleme ===
    preprocess_mesh(target_mesh)
    
    # === 3. Ölçüler ve Pose Tespiti ===
    mesh_height, _ = get_mesh_dimensions(target_mesh)
    print(f"📏 Mesh yüksekliği: {mesh_height:.4f}")
    
    # === 4. Voxel Proxy Oluştur ===
    print("📦 Voxel proxy oluşturuluyor...")
    ensure_object_mode()
    voxel_proxy = create_voxel_proxy(target_mesh)
    ensure_object_mode()
    
    # Cross-section tabanlı pose tespiti
    pose_type = detect_humanoid_pose(target_mesh)
    
    selected_rig = RIG_FILE_A if pose_type == 'A_POSE' else RIG_FILE_T
    rig_path = os.path.join(TEMPLATE_DIR, selected_rig)
    print(f"📂 Seçilen template rig: {selected_rig}")
    
    # === 5. Template Rig'i Sahneye Ekle ===
    custom_rig = append_custom_rig(rig_path, RIG_OBJECT_NAME)
    
    if not custom_rig:
        print("❌ Template rig sahneye eklenemedi.")
        cleanup_proxy(voxel_proxy)
        return
    custom_rig.location = (0, 0, 0)
    
    # === 6. Rig'i Mesh Boyutuna Ölçekle ===
    bpy.context.view_layer.update()
    rig_height, _ = get_mesh_dimensions(custom_rig)
    
    if rig_height <= 1e-6:
        print("❌ Rig yüksekliği hesaplanamadı.")
        cleanup_proxy(voxel_proxy)
        return

    scale_factor = (mesh_height / rig_height) * 0.92
    scale_factor = max(0.20, min(scale_factor, 8.00))
    custom_rig.scale = (scale_factor, scale_factor, scale_factor)
    print(f"📐 Ölçek faktörü: {scale_factor:.4f}")
    
    select_only(custom_rig)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # === 7. Kemikleri Anatomik Noktalara Otur (Proxy üzerinden) ===
    fit_ok = fit_bones_to_anatomy(target_mesh, custom_rig, proxy_mesh=voxel_proxy)
    if not fit_ok:
        print("⚠️ Fitting atlandı, yalnızca template ölçeklenerek devam ediliyor.")
    
    # === 8. Raycasting ile Kemikleri Hacim Ortasına Merkezle ===
    if fit_ok:
        ensure_object_mode()
        refine_bones_with_raycast(voxel_proxy, custom_rig)
    
    # === 9. Voxel Proxy Temizliği ===
    ensure_object_mode()
    cleanup_proxy(voxel_proxy)
    print("🗑️ Voxel proxy temizlendi.")

    # === 10. Skinning (Deri Giydirme) ===
    ensure_object_mode()
    select_only(target_mesh)
    target_mesh.select_set(True)
    custom_rig.select_set(True)
    bpy.context.view_layer.objects.active = custom_rig
    
    print("⚙️ Otomatik Ağırlıklandırma (Skinning) yapılıyor...")
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print("🎉 Voxel+Raycast Auto-Rigging Başarıyla Tamamlandı!\n")
    except Exception as e:
        print(f"⚠️ ARMATURE_AUTO başarısız: {e}")
        print("↪️ ARMATURE_NAME fallback deneniyor...")
        bpy.ops.object.select_all(action='DESELECT')
        target_mesh.select_set(True)
        custom_rig.select_set(True)
        bpy.context.view_layer.objects.active = custom_rig
        try:
            bpy.ops.object.parent_set(type='ARMATURE_NAME')
            print("✅ Fallback ile parent kuruldu (weights manuel/sonradan düzeltilebilir).")
        except Exception as e2:
            print(f"❌ Fallback de başarısız: {e2}")

if __name__ == "__main__":
    auto_rig_advanced()