# PANDUAN LENGKAP ALUR KERJA KODE (WORKFLOW CODE)
## Aplikasi Perancangan PLTS Multi-Topologi (On-Grid, Off-Grid, Hybrid)

Dokumen ini menjelaskan bagaimana seluruh baris kode di aplikasi ini bekerja, dari saat kamu membuka aplikasi, memasukkan data, sistem melakukan kalkulasi listrik, hingga menghasilkan grafik dan berkas Excel.

Bahasa yang digunakan dirancang sesederhana mungkin agar mudah dipahami siapa saja yang memahami konsep dasar Python (seperti variabel, fungsi `def`, tipe data `list` dan `dict`, serta perulangan `for`).

---

## 1. Gambaran Besar: Pemisahan Tugas (Frontend vs Backend)

Aplikasi ini dibangun menggunakan arsitektur **Modular**:

```
[ FRONTEND / TAMPILAN ]                   [ BACKEND / MESIN KALKULASI ]
       app.py              ===========>              core/
  (Streamlit & UI)                          (Fungsi Matematika Murni)
- Menerima klik user                      - Tidak ada tombol/grafik
- Mengambil input angka                   - Hanya Python murni: terima
- Menampilkan grafik Plotly                 angka, hitung rumus, kembalikan
- Menampilkan tombol unduh                  hasil berupa dictionary.
```

**Kenapa dipisah?**
Jika rumus kalkulasi dicampur aduk dengan kode tombol antarmuka, aplikasi akan sangat sulit diperbaiki saat ada galat. Dengan dipisah:
- Rumus di folder `core/` bisa diuji secara otomatis memakai skrip uji di folder `tests/` tanpa perlu membuka browser.
- File `app.py` tugasnya hanya menerima input dari layar, menyuapkannya ke fungsi di `core/`, lalu menampilkan jawabannya.

---

## 2. Peta File dan Fungsinya

```
plts-sizing-app/
│
├── app.py                  <- Pusat antarmuka visual (Streamlit). Menghubungkan semua fungsi.
├── presets.json            <- "Kamus" spesifikasi modul PV, inverter, dan baterai yang ada di pasaran.
├── requirements.txt        <- Daftar pustaka luar yang dibutuhkan (streamlit, pandas, plotly, dll).
│
├── core/                   <- Folder "Mesin Otak" (Kalkulasi Matematis murni)
│   ├── data_loader.py      <- Membaca & mengubah data beban (CSV/Excel/Tabel) jadi list 24 jam.
│   ├── ninja_client.py     <- Mengambil data radiasi matahari dari internet (API Renewables.ninja).
│   ├── sizing.py           <- Menghitung jumlah modul, susunan string, dan batas aman inverter.
│   ├── dispatch.py         <- Menyimulasikan aliran daya per jam (kapan PV dipakai, disimpan, diekspor).
│   ├── economics.py        <- Menghitung uang: Biaya awal (CAPEX), balik modal, dan keuntungan 25 tahun.
│   └── exporter.py         <- Mencetak seluruh hasil kalkulasi ke dalam berkas Excel (.xlsx).
│
└── tests/                  <- Kumpulan skrip penguji otomatis untuk mengecek kebenaran rumus.
```

---

## 3. Alur Kerja Langkah Demi Langkah (Step-by-Step Flow)

Berikut urutan peristiwa yang terjadi di dalam kode:

```
[1. User Input Beban]    ──> core/data_loader.py    ──> Menghasilkan list beban 24 jam [kW]
[2. User Pilih Radiasi]  ──> core/ninja_client.py   ──> Menghasilkan dict radiasi 24 jam [W/m²]
[3. User Klik Hitung]    ──> core/sizing.py         ──> Hitung Modul, String, Inverter, Baterai
                                  │
                                  ▼
                             core/dispatch.py       ──> Simulasi 24 jam (Produksi, Ekspor, Baterai)
                                  │
                                  ▼
                             core/economics.py      ──> Hitung Finansial (CAPEX, LCOE, Payback)
                                  │
                                  ▼
[4. Output di Layar]     <── app.py                 ──> Tampilkan Metrik & Grafik Plotly
[5. Unduh Laporan]       ──> core/exporter.py       ──> Hasilkan file .xlsx multi-sheet
```

---

## 4. Penjelasan Mendalam Setiap Modul di `core/`

### A. Modul 1: `core/data_loader.py` (Pengolah Data Beban)
**Tugas:** Mengubah input pemakaian listrik user menjadi deret angka 24 jam (jam 00:00 sampai 23:00).

- **Fungsi `blocks_to_hourly(blocks)`:**
  User seringkali tidak tahu pemakaian tiap jam, mereka hanya tahu: "Jam 00-06 pakai 89 kW, Jam 06-09 pakai 98 kW". Fungsi ini menggunakan perulangan sederhana untuk mengisi array 24 angka sesuai rentang jam tersebut.
- **Fungsi `parse_load_profile_csv` & `parse_load_profile_excel`:**
  Membaca berkas unggahan user menggunakan library `pandas`. Jika user mengunggah data per 15 menit (ada 96 baris), fungsi ini otomatis menghitung rata-rata tiap 4 baris sehingga kembali menjadi 24 jam yang rapi.

