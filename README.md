# Auto Rigging System

## 1. Projenin Amacı

Bu projenin temel amacı, kullanıcı tarafından yüklenen statik 3D (mesh) modelleri analiz ederek, modelin türüne uygun iskelet (rig) sistemini otomatik olarak seçen, boyutlandıran ve deri giydirme (skinning) işlemini tamamlayarak animasyona hazır hale getiren web tabanlı bir sistem geliştirmektir.

## 2. Sistem Mimarisi ve Kullanılacak Teknolojiler

Görüntü İşleme & Sınıflandırma (ML): TensorFlow / Keras (ResNet50 Mimarisi - Transfer Learning).

3D Motoru & Otomasyon: Blender Python API (bpy) - Sunucuda arayüzsüz (headless) çalışacak.

Backend & API: Python tabanlı FastAPI (Asenkron dosya yükleme ve Blender scriptlerini tetikleme).

Frontend: React (Kullanıcı arayüzü, 3D model yükleme ve Three.js/Fiber ile ön izleme).

## 3. Çalışma Akışı (Pipeline)

Veri Girişi ve Ön İşleme (Render):

Kullanıcı .obj veya .fbx formatında bir model yükler.

Blender scripti devreye girerek modeli merkeze alır ve 4 ila 6 farklı açıdan (ön, yan, üst vb.) 2D siluet/render fotoğraflarını çeker.

Yapay Zeka ile Sınıflandırma (Classification):

Çekilen bu 2D görüntüler, eğitilmiş Multi-view ResNet50 modeline beslenir.

Model, nesnenin kategorisini yüksek bir güven skoruyla belirler (Örn: Sınıf: İnsansı, Sınıf: Dört Ayaklı).

Şablon Eşleştirme ve Ölçeklendirme (Template Matching & Scaling):

Belirlenen sınıfa ait önceden hazırlanmış, mükemmel ağırlıklandırılmış iskelet şablonu (Örn: humanoid_template.blend) sahneye çağrılır.

Yüklenen 3D modelin en, boy ve yükseklik sınırları (Bounding Box) hesaplanır. Şablon iskelet, bu sınırlara tam oturacak şekilde X, Y, Z eksenlerinde matematiksel olarak ölçeklendirilir.

Deri Giydirme ve Çıktı (Skinning & Export):

Ölçeklendirilen iskelet, Auto-Weights (Otomatik Ağırlıklandırma) algoritması ile 3D modele bağlanır.

Riglenmiş sonuç, web arayüzünde gösterilmek veya indirilmek üzere .glb veya .fbx formatında dışa aktarılır.
