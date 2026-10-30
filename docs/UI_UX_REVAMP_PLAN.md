# Dokumen Revamp UI/UX & Flow Aplikasi: plts-sizing-app
**Tim Penyusun:** Sarah (Lead UX & Product Documentation - ByME Corporate)  
**Tanggal:** 30 Oktober 2026  
**Referensi Riset Kompetitor:** OpenSolar, HelioScope, PVsyst, SurgePV  

---

## 1. Rangkuman Permasalahan Eksisting
1. **Flow & Arsitektur Halaman:** Pengguna kewalahan dengan *Single-Page Scroll* panjang, di mana parameter kunci (Tarif, PR, Suhu) tersembunyi di Sidebar.
2. **Keterbacaan Wording & Input:** Instruksi `"Isi 0 untuk Auto"` pada target sizing tidak intuitif, serta penamaan teknis yang kaku (`Voc`, `Vmp`, `Pola A/B`).
3. **Keterbatasan Kartu Metrik Finansial:** Penggunaan `st.columns(5)` untuk angka rupiah besar menyebabkan teks terpotong ellipsis (`...`).
4. **Visualisasi Keuangan & Aliran Daya:** Grafik arus kas kumulatif terlalu sederhana (hanya garis tunggal) tanpa pembeda visual antara masa negatif (sebelum BEP) dan positif.

---

## 2. Solusi & Peningkatan UI/UX Baru
1. **Penerapan Wizard-Style Tabbing / Multi-Step Navigation:** Memecah alur kerja menjadi 4 tahapan logis:
   - Tahap 1: *Setup Lokasi & Profil Beban* (Input radiasi dipindah dari sidebar ke halaman utama).
   - Tahap 2: *Spesifikasi & Kriteria Sizing* (Progressive disclosure untuk parameter lanjutan; Radio button eksplisit untuk Auto vs Manual).
   - Tahap 3: *Hasil Teknis, Stringing & Diagram 24 Jam* (Notasi string standar industri & visualisasi jendela MPPT).
   - Tahap 4: *Analisis Finansial, Cashflow & Ekspor Laporan*.
2. **Format Angka Kompak di Kartu Finansial:** Menggunakan format miliar/juta untuk KPI utama (misal: `Rp 1,45 Miliar`) dengan *tooltip* detail nilai penuh.
3. **Grafik Finansial Combo (Bar + Line):** Menampilkan arus kas tahunan (bar) bersanding dengan kas kumulatif (line) serta anotasi *Break-Even Point* (BEP) yang jelas.