---

### B. Modul 2: `core/ninja_client.py` (Koneksi Satelit Cuaca)
**Tugas:** Mengambil data iradiansi matahari nyata dari situs Renewables.ninja berdasarkan titik koordinat (Latitude & Longitude).

- **Fungsi `fetch_pv_profile(api_token, lat, lon, tilt, azim)`:**
  1. Cek folder `.cache/` lebih dulu. Jika user pernah meminta lokasi yang sama, ambil file cache lokal agar cepat dan menghemat kuota API.
  2. Jika belum ada, fungsi mengirim permintaan internet (`requests.get`) ke server Renewables.ninja dengan membawa token autentikasi.
  3. Mengubah timestamp dunia (UTC) ke waktu lokal Indonesia:
     - Longitude < 115° = WIB (UTC+7)
     - Longitude 115° - 125° = WITA (UTC+8)
     - Longitude > 125° = WIT (UTC+9)
  4. Mengembalikan nilai daya surya per jam dalam bentuk dictionary `{jam: watt}`.

---

### C. Modul 3: `core/sizing.py` (Kalkulator Fisik Modul & Inverter)
**Tugas:** Menentukan berapa lembar panel surya dan berapa unit inverter yang harus dibeli, serta memastikan alat tidak meledak atau rusak akibat tegangan berlebih.

- **Fungsi `calc_thermal_voltages(...)`:**
  Panel surya sensitif terhadap suhu. Saat udara sangat dingin, tegangannya naik drastis ($V_{oc,cold}$). Saat matahari terik panas, tegangannya turun ($V_{mp,hot}$). Fungsi ini menghitung kedua batas kritis tersebut dengan rumus koefisien suhu termal:
  $$V_{oc,cold} = V_{oc} \times (1 + \frac{k_{voc}}{100} \times (T_{min} - 25))$$
- **Fungsi `calc_string_limits(...)`:**
  Menghitung berapa modul minimal dan maksimal yang boleh dirangkai seri dalam satu kabel:
  - Jumlah modul maksimal ditentukan oleh tegangan maksimum inverter ($V_{dc,max} / V_{oc,cold}$).
  - Jumlah modul minimal ditentukan oleh batas bawah pelacak MPPT inverter ($V_{mppt,min} / V_{mp,hot}$).
- **Fungsi `size_pv_system(...)`:**
  1. Menghitung total modul yang dibutuhkan: $\text{Kapasitas Target (Wp)} / \text{Daya Modul (Pmax)}$.
  2. Menghitung jumlah inverter yang dibutuhkan.
  3. Membagi modul ke dalam konfigurasi string yang seimbang (algoritma pencarian modular: misal 7 string isi 19 modul, dan 129 string isi 18 modul).
  4. Memvalidasi 3 syarat aman teknik:
     - Apakah tegangan dingin melampaui batas inverter? (`status_vdc`)
     - Apakah rentang MPPT terpenuhi? (`status_mppt`)
     - Apakah arus panel melebihi batas arus inverter? (`status_arus`)
- **Fungsi `size_battery_bank(...)`:**
  Jika memilih topologi **Off-Grid** atau **Hybrid**, fungsi ini menghitung kapasitas baterai yang dibutuhkan berdasarkan cadangan hari otonomi (misal harus tahan 1 hari tanpa matahari) dengan mempertimbangkan batas DoD (kedalaman pengosongan baterai agar tidak cepat rusak).

---

### D. Modul 4: `core/dispatch.py` (Simulasi Aliran Daya Harian)
**Tugas:** Menjalankan simulasi gerak daya per jam selama satu hari penuh (24 langkah perulangan `for hour in range(24)`).

Setiap jam, rumus mempertemukan dua hal: **Daya Beban** vs **Daya Hasil Surya (PV)**.
- **Kasus 1: Produksi PV > Beban (Kelebihan Daya)**
  - Beban dipenuhi 100% dari PV.
  - Sisa daya surplus:
    - Jika ada baterai (Hybrid/Off-Grid) dan belum penuh: Daya dialirkan untuk mengisi baterai.
    - Jika baterai sudah penuh (atau sistem On-Grid): Daya surplus diekspor/dibuang.
- **Kasus 2: Produksi PV < Beban (Kekurangan Daya)**
  - Semua daya PV dipakai sendiri (*Self Consumption*).
  - Kekurangan daya (defisit):
    - Jika ada baterai: Ambil daya dari baterai sampai batas DoD.
    - Jika baterai habis atau On-Grid: Impor daya dari jaringan listrik PLN.

Modul ini juga melacak persentase baterai setiap jam (**State of Charge / SOC** dari 0% sampai 100%).

---

### E. Modul 5: `core/economics.py` (Analisis Kelayakan Finansial 25 Tahun)
**Tugas:** Menghitung apakah proyek ini menguntungkan secara finansial.

- **Biaya Investasi Awal (CAPEX):**
  $$\text{CAPEX} = \text{Harga Modul} + \text{Harga Inverter} + \text{Harga Baterai} + \text{Biaya Kabel, Rak, Instalasi (BoS)}$$
