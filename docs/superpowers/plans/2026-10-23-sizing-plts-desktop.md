# Sizing PLTS Multi-Topology Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun aplikasi desktop Streamlit untuk sizing PLTS komprehensif (On-Grid, Off-Grid, Hybrid) dengan integrasi API Renewables.ninja, pembacaan beban/surya CSV/XLSX, pengecekan batas inverter, bank baterai, evaluasi dimensi, analisis finansial, dan ekspor Excel.

**Architecture:** Arsitektur modular 3-tier: Presentasi murni di `app.py` (Streamlit + Plotly), logika rekayasa independen di package `core/` (data_loader, ninja_client, sizing, dispatch, economics), data acuan di `presets.json`.

**Tech Stack:** Python 3.14, Streamlit, Pandas, Openpyxl, XlsxWriter, Plotly, Requests.

**Spec:** `docs/specs/2026-10-23-sizing-plts-desktop-design.md`

## Global Constraints
- Bahasa kode dan komentar: Python idiomatik standar, komentar singkat bila perlu.
- Non-trivial logic wajib disertai unit test assert murni di `tests/test_core.py` tanpa framework luar.
- Toleransi error floating-point pada kalkulasi dispatch <= 1e-4.
- API call ke Renewables.ninja harus di-cache lokal di direktori `.cache/` berbasis MD5 hash parameter.
- Sizing inverter dan termal modul wajib mempertahankan akurasi formula dari `Sizing PLTS On-Grid.html`.

---

### Task 1: Environment & Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `presets.json`
- Create: `core/__init__.py`

**Interfaces:**
- Consumes: None
- Produces: File konfigurasi dependensi dan basis data komponen modul, inverter, dan baterai.

- [ ] **Step 1: Buat file requirements.txt**

```txt
streamlit>=1.35.0
pandas>=2.2.0
openpyxl>=3.1.2
xlsxwriter>=3.2.0
plotly>=5.20.0
requests>=2.32.0
```

- [ ] **Step 2: Install dependensi via pip**

Run: `pip3 install -r requirements.txt`
Expected: Instalasi sukses tanpa error.

- [ ] **Step 3: Buat database presets.json**

Buat data katalog awal untuk modul PV (Longi 550Wp, Jinko 580Wp, Canadian Solar 650Wp), Inverter (Sungrow 50kW, Huawei 100kW, Growatt 5kW Hybrid), dan Baterai (LiFePO4 48V 100Ah, Gel Deep Cycle 12V 200Ah).

```json
{
  "modules": [
    {
      "name": "Standard Mono-PERC 550Wp",
      "pmax": 550.0,
      "voc": 49.5,
      "vmp": 41.5,
      "isc": 14.0,
      "kvoc": -0.28,
      "kvmp": -0.35,
      "length_mm": 2278,
      "width_mm": 1134,
      "cost_per_wp": 3500
    },
    {
      "name": "Jinko Tiger Neo N-Type 580Wp",
      "pmax": 580.0,
      "voc": 51.2,
      "vmp": 42.8,
      "isc": 14.15,
      "kvoc": -0.25,
      "kvmp": -0.30,
      "length_mm": 2278,
      "width_mm": 1134,
      "cost_per_wp": 4000
    }
  ],
  "inverters": [
    {
      "name": "String Inverter 50kW On-Grid",
      "type": "on-grid",
      "pac_kw": 50.0,
      "mppt_min": 500.0,
      "mppt_max": 850.0,
      "vdc_max": 1000.0,
      "n_mppt": 4,
      "imax_mppt": 30.0,
      "string_per_mppt": 2,
      "efficiency": 0.985,
      "cost_per_w": 1200
    },
    {
      "name": "Commercial Inverter 100kW On-Grid",
      "type": "on-grid",
      "pac_kw": 100.0,
      "mppt_min": 200.0,
      "mppt_max": 1000.0,
      "vdc_max": 1100.0,
      "n_mppt": 10,
      "imax_mppt": 30.0,
      "string_per_mppt": 2,
      "efficiency": 0.987,
      "cost_per_w": 1000
    },
    {
      "name": "Hybrid Inverter 10kW",
      "type": "hybrid",
      "pac_kw": 10.0,
      "mppt_min": 200.0,
      "mppt_max": 650.0,
      "vdc_max": 800.0,
      "n_mppt": 2,
      "imax_mppt": 16.0,
      "string_per_mppt": 2,
      "efficiency": 0.975,
      "cost_per_w": 2500
    }
  ],
  "batteries": [
    {
      "name": "Lithium LiFePO4 48V 100Ah",
      "voltage_nominal": 48.0,
      "capacity_ah": 100.0,
      "dod_max": 0.85,
      "efficiency": 0.95,
      "cost_per_kwh": 3500000
    },
    {
      "name": "VRLA Gel Deep Cycle 12V 200Ah",
      "voltage_nominal": 12.0,
      "capacity_ah": 200.0,
      "dod_max": 0.50,
      "efficiency": 0.85,
      "cost_per_kwh": 2200000
    }
  ]
}
```

