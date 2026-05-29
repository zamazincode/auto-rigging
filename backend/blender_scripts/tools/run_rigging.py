import bpy
import sys
import os
import argparse

# Sisteme diğer modülleri import edebilmek için script yolunu ekleyelim
script_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Parse arguments
argv = sys.argv
if "--" not in argv:
    argv = []
else:
    argv = argv[argv.index("--") + 1:]

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True, help="Input 3D model file")
parser.add_argument("--output", required=True, help="Output FBX file path")
parser.add_argument("--type", required=True, choices=['humanoid', 'quadruped'], help="Rig type")
args, unknown = parser.parse_known_args(argv)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def import_model(filepath):
    ext = filepath.split('.')[-1].lower()
    if ext == 'obj':
        bpy.ops.wm.obj_import(filepath=filepath)
    elif ext == 'fbx':
        bpy.ops.import_scene.fbx(filepath=filepath)
    elif ext in ['glb', 'gltf']:
        bpy.ops.import_scene.gltf(filepath=filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}")

def main():
    clear_scene()
    
    # Modeli içeri aktar
    print(f"[WRAPPER] Importing {args.input}")
    import_model(args.input)
    
    # Eski iskeletleri (varsa) temizle ki çakışma olmasın
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            obj.select_set(True)
    bpy.ops.object.delete()

    
    # İlgili script modülünü yükle
    print(f"[WRAPPER] Running {args.type} auto-rig pipeline")
    if args.type == 'humanoid':
        from humanoid.rigging import auto_rig_advanced
        auto_rig_advanced()
    elif args.type == 'quadruped':
        from quadruped.rigging import auto_rig_quadruped
        auto_rig_quadruped()
    else:
        raise ValueError("Invalid rig type")
    
    # Sonucu dışarı aktar (.fbx)
    print(f"[WRAPPER] Exporting rigged model to {args.output}")
    # Sadece MESH ve ARMATURE objelerini seçip kaydet (Widget'ları atla)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in ['MESH', 'ARMATURE'] and not obj.name.startswith("WGT"):
            obj.select_set(True)
            
    bpy.ops.export_scene.fbx(
        filepath=args.output,
        use_selection=True,
        add_leaf_bones=False,
        mesh_smooth_type='FACE',
        axis_forward='-Z',
        axis_up='Y'
    )
    print("[WRAPPER] Done!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)
