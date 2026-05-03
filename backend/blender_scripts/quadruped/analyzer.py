"""
Quadruped Cross-Section Analyzer
=================================
4 bacaklı hayvan modelleri için Y ekseni boyunca anatomik landmark tespiti.
"""
import bpy, os, sys, importlib
from mathutils import Vector

script_dir = os.path.normpath(r"c:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\blender_scripts")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from common.mesh_utils import get_world_verts, get_mesh_dimensions, average_vec
from common.profile_analysis import build_profile, smooth_profile, find_local_extrema


def detect_quadruped_landmarks(obj):
    """
    Y ekseni boyunca profil alarak quadruped anatomik noktalarını tespit et.
    
    Quadruped'de Y ekseni = uzunluk (kuyruktan başa).
    Profil width_x (sol-sağ genişlik) ile analiz edilir.
    
    İki genişlik maximumu: kalça bölgesi + göğüs bölgesi
    İkisi arasındaki minimum: bel
    """
    verts = get_world_verts(obj)
    if len(verts) < 50:
        return None

    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    body_length = y_max - y_min
    body_height = z_max - z_min
    body_width = x_max - x_min

    if body_length < 1e-6 or body_height < 1e-6:
        return None

    center_x = (x_min + x_max) / 2.0
    ground_z = z_min

    # Y ekseni boyunca profil (kuyruktan başa)
    profile = build_profile(obj, axis='Y', num_slices=80)
    if len(profile) < 20:
        return None

    n = len(profile)
    widths_x = [s['width_x'] for s in profile]
    heights_z = [s.get('width_z', 0) for s in profile]
    smoothed_wx = smooth_profile(widths_x, window=5)
    smoothed_hz = smooth_profile(heights_z, window=5)

    # === İKİ GENİŞLİK MAXMUMU: kalça + göğüs ===
    _, local_maxs = find_local_extrema(smoothed_wx, prominence_ratio=0.06)

    # Profili iki yarıya böl
    mid = n // 2
    # profile[0] baş tarafı (göğüs), profile[n-1] kuyruk tarafı (kalça)
    front_maxs = [m for m in local_maxs if m < mid + 5]
    rear_maxs = [m for m in local_maxs if m >= mid - 5]

    # Göğüs: ön yarının en geniş noktası
    if front_maxs:
        chest_idx = max(front_maxs, key=lambda i: smoothed_wx[i])
    else:
        chest_idx = int(n * 0.30)

    # Kalça: arka yarının en geniş noktası
    if rear_maxs:
        hip_idx = max(rear_maxs, key=lambda i: smoothed_wx[i])
    else:
        hip_idx = int(n * 0.70)

    # Sıralama güvenliği (Göğüs indeks olarak kalçadan KÜÇÜK olmalı)
    if chest_idx >= hip_idx:
        chest_idx = max(3, hip_idx - int(n * 0.25))
        
    hip_y = profile[hip_idx]['pos']
    chest_y = profile[chest_idx]['pos']

    # === BEL: kalça ile göğüs arasındaki en dar nokta ===
    if hip_idx - chest_idx > 2:
        waist_region = smoothed_wx[chest_idx:hip_idx]
        waist_local = waist_region.index(min(waist_region))
        waist_idx = chest_idx + waist_local
    else:
        waist_idx = (hip_idx + chest_idx) // 2
    waist_y = profile[waist_idx]['pos']

    # === BOYUN: göğüsten başa doğru (-Y yönü, azalan indeks) genişlik düşüşü ===
    neck_idx = chest_idx
    chest_w = smoothed_wx[chest_idx]
    for i in range(chest_idx - 1, -1, -1):
        if smoothed_wx[i] < chest_w * 0.55:
            neck_idx = i
            break
    neck_y = profile[neck_idx]['pos']

    # === BAŞ: boyundan sonraki kısım ===
    head_y = y_min  
    for i in range(neck_idx - 1, -1, -1):
        if profile[i]['count'] < 2:
            head_y = profile[min(n-1, i + 1)]['pos']
            break
    if head_y < neck_y - body_length * 0.02:
        pass # head_y is fine

    # === KUYRUK: kalçadan geriye (+Y yönü, artan indeks) ===
    tail_y = y_max

    # === BACAK POZİSYONLARI ===
    # Arka bacaklar: kalça bölgesindeki vertexler
    hip_band = [v for v in verts if abs(v.y - hip_y) < body_length * 0.08]
    hip_left = [v for v in hip_band if v.x > center_x + body_width * 0.02]
    hip_right = [v for v in hip_band if v.x < center_x - body_width * 0.02]

    # Ön bacaklar: göğüs bölgesindeki vertexler
    chest_band = [v for v in verts if abs(v.y - chest_y) < body_length * 0.08]
    chest_left = [v for v in chest_band if v.x > center_x + body_width * 0.02]
    chest_right = [v for v in chest_band if v.x < center_x - body_width * 0.02]

    # Ayak vertexleri (zemine yakın)
    foot_band_z = ground_z + body_height * 0.08
    rear_feet = [v for v in verts if v.z < foot_band_z and abs(v.y - hip_y) < body_length * 0.20]
    front_feet = [v for v in verts if v.z < foot_band_z and abs(v.y - chest_y) < body_length * 0.20]

    rf_left = [v for v in rear_feet if v.x > center_x]
    rf_right = [v for v in rear_feet if v.x < center_x]
    ff_left = [v for v in front_feet if v.x > center_x]
    ff_right = [v for v in front_feet if v.x < center_x]

    # Gövde yüksekliği (sırt seviyesi)
    spine_z_at_waist = max((v.z for v in verts if abs(v.y - waist_y) < body_length * 0.05), default=z_max)

    # Sol/sağ hip pozisyonu
    hip_l_pos = average_vec(hip_left) if hip_left else Vector((center_x + body_width * 0.15, hip_y, spine_z_at_waist * 0.85))
    hip_r_pos = average_vec(hip_right) if hip_right else Vector((center_x - body_width * 0.15, hip_y, spine_z_at_waist * 0.85))

    # Ön omuz pozisyonu
    shoulder_l_pos = average_vec(chest_left) if chest_left else Vector((center_x + body_width * 0.15, chest_y, spine_z_at_waist * 0.90))
    shoulder_r_pos = average_vec(chest_right) if chest_right else Vector((center_x - body_width * 0.15, chest_y, spine_z_at_waist * 0.90))

    # Ayak pozisyonları
    def foot_pos(vlist, fallback_x, fallback_y):
        if vlist:
            return min(vlist, key=lambda v: v.z)
        return Vector((fallback_x, fallback_y, ground_z))

    rear_foot_l = foot_pos(rf_left, center_x + body_width * 0.12, hip_y)
    rear_foot_r = foot_pos(rf_right, center_x - body_width * 0.12, hip_y)
    front_foot_l = foot_pos(ff_left, center_x + body_width * 0.12, chest_y)
    front_foot_r = foot_pos(ff_right, center_x - body_width * 0.12, chest_y)

    print(f"[RAPOR] Quadruped landmark tespitleri:")
    print(f"   Baş Y:    {head_y:.4f}")
    print(f"   Boyun Y:  {neck_y:.4f}")
    print(f"   Göğüs Y:  {chest_y:.4f} (dilim {chest_idx}/{n})")
    print(f"   Bel Y:    {waist_y:.4f} (dilim {waist_idx}/{n})")
    print(f"   Kalça Y:  {hip_y:.4f} (dilim {hip_idx}/{n})")
    print(f"   Kuyruk Y: {tail_y:.4f}")
    print(f"   Zemin Z:  {ground_z:.4f}")
    print(f"   Sırt Z:   {spine_z_at_waist:.4f}")

    return {
        "head_y": head_y, "neck_y": neck_y, "chest_y": chest_y,
        "waist_y": waist_y, "hip_y": hip_y, "tail_y": tail_y,
        "ground_z": ground_z, "spine_z": spine_z_at_waist,
        "center_x": center_x,
        "body_length": body_length, "body_height": body_height,
        "body_width": body_width,
        "shoulder_l": shoulder_l_pos, "shoulder_r": shoulder_r_pos,
        "hip_l": hip_l_pos, "hip_r": hip_r_pos,
        "front_foot_l": front_foot_l, "front_foot_r": front_foot_r,
        "rear_foot_l": rear_foot_l, "rear_foot_r": rear_foot_r,
    }