- [ ] **Step 4: Buat package core**

Run: `mkdir -p core tests .cache && touch core/__init__.py`

- [ ] **Step 5: Verifikasi scaffolding awal**

Run: `python3 -c "import json; d=json.load(open('presets.json')); assert len(d['modules']) >= 2"`
Expected: Exit code 0.

---

### Task 2: Core Data Loader (CSV/XLSX & Manual Period Parser)

**Files:**
- Create: `core/data_loader.py`
- Test: `tests/test_data_loader.py`

**Interfaces:**
- Consumes: File buffer CSV/Excel atau list of tuple beban manual.
- Produces: 
  - `parse_load_profile(file_or_path) -> list[float]` (panjang 24 float)
  - `parse_solar_profile(file_or_path, factor=1.0) -> dict[int, float]`
  - `blocks_to_hourly(blocks: list[tuple[int, int, float]]) -> list[float]`
  - `generate_load_template_csv() -> str`

- [ ] **Step 1: Tulis unit test untuk data_loader**

```python
# tests/test_data_loader.py
import io
import csv
from core.data_loader import blocks_to_hourly, parse_load_profile_csv

def test_blocks_to_hourly():
    # 7 periode acuan user
    blocks = [
        (0, 6, 89.0),
        (6, 9, 98.0),
        (9, 12, 180.0),
        (12, 15, 208.0),
        (15, 18, 167.0),
        (18, 21, 79.0),
        (21, 24, 59.0)
    ]
    hourly = blocks_to_hourly(blocks)
    assert len(hourly) == 24
    assert hourly[0] == 89.0
    assert hourly[7] == 98.0
    assert hourly[12] == 208.0
    assert sum(hourly) == 2907.0

def test_parse_load_profile_csv():
    data = "jam,beban_kw\n" + "\n".join([f"{h},100" for h in range(24)])
    f = io.StringIO(data)
    hourly = parse_load_profile_csv(f)
    assert len(hourly) == 24
    assert sum(hourly) == 2400.0

if __name__ == "__main__":
    test_blocks_to_hourly()
    test_parse_load_profile_csv()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

Run: `python3 tests/test_data_loader.py`
Expected: ModuleNotFoundError atau ImportError.

- [ ] **Step 3: Implementasikan core/data_loader.py**

```python
import io
import pandas as pd

def blocks_to_hourly(blocks: list[tuple[int, int, float]]) -> list[float]:
    """Mengubah list blok (start_hour, end_hour, kw) menjadi 24 jam daya rata-rata."""
    hourly = [0.0] * 24
    covered = [0] * 24
    for start, end, kw in blocks:
        if not (0 <= start < end <= 24):
            raise ValueError(f"Rentang jam tidak valid: {start}-{end}")
        if kw < 0:
            raise ValueError(f"Daya beban tidak boleh negatif: {kw}")
        for h in range(start, end):
            covered[h] += 1
            hourly[h] = float(kw)
    
    missing = [h for h, c in enumerate(covered) if c == 0]
    overlap = [h for h, c in enumerate(covered) if c > 1]
    if missing or overlap:
        raise ValueError(f"Profil beban tidak menutup 24 jam (hilang: {missing}, overlap: {overlap})")
    return hourly

def parse_load_profile_csv(file_obj) -> list[float]:
    """Membaca CSV kolom [jam, beban_kw] atau file 24 baris data."""
    df = pd.read_csv(file_obj)
    return _extract_24h_from_df(df, target_col_keywords=["beban", "load", "kw", "power"])

def parse_load_profile_excel(file_obj) -> list[float]:
    """Membaca file Excel profil beban."""
    df = pd.read_excel(file_obj)
    return _extract_24h_from_df(df, target_col_keywords=["beban", "load", "kw", "power"])

