import bpy
import os
import math
from mathutils import Vector

TEMPLATE_DIR = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\templates"

RIG_FILE_T = "human_rig_T.blend" 
RIG_FILE_A = "human_rig_A.blend" 

RIG_OBJECT_NAME = "Armature"

def get_world_bbox(obj):
    """
    Obje'nin dünya uzayındaki bounding box'ını hesapla.
    
    Bounding box: objeyi saracak hayali bir kutunun min ve max köşeleri.
    Dünya uzayı: Sahnedeki global koordinat sistemi.
    
    Döndürülen değerler:
    - min_v: Kutunun minimum X, Y, Z köşesi
    - max_v: Kutunun maksimum X, Y, Z köşesi
    """
    # Blender'in bounding box'ı 8 köşe olarak verir. Her köşeyi dünya uzayına çevir.
    world_pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    # Tüm X, Y, Z koordinatlarını ayır
    xs = [p.x for p in world_pts]
    ys = [p.y for p in world_pts]
    zs = [p.z for p in world_pts]
    
    # Min ve max köşeleri belirle
    min_v = Vector((min(xs), min(ys), min(zs)))
    max_v = Vector((max(xs), max(ys), max(zs)))
    
    return min_v, max_v



def get_mesh_dimensions(obj):
    """
    Obje'nin yüksekliğini ve 3D boyutlarını hesapla.
    
    Döndürülen değerler:
    - height: Z eksenindeki yükseklik (en önemli ölçek)
    - dims: X, Y, Z boyutlarının Vector'ü
    """
    min_v, max_v = get_world_bbox(obj)
    dims = max_v - min_v
    return dims.z, dims



def pick_target_mesh():
    """
    Sahnedeki riglenmesi gereken mesh'i seç.
    
    Tercih sırası:
    1. Eğer aktif obje mesh ise, onu kullan.
    2. Değilse, sahnedeki en büyük hacimli mesh'i seç.
    3. Hiç mesh yoksa None dön.
    
    Böylece kullanıcı hangi mesh'i seçerse onu başlıyor,
    seçili değilse de otomatik olarak en büyük mesh bulunuyor.
    """
    # Aktif obje nedir?
    active = bpy.context.view_layer.objects.active
    
    # Aktif obje mesh ve geçerliyse onu döndür
    if active and active.type == 'MESH':
        return active

    # Sahnedeki tüm mesh'leri topla
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        return None

    # Mesh'in hacmini hesapla (genişlik × derin × yükseklik)
    def mesh_volume_world(obj):
        _, dims = get_mesh_dimensions(obj)
        return dims.x * dims.y * dims.z

    # En büyük hacimli mesh'i döndür
    return max(meshes, key=mesh_volume_world)



