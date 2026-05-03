"""
Cross-Section Profil Analizi
=============================
Mesh'i dilimleyerek genişlik/yükseklik profili çıkarır.
Eksen bağımsızdır — Z (humanoid), Y (quadruped) veya X ile çalışır.
"""

from .mesh_utils import get_world_verts


def build_profile(obj, axis='Z', num_slices=80):
    """
    Mesh'i belirtilen eksen boyunca dilimle ve her dilimin
    genişlik profilini çıkar.
    
    Args:
        obj: Blender mesh objesi
        axis: Dilimleme ekseni ('X', 'Y', veya 'Z')
        num_slices: Dilim sayısı
    
    Returns:
        List[dict]: Her dilim için istatistikler
    """
    verts = get_world_verts(obj)
    if len(verts) < 50:
        return []
    
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
    
    # 1e-6 = 1m
    if total_length < 1e-6:
        return []
    
    slice_size = total_length / num_slices
    
    bins = [[] for _ in range(num_slices)]
    for v in verts:
        idx = int((get_axis(v) - axis_min) / slice_size)
        idx = min(idx, num_slices - 1)
        bins[idx].append(v)
    
    profile = []
    for i in range(num_slices):
        slice_verts = bins[i]
        pos = axis_min + (i + 0.5) * slice_size
        
        if len(slice_verts) < 2:
            profile.append({
                'index': i, 'pos': pos,
                'width_x': 0.0, 'width_y': 0.0,
                'width_z': 0.0,
                'center_x': 0.0, 'center_y': 0.0, 'center_z': 0.0,
                'count': len(slice_verts),
            })
            continue
        
        xs = [v.x for v in slice_verts]
        ys = [v.y for v in slice_verts]
        zs = [v.z for v in slice_verts]
        
        profile.append({
            'index': i, 'pos': pos,
            'width_x': max(xs) - min(xs),
            'width_y': max(ys) - min(ys),
            'width_z': max(zs) - min(zs),
            'x_min': min(xs), 'x_max': max(xs),
            'y_min': min(ys), 'y_max': max(ys),
            'z_min': min(zs), 'z_max': max(zs),
            'center_x': (max(xs) + min(xs)) / 2,
            'center_y': (max(ys) + min(ys)) / 2,
            'center_z': (max(zs) + min(zs)) / 2,
            'count': len(slice_verts),
        })
    
    return profile


def smooth_profile(values, window=5):
    """Hareketli ortalama ile profil düzleştirme."""
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
    Prominence filtresi ile küçük dalgalanmalar elenir.
    
    Returns:
        (local_minima_indices, local_maxima_indices)
    """
    if len(values) < 3:
        return [], []
    
    val_range = max(values) - min(values)
    if val_range < 1e-8:
        return [], []
    
    min_prominence = val_range * prominence_ratio
    
    local_mins = []
    local_maxs = []
    
    for i in range(1, len(values) - 1):
        if values[i] <= values[i-1] and values[i] <= values[i+1]:
            left_max = max(values[:i+1])
            right_max = max(values[i:])
            prom = min(left_max, right_max) - values[i]
            if prom >= min_prominence:
                local_mins.append(i)
        
        if values[i] >= values[i-1] and values[i] >= values[i+1]:
            left_min = min(values[:i+1])
            right_min = min(values[i:])
            prom = values[i] - max(left_min, right_min)
            if prom >= min_prominence:
                local_maxs.append(i)
    
    return local_mins, local_maxs
