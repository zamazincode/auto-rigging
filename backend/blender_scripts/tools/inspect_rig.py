"""Quadruped rig kemik pozisyonlarını detaylı listele."""
import bpy, os

TEMPLATE_DIR = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\backend\templates"
rig_path = os.path.join(TEMPLATE_DIR, "quadruped_rig.blend")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

with bpy.data.libraries.load(rig_path) as (data_from, data_to):
    data_to.objects = [name for name in data_from.objects]

rig = None
for obj in data_to.objects:
    if obj is not None:
        bpy.context.collection.objects.link(obj)
        if obj.type == 'ARMATURE':
            rig = obj

if rig:
    w = rig.matrix_world
    print("\n### QUADRUPED BONE MAP ###")
    
    def print_tree(bone, depth=0):
        h = w @ bone.head_local
        t = w @ bone.tail_local
        pad = "  " * depth
        children = ", ".join(c.name for c in bone.children)
        print(f"{pad}{bone.name}: head=({h.x:.3f},{h.y:.3f},{h.z:.3f}) tail=({t.x:.3f},{t.y:.3f},{t.z:.3f}) children=[{children}]")
        for c in bone.children:
            print_tree(c, depth+1)
    
    roots = [b for b in rig.data.bones if b.parent is None]
    for r in roots:
        print_tree(r)