def ensure_object_mode():
    """
    Blender'in Object Mode (nesne modu) olmasını sağla.
    Edit, Pose, Sculpt gibi modların dışına çık.
    """
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def select_only(obj):
    """
    Tüm seçimleri kaldır ve yalnızca verilen objeyi seç.
    
    Argüman:
    - obj: Seçilmesi gereken obje
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def average_vec(points):
    """
    Vector listesinin ortalamasını al (merkez/centroid).
    
    Argüman:
    - points: Vector nesnelerinin listesi
    
    Döndürülen değer:
    - Tüm noktaların ortalaması veya None (liste boşsa)
    """
    if not points:
        return None
    total = Vector((0.0, 0.0, 0.0))
    for p in points:
        total += p
    return total / len(points)


def lerp_vec(a, b, t):
    """
    A ile B arasında doğrusal interpolasyon yap.
    
    Argümanlar:
    - a: Başlangıç noktası
    - b: Bitiş noktası
    - t: 0.0 ila 1.0 arasında interpolasyon faktörü (0.0=A, 1.0=B, 0.5=ortası)
    
    Örnek: Omuz ile el arasında %52'de noktayı bul (dirsek tahmini)
    """
    return a + (b - a) * t


def get_pose_landmarks(mesh):
    """
    Mesh'in özür anatomik noktalarını (landmark'larını) bul.
    
    MANTIK:
    Mesh'i yükseklik dilimleri (bands) halinde bölüp, her dilimde anatomik noktalar ara.
    
    Örnek:
    - %72-88: Omuz bölgesi
    - %45-90: Kol bölgesi
    - %46-60: Kalça/pelvis
    - %20-45: Diz bölgesi
    - %0-14: Ayak bölgesi
    
    Her bölgede sola ve sağaya bakacak noktaları seç.
    
    Döndürülen değer:
    - Dict: anatomik noktaların koordinatları {omuz_l, omuz_r, ...}
    - None: Yetersiz veri veya mesh çok small
    """
    # Tüm vertexleri dünya koordinatına çevir
    verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    
    # Çok az vertex varsa (örn. primitive cube), landmark yapmaya gerek yok
    if len(verts) < 50:
        return None

    # X koordinatlarını ve Z koordinatlarını ayır
    xs = [v.x for v in verts]
    zs = [v.z for v in verts]
    
    # Gövde'nin merkez X eksenini bul (sol/sağ ayrımı için)
    center_x = sorted(xs)[len(xs) // 2]
    
    # Z eksendeki min ve max bularak yüksekliği hesapla
    z_min = min(zs)
    z_max = max(zs)
    h = max(1e-6, z_max - z_min)  # Bölmede 0 olmamak için güvenlik

    # Band fonksiyonu: Yüksekliğin z0 ile z1 yüzdesi arasındaki vertexleri döndür
    def band(z0, z1):
        """
        z0: Başlangıç yüzdesi (0.0-1.0)
        z1: Bitiş yüzdesi
        
        Örn: band(0.72, 0.88) = Vücudun üst %72-%88'inde bulunan vertexler
        """
        lo = z_min + h * z0
        hi = z_min + h * z1
        return [v for v in verts if lo <= v.z <= hi]

    # Her anatomik bölge için band'leri tanımla
    shoulder_band = band(0.72, 0.88)  # Omuz seviyesi
    arm_band = band(0.45, 0.90)       # Kol boyunca
    pelvis_band = band(0.46, 0.60)    # Kalça/pelvis
    knee_band = band(0.20, 0.45)      # Diz seviyesi
    foot_band = band(0.00, 0.14)      # Ayak seviyesi

    # Her band içinde sola ve sağa seçme kriteri uygula
    shoulder_left_candidates = [v for v in shoulder_band if v.x > center_x + 0.02]
    shoulder_right_candidates = [v for v in shoulder_band if v.x < center_x - 0.02]
    hand_left_candidates = [v for v in arm_band if v.x > center_x + 0.04]
    hand_right_candidates = [v for v in arm_band if v.x < center_x - 0.04]
    hip_left_candidates = [v for v in pelvis_band if v.x > center_x + 0.01]
    hip_right_candidates = [v for v in pelvis_band if v.x < center_x - 0.01]
    knee_left_candidates = [v for v in knee_band if v.x > center_x + 0.01]
    knee_right_candidates = [v for v in knee_band if v.x < center_x - 0.01]
    foot_left_candidates = [v for v in foot_band if v.x > center_x + 0.01]
    foot_right_candidates = [v for v in foot_band if v.x < center_x - 0.01]

    # Güvenlik kontrolü: her alanın aday noktası var mı?
    if not shoulder_left_candidates or not shoulder_right_candidates:
        return None
    if not hand_left_candidates or not hand_right_candidates:
        return None
    if not foot_left_candidates or not foot_right_candidates:
        return None

    # Her anatomik nokta için en uygun adayı seç
    # Omuz: Bölgede en uç noktalar
    shoulder_l = max(shoulder_left_candidates, key=lambda v: v.x)
    shoulder_r = min(shoulder_right_candidates, key=lambda v: v.x)
    
    # El: Kol bölgesinde açılan en uç noktalar
    hand_l = max(hand_left_candidates, key=lambda v: v.x)
    hand_r = min(hand_right_candidates, key=lambda v: v.x)

    # Pelvis merkez: Pelvis band'inin merkezi
    pelvis_center = average_vec(pelvis_band) or Vector((center_x, 0.0, z_min + h * 0.52))
    
    # Kalça: Pelvis merkeze yakın
    hip_l = average_vec(hip_left_candidates) or Vector((shoulder_l.x * 0.65, pelvis_center.y, pelvis_center.z))
    hip_r = average_vec(hip_right_candidates) or Vector((shoulder_r.x * 0.65, pelvis_center.y, pelvis_center.z))
    
    # Diz: Kalça ile ayak arasında %52'de
    knee_l = average_vec(knee_left_candidates) or lerp_vec(hip_l, min(foot_left_candidates, key=lambda v: v.z), 0.52)
    knee_r = average_vec(knee_right_candidates) or lerp_vec(hip_r, min(foot_right_candidates, key=lambda v: v.z), 0.52)
    
    # Ayak: En düşük Z noktaları (yere temas)
    foot_l = min(foot_left_candidates, key=lambda v: v.z)
    foot_r = min(foot_right_candidates, key=lambda v: v.z)

    # Tüm bulduğun noktaları dict olarak döndür
    return {
        "shoulder_l": shoulder_l,
        "shoulder_r": shoulder_r,
        "hand_l": hand_l,
        "hand_r": hand_r,
        "pelvis_center": pelvis_center,
        "hip_l": hip_l,
        "hip_r": hip_r,
        "knee_l": knee_l,
        "knee_r": knee_r,
        "foot_l": foot_l,
        "foot_r": foot_r,
    }


def detect_pose_angle(obj):
    """
    Mesh'in pose'unu algıla: T-Pose mi yoksa A-Pose mi?
    
    MANTIK:
    - Sağ eli bulup, omuz seviyesiyle karşılaştır.
    - T-Pose: El omuz seviyesine yakın (açı ~90°)
    - A-Pose: El omuz üstüne (açı <15°)
    
    Döndürülen değer:
    - Derece cinsinden açı
    - 15° üzeri: A-Pose (kollar açık yukarı)
    - 15° altı: T-Pose (kollar yanlara)
    """
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    z_coords = [v.z for v in verts]
    total_height = max(z_coords) - min(z_coords)
    
    # Omuz seviyesini vücudun %80'i olarak tanımla
    shoulder_z = min(z_coords) + (total_height * 0.8)
    
    # Sağ eli bul (en uç X noktası)
    right_hand = max(verts, key=lambda v: v.x)
    
    # Omuz ile El arasındaki Z farkı (dz) ve X farkı (dx)
    dz = shoulder_z - right_hand.z
    dx = right_hand.x
    
    # Trigonometri: atan2 kullanarak açıyı hesapla
    angle_rad = math.atan2(dz, dx)
    
    # Radyan'ı dereceye çevir
    return math.degrees(angle_rad)


def append_custom_rig(filepath, obj_name):
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

def fit_bones_to_anatomy(mesh, rig):
    """Kemikleri Edit modunda anatomik noktalara çeker."""
    print("🦴 Sezgisel Kemik Oturtma (Heuristic Fitting) başlatılıyor...")

    lm = get_pose_landmarks(mesh)
    if not lm:
        print("⚠️ Landmark güveni düşük, kemik fitting atlandı.")
        return False

    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    to_local = rig.matrix_world.inverted()

    # Hedef noktaları daha doğal hale getirmek için global düzeltmeler uygula.
    mesh_h, _ = get_mesh_dimensions(mesh)
    center_x = (lm["shoulder_l"].x + lm["shoulder_r"].x) * 0.5
    torso_y = lm["pelvis_center"].y
    shoulder_drop = mesh_h * 0.015  # Omuz seviyesi yukarı kaldırıldı (0.035 -> 0.015)
    shoulder_inset = 0.76           # Omuzlar daraltıldı, daha anatomik (0.90 -> 0.76)

    shoulder_l_w = lm["shoulder_l"].copy()
    shoulder_r_w = lm["shoulder_r"].copy()
    shoulder_l_w.x = center_x + (shoulder_l_w.x - center_x) * shoulder_inset
    shoulder_r_w.x = center_x + (shoulder_r_w.x - center_x) * shoulder_inset
    shoulder_l_w.z -= shoulder_drop
    shoulder_r_w.z -= shoulder_drop
    shoulder_l_w.y = torso_y
    shoulder_r_w.y = torso_y

    hand_l_w = lm["hand_l"].copy()
    hand_r_w = lm["hand_r"].copy()
    hand_l_w.y = torso_y
    hand_r_w.y = torso_y

    # Ayağın en alt vertex'i genelde parmak/tırnak olduğu için bilek hedefini biraz yukarı al.
    ground_z = min(lm["foot_l"].z, lm["foot_r"].z)
    ankle_z = ground_z + (mesh_h * 0.035)
    foot_l_w = lm["foot_l"].copy()
    foot_r_w = lm["foot_r"].copy()
    foot_l_w.z = ankle_z
    foot_r_w.z = ankle_z

    # Pelvis düzeltmesi: Dış kıyafet veya kalça sınırları yerine, iskeletin gerçek omuz genişliği baz alınarak anatomik kalça hesaplanıyor.
    hip_l_w = lm["hip_l"].copy()
    hip_r_w = lm["hip_r"].copy()
    hip_l_w.x = center_x + (shoulder_l_w.x - center_x) * 0.40  # Sola açılmayı kes
    hip_r_w.x = center_x + (shoulder_r_w.x - center_x) * 0.40  # Sağa açılmayı kes

    shoulder_l = to_local @ shoulder_l_w
    shoulder_r = to_local @ shoulder_r_w
    hand_l = to_local @ hand_l_w
    hand_r = to_local @ hand_r_w
    hip_l = to_local @ hip_l_w
    hip_r = to_local @ hip_r_w
    knee_l = to_local @ lm["knee_l"]
    knee_r = to_local @ lm["knee_r"]
    foot_l = to_local @ foot_l_w
    foot_r = to_local @ foot_r_w

    # Bilek tespiti: hand_l ve hand_r parmak uçlarıdır. Bilek ise omuzdan parmak ucuna giden yolun %82 civarıdır.
    wrist_l = lerp_vec(shoulder_l, hand_l, 0.82)
    wrist_r = lerp_vec(shoulder_r, hand_r, 0.82)

    elbow_l = lerp_vec(shoulder_l, wrist_l, 0.52)
    elbow_r = lerp_vec(shoulder_r, wrist_r, 0.52)

    # Dirsekleri hafif dışa alarak kolların gövdeye doğru kırılmasını engelle.
    elbow_l.x += abs(wrist_l.x - shoulder_l.x) * 0.08
    elbow_r.x -= abs(wrist_r.x - shoulder_r.x) * 0.08

    # Dizler için de benzer şekilde hafif dış ofset ver.
    knee_l.x += abs(foot_l.x - hip_l.x) * 0.04
    knee_r.x -= abs(foot_r.x - hip_r.x) * 0.04

    # Parent kemiklerini de hedefe yaklaştır; connected zincirlerde bu kritik.
    if "shoulder.L" in eb:
        shoulder_l_bone = eb["shoulder.L"]
        shoulder_l_bone.tail = shoulder_l
    if "shoulder.R" in eb:
        shoulder_r_bone = eb["shoulder.R"]
        shoulder_r_bone.tail = shoulder_r
    if "pelvis.L" in eb:
        pelvis_l_bone = eb["pelvis.L"]
        pelvis_l_bone.tail = hip_l
    if "pelvis.R" in eb:
        pelvis_r_bone = eb["pelvis.R"]
        pelvis_r_bone.tail = hip_r

    if "upper_arm.L" in eb:
        eb["upper_arm.L"].head = shoulder_l
        eb["upper_arm.L"].tail = elbow_l
    if "forearm.L" in eb:
        eb["forearm.L"].head = elbow_l
        eb["forearm.L"].tail = wrist_l
    if "hand.L" in eb:
        hand_l_bone = eb["hand.L"]
        hand_l_bone.head = wrist_l
        hand_l_bone.tail = hand_l  # hand.L kemiğinin sonu parmak uçları olsun

    if "upper_arm.R" in eb:
        eb["upper_arm.R"].head = shoulder_r
        eb["upper_arm.R"].tail = elbow_r
    if "forearm.R" in eb:
        eb["forearm.R"].head = elbow_r
        eb["forearm.R"].tail = wrist_r
    if "hand.R" in eb:
        hand_r_bone = eb["hand.R"]
        hand_r_bone.head = wrist_r
        hand_r_bone.tail = hand_r  # hand.R kemiğinin sonu parmak uçları olsun

    if "thigh.L" in eb:
        eb["thigh.L"].head = hip_l
        eb["thigh.L"].tail = knee_l
    if "shin.L" in eb:
        eb["shin.L"].head = knee_l
        eb["shin.L"].tail = foot_l
    if "foot.L" in eb:
        foot_l_bone = eb["foot.L"]
        foot_l_dir = (foot_l_bone.tail - foot_l_bone.head)
        foot_l_dir.x = 0.0  # Ayakların içe/dışa kıvrılmasını tamamen engelle
        if foot_l_dir.length < 1e-6:
            foot_l_dir = Vector((0.0, -0.08, 0.0))
        foot_l_bone.head = foot_l
        foot_l_bone.tail = foot_l + foot_l_dir

    if "thigh.R" in eb:
        eb["thigh.R"].head = hip_r
        eb["thigh.R"].tail = knee_r
    if "shin.R" in eb:
        eb["shin.R"].head = knee_r
        eb["shin.R"].tail = foot_r
    if "foot.R" in eb:
        foot_r_bone = eb["foot.R"]
        foot_r_dir = (foot_r_bone.tail - foot_r_bone.head)
        foot_r_dir.x = 0.0  # Ayakların içe/dışa kıvrılmasını tamamen engelle
        if foot_r_dir.length < 1e-6:
            foot_r_dir = Vector((0.0, -0.08, 0.0))
        foot_r_bone.head = foot_r
        foot_r_bone.tail = foot_r + foot_r_dir

    print(
        f"ℹ️ Fitting düzeltmeleri: shoulder_drop={shoulder_drop:.4f}, ankle_offset={(mesh_h * 0.035):.4f}"
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    print("🦴 Kemikler yeni pozisyonlarına kilitlendi.")
    return True


def auto_rig_advanced():
    ensure_object_mode()

    target_mesh = pick_target_mesh()
    if not target_mesh:
        print("❌ Sahnede mesh bulunamadı.")
        return
    select_only(target_mesh)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    
    mesh_height, _ = get_mesh_dimensions(target_mesh)
    angle_deg = detect_pose_angle(target_mesh)
    
    selected_rig = RIG_FILE_A if angle_deg > 15.0 else RIG_FILE_T
    rig_path = os.path.join(TEMPLATE_DIR, selected_rig)
    custom_rig = append_custom_rig(rig_path, RIG_OBJECT_NAME)
    
    if not custom_rig:
        print("❌ Template rig sahneye eklenemedi.")
        return
    custom_rig.location = (0, 0, 0)
    
    bpy.context.view_layer.update()
    rig_height, _ = get_mesh_dimensions(custom_rig)
    
    if rig_height <= 1e-6:
        print("❌ Rig yüksekliği hesaplanamadı.")
        return

    # Güvenli uniform ölçek: yükseklikten hesapla ve aşırı değerleri sınırla.
    scale_factor = (mesh_height / rig_height) * 0.92
    scale_factor = max(0.20, min(scale_factor, 8.00))
    custom_rig.scale = (scale_factor, scale_factor, scale_factor)
    select_only(custom_rig)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    fit_ok = fit_bones_to_anatomy(target_mesh, custom_rig)
    if not fit_ok:
        print("⚠️ Fitting atlandı, yalnızca template ölçeklenerek devam ediliyor.")

    # Skinning
    select_only(target_mesh)
    target_mesh.select_set(True)
    custom_rig.select_set(True)
    bpy.context.view_layer.objects.active = custom_rig
    
    print("⚙️ Otomatik Ağırlıklandırma (Skinning) yapılıyor...")
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        print("🎉 Zeki Auto-Rigging Başarıyla Tamamlandı!\n")
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