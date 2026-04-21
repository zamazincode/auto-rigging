"""
Cross-Section Anatomical Analyzer
==================================
Mesh'i dilimleyerek genişlik/yükseklik profilini çıkarır ve
anatomik noktaları (landmark) otomatik olarak tespit eder.

Hem insansı (humanoid) hem dört bacaklı (quadruped) modellerde
kullanılacak ortak analiz modülüdür.

YÖNTEM (v2 — Hibrit):
    Cross-section profili + anatomik oranlar birlikte kullanılır.
    Boyun tespiti cross-section'dan (en güvenilir nokta),
    omuz tespiti boyundan anatomik oran ile (%7 aşağı),
    bel/kalça cross-section doğrulamasıyla.
"""

import bpy
from mathutils import Vector
import math


# =============================================================================
# YARDIMCI FONKSİYONLAR (Shared Utilities)
# =============================================================================

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
    """
    return a + (b - a) * t


def get_world_verts(obj):
    """
    Mesh'in tüm vertex'lerini dünya koordinatlarına çevir.
    
    Argüman:
    - obj: Blender mesh objesi
    
    Döndürülen değer:
    - List[Vector]: Dünya uzayındaki tüm vertex pozisyonları
    """
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


# =============================================================================
# CROSS-SECTION PROFİL ANALİZİ
# =============================================================================

def build_profile(obj, axis='Z', num_slices=80):
    """
    Mesh'i belirtilen eksen boyunca dilimle ve her dilimin
    genişlik/yükseklik profilini çıkar.
    
    Args:
        obj: Blender mesh objesi
        axis: Dilimleme ekseni ('X', 'Y', veya 'Z')
        num_slices: Dilim sayısı (fazla = daha hassas ama daha yavaş)
    
    Returns:
        List[dict]: Her dilim için istatistikler. Boş dilimler dahil.
    
    Her dilim dict'i şunları içerir:
        - index: Dilim indeksi (0 = en alt/sol/arka)
        - pos: Dilimin merkez Z (veya X/Y) pozisyonu
        - width_x: X eksenindeki genişlik
        - width_y: Y eksenindeki derinlik
        - center_x, center_y: Dilimdeki vertexlerin merkezi
        - z_min, z_max: Z sınırları
        - count: Dilimdeki vertex sayısı
    """
    verts = get_world_verts(obj)
    if len(verts) < 50:
        return []
    
    # Eksen erişim fonksiyonları
    axis_map = {
        'X': lambda v: v.x,
        'Y': lambda v: v.y,
        'Z': lambda v: v.z,
    }
    get_axis = axis_map[axis]
    
    axis_vals = [get_axis(v) for v in verts]
    axis_min = min(axis_vals)
    axis_max = max(axis_vals)
    total_length = axis_max - axis_min
    
    if total_length < 1e-6:
        return []
    
    slice_size = total_length / num_slices
    
    # Vertex'leri tek geçişte bin'lere (dilimlere) dağıt — O(N) karmaşıklık
    # (Her dilim için tüm vertexleri taramak O(N*num_slices) olurdu)
    bins = [[] for _ in range(num_slices)]
    for v in verts:
        idx = int((get_axis(v) - axis_min) / slice_size)
        idx = min(idx, num_slices - 1)  # Tam sınırda olan vertex'ler için güvenlik
        bins[idx].append(v)
    
    profile = []
    for i in range(num_slices):
        slice_verts = bins[i]
        pos = axis_min + (i + 0.5) * slice_size  # Dilimin merkez pozisyonu
        
        if len(slice_verts) < 2:
            profile.append({
                'index': i,
                'pos': pos,
                'width_x': 0.0,
                'width_y': 0.0,
                'center_x': 0.0,
                'center_y': 0.0,
                'z_min': 0.0,
                'z_max': 0.0,
                'count': len(slice_verts),
            })
            continue
        
        xs = [v.x for v in slice_verts]
        ys = [v.y for v in slice_verts]
        zs = [v.z for v in slice_verts]
        
        profile.append({
            'index': i,
            'pos': pos,
            'width_x': max(xs) - min(xs),
            'width_y': max(ys) - min(ys),
            'x_min': min(xs),
            'x_max': max(xs),
            'y_min': min(ys),
            'y_max': max(ys),
            'z_min': min(zs),
            'z_max': max(zs),
            'center_x': (max(xs) + min(xs)) / 2,
            'center_y': (max(ys) + min(ys)) / 2,
            'count': len(slice_verts),
        })
    
    return profile


def smooth_profile(values, window=5):
    """
    Basit hareketli ortalama (moving average) ile gürültü azaltma.
    
    Küçük mesh bozukluklarından kaynaklanan piksel düzeyindeki
    dalgalanmaları filtreleyerek daha net lokal min/max tespiti yapar.
    
    Args:
        values: Sayısal değerler listesi
        window: Pencere boyutu (varsayılan 5)
    
    Returns:
        Düzleştirilmiş değerler listesi (aynı uzunlukta)
    """
    if len(values) < window:
        return values[:]
    
    half = window // 2
    smoothed = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        smoothed.append(sum(values[lo:hi]) / (hi - lo))
    return smoothed


def find_local_extrema(values, prominence_ratio=0.08):
    """
    Profilden anlamlı lokal minimum ve maksimumları bul.
    
    Çok küçük dalgalanmaları görmezden gelmek için "prominence" (önem)
    filtresi uygular. Sadece toplam değer aralığının belirli bir
    yüzdesinden daha belirgin olan extrema'lar döndürülür.
    
    Args:
        values: Sayısal değerler listesi
        prominence_ratio: Minimum önem eşiği (toplam range'in yüzdesi)
                         Varsayılan %8 — çok küçük yapılırsa gürültü geçer,
                         çok büyük yapılırsa gerçek noktalar kaçırılır.
    
    Returns:
        (local_minima_indices, local_maxima_indices): İki liste
    """
    if len(values) < 3:
        return [], []
    
    val_range = max(values) - min(values)
    if val_range < 1e-8:
        return [], []
    
    min_prominence = val_range * prominence_ratio
    
    # === Tüm lokal min/max adaylarını bul ===
    raw_mins = []
    raw_maxs = []
    
    for i in range(1, len(values) - 1):
        if values[i] <= values[i-1] and values[i] <= values[i+1]:
            raw_mins.append(i)
        if values[i] >= values[i-1] and values[i] >= values[i+1]:
            raw_maxs.append(i)
    
    # === Prominence (önem) filtresi ===
    # Bir tepe ne kadar belirgin? Sol ve sağdaki en derin vadiden ne kadar yüksek?
    def prominence(idx, is_max):
        val = values[idx]
        if is_max:
            left_min = min(values[0:idx+1])
            right_min = min(values[idx:len(values)])
            return val - max(left_min, right_min)
        else:
            left_max = max(values[0:idx+1])
            right_max = max(values[idx:len(values)])
            return min(left_max, right_max) - val
    
    filtered_mins = [i for i in raw_mins if prominence(i, False) >= min_prominence]
    filtered_maxs = [i for i in raw_maxs if prominence(i, True) >= min_prominence]
    
    return filtered_mins, filtered_maxs


# =============================================================================
# İNSANSI (HUMANOID) ANATOMİK TESPİT
# =============================================================================

def detect_humanoid_pose(obj):
    """
    Cross-section analizi ile T-Pose / A-Pose ayrımını yap.
    
    ESKİ YÖNTEM: En sağdaki vertex'i "el" varsayıp açı hesaplıyordu.
    Bu yöntem silah, pelerin, kanat gibi aksesuarlarda çöküyordu.
    
    YENİ YÖNTEM: Omuz seviyesindeki genişliği bel seviyesiyle karşılaştırır.
    - T-Pose: Kollar yatay → omuz genişliği belin 2.5x+ katı
    - A-Pose: Kollar çapraz → omuz genişliği belin 1.5x-2.5x katı
    
    Returns:
        'T_POSE' veya 'A_POSE'
    """
    profile = build_profile(obj, axis='Z', num_slices=60)
    if len(profile) < 10:
        return 'A_POSE'  # Güvenli varsayılan
    
    widths = [s['width_x'] for s in profile]
    smoothed = smooth_profile(widths, window=5)
    
    n = len(smoothed)
    
    # Üst %60-%85 bölgesindeki max genişlik (omuz-kol bölgesi)
    upper_start = int(n * 0.60)
    upper_end = int(n * 0.85)
    upper_widths = smoothed[upper_start:upper_end]
    
    # Orta %40-%55 bölgesindeki genişlik (bel bölgesi — kollar burada yoktur)
    mid_start = int(n * 0.40)
    mid_end = int(n * 0.55)
    mid_widths = smoothed[mid_start:mid_end]
    
    if not upper_widths or not mid_widths:
        return 'A_POSE'
    
    shoulder_width = max(upper_widths)
    waist_width = sum(mid_widths) / len(mid_widths)
    
    if waist_width < 1e-6:
        return 'A_POSE'
    
    ratio = shoulder_width / waist_width
    
    print(f"📐 Pose tespiti: omuz/bel oranı = {ratio:.2f}")
    
    if ratio > 2.5:
        print("   → T-Pose tespit edildi (kollar yatay)")
        return 'T_POSE'
    else:
        print("   → A-Pose tespit edildi (kollar çapraz)")
        return 'A_POSE'


def _detect_crotch_z(profile, hip_z, ground_z):
    """
    Kasık (crotch) seviyesini tespit et — bacakların gövdeden ayrıldığı nokta.
    
    Hip (kalça) seviyesinden aşağıya doğru genişliğin dramatik
    olarak düştüğü Z seviyesini bulur. Genişliğin düşmesi,
    tek gövde silüetinin iki ayrı bacak silüetine dönüştüğü anlamına gelir.
    
    Args:
        profile: build_profile() çıktısı
        hip_z: Kalça Z seviyesi (cross-section'dan bulunmuş)
        ground_z: Mesh'in en alt Z koordinatı
    
    Returns:
        float: Kasık Z seviyesi
    """
    # Hip'ten aşağıdaki dilimleri al
    below_hip = [s for s in profile if ground_z <= s['pos'] <= hip_z and s['count'] > 0]
    if len(below_hip) < 3:
        # Yeterli dilim yoksa, hip-zemin aralığının %85'ini kullan
        return hip_z - (hip_z - ground_z) * 0.15
    
    # Yukarıdan aşağiya sırala
    below_hip.sort(key=lambda s: s['pos'], reverse=True)
    
    # Hip genişliğini referans al
    hip_width = below_hip[0]['width_x'] if below_hip else 1.0
    
    for s in below_hip:
        # Genişlik hip'in %65'inin altına düştüğünde kasık bulunmuş demektir
        # (Tek gövde → iki bacak geçişi genişliği ciddi düşürür)
        if s['width_x'] < hip_width * 0.65 and s['count'] > 0:
            return s['pos']
    
    # Bulunamazsa fallback
    return hip_z - (hip_z - ground_z) * 0.15


def _z_to_profile_idx(profile, target_z):
    """Z değerini en yakın dilim indeksine çevir."""
    return min(range(len(profile)), key=lambda i: abs(profile[i]['pos'] - target_z))


def detect_humanoid_landmarks(obj):
    """
    Cross-section profili + anatomik oran kullanarak insansı mesh'in
    anatomik noktalarını (landmark) tespit et.
    
    YAKLAŞIM (v2 — Hibrit):
    ─────────────────────────────────────────────────────────────
    1. BOYUN: Cross-section'dan — Üst %30'daki en dar nokta.
       En güvenilir landmark çünkü baş↔gövde geçişi tüm 
       modellerde belirgindir.
    
    2. OMUZ: Anatomik oran + cross-section doğrulama.
       İnsan anatomisinde omuz eklemi boyundan ~%7 aşağıdadır.
       Sadece cross-section local max'a güvenmek, A-pose 
       modellerde aksesuarları (kemer, silah) omuz olarak 
       algılatıyordu.
    
    3. BEL/KALÇA: Cross-section, minimum ayrım güvencesiyle.
    
    4. EL: Üst vücuttaki en uç X noktaları (geniş band).
    ─────────────────────────────────────────────────────────────
    
    Args:
        obj: Blender mesh objesi (insansı karakter)
    
    Returns:
        dict: Anatomik landmarklar + ek metrik bilgiler.
        None: Yetersiz veri
    """
    verts = get_world_verts(obj)
    if len(verts) < 50:
        return None
    
    # === Temel Ölçüler ===
    zs = [v.z for v in verts]
    xs = [v.x for v in verts]
    z_min, z_max = min(zs), max(zs)
    total_height = z_max - z_min
    
    if total_height < 1e-6:
        return None
    
    # Merkez X — median kullan (outlier'lara mean'dan daha dayanıklıdır)
    sorted_xs = sorted(xs)
    center_x = sorted_xs[len(sorted_xs) // 2]
    
    # === 1. Cross-Section Profili Oluştur ===
    profile = build_profile(obj, axis='Z', num_slices=80)
    if len(profile) < 20:
        return None
    
    widths = [s['width_x'] for s in profile]
    smoothed_widths = smooth_profile(widths, window=5)
    
    # === 2. Lokal Min/Max Tespiti ===
    local_mins, local_maxs = find_local_extrema(smoothed_widths, prominence_ratio=0.06)
    
    n = len(profile)
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 1: BOYUN — En güvenilir cross-section noktası
    # Baş ile gövde arasındaki en dar geçiş. Üst %30'da ara.
    # Tüm modellerde (stilize/gerçekçi) belirgin olur.
    # ═══════════════════════════════════════════════════════════
    neck_idx = None
    upper_start = int(n * 0.65)  # Sadece üst %35'te ara
    upper_mins = [m for m in local_mins if m >= upper_start]
    if upper_mins:
        # Üst bölgedeki EN DAR minimum (birden fazla varsa en darı al)
        neck_idx = min(upper_mins, key=lambda m: smoothed_widths[m])
    
    if neck_idx is None:
        neck_idx = int(n * 0.82)
        print("   ⚠️ Boyun tespiti başarısız, fallback (%82) kullanılıyor")
    
    neck_z = profile[neck_idx]['pos']
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 2: OMUZ — Anatomik oran + cross-section doğrulama
    # 
    # İnsan anatomisinde omuz eklemi (akromion) boyundan ~%4 
    # aşağıdadır. (%7 çok agresifti — omuzları göğüs seviyesine
    # düşürüyordu.)
    #
    # NEDEN SADECE LOCAL MAX ÇALIŞMIYOR:
    # A-pose modellerde kollar kademeli yayılır → belirgin omuz 
    # tepe noktası oluşmaz. Kemer/silah gibi aksesuarlar belde 
    # sahte genişlik tepe noktası yaratır → omuz yanlışlıkla 
    # bel seviyesine düşer.
    # ═══════════════════════════════════════════════════════════
    shoulder_estimate_z = neck_z - total_height * 0.025
    shoulder_estimate_idx = _z_to_profile_idx(profile, shoulder_estimate_z)
    
    # Tahmine ±%8 yakınlıkta local max var mı? Varsa onu tercih et.
    search_radius = int(n * 0.08)
    nearby_maxs = [m for m in local_maxs
                   if abs(m - shoulder_estimate_idx) <= search_radius]
    if nearby_maxs:
        # En yüksekteki max'ı tercih et (anatomik olarak omuz en üsttedir)
        shoulder_idx = max(nearby_maxs)
        print(f"   ✅ Omuz: anatomik tahmin ({shoulder_estimate_idx}) + cross-section max ({shoulder_idx})")
    else:
        shoulder_idx = shoulder_estimate_idx
        print(f"   ℹ️ Omuz: cross-section max bulunamadı, anatomik tahmin kullanılıyor ({shoulder_idx})")
    
    # Güvenlik: Omuz boyundan en az %4 aşağıda olmalı
    max_shoulder_idx = neck_idx - max(int(n * 0.04), 3)
    shoulder_idx = min(shoulder_idx, max_shoulder_idx)
    # Güvenlik: Omuz %55'ten yukarıda olmalı (bacak bölgesine düşmemeli)
    shoulder_idx = max(shoulder_idx, int(n * 0.55))
    
    shoulder_z = profile[shoulder_idx]['pos']
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 3: BEL — Omuz ile kalça arasındaki GÖVDE'nin en dar noktası
    #
    # Arama alt sınırı %43 — bunun altı kasık/bacak bölgesi.
    # ÖNCEKİ HATA: Alt sınır %35'ti → kasık bölgesinde bacaklar
    # ayrıldığında genişlik düşüyordu → yanlışlıkla "bel" olarak
    # tespit ediliyordu → tüm kemikler aşağı kayıyordu.
    # ═══════════════════════════════════════════════════════════
    waist_search_lo = int(n * 0.43)
    waist_search_hi = shoulder_idx - max(int(n * 0.06), 3)
    waist_candidates = [m for m in local_mins
                        if waist_search_lo <= m <= waist_search_hi]
    if waist_candidates:
        # En dar olanı seç (gövdenin en ince noktası = bel)
        waist_idx = min(waist_candidates, key=lambda m: smoothed_widths[m])
    else:
        waist_idx = int(n * 0.52)
        print("   ⚠️ Bel tespiti başarısız, fallback (%52) kullanılıyor")
    
    waist_z = profile[waist_idx]['pos']
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 4: KALÇA — Bel altındaki en geniş nokta
    # Arama alanı: Belden en az %3 aşağıda, %30'a kadar
    # ═══════════════════════════════════════════════════════════
    hip_search_lo = int(n * 0.30)
    hip_search_hi = waist_idx - max(int(n * 0.03), 2)
    hip_candidates = [m for m in local_maxs
                      if hip_search_lo <= m <= hip_search_hi]
    if hip_candidates:
        # En geniş olanı seç
        hip_idx = max(hip_candidates, key=lambda m: smoothed_widths[m])
    else:
        # Fallback: belden %5 aşağıda veya %42 seviyesi
        hip_idx = max(int(n * 0.42), waist_idx - max(int(n * 0.05), 3))
        print("   ⚠️ Kalça tespiti başarısız, fallback kullanılıyor")
    
    # Güvenlik: Hip belden en az %3 aşağıda olmalı
    hip_idx = min(hip_idx, waist_idx - max(int(n * 0.03), 2))
    
    hip_z = profile[hip_idx]['pos']
    
    # ═══════════════════════════════════════════════════════════
    # ADIM 5: Kasık, diz, ayak bileği
    # ═══════════════════════════════════════════════════════════
    crotch_z = _detect_crotch_z(profile, hip_z, z_min)
    ankle_z = z_min + total_height * 0.035
    # Diz: Femur (uyluk) tibiadan (baldır) uzundur → basit midpoint dizi
    # çok aşağı çeker. %55 bias + %25 total_height minimum tabanı kullan.
    knee_z_biased = ankle_z + (crotch_z - ankle_z) * 0.55
    knee_z_floor = z_min + total_height * 0.25
    knee_z = max(knee_z_biased, knee_z_floor)
    
    print(f"📊 Cross-section anatomik tespitler:")
    print(f"   Boyun Z:  {neck_z:.4f}  (dilim {neck_idx}/{n})")
    print(f"   Omuz Z:   {shoulder_z:.4f}  (dilim {shoulder_idx}/{n})")
    print(f"   Bel Z:    {waist_z:.4f}  (dilim {waist_idx}/{n})")
    print(f"   Kalça Z:  {hip_z:.4f}  (dilim {hip_idx}/{n})")
    print(f"   Kasık Z:  {crotch_z:.4f}")
    print(f"   Diz Z:    {knee_z:.4f}")
    print(f"   Ayak B. Z:{ankle_z:.4f}")
    
    # === 6. Oransal Threshold ile Sol/Sağ Vertex Tespiti ===
    
    def get_band_verts(z_center, z_range_ratio=0.06):
        """Belirli Z etrafındaki vertexleri topla (oransal band)."""
        half = total_height * z_range_ratio / 2
        return [v for v in verts if z_center - half <= v.z <= z_center + half]
    
    def split_left_right(band_verts, offset_ratio=0.01):
        """Vertex'leri sol ve sağ olarak ayır (oransal deadzone)."""
        offset = total_height * offset_ratio
        left = [v for v in band_verts if v.x > center_x + offset]
        right = [v for v in band_verts if v.x < center_x - offset]
        return left, right
    
    # --- Omuz bölgesi vertexleri ---
    shoulder_verts = get_band_verts(shoulder_z, 0.10)
    shoulder_left, shoulder_right = split_left_right(shoulder_verts, 0.01)
    
    # --- Kol/el bölgesi ---
    # ÖNCEKİ HATA: shoulder_z ile hip_z arası çok dar bir band kullanıyordu.
    # Shoulder yanlış tespit edildiğinde (bele düştüğünde) arm band da
    # yanlış bölgeyi tarıyordu.
    # YENİ: Üst vücudun %40-%92 bölgesi — her zaman elleri kapsar.
    arm_lo = z_min + total_height * 0.40
    arm_hi = z_min + total_height * 0.92
    arm_verts = [v for v in verts if arm_lo <= v.z <= arm_hi]
    arm_left = [v for v in arm_verts if v.x > center_x + total_height * 0.02]
    arm_right = [v for v in arm_verts if v.x < center_x - total_height * 0.02]
    
    # --- Kalça/pelvis vertexleri ---
    hip_verts = get_band_verts(hip_z, 0.10)
    hip_left, hip_right = split_left_right(hip_verts, 0.005)
    
    # --- Diz bölgesi vertexleri ---
    knee_verts = get_band_verts(knee_z, 0.12)
    knee_left, knee_right = split_left_right(knee_verts, 0.005)
    
    # --- Ayak bölgesi vertexleri ---
    foot_verts = get_band_verts(z_min + total_height * 0.05, 0.10)
    foot_left, foot_right = split_left_right(foot_verts, 0.005)
    
    # === 7. Güvenlik Kontrolleri ===
    if not shoulder_left or not shoulder_right:
        print("⚠️ Omuz vertexleri bulunamadı (sol/sağ)")
        return None
    if not arm_left or not arm_right:
        print("⚠️ Kol vertexleri bulunamadı (sol/sağ)")
        return None
    if not foot_left or not foot_right:
        print("⚠️ Ayak vertexleri bulunamadı (sol/sağ)")
        return None
    
    # === 8. Landmark Pozisyonlarını Hesapla ===
    
    # Omuz: Bölgedeki en uç noktalar
    shoulder_l = max(shoulder_left, key=lambda v: v.x)
    shoulder_r = min(shoulder_right, key=lambda v: v.x)
    
    # El: Üst vücuttaki en uç X noktaları
    hand_l = max(arm_left, key=lambda v: v.x)
    hand_r = min(arm_right, key=lambda v: v.x)
    
    # Pelvis merkezi
    pelvis_verts = get_band_verts(crotch_z, 0.06)
    pelvis_center = average_vec(pelvis_verts) if pelvis_verts else Vector((center_x, 0.0, crotch_z))
    
    # Kalça
    hip_l = average_vec(hip_left) if hip_left else Vector((shoulder_l.x * 0.5, pelvis_center.y, hip_z))
    hip_r = average_vec(hip_right) if hip_right else Vector((shoulder_r.x * 0.5, pelvis_center.y, hip_z))
    
    # Diz
    knee_l = average_vec(knee_left) if knee_left else lerp_vec(
        hip_l, Vector((hip_l.x, hip_l.y, ankle_z)), 0.5
    )
    knee_r = average_vec(knee_right) if knee_right else lerp_vec(
        hip_r, Vector((hip_r.x, hip_r.y, ankle_z)), 0.5
    )
    
    # Ayak
    foot_l = min(foot_left, key=lambda v: v.z)
    foot_r = min(foot_right, key=lambda v: v.z)
    
    # === 9. Dinamik Shoulder / Hip Inset Hesaplama ===
    
    waist_width = profile[waist_idx]['width_x'] if profile[waist_idx]['count'] > 2 else total_height * 0.15
    shoulder_full_width = abs(shoulder_l.x - shoulder_r.x)
    
    # Gövde omuz genişliği ≈ bel genişliğinin 1.3 katı
    torso_shoulder_width = waist_width * 1.3
    
    if shoulder_full_width > 1e-6:
        # Taban 0.55 — omuz eklemi asla gövde merkezine çok yaklaşmamalı
        # Tavan 0.90 — omuz eklemi asla mesh dışına çıkmamalı
        shoulder_inset = max(0.55, min(0.90, torso_shoulder_width / shoulder_full_width))
    else:
        shoulder_inset = 0.76
    
    # Kalça eklemi genişliği ≈ bel genişliğinin 0.75 katı
    hip_full_width = abs(hip_l.x - hip_r.x)
    target_hip_width = waist_width * 0.75
    if hip_full_width > 1e-6:
        hip_inset = max(0.30, min(0.85, target_hip_width / hip_full_width))
    else:
        hip_inset = 0.40
    
    print(f"📏 Oransal hesaplamalar:")
    print(f"   Bel genişliği:     {waist_width:.4f}")
    print(f"   Omuz tam genişlik: {shoulder_full_width:.4f}")
    print(f"   Omuz inset oranı:  {shoulder_inset:.3f}")
    print(f"   Kalça tam genişlik:{hip_full_width:.4f}")
    print(f"   Kalça inset oranı: {hip_inset:.3f}")
    
    return {
        # Anatomik noktalar (dünya koordinatları)
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
        
        # Z seviyeleri
        "neck_z": neck_z,
        "shoulder_z": shoulder_z,
        "waist_z": waist_z,
        "hip_z": hip_z,
        "crotch_z": crotch_z,
        "knee_z": knee_z,
        "ankle_z": ankle_z,
        
        # Ölçüler ve oranlar
        "total_height": total_height,
        "center_x": center_x,
        "shoulder_inset": shoulder_inset,
        "hip_inset": hip_inset,
        "waist_width": waist_width,
    }