def _extract_24h_from_df(df: pd.DataFrame, target_col_keywords: list[str]) -> list[float]:
    val_col = None
    for col in df.columns:
        if any(k in str(col).lower() for k in target_col_keywords):
            val_col = col
            break
    if val_col is None:
        # Fallback ke kolom numerik kedua atau pertama
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) >= 2:
            val_col = num_cols[1]
        elif len(num_cols) == 1:
            val_col = num_cols[0]
        else:
            raise ValueError("Tidak ditemukan kolom numerik beban dalam file.")
    
    vals = df[val_col].dropna().astype(float).tolist()
    if len(vals) == 24:
        return vals
    elif len(vals) == 96: # Interval 15-menit -> resample ke 24 jam
        return [sum(vals[i:i+4])/4.0 for i in range(0, 96, 4)]
    else:
        raise ValueError(f"Data harus berjumlah 24 jam (atau 96 baris untuk interval 15 menit). Ditemukan: {len(vals)}")

def generate_load_template_csv() -> str:
    lines = ["jam,beban_kw"]
    for h in range(24):
        lines.append(f"{h},0.0")
    return "\n".join(lines)
```

- [ ] **Step 4: Jalankan test kembali dan pastikan lulus**

Run: `python3 tests/test_data_loader.py`
Expected: Output `ALL TESTS PASSED`.

---

### Task 3: Core API Client Renewables.ninja

**Files:**
- Create: `core/ninja_client.py`
- Test: `tests/test_ninja_client.py`

**Interfaces:**
- Consumes: Token, latitude, longitude, tilt, azimuth, dataset (merra2/sarah).
- Produces: `fetch_pv_profile(...) -> dict[int, float]` (jam 0-23 ke kWh/kWp rata-rata) dengan caching lokal.

- [ ] **Step 1: Tulis unit test untuk ninja_client (mock & cache)**

```python
# tests/test_ninja_client.py
import os
import json
from core.ninja_client import get_cache_key, parse_ninja_response

def test_parse_ninja_response():
    # Contoh struktur JSON response dari Renewables.ninja
    sample = {
        "data": {
            "2026-01-01 06:00:00": {"electricity": 0.1},
            "2026-01-01 07:00:00": {"electricity": 0.3},
            "2026-01-01 12:00:00": {"electricity": 0.8},
            "2026-01-01 18:00:00": {"electricity": 0.0}
        }
    }
    hourly = parse_ninja_response(sample)
    assert len(hourly) == 24
    assert hourly[6] == 0.1
    assert hourly[12] == 0.8
    assert hourly[0] == 0.0

if __name__ == "__main__":
    test_parse_ninja_response()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

Run: `python3 tests/test_ninja_client.py`
Expected: ImportError.

- [ ] **Step 3: Implementasikan core/ninja_client.py**

```python
import hashlib
import json
import os
from typing import Optional
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")

def get_cache_key(lat: float, lon: float, tilt: float, azim: float, dataset: str) -> str:
    raw = f"{lat:.4f}_{lon:.4f}_{tilt:.1f}_{azim:.1f}_{dataset}"
    return hashlib.md5(raw.encode()).hexdigest()

def parse_ninja_response(data_json: dict) -> list[float]:
    """Mengolah data time-series ninja menjadi profil rata-rata 24 jam [0-23]."""
    buckets = {h: [] for h in range(24)}
    data_dict = data_json.get("data", {})
    for time_str, entry in data_dict.items():
        # format: "YYYY-MM-DD HH:MM:SS" atau ISO
        try:
            hour = int(time_str.split(" ")[1].split(":")[0])
        except Exception:
            try:
                hour = int(time_str.split("T")[1].split(":")[0])
            except Exception:
                continue
        val = float(entry.get("electricity", 0.0))
        buckets[hour].append(val)
    
    hourly_avg = [0.0] * 24
    for h in range(24):
        if buckets[h]:
            hourly_avg[h] = sum(buckets[h]) / len(buckets[h])
    return hourly_avg

def fetch_pv_profile(
    api_token: str,
    lat: float,
    lon: float,
    tilt: float = 15.0,
    azim: float = 180.0,
    dataset: str = "merra2",
    use_cache: bool = True
) -> list[float]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    ckey = get_cache_key(lat, lon, tilt, azim, dataset)
    cpath = os.path.join(CACHE_DIR, f"{ckey}.json")
    
    if use_cache and os.path.exists(cpath):
        with open(cpath, "r") as f:
            return parse_ninja_response(json.load(f))
            
    if not api_token:
        raise ValueError("API Token Renewables.ninja tidak boleh kosong.")

    url = "https://www.renewables.ninja/api/v1/data/pv"
    headers = {"Authorization": f"Bearer {api_token.strip()}"}
    params = {
        "lat": lat,
        "lon": lon,
        "date_from": "2022-01-01",
        "date_to": "2022-01-07",
        "dataset": dataset,
        "capacity": 1.0,
        "system_loss": 0.1,
        "tracking": 0,
        "tilt": tilt,
        "azim": azim,
        "format": "json"
    }
    
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Gagal mengambil data Ninja API ({resp.status_code}): {resp.text}")
        
    data = resp.json()
    with open(cpath, "w") as f:
        json.dump(data, f)
        
    return parse_ninja_response(data)
```

