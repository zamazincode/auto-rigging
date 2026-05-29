import bpy
import sys
import os
import math
import argparse

# Parse arguments
# Expected usage: blender --background --python take_renders.py -- --input "model.obj" --output "output_dir"
argv = sys.argv
if "--" not in argv:
    argv = []
else:
    argv = argv[argv.index("--") + 1:]

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True, help="Input 3D model file")
parser.add_argument("--output", required=True, help="Output directory for renders")
args, unknown = parser.parse_known_args(argv)

INPUT_FILE = args.input
OUTPUT_FOLDER = args.output
RESOLUTION = 256
VIEWS = 4

def clear_scene():
    """Sahnedeki her şeyi siler."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_camera_and_light():
    """Standart kamera ve ışık kurar."""
    bpy.ops.object.camera_add(location=(0, -4, 0), rotation=(math.radians(90), 0, 0))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    light = bpy.context.object
    light.data.energy = 2.0

def import_model(filepath):
    """Modeli sahneye aktarır."""
    ext = filepath.split('.')[-1].lower()
    try:
        if ext == 'obj':
            bpy.ops.wm.obj_import(filepath=filepath)
        elif ext == 'fbx':
            bpy.ops.import_scene.fbx(filepath=filepath)
        elif ext in ['glb', 'gltf']:
            bpy.ops.import_scene.gltf(filepath=filepath)
        else:
            print(f"Desteklenmeyen format: {ext}")
            return False
        return True
    except Exception as e:
        print(f"Import hatası: {e}")
        return False

def normalize_and_center_model():
    """Modeli merkeze alır ve kameraya sığdırır."""
    bpy.ops.object.select_all(action='DESELECT')
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not meshes:
        return None

    bpy.context.view_layer.objects.active = meshes[0]
    for mesh in meshes:
        mesh.select_set(True)
    bpy.ops.object.join()
    
    obj = bpy.context.view_layer.objects.active

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location = (0, 0, 0)
    bpy.context.view_layer.update()

    max_dim = max(obj.dimensions)
    if max_dim > 0:
        scale_factor = 2.2 / max_dim
        obj.scale = (scale_factor, scale_factor, scale_factor)
    
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    mat = bpy.data.materials.new(name="BaseGray")
    mat.use_nodes = False 
    mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    return obj

def render_model(root_empty):
    """4 açıdan render alır."""
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.render.resolution_x = RESOLUTION
    bpy.context.scene.render.resolution_y = RESOLUTION
    bpy.context.scene.render.film_transparent = True
    
    cam = bpy.context.scene.camera
    cam.location = (0, -4, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)

    for i in range(VIEWS):
        root_empty.rotation_euler[2] = math.radians(i * 90)
        bpy.context.view_layer.update()
        
        output_file = os.path.join(OUTPUT_FOLDER, f"render_{i}.png")
        bpy.context.scene.render.filepath = output_file
        bpy.ops.render.render(write_still=True)
        print(f"Render tamamlandı: {output_file}")

def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        
    clear_scene()
    setup_camera_and_light()
    
    is_success = import_model(INPUT_FILE)
    if not is_success:
        sys.exit(1)
        
    root_empty = normalize_and_center_model()
    
    if root_empty:
        render_model(root_empty)
    else:
        print("HATA: Mesh bulunamadı.")
        sys.exit(1)

if __name__ == "__main__":
    main()
