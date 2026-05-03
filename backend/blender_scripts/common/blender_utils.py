"""
Blender Sahne/Obje Yardımcıları
================================
Mesh seçimi, obje yönetimi, rig yükleme gibi
Blender API ile etkileşen ortak fonksiyonlar.
"""

import bpy
import os
from .mesh_utils import get_mesh_dimensions


def pick_target_mesh():
    """
    Sahnedeki riglenmesi gereken mesh'i seç.
    Öncelik: aktif obje > en büyük hacimli mesh.
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
    """Blender'ın Object Mode olmasını sağla."""
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def select_only(obj):
    """Tüm seçimleri kaldır ve yalnızca verilen objeyi seç."""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def append_custom_rig(filepath, obj_name="Armature"):
    """
    Harici .blend dosyasından armature objesini sahneye ekle.
    Bazı template'lerde obje ismi farklı olabilir — tüm
    yeni eklenen objeleri kontrol eder.
    """
    if not os.path.exists(filepath):
        print(f"   [HATA] Template dosyası bulunamadı: {filepath}")
        return None

    bpy.ops.object.select_all(action='DESELECT')
    existing_objects = set(obj.name for obj in bpy.context.scene.objects)

    # Önce belirtilen isimle dene
    inner_path = "Object"
    try:
        bpy.ops.wm.append(
            filepath=os.path.join(filepath, inner_path, obj_name),
            directory=os.path.join(filepath, inner_path),
            filename=obj_name
        )
    except Exception:
        pass

    new_objects = [obj for obj in bpy.context.scene.objects
                   if obj.name not in existing_objects]

    # Bulunamazsa, dosyadaki tüm objeleri yükle ve armature'ı seç
    if not new_objects:
        try:
            with bpy.data.libraries.load(filepath) as (data_from, data_to):
                data_to.objects = list(data_from.objects)
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
            new_objects = [obj for obj in bpy.context.scene.objects
                          if obj.name not in existing_objects]
        except Exception as e:
            print(f"   [HATA] Template yükleme hatası: {e}")
            return None

    # Armature objesini bul
    armatures = [o for o in new_objects if o.type == 'ARMATURE']
    if armatures:
        rig = armatures[0]
        select_only(rig)
        return rig

    if new_objects:
        rig = new_objects[0]
        select_only(rig)
        return rig

    return None