- [ ] **Step 4: Jalankan test kembali dan pastikan lulus**

Run: `python3 tests/test_ninja_client.py`
Expected: Output `ALL TESTS PASSED`.

---

### Task 4: Core Sizing Engine (Termal, String, Inverter, Baterai, Dimensi)

**Files:**
- Create: `core/sizing.py`
- Test: `tests/test_sizing.py`

**Interfaces:**
- Consumes: Spesifikasi modul, inverter, baterai, parameter lingkungan.
- Produces: 
  - `calc_module_voltages(modul, tmin, tmax_sel) -> dict`
  - `size_pv_system(kwp, modul, inverter, tmin, tmax_sel) -> dict`
  - `size_battery_bank(daily_kwh, autonomy_days, dod, v_sys, battery_spec) -> dict`
  - `calc_dimensions(num_modules, mod_length_mm, mod_width_mm, pitch_factor=1.25) -> dict`

- [ ] **Step 1: Tulis unit test untuk sizing (verifikasi hasil acuan tim: 1350 kWp, 17 inverter, 2455 modul)**

```python
# tests/test_sizing.py
from core.sizing import calc_module_voltages, size_pv_system, size_battery_bank, calc_dimensions

def test_pv_sizing_reference():
    modul = {
        "pmax": 550.0,
        "voc": 49.5,
        "vmp": 41.5,
        "isc": 14.0,
        "kvoc": -0.28,
        "kvmp": -0.35
    }
    inv = {
        "pac_kw": 50.0,
        "mppt_min": 500.0,
        "mppt_max": 850.0,
        "vdc_max": 1000.0,
        "n_mppt": 4,
        "imax_mppt": 30.0,
        "string_per_mppt": 2
    }
    tmin = 18.0
    tmax = 50.0
    
    # Uji voltase termal
    vt = calc_module_voltages(modul, tmin, tmax)
    assert round(vt["voc_cold"], 2) == 50.47
    assert round(vt["vmp_cold"], 2) == 42.52
    assert round(vt["vmp_hot"], 2) == 37.87
    
    # Uji sistem sizing 1350 kWp
    res = size_pv_system(1350.0, modul, inv, tmin, tmax)
    assert res["n_modul"] == 2455
    assert res["n_max_string"] == 19
    assert res["n_min_string"] == 14
    assert res["n_inverter"] == 17
    assert res["total_strings"] == 136
    assert round(res["dc_ac_ratio"], 2) == 1.59
    assert res["status_mppt"] is True
    assert res["status_vdc"] is True

def test_battery_sizing():
    spec = {"voltage_nominal": 48.0, "capacity_ah": 100.0}
    res = size_battery_bank(daily_kwh=100.0, autonomy_days=1, dod=0.8, v_sys=48.0, battery_spec=spec, inv_eff=0.95)
    # 100 / 0.95 / 0.8 = 131.57 kWh -> Ah = 2741 Ah -> 28 unit baterai 100Ah
    assert res["capacity_kwh"] > 130
    assert res["total_units"] == 28

if __name__ == "__main__":
    test_pv_sizing_reference()
    test_battery_sizing()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

Run: `python3 tests/test_sizing.py`
Expected: ImportError.

- [ ] **Step 3: Implementasikan core/sizing.py**

```python
import math

def calc_module_voltages(m: dict, tmin: float, tmax_sel: float) -> dict:
    """Menghitung tegangan termal ekstrem sesuai temperatur."""
    kvoc = m["kvoc"] / 100.0
    kvmp = m["kvmp"] / 100.0
    voc_cold = m["voc"] * (1.0 + kvoc * (tmin - 25.0))
    vmp_cold = m["vmp"] * (1.0 + kvmp * (tmin - 25.0))
    vmp_hot = m["vmp"] * (1.0 + kvmp * (tmax_sel - 25.0))
    return {
        "voc_cold": voc_cold,
        "vmp_cold": vmp_cold,
        "vmp_hot": vmp_hot
    }

