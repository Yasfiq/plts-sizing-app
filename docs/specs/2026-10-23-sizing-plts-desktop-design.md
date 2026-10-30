# Design Spec — Sizing PLTS On-Grid / Off-Grid / Hybrid Desktop (Streamlit)

Tanggal: 2026-10-23
Status: Menunggu review

## 1. Tujuan
Aplikasi sizing PLTS desktop (Streamlit) multi-topologi: On-Grid, Off-Grid, dan Hybrid.
Mendukung input profil beban & surya (file/manual/API Renewables.ninja), preset modul,
inverter, baterai, kalkulasi termal string, sizing bank baterai, dispatch 24 jam dengan
aliran energi baterai, verifikasi batas teknis, evaluasi luas dimensi, analisis finansial
(CAPEX, OPEX, Payback Period, NPV, LCOE), dan ekspor data ke Excel.

## 2. Teknologi (Locked)
- UI: Streamlit (jalan lokal di browser `localhost:8501`)
- Data: Pandas (CSV/XLSX via openpyxl), Requests (API Renewables.ninja)
- Grafik: Plotly (kurva beban, PV, baterai SOC 24 jam interaktif)
- Python 3.14 + dependensi via pip (streamlit, plotly, pandas, openpyxl, xlsxwriter)

## 3. Logika Tambahan Tiap Topologi
- **On-Grid**: Tanpa baterai. PV langsung ke beban. Surplus = ekspor/curtailed. Defisit = impor PLN.
- **Off-Grid**: Mandiri tanpa PLN. Wajib baterai.
  - Rumus Baterai: Kapasitas kWh = (Energi Harian / efisiensi_inverter) * Hari_Otonomi / DoD.
  - Kapasitas Ah = (Kapasitas kWh * 1000) / V_sistem_dc.
  - Sizing PV: Menutup konsumsi harian + rugi charging baterai.
- **Hybrid**: Inverter hybrid + baterai.
  - Prioritas dispatch siang: PV -> Beban -> Cas Baterai -> Surplus ekspor ke grid.
  - Prioritas dispatch malam/defisit: Baterai (sampai batas DoD) -> Impor grid.
  - Menghitung kurva State of Charge (SOC) baterai per jam.

## 3. Struktur File
```
plts-app/
├── app.py               # UI Streamlit (semua st.* calls)
├── core/
│   ├── data_loader.py   # parse CSV/XLSX beban & surya -> array 24 jam
│   ├── ninja_client.py  # GET renewables.ninja /v1/data/pv, cache lokal
│   ├── sizing.py        # hitungan termal, string, inverter, baterai, luas
│   ├── dispatch.py      # simulasi 24 jam (on-grid, off-grid, hybrid + SOC)
│   └── economics.py     # CAPEX, OPEX, penghematan tahunan, Payback Period, NPV, LCOE
├── presets.json         # database modul, inverter, dan baterai
├── tests/
│   └── test_core.py     # assert-based test (teknis + finansial)
└── requirements.txt
```

## 4. Alur UI (single page, urut atas-bawah)
1. Sidebar: sumber data surya (API / upload / manual), lokasi (lat-lon atau pilih kota),
   tilt & azimuth, API token (disimpan di session, tidak di-hardcode).
2. Section "Profil Beban": upload CSV/XLSX ATAU editor periode manual (port dari HTML tim).
3. Section "Komponen": dropdown preset modul & inverter (nilai terisi otomatis, bisa diedit)
   + input dimensi modul (P x L mm) + luas atap tersedia (m²).
4. Section "Sizing": kWp manual ATAU 0 = auto (target self-consumption %),
   suhu min & suhu sel maks.
5. Tombol "Hitung" -> hasil:
   - KPI cards: kWp, jumlah modul, jumlah inverter, DC/AC, PSH, SC%, SF%, luas terpakai
   - Status batas teknis (badge Lolos/Gagal per parameter)
   - Tabel susunan string per inverter
   - Grafik Plotly 24 jam: beban vs PV vs terpakai, area surplus/defisit
   - Tabel kinerja per periode & per jam
