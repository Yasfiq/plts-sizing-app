# Skenario Pengujian (Test Cases) Sizing PLTS

Dokumen ini memuat panduan parameter input untuk pengujian 3 topologi utama: **On-Grid**, **Off-Grid**, dan **Hybrid** menggunakan aplikasi `plts-sizing-app`.

---

## 1. Skenario On-Grid (Komersial / Industri)
* **Tujuan:** Penghematan tagihan listrik PLN (Self-Consumption & Ekspor surplus ke grid).
* **Parameter Input Tab 1 (Topologi & Beban):**
  - Topologi: `On-Grid`
  - Sumber Radiasi: `Upload CSV/Excel` (Gunakan `sample_data/sample_solar_profile.csv`)
  - Profil Beban: `Upload Berkas CSV / Excel` (Gunakan `sample_data/sample_load_profile.csv`)
* **Parameter Input Tab 2 (Komponen & Sizing):**
  - Modul PV: `Jinko Tiger Neo N-Type 580Wp` (Terkunci)
  - Inverter: `Commercial Inverter 100kW On-Grid` (Terkunci)
  - Metode Sizing: `Otomatis (Berdasarkan Target Self-Consumption)` dengan target `60%`
  - Batasan Luas Lahan: `0` (Tanpa Batas -> warning "Luas Lahan Tanpa Batas" muncul)
  - Biaya BoS & Instalasi: `Rp 250,000,000`
  - Biaya OPEX Tahunan: `Rp 20,000,000`
  - Tarif PLN: `Rp 1,444.70 / kWh`
* **Hasil Verifikasi yang Diharapkan:**
  - Kapasitas PV otomatis terpilih proporsional terhadap beban (misal ~1,200 - 1,500 kWp).
  - Grafik Aliran Daya Harian menampilkan Kurva Beban, Produksi PV, Impor Grid, dan Ekspor Grid dengan garis smooth.
  - Analisis Finansial: Payback Period wajar (3 - 6 tahun), NPV positif, LCOE sekitar Rp 400 - Rp 600 / kWh (jauh di bawah tarif PLN).

---

## 2. Skenario Off-Grid (Sistem Mandiri dengan Baterai)
* **Tujuan:** Suplai listrik 100% mandiri tanpa koneksi grid PLN (mengandalkan PV dan Bank Baterai).
* **Parameter Input Tab 1 (Topologi & Beban):**
  - Topologi: `Off-Grid`
  - Sumber Radiasi: `API Renewables.ninja` (atau Input Manual / Upload)
  - Profil Beban: `Tabel Blok Waktu Operasional` (Isi total beban harian moderat, misal 500 kWh/hari).
* **Parameter Input Tab 2 (Komponen & Sizing):**
  - Modul PV: `Standard Mono-PERC 550Wp`
  - Inverter: `String Inverter 50kW On-Grid` (atau Kustom)
  - Bank Baterai: `LiFePO4 48V 100Ah Rack`
    - Hari Otonomi: `1.5 Hari`
    - DoD Maks: `80%`
    - Tegangan Sistem: `48V`
    - Harga Baterai: `Rp 3,500,000 / kWh`
  - Metode Sizing: `Manual (Input kWp Langsung)` -> 300 kWp
  - Biaya BoS & Instalasi: `Rp 150,000,000`
  - Biaya OPEX Tahunan: `Rp 15,000,000`
* **Hasil Verifikasi yang Diharapkan:**
  - Bank Baterai terkalkulasi kapasitas totalnya (kWh) beserta jumlah unit baterai dan inverter.
  - Kurva State of Charge (SOC) Baterai (%) tampil di Tab 3 (berfluktuasi antara min DoD hingga 100%).
  - Impor Grid bernilai 0 kW pada kurva aliran daya.

---

## 3. Skenario Hybrid (Grid + Cadangan Baterai)
* **Tujuan:** Keandalan tinggi (backup saat pemadaman grid) dan optimasi tagihan harian.
* **Parameter Input Tab 1 (Topologi & Beban):**
  - Topologi: `Hybrid`
  - Sumber Radiasi & Beban: Gunakan file sample CSV.
* **Parameter Input Tab 2 (Komponen & Sizing):**
  - Modul PV & Inverter: Sesuai preset pilihan.
  - Bank Baterai: `LiFePO4 48V 100Ah Rack` (Hari Otonomi: `1.0 Hari`, DoD: `85%`).
  - Metode Sizing: `Otomatis` (Target Self-Consumption `80%`).
  - Biaya BoS & Instalasi: `Rp 300,000,000`
  - Biaya OPEX Tahunan: `Rp 25,000,000`
* **Hasil Verifikasi yang Diharapkan:**
  - Kombinasi suplai dari PV, Baterai, dan Grid bekerja optimal.
  - Surplus siang hari mengisi baterai terlebih dahulu, selebihnya diekspor ke grid.
  - Laporan Excel lengkap mencakup ringkasan finansial, teknis, dan cashflow 25 tahun.