def size_pv_system(kwp: float, m: dict, inv: dict, tmin: float, tmax_sel: float) -> dict:
    n_modul = math.ceil(kwp * 1000.0 / m["pmax"])
    vt = calc_module_voltages(m, tmin, tmax_sel)
    
    n_max_vdc = math.floor(inv["vdc_max"] / vt["voc_cold"])
    n_max_mppt = math.floor(inv["mppt_max"] / vt["vmp_cold"])
    n_max = min(n_max_vdc, n_max_mppt)
    n_min = math.ceil(inv["mppt_min"] / vt["vmp_hot"])
    
    if n_min > n_max:
        raise ValueError(f"Rentang string tidak valid: N_min ({n_min}) > N_maks ({n_max}). Modul dan inverter tidak kompatibel.")
        
    str_per_inv = inv["n_mppt"] * inv["string_per_mppt"]
    modul_per_inv = str_per_inv * n_max
    n_inverter = math.ceil(n_modul / modul_per_inv)
    total_str = n_inverter * str_per_inv
    
    dasar = math.floor(n_modul / total_str)
    sisa = n_modul % total_str
    if dasar < n_min:
        raise ValueError("Modul terlalu sedikit untuk batas bawah MPPT inverter.")
        
    str_p = sisa
    str_k = total_str - sisa
    n_p = dasar + 1
    n_k = dasar
    
    layout = []
    sp = str_p
    for i in range(n_inverter):
        k = min(str_per_inv, sp)
        sp -= k
        layout.append({"inv_idx": i + 1, "str_p": k, "mod_p": n_p, "str_k": str_per_inv - k, "mod_k": n_k})
        
    n_tp = n_p if str_p else n_k
    n_tk = n_k if str_k else n_p
    
    voc_maks_act = n_tp * vt["voc_cold"]
    mppt_hi_act = n_tp * vt["vmp_cold"]
    mppt_lo_act = n_tk * vt["vmp_hot"]
    arus_mppt_act = inv["string_per_mppt"] * m["isc"]
    
    return {
        "n_modul": n_modul,
        "n_max_string": n_max,
        "n_min_string": n_min,
        "n_inverter": n_inverter,
        "total_strings": total_str,
        "dc_ac_ratio": kwp / (n_inverter * inv["pac_kw"]),
        "layout": layout,
        "voc_max_act": voc_maks_act,
        "mppt_hi_act": mppt_hi_act,
        "mppt_lo_act": mppt_lo_act,
        "arus_mppt_act": arus_mppt_act,
        "status_mppt": (inv["mppt_min"] <= mppt_lo_act and mppt_hi_act <= inv["mppt_max"]),
        "status_vdc": (voc_maks_act <= inv["vdc_max"]),
        "status_arus": (arus_mppt_act <= inv["imax_mppt"])
    }

def size_battery_bank(daily_kwh: float, autonomy_days: float, dod: float, v_sys: float, battery_spec: dict, inv_eff: float = 0.95) -> dict:
    if dod <= 0 or dod > 1.0:
        raise ValueError("DoD harus di antara 0 dan 1.0.")
    cap_kwh = (daily_kwh / inv_eff) * autonomy_days / dod
    cap_ah = (cap_kwh * 1000.0) / v_sys
    unit_kwh = (battery_spec["voltage_nominal"] * battery_spec["capacity_ah"]) / 1000.0
    total_units = math.ceil(cap_kwh / unit_kwh)
    return {
        "capacity_kwh": cap_kwh,
        "capacity_ah": cap_ah,
        "unit_kwh": unit_kwh,
        "total_units": total_units
    }

def calc_dimensions(num_modules: int, mod_len_mm: float, mod_wid_mm: float, pitch_factor: float = 1.25) -> dict:
    area_netto = num_modules * (mod_len_mm / 1000.0) * (mod_wid_mm / 1000.0)
    area_bruto = area_netto * pitch_factor
    return {
        "area_netto_m2": area_netto,
        "area_bruto_m2": area_bruto
    }
```

- [ ] **Step 4: Jalankan test kembali dan pastikan lulus**

Run: `python3 tests/test_sizing.py`
Expected: Output `ALL TESTS PASSED`.

---

### Task 5: Core Dispatch Engine (On-Grid, Off-Grid, Hybrid & Auto-Sizing)

**Files:**
- Create: `core/dispatch.py`
- Test: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: Load array 24h, Solar profile 24h, PR, sistem kWp, topologi, parameter baterai.
- Produces: 
  - `dispatch_simulation(...) -> tuple[list[dict], dict]`
  - `auto_size_capacity(...) -> float`

- [ ] **Step 1: Tulis unit test untuk dispatch (On-Grid & Hybrid)**

```python
# tests/test_dispatch.py
from core.dispatch import dispatch_simulation, auto_size_capacity