6. Tombol ekspor: XLSX multi-sheet (input, hasil, dispatch). PDF menyusul bila diminta.

## 5. Logika Inti (port dari versi tim, tanpa perubahan rumus)
- Voc_cold = Voc * (1 + kvoc/100 * (Tmin - 25)); Vmp_hot = Vmp * (1 + kvmp/100 * (Tcell_max - 25))
- N_string_maks = min(floor(Vdc_max/Voc_cold), floor(MPPT_max/Vmp_cold))
- N_string_min = ceil(MPPT_min/Vmp_hot); valid N_min <= N_maks
- N_modul = ceil(kWp*1000/Pmax); string/inverter = MPPT * string_per_MPPT
- N_inverter = ceil(N_modul / (string_per_inv * N_string_maks))
- Dispatch per jam: terpakai = min(load, pv); surplus = max(pv-load, 0); defisit = max(load-pv, 0)
- Auto-kapasitas: kelipatan step (default 50 kWp), cari kWp terbesar yang SC >= target
- API ninjaa: capacity=1, tracking=0, dataset=merra2; output hourly kW/kWp -> kalikan PR.
  Cache: file JSON per (lat,lon,tilt,azim,tahun) di folder .cache/, cegah rate-limit 50 req/jam.
  Gagal/offline -> fallback ke upload/manual dengan pesan info.

## 6. Format File Input
- Beban CSV/XLSX: kolom `jam` (0-23 atau datetime) + `kw`. Template disediakan (tombol download).
- Surya CSV/XLSX: kolom `jam` + `irradiansi` (pilih satuan W/m2 atau kW/m2).
- Validasi: 24 jam penuh tanpa tumpang tindih; nilai >= 0; pesan error spesifik per baris.

## 7. Preset (presets.json)
Contoh entri, bisa ditambah user via form (disimpan ke presets.json):
- Modul: Pmax, Voc, Vmp, Isc, kvoc, kvmp, panjang_mm, lebar_mm
- Inverter: pac_kw, mppt_min, mppt_max, vdc_max, n_mppt, imax_mppt, string_per_mppt

## 8. Testing
- tests/test_core.py: assert vektor 24 jam dari contoh tim (beban 89/98/180/208/167/79/59,
  radiasi Kupang) -> total 2907 kWh beban, 4860 kWh PV @1350 kWp, SC 38.3% (per jam).
- Cek batas: 19 modul/string maks pada inverter contoh, Voc_cold 50.47 V.

## 8. Analisis Finansial
- Default Parameter:
  - Tarif PLN: Rp 1.444,70 / kWh (bisa diedit)
  - Biaya Sistem: Modul (Rp/Wp), Inverter (Rp/W), Baterai (Rp/kWh), BoS & Jasa (15% dari komponen)
  - Umur Proyek: 25 tahun (degradasi 0.7%/tahun), Discount Rate: 8%
- Formula:
  - CAPEX = Biaya PV + Biaya Inverter + Biaya Baterai + BoS
  - Penghematan_t = Energi_terpakai_t * Tarif_PLN
  - Simple Payback Period = CAPEX / Penghematan_Tahun_1
  - NPV = -CAPEX + Sum[ (Penghematan_t - OPEX_t) / (1 + r)^t ]
  - LCOE = (CAPEX + Sum[ OPEX_t / (1+r)^t ]) / Sum[ Energi_t / (1+r)^t ]

## 9. Batas (Non-goals, versi ini)
- Tanpa skema pinjaman bank / kalkulasi bunga kredit kompleks (asumsi cash equity)
- Tanpa packaging installer .exe (jalan via `streamlit run app.py`)

## 10. Dependensi
streamlit, pandas, openpyxl, requests, plotly, xlsxwriter (ekspor)
