# Aplikasi Sizing PLTS Multi-Topologi

Aplikasi desktop berbasis Streamlit untuk perancangan dan kalkulasi sistem PLTS (On-Grid, Off-Grid, Hybrid) dengan integrasi Renewables.ninja API, optimasi dispatch 24 jam, batas teknis inverter, dan analisis finansial 25 tahun.

---

## Persyaratan Sistem

- **Python**: Versi 3.10, 3.11, atau 3.12
- **Sistem Operasi**: Windows, macOS, atau Linux
- Koneksi internet (hanya dibutuhkan jika menarik data radiasi via API Renewables.ninja)

---

## Panduan Instalasi Cepat

### 1. Clone atau Ekstrak Folder Proyek
Buka terminal (macOS/Linux) atau Command Prompt/PowerShell (Windows), lalu masuk ke folder proyek:
```bash
cd "Assignment - Group"
```

### 2. Buat Lingkungan Virtual (Virtual Environment)
Disarankan agar tidak bentrok dengan paket Python lain di komputermu:

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Pasang Dependensi
```bash
pip install -r requirements.txt
```

---

## Menjalankan Aplikasi

Jalankan perintah ini di terminal:
```bash
streamlit run app.py
```

Browser akan otomatis terbuka di alamat:
```
http://localhost:8501
```

*(Jika browser tidak terbuka otomatis, salin URL di atas dan buka secara manual di Chrome/Edge/Firefox).*

---

## Menjalankan Pengujian (Testing)

Semua engine kalkulasi sudah dilengkapi self-test berbasis `assert` bawaan Python (tanpa perlu install library tambahan):

```bash
# Uji seluruh modul logika kalkulasi & integrasi
python tests/test_core.py

# Uji ekspor laporan Excel
python tests/test_e2e_export.py

# Uji client API Renewables.ninja
python tests/test_ninja_client.py
```

---

## Catatan Tambahan

1. **Token API Renewables.ninja**: Bersifat opsional. Jika temanmu tidak punya token, pilih opsi radiasi **"Manual / File Lokal"** -> **"Data Standar Default"** di sidebar.
2. **Ekspor Laporan**: Tombol unduh laporan `.xlsx` ada di bagian paling bawah setelah kalkulasi dijalankan.