def test_dispatch_on_grid_reference():
    load = [89]*6 + [98]*3 + [180]*3 + [208]*3 + [167]*3 + [79]*3 + [59]*3
    solar = {
        7: 153.33, 8: 296.22, 9: 418.92, 10: 513.06, 11: 572.25,
        12: 592.44, 13: 572.25, 14: 513.06, 15: 418.92, 16: 296.22, 17: 153.33
    }
    pr = 0.8
    kwp = 1350.0
    rows, summary = dispatch_simulation(load, solar, pr, kwp, topology="on-grid")
    
    assert round(summary["total_load"]) == 2907
    assert round(summary["total_pv"]) == 4860
    assert round(summary["self_consumption_pct"], 1) == 38.3
    assert round(summary["solar_fraction_pct"], 1) == 64.0

def test_auto_sizing():
    load = [89]*6 + [98]*3 + [180]*3 + [208]*3 + [167]*3 + [79]*3 + [59]*3
    solar = {
        7: 153.33, 8: 296.22, 9: 418.92, 10: 513.06, 11: 572.25,
        12: 592.44, 13: 572.25, 14: 513.06, 15: 418.92, 16: 296.22, 17: 153.33
    }
    kwp = auto_size_capacity(load, solar, pr=0.8, target_sc=38.0, step=50.0)
    assert kwp >= 1350.0

if __name__ == "__main__":
    test_dispatch_on_grid_reference()
    test_auto_sizing()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

Run: `python3 tests/test_dispatch.py`
Expected: ImportError.

- [ ] **Step 3: Implementasikan core/dispatch.py**

```python
from typing import Optional

def dispatch_simulation(
    load: list[float],
    solar_irr: dict[int, float],
    pr: float,
    kwp: float,
    topology: str = "on-grid",
    battery_cap_kwh: float = 0.0,
    battery_dod_max: float = 0.8,
    battery_eff: float = 0.95
) -> tuple[list[dict], dict]:
    """Simulasi dispatch aliran energi per jam 0-23."""
    pv_hourly = [kwp * pr * (solar_irr.get(h, 0.0) / 1000.0) for h in range(24)]
    
    rows = []
    soc_kwh = battery_cap_kwh * (1.0 - battery_dod_max) # SOC awal pada DoD limit
    min_soc_kwh = battery_cap_kwh * (1.0 - battery_dod_max)
    
    tot_load = sum(load)
    tot_pv = sum(pv_hourly)
    tot_used = 0.0
    tot_surplus = 0.0
    tot_deficit = 0.0
    tot_batt_charge = 0.0
    tot_batt_discharge = 0.0
    
    for h in range(24):
        dem = load[h]
        gen = pv_hourly[h]
        
        pv_direct = min(dem, gen)
        rem_pv = max(gen - dem, 0.0)
        rem_dem = max(dem - gen, 0.0)
        
        batt_chg = 0.0
        batt_dis = 0.0
        
        if topology in ["hybrid", "off-grid"]:
            # Surplus PV men-charge baterai
            if rem_pv > 0 and battery_cap_kwh > 0:
                space = (battery_cap_kwh - soc_kwh) / battery_eff
                batt_chg = min(rem_pv, space)
                soc_kwh += batt_chg * battery_eff
                rem_pv -= batt_chg
            
            # Defisit daya diambil dari baterai
            if rem_dem > 0 and battery_cap_kwh > 0:
                avail = (soc_kwh - min_soc_kwh) * battery_eff
                batt_dis = min(rem_dem, avail)
                soc_kwh -= batt_dis / battery_eff
                rem_dem -= batt_dis
                
        surplus = rem_pv
        deficit = rem_dem
        used = pv_direct + batt_dis
        
        tot_used += used
        tot_surplus += surplus
        tot_deficit += deficit
        tot_batt_charge += batt_chg
        tot_batt_discharge += batt_dis
        
        soc_pct = (soc_kwh / battery_cap_kwh * 100.0) if battery_cap_kwh > 0 else 0.0
        
        rows.append({
            "hour": h,
            "load": dem,
            "pv": gen,
            "used": used,
            "surplus": surplus,
            "deficit": deficit,
            "batt_charge": batt_chg,
            "batt_discharge": batt_dis,
            "soc_pct": soc_pct
        })
        
    sc_pct = (tot_used / tot_pv * 100.0) if tot_pv > 0 else 0.0
    sf_pct = (tot_used / tot_load * 100.0) if tot_load > 0 else 0.0
    psh = sum(solar_irr.get(h, 0.0) for h in range(24)) / 1000.0
    
    summary = {
        "total_load": tot_load,
        "total_pv": tot_pv,
        "total_used": tot_used,
        "total_surplus": tot_surplus,
        "total_deficit": tot_deficit,
        "self_consumption_pct": sc_pct,
        "solar_fraction_pct": sf_pct,
        "psh": psh,
        "specific_yield": psh * pr
    }
    return rows, summary

def auto_size_capacity(
    load: list[float],
    solar_irr: dict[int, float],
    pr: float,
    target_sc: float,
    step: float = 50.0,
    max_kwp: float = 10000.0
) -> float:
    best = step
    k = step
    while k <= max_kwp:
        _, s = dispatch_simulation(load, solar_irr, pr, k, topology="on-grid")
        if s["self_consumption_pct"] >= target_sc:
            best = k
        else:
            break
        k += step
    return best
```

