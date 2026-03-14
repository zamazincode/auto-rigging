import bpy
import os
import math
import random

# ================= AYARLAR =================
# for Quadruped
# INPUT_FOLDER = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\dataset\renders\quadruped" 
# OUTPUT_FOLDER = r"C:/Users/fatih/Desktop/Masaustu/Programming/Projects/auto-rigging/dataset/renders/quadruped"

# for Humanoid
# INPUT_FOLDER = r"C:\Users\fatih\Desktop\Masaustu\Programming\Projects\auto-rigging\dataset\renders\humanoid" 
# OUTPUT_FOLDER = r"C:/Users/fatih/Desktop/Masaustu/Programming/Projects/auto-rigging/dataset/renders/humanoid"

# for Test
INPUT_FOLDER = r"C:\Users\fatih\Desktop\model-clean\test-models" 
OUTPUT_FOLDER = r"C:/Users/fatih/Desktop/Masaustu/Programming/Projects/auto-rigging/dataset/test_renders"

RESOLUTION = 256 
VIEWS = 4 

MAX_MODELS = 300
# ===========================================

def clear_scene():
    """Sahnedeki her şeyi (Kamera, Işık, Model) siler."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_camera_and_light():
    """Standart bir kamera ve ışık sistemi kurar."""
    # Kamera Ekle
    bpy.ops.object.camera_add(location=(0, -4, 0), rotation=(math.radians(90), 0, 0))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    
    # Işık Ekle (Güneş ışığı her yeri eşit aydınlatır)
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    light = bpy.context.object
    light.data.energy = 2.0

def import_model(filepath):
    """Dosya uzantısına göre modeli sahneye aktarır. Hata olursa atlar."""
    ext = filepath.split('.')[-1].lower()
    
    try:
        if ext == 'obj':
            bpy.ops.wm.obj_import(filepath=filepath)
        elif ext == 'fbx':
            bpy.ops.import_scene.fbx(filepath=filepath)
        elif ext == 'glb' or ext == 'gltf':
            bpy.ops.import_scene.gltf(filepath=filepath)
        else:
            print(f"Desteklenmeyen format: {ext}")
            return False
        return True # İşlem başarılıysa True döndür
        
    except Exception as e:
        print(f"\n[ATLANDI] {filepath} dosyası hatalı veya uyumsuz. Sebep: {e}")
        return False # İşlem başarısızsa False döndür


def normalize_and_center_model():
    """Modeli tam merkeze alır ve kameraya tam sığacak şekilde hizalar."""
    bpy.ops.object.select_all(action='DESELECT')
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    if not meshes:
        return None

    # Tüm parçaları birleştir
    bpy.context.view_layer.objects.active = meshes[0]
    for mesh in meshes:
        mesh.select_set(True)
    bpy.ops.object.join()
    
    obj = bpy.context.view_layer.objects.active

    # Merkez noktasını objenin tam ortasına al ve 0,0,0'a (kameranın baktığı yere) taşı
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location = (0, 0, 0)
    bpy.context.view_layer.update()

    # Boyutlandırma (Kenarlardan pay kalması için 2.2'ye düşürdük)
    max_dim = max(obj.dimensions)
    if max_dim > 0:
        scale_factor = 2.2 / max_dim
        obj.scale = (scale_factor, scale_factor, scale_factor)
    
    # Tüm dönüşümleri kalıcı olarak uygula
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Görünürlük için Gri Materyal ekle (Gölgelerin belli olması için)
    mat = bpy.data.materials.new(name="BaseGray")
    mat.use_nodes = False 
    mat.diffuse_color = (0.8, 0.8, 0.8, 1.0) # Açık gri
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    return obj

def render_model(model_name, root_empty):
    """Modeli Z ekseninde döndürerek toplam 4 render alır."""
    # Render Motoru Ayarları
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.render.resolution_x = RESOLUTION
    bpy.context.scene.render.resolution_y = RESOLUTION
    bpy.context.scene.render.film_transparent = True # Arka planı transparan (PNG) yapar
    
    cam = bpy.context.scene.camera
    
    # Kamera ayarını yana al (Standart profil açısı)
    cam.location = (0, -4, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)

    
    for i in range(VIEWS):
        # Modeli döndür
        root_empty.rotation_euler[2] = math.radians(i * 90)
        bpy.context.view_layer.update()
        
        # Çıktı yolunu ayarla ve render al
        output_file = os.path.join(OUTPUT_FOLDER, f"{model_name}__{i}.png")
        bpy.context.scene.render.filepath = output_file
        bpy.ops.render.render(write_still=True)
        print(f"Render tamamlandı (X): {output_file}")


def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # Klasördeki tüm dosyaları bul
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(('.obj', '.fbx', '.glb', '.gltf'))]
    
    random.shuffle(files)
    if(len(files) > MAX_MODELS):
        files = files[:MAX_MODELS]
    MODEL_COUNT = len(files)
    
    print(f"Toplam {MODEL_COUNT} adet model seçildi ve işleniyor...")

    for count, file in enumerate(files, 1):
        model_name = os.path.splitext(file)[0]
        filepath = os.path.join(INPUT_FOLDER, file)
        
        print(f"\n--- [{count}/{MODEL_COUNT}] İşleniyor: {file} ---")
        
        clear_scene()
        setup_camera_and_light()
        
        # Eğer import işlemi başarısız olursa (False dönerse), alttaki işlemleri yapma, sıradakine geç (continue)
        is_success = import_model(filepath)
        if not is_success:
            continue
        
        root_empty = normalize_and_center_model()
        
        if root_empty:
            render_model(model_name, root_empty)
        else:
            print(f"HATA: {file} içinde 3D Mesh bulunamadı.")

if __name__ == "__main__":
    main()