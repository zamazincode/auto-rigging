# Bu klasördeki dosyalar dataset hazırlık aşaması için kullanıldı.

**model_normalizer.py**: Seçilen modele uygulandığında onu sahnenin ortasına ve belirlenen yüksekliğe göre hizalama işlemi yapar. (Add-on olarak kullanılır)

**export_all.py**: Sahnedeki tüm modelleri ayrı ayrı olarak fbx export almayı sağlar.

**render_dataset.py**: Klasörlerdeki tüm modelleri tek tek sahneye alıp 4 farklı yönden render alıp png formatında kaydeder.
Çalıştırmak için:
`"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" --background --python /blender/scripts/render_dataset.py`