- [ ] **Step 4: Jalankan test kembali dan pastikan lulus**

Run: `python3 tests/test_dispatch.py`
Expected: Output `ALL TESTS PASSED`.

---

### Task 6: Core Economics Engine (Finansial, LCOE, NPV, Payback)

**Files:**
- Create: `core/economics.py`
- Test: `tests/test_economics.py`

**Interfaces:**
- Consumes: Sizing result, tarif PLN, biaya komponen, PR & degradasi.
- Produces: `calc_financial_metrics(...) -> dict`

- [ ] **Step 1: Tulis unit test untuk financial engine**

```python
# tests/test_economics.py
from core.economics import calc_financial_metrics

def test_financial_metrics():
    res = calc_financial_metrics(
        kwp=100.0,
        battery_kwh=0.0,
        annual_energy_kwh=140000.0,
        tarif_pln=1444.7,
        mod_cost_wp=3500.0,
        inv_cost_w=1200.0,
        battery_cost_kwh=0.0,
        discount_rate=0.08,
        years=25
    )
    assert res["capex"] > 0
    assert res["payback_years"] > 0
    assert res["lcoe_per_kwh"] > 0

if __name__ == "__main__":
    test_financial_metrics()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: Jalankan test dan pastikan gagal**

Run: `python3 tests/test_economics.py`
Expected: ImportError.

- [ ] **Step 3: Implementasikan core/economics.py**

```python
def calc_financial_metrics(
    kwp: float,
    battery_kwh: float,
    annual_energy_kwh: float,
    tarif_pln: float = 1444.70,
    mod_cost_wp: float = 3500.0,
    inv_cost_w: float = 1200.0,
    battery_cost_kwh: float = 3500000.0,
    bos_cost_pct: float = 0.15,
    opex_pct: float = 0.015,
    discount_rate: float = 0.08,
    degradation_rate: float = 0.007,
    years: int = 25
) -> dict:
    pv_cost = kwp * 1000.0 * mod_cost_wp
    inv_cost = kwp * 1000.0 * inv_cost_w
    bat_cost = battery_kwh * battery_cost_kwh
    base_component = pv_cost + inv_cost + bat_cost
    bos_cost = base_component * bos_cost_pct
    capex = base_component + bos_cost
    
    annual_opex = capex * opex_pct
    
    # Arus kas 25 tahun
    npv = -capex
    cum_cash = -capex
    payback_years = None
    
    pv_discounted_costs = capex
    pv_discounted_energy = 0.0
    
    for t in range(1, years + 1):
        eff = (1.0 - (t - 1) * degradation_rate)
        gen_t = annual_energy_kwh * eff
        saving_t = gen_t * tarif_pln
        net_cash_t = saving_t - annual_opex
        
        # Payback period
        cum_cash_prev = cum_cash
        cum_cash += net_cash_t
        if cum_cash >= 0 and payback_years is None:
            payback_years = (t - 1) + (-cum_cash_prev / net_cash_t)
            
        discount_factor = (1.0 + discount_rate) ** t
        npv += net_cash_t / discount_factor
        
        pv_discounted_costs += annual_opex / discount_factor
        pv_discounted_energy += gen_t / discount_factor
        
    lcoe = pv_discounted_costs / pv_discounted_energy if pv_discounted_energy > 0 else 0.0
    
    return {
        "capex": capex,
        "annual_opex": annual_opex,
        "first_year_saving": annual_energy_kwh * tarif_pln,
        "payback_years": payback_years if payback_years is not None else float("inf"),
        "npv": npv,
        "lcoe_per_kwh": lcoe
    }
