# Panduan uji dan unggah ParcelForge 26.1.0

## A. Uji lokal di QGIS

1. Tutup dan buka ulang QGIS agar kode plugin lama tidak tertahan di memori.
2. Buka **Plugins > Manage and Install Plugins > Install from ZIP**.
3. Pilih ZIP final. Jangan ekstrak ZIP untuk langkah ini.
4. Aktifkan **ParcelForge**, lalu buka dari **Vector > ParcelForge**.
5. Jalankan sampel `sample_data/parcels.dxf`:
   - Boundary: `BOUNDARY`
   - DXF CRS: CRS projected apa pun untuk sampel sintetis ini saja
   - Output field: `OWNER`
   - Source text layer: `OWNER`
   - Output: nama GeoPackage baru
6. Pastikan hasilnya dua polygon: `OWNER_A` dan `OWNER_B`.
7. Jalankan ulang ke nama output yang sama. Plugin wajib menolak dan tidak
   menimpa hasil pertama.
8. Pindahkan satu label sampel tepat ke batas polygon, lalu uji salinan DXF.
   Proses wajib berhenti dengan pesan label ambigu.
9. Tambahkan label di luar polygon. Proses boleh selesai, tetapi ringkasan wajib
   menampilkan jumlah label di luar polygon.
10. Uji tombol **Cancel**, GeoPackage, Shapefile, 1 mapping, dan 10 mapping.

Untuk data produksi, CRS harus sesuai koordinat gambar sebenarnya. Pilihan CRS
di ParcelForge hanya memberi definisi CRS; koordinat DXF tidak direproyeksi.

## B. Susunan GitHub

Repository publik harus berada di:
<https://github.com/purwantodwigeo10/ParcelForge>

Di halaman utama repository, file berikut harus langsung terlihat pada root:

- `metadata.txt`
- `__init__.py`
- `parcelforge_plugin.py`
- `README.md`
- `LICENSE`
- kode dan folder `sample_data`

Jangan mengunggah ZIP sebagai satu-satunya isi repository dan jangan membuat
susunan `ParcelForge/ParcelForge/metadata.txt`. Jika memakai tombol GitHub
**Add file > Upload files**, ekstrak ZIP lebih dahulu lalu unggah **isi folder
ParcelForge**, bukan folder pembungkusnya.

Pesan commit yang disarankan:

`Finalize ParcelForge 26.1.0 for QGIS publication`

Setelah commit, buka dan pastikan kedua URL ini tidak 404:

- <https://github.com/purwantodwigeo10/ParcelForge>
- <https://github.com/purwantodwigeo10/ParcelForge/issues>

## C. Unggah ke QGIS Plugins

1. Masuk ke <https://plugins.qgis.org/> dengan OSGeo ID.
2. Jika `26.1.0` lama masih ada dan belum disetujui, buka versi tersebut lalu
   **Manage**. Hapus hanya versi yang salah bila situs tidak menyediakan
   penggantian file; jangan menghapus seluruh entri plugin.
3. Pilih **Upload a plugin**, lalu unggah ZIP final yang memiliki satu folder
   teratas bernama `ParcelForge`.
4. Isi changelog dengan ringkasan dari `CHANGELOG.md` bila kolom tidak terisi
   otomatis.
5. Pastikan **Security Scan** dan **Qt6 Check** hijau.
6. Buka tab **Details** dan periksa:
   - Version: `26.1.0`
   - Minimum QGIS: `3.22`
   - Maximum QGIS: `3.99`
   - Experimental: `no`
   - Repository, tracker, homepage, dan license dapat dibuka
7. Status **Approved: no** setelah upload berarti masih menunggu review manual;
   itu bukan kegagalan jika pemeriksaan otomatis sudah hijau.

Jangan menaikkan `qgisMaximumVersion` ke `4.99` hanya untuk memperoleh tanda
QGIS 4 Ready. Paket ini sengaja belum mengklaim kompatibilitas QGIS 4 penuh.
