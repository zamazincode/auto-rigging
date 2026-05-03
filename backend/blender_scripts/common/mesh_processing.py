"""
Mesh Ön İşleme ve Voxel Proxy
===============================
Auto-weights öncesi mesh temizleme ve ekipman yumuşatma
için voxel proxy oluşturma/silme.
"""

import bpy
from .mesh_utils import get_mesh_dimensions
from .blender_utils import select_only


def preprocess_mesh(obj):
    """
    Mesh'i auto-weights öncesi temizle.
    Çift vertexler, tutarsız normaller ve degenerate yüzeyleri düzeltir.
    """
    print("Mesh ön işleme yapılıyor...")
    select_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    print("Mesh ön işleme tamamlandı.")


def create_voxel_proxy(target_mesh, voxel_size=None):
    """
    Modelin katı, basitleştirilmiş Voxel kopyasını oluşturur.
    Ekipman detaylarını yumuşatır, açık kenarları kapatır.
    """
    mesh_h, _ = get_mesh_dimensions(target_mesh)
    if voxel_size is None:
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

    print(f"   [OK] Voxel proxy oluşturuldu (voxel_size={voxel_size:.3f}, "
          f"verts: {len(proxy.data.vertices)})")
    return proxy


def cleanup_proxy(proxy):
    """Voxel proxy objesini sahneden sil."""
    if proxy:
        bpy.data.objects.remove(proxy, do_unlink=True)