- **Penghematan Tahunan:**
  Jumlah kWh listrik surya yang berhasil menggantikan listrik PLN dikalikan dengan tarif PLN (Rp/kWh).
- **Simulasi 25 Tahun:**
  Menghitung arus kas masa depan dengan memperhitungkan degradasi panel (efisiensi turun ~0.7% tiap tahun) dan suku bunga diskonto (*Discount Factor*).
- **Metrik Utama yang Dihasilkan:**
  - **Payback Period (BEP):** Tahun ke berapa modal awal kembali impas.
  - **NPV (Net Present Value):** Nilai bersih keuntungan proyek dalam nilai uang sekarang. Jika positif, proyek layak dijalankan.
  - **LCOE (Levelized Cost of Electricity):** Biaya pokok per 1 kWh listrik yang dihasilkan oleh PLTS sepanjang umurnya. Jika LCOE < Tarif PLN, PLTS lebih murah daripada beli ke PLN.

---

### F. Modul 6: `core/exporter.py` (Pencetak Laporan Excel)
**Tugas:** Mengambil seluruh dictionary hasil kalkulasi, lalu menyusunnya menjadi file Excel profesional menggunakan library `openpyxl` dan `xlsxwriter`.

File Excel yang dibuat memiliki 4 lembar kerja (Sheets):
1. **Ringkasan Proyek:** Berisi informasi kapasitas, spesifikasi alat, dan metrik ekonomi penting.
2. **Kalkulasi Teknis:** Rincian batas termal inverter, konfigurasi string, dimensi lahan.
3. **Simulasi Aliran Daya 24 Jam:** Tabel angka per jam (Beban, PV, Terpakai, Surplus, Impor Grid, SOC Baterai).
4. **Kelayakan Finansial 25 Tahun:** Tabel arus kas tahunan dari Tahun 0 sampai Tahun 25.

---

## 5. Bagaimana `app.py` Bekerja Sebagai Konduktor

File `app.py` menggunakan Streamlit, sebuah kerangka kerja Python yang membaca file dari baris pertama sampai baris terakhir setiap kali user berinteraksi dengan komponen di layar.

Berikut logika alur di `app.py`:

```python
# 1. Baca Konfigurasi Sidebar
topologi = st.sidebar.selectbox("Pilih Topologi", ["On-Grid", "Off-Grid", "Hybrid"])
radiasi  = st.session_state["solar_irr"]

# 2. Baca Input Halaman Utama
beban_24jam = dapatkan_data_beban()
komponen    = baca_pilihan_modul_dan_inverter()

# 3. Saat Tombol Ditekan
if st.button("Kalkulasi Sizing & Kinerja"):
    # Panggil fungsi-fungsi dari core/
    hasil_pv       = size_pv_system(...)
    hasil_dispatch = dispatch_simulation(...)
    hasil_ekonomi  = calc_financial_metrics(...)
    
    # Simpan jawaban ke session_state agar tidak hilang
    st.session_state["calc_results"] = gabungan_semua_hasil

# 4. Gambar Ulang Layar
if st.session_state["calc_results"] is not None:
    # Tampilkan angka metrik
    st.metric(...)
    # Gambar kurva daya dan SOC menggunakan Plotly
    st.plotly_chart(...)
    # Sediakan tombol unduh Excel
    st.download_button(...)
```

---

## 6. Kamus Singkat Istilah Teknis

| Istilah | Kepanjangan / Arti Sederhana |
|---|---|
| **Wp / kWp** | *Watt-peak / kiloWatt-peak* — Kapasitas daya maksimum yang bisa dihasilkan panel surya saat kondisi uji standar. |
| **PSH** | *Peak Sun Hours* — Jam ekuivalen matahari bersinar terik penuh (1000 W/m²). Di Indonesia rata-rata 3.5 - 5.0 jam per hari. |
| **Voc** | *Open Circuit Voltage* — Tegangan maksimum panel saat belum diberi beban. Penting agar inverter tidak jebol. |
| **Vmp** | *Maximum Power Voltage* — Tegangan kerja optimal saat panel menghasilkan daya tertinggi. |
| **MPPT** | *Maximum Power Point Tracking* — Otak inverter yang terus mencari titik tegangan terbaik agar daya surya maksimal. |
| **DoD** | *Depth of Discharge* — Batas maksimal pengosongan baterai agar awet (misal DoD 85% artinya baterai disisakan minimal 15%). |
| **Self Consumption** | Persentase listrik surya yang langsung habis dipakai sendiri oleh gedung tanpa perlu dibuang atau diekspor. |
| **Solar Fraction** | Porsi kebutuhan listrik gedung yang berhasil ditutupi oleh tenaga surya (sisanya dari PLN/baterai). |
| **CAPEX** | *Capital Expenditure* — Total biaya modal investasi awal yang harus dibayarkan di depan. |
| **LCOE** | *Levelized Cost of Electricity* — Harga modal listrik per kWh yang dihasilkan sistem surya selama masa hidupnya. |