```

- [ ] **Step 4: Jalankan test kembali dan pastikan lulus**

Run: `python3 tests/test_economics.py`
Expected: Output `ALL TESTS PASSED`.

---

### Task 7: Full Assert Integration Suite

**Files:**
- Create: `tests/test_core.py`

**Interfaces:**
- Menghubungkan seluruh fungsi di `core/` dalam skenario pengujian komprehensif.

- [x] **Step 1: Tulis tes integrasi lengkap**

```python
# tests/test_core.py
from core.data_loader import blocks_to_hourly
from core.sizing import size_pv_system, calc_dimensions, size_battery_bank
from core.dispatch import dispatch_simulation
from core.economics import calc_financial_metrics

def test_full_pipeline_on_grid():
    blocks = [
        (0, 6, 89.0), (6, 9, 98.0), (9, 12, 180.0),
        (12, 15, 208.0), (15, 18, 167.0), (18, 21, 79.0), (21, 24, 59.0)
    ]
    load = blocks_to_hourly(blocks)
    solar = {
        7: 153.33, 8: 296.22, 9: 418.92, 10: 513.06, 11: 572.25,
        12: 592.44, 13: 572.25, 14: 513.06, 15: 418.92, 16: 296.22, 17: 153.33
    }
    modul = {
        "pmax": 550.0, "voc": 49.5, "vmp": 41.5, "isc": 14.0,
        "kvoc": -0.28, "kvmp": -0.35, "length_mm": 2278, "width_mm": 1134
    }
    inv = {
        "pac_kw": 50.0, "mppt_min": 500.0, "mppt_max": 850.0, "vdc_max": 1000.0,
        "n_mppt": 4, "imax_mppt": 30.0, "string_per_mppt": 2
    }
    
    pv_res = size_pv_system(1350.0, modul, inv, 18.0, 50.0)
    assert pv_res["n_inverter"] == 17
    assert pv_res["status_vdc"] is True
    
    rows, summary = dispatch_simulation(load, solar, pr=0.8, kwp=1350.0, topology="on-grid")
    assert round(summary["total_load"]) == 2907
    
    dims = calc_dimensions(pv_res["n_modul"], modul["length_mm"], modul["width_mm"])
    assert dims["area_bruto_m2"] > 0
    
    econ = calc_financial_metrics(1350.0, 0.0, summary["total_used"]*365.0)
    assert econ["capex"] > 0

if __name__ == "__main__":
    test_full_pipeline_on_grid()
    print("INTEGRATION SUITE PASSED")
```

- [x] **Step 2: Jalankan full integration test**

Run: `python3 tests/test_core.py`
Expected: Output `INTEGRATION SUITE PASSED`.

---

### Task 8: Streamlit Application UI Implementation

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: All `core/` functions and `presets.json`.
- Produces: Interactive GUI on Streamlit with reactive inputs, tabs, Plotly charts, and Excel exporter.

- [x] **Step 1: Implementasikan app.py**

Membangun antarmuka Streamlit:
- Form konfigurasi Topologi (On-Grid / Off-Grid / Hybrid).
- Input Beban (Tab Upload File CSV/XLSX vs Tab Manual Form).
- Input Radiasi (Tab API Renewables.ninja dengan pilihan Kota Indonesia vs Tab Upload).
- Dropdown Preset Modul, Inverter, Baterai.
- Parameter Sizing (kWp / Target SC, Tmin, Tmax, Luas atap).
- Visualisasi Plotly: Kurva Beban vs PV 24 Jam, Kurva SOC Baterai, Kurva Arus Kas 25 Tahun.
- Tabel hasil breakdown stringing per inverter.
- Tombol download template input dan tombol ekspor report `.xlsx`.

- [x] **Step 2: Uji startup Streamlit headless**

Run: `python3 -m streamlit help`
Expected: Streamlit CLI output ready.

---

### Task 9: End-to-End Verification

- [x] **Step 1: Validasi kalkulasi UI dan ekspor Excel**

Eksekusi skrip end-to-end headless runner untuk memverifikasi ekspor xlsx dan kalkulasi tanpa crash.
Expected: File Excel berhasil dibuat dengan multi-sheet (Input, Sizing, Dispatch, Financial).
