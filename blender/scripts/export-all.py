import bpy
import os

# 1. Blender dosyasının kayıtlı olduğu konumu bul
blend_dosya_yolu = bpy.data.filepath

if not blend_dosya_yolu:
    print("HATA: Lütfen önce Blender dosyanızı (Ctrl+S) bilgisayara kaydedin!")
else:
    # 2. Blend dosyasının yanına 'cleaned' adında bir klasör oluştur
    ana_klasor = os.path.dirname(blend_dosya_yolu)
    export_klasoru = os.path.join(ana_klasor, "cleaned")
    
    if not os.path.exists(export_klasoru):
        os.makedirs(export_klasoru)

    # 3. Sadece seçili MESH objelerini listeye al
    secili_modeller = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    
    # Tüm seçimleri temizle
    bpy.ops.object.select_all(action='DESELECT')

    # 4. Her bir model için export işlemi
    for obj in secili_modeller:
        # Sadece sıradaki modeli seç ve aktif yap
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        
        # Dosya adını objenin Blender'daki adından al
        dosya_adi = f"{obj.name}.fbx"
        kayit_yolu = os.path.join(export_klasoru, dosya_adi)
        
        # FBX olarak dışa aktar (Sadece seçili olanı)
        bpy.ops.export_scene.fbx(
            filepath=kayit_yolu,
            use_selection=True,          # Sadece seçili objeyi aktar
            mesh_smooth_type='FACE',     # Yüzey yumuşatmasını koru
            add_leaf_bones=False,        # Gereksiz kemik eklemelerini kapat
            bake_anim=False              # Animasyonları dahil etme
        )
        
        # İşlem bitince seçimi kaldır
        obj.select_set(False)

    # 5. İşlem bitince orijinal seçimi geri yükle
    for obj in secili_modeller:
        obj.select_set(True)

    print(f"BAŞARILI: {len(secili_modeller)} adet model '{export_klasoru}' içine aktarıldı!")