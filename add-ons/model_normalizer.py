bl_info = {
    "name": "Model Normalizer",
    "author": "Fatih", 
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar (N) > Normalizer",
    "description": "Seçili modellerin oranını bozmadan boyutlarını eşitler ve merkeze alır.",
    "category": "Object",
}

import bpy

class OBJECT_OT_normalize_models(bpy.types.Operator):
    bl_idname = "object.normalize_models"
    bl_label = "Modelleri Normalize Et"
    bl_description = "Seçili modelleri hedef boyuta orantılı ölçekler ve merkeze alır"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        hedef_boyut = context.scene.hedef_model_boyutu
        # Sadece mesh objelerini seç
        secili_objeler = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not secili_objeler:
            self.report({'WARNING'}, "Lütfen işlem yapmak için en az bir Mesh obje seçin!")
            return {'CANCELLED'}

        for obj in secili_objeler:
            context.view_layer.objects.active = obj
            
            # Boyut orantılama
            en_buyuk_kenar = max(obj.dimensions)
            if en_buyuk_kenar > 0:
                oran = hedef_boyut / en_buyuk_kenar
                obj.scale = (obj.scale[0] * oran, obj.scale[1] * oran, obj.scale[2] * oran)

            # Origin'i geometriye al ve dünyada sıfıra taşı
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
            obj.location = (0, 0, 0)

        # Transformasyonları (Scale) kalıcı olarak uygula
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Kullanıcıya altta bilgi mesajı göster
        self.report({'INFO'}, f"{len(secili_objeler)} adet model {hedef_boyut} birim boyutuna eşitlendi.")
        
        return {'FINISHED'}

class VIEW3D_PT_model_normalizer(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Normalizer'
    bl_label = "Model Hizalama ve Ölçekleme"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Hedef boyut parametresi
        layout.prop(scene, "hedef_model_boyutu", text="Hedef Boyut")
        layout.separator()
        
        # Çalıştırma butonu
        layout.operator("object.normalize_models", text="Boyutlandır ve Sıfırla", icon='VIEW_ZOOM')

classes = (
    OBJECT_OT_normalize_models,
    VIEW3D_PT_model_normalizer,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Arayüzden değiştirilebilir hedef boyut değişkeni oluşturma
    bpy.types.Scene.hedef_model_boyutu = bpy.props.FloatProperty(
        name="Hedef Boyut",
        description="Modellerin en uzun kenarının ulaşacağı standart boyut",
        default=2.0,
        min=0.01
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.hedef_model_boyutu

if __name__ == "__main__":
    register()