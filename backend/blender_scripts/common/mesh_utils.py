"""
Mesh Geometri Yardımcıları
==========================
Dünya koordinatında bbox, boyut, vertex, interpolasyon hesaplamaları.
Hem humanoid hem quadruped tarafından kullanılır.
"""

from mathutils import Vector


def get_world_bbox(obj):
    """Objenin dünya uzayındaki bounding box min/max köşelerini hesapla."""
    world_pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [p.x for p in world_pts]
    ys = [p.y for p in world_pts]
    zs = [p.z for p in world_pts]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def get_mesh_dimensions(obj):
    """Objenin yüksekliğini (Z) ve 3D boyutlarını döndür."""
    min_v, max_v = get_world_bbox(obj)
    dims = max_v - min_v
    return dims.z, dims


def average_vec(points):
    """Vector listesinin centroid'ini hesapla."""
    if not points:
        return None
    total = Vector((0.0, 0.0, 0.0))
    for p in points:
        total += p
    return total / len(points)


def lerp_vec(a, b, t):
    """A ile B arasında doğrusal interpolasyon (t=0→A, t=1→B)."""
    return a + (b - a) * t


def get_world_verts(obj):
    """Mesh'in tüm vertex'lerini dünya koordinatlarına çevir."""
    return [obj.matrix_world @ v.co for v in obj.data.vertices]
