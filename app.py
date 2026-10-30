import json
import os
import io
import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.data_loader import (
    blocks_to_hourly,
    parse_load_profile_csv,
    parse_load_profile_excel,
    parse_solar_profile,
    generate_load_template_csv,
)
from core.sizing import size_pv_system, calc_dimensions, size_battery_bank
from core.dispatch import dispatch_simulation, auto_size_capacity
from core.economics import calc_financial_metrics
from core.ninja_client import fetch_pv_profile
from core.exporter import export_to_excel

# Konfigurasi Halaman
st.set_page_config(
    page_title="Sizing PLTS Multi-Topologi",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk gaya Engineering-Clean (ENERGY 1 / RHYTHM 1 / MOTION 1)
st.markdown("""
<style>
    /* Tipografi & Padding Ramping */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
        max-width: 1200px;
    }
    /* Kartu Metrik Teknik */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.45rem;
        font-weight: 700;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
    }
    /* Tombol Bersih */
    button[kind="primary"] {
        border-radius: 4px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    /* Header Ringkas */
    h1 {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin-bottom: 0.2rem !important;
    }
    h2 {
        font-size: 1.25rem !important;
        font-weight: 600 !important;
        color: #1E293B !important;
        border-bottom: 1px solid #E2E8F0;
        padding-bottom: 6px;
        margin-top: 1.5rem !important;
    }
    h3 {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
    }
</style>
""", unsafe_allow_html=True)

# Muat Basis Data Komponen
PRESET_PATH = os.path.join(os.path.dirname(__file__), "presets.json")
with open(PRESET_PATH, "r") as f:
    PRESETS = json.load(f)

# Koordinat Kota Referensi Indonesia
INDONESIA_CITIES = {
    "Jakarta": (-6.2088, 106.8456),
    "Surabaya": (-7.2575, 112.7521),
    "Kupang": (-10.1772, 123.6070),
    "Medan": (3.5952, 98.6722),
    "Makassar": (-5.1477, 119.4327),
    "Denpasar": (-8.6705, 115.2126),
    "Kustom": (0.0, 0.0)
}

# Profil Surya Acuan Standar (Data Tipikal Wilayah Indonesia Timur)
DEFAULT_SOLAR = {
    7: 153.33, 8: 296.22, 9: 418.92, 10: 513.06, 11: 572.25,
    12: 592.44, 13: 572.25, 14: 513.06, 15: 418.92, 16: 296.22, 17: 153.33
}

# State Session
if "solar_irr" not in st.session_state:
    st.session_state["solar_irr"] = {h: DEFAULT_SOLAR.get(h, 0.0) for h in range(24)}
if "calc_results" not in st.session_state:
    st.session_state["calc_results"] = None

# ==============================================================================
# SIDEBAR: PARAMETER SISTEM
# ==============================================================================
st.sidebar.markdown("### Konfigurasi Sistem")

topology = st.sidebar.selectbox(
    "Topologi Sistem",
    options=["On-Grid", "Off-Grid", "Hybrid"],
    index=0,
    help="On-Grid: Tanpa baterai | Off-Grid: Sistem mandiri baterai | Hybrid: Grid dengan cadangan baterai"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Radiasi Surya")
solar_source = st.sidebar.radio(
    "Sumber Data Radiasi",
    options=["API Renewables.ninja", "Manual / File Lokal"],
    index=1
)

if solar_source == "API Renewables.ninja":
    ninja_token = st.sidebar.text_input("API Token Renewables.ninja", type="password")
    city_choice = st.sidebar.selectbox("Lokasi Referensi", options=list(INDONESIA_CITIES.keys()), index=2)
    
    if city_choice == "Kustom":
        c_lat = st.sidebar.number_input("Latitude", value=-6.2088, format="%.4f")
        c_lon = st.sidebar.number_input("Longitude", value=106.8456, format="%.4f")
    else:
        c_lat, c_lon = INDONESIA_CITIES[city_choice]
        st.sidebar.caption(f"Koordinat: {c_lat:.4f}, {c_lon:.4f}")
        
    tilt = st.sidebar.number_input("Sudut Kemiringan Modul / Tilt (°)", value=15.0, min_value=0.0, max_value=90.0, step=1.0)
    azim = st.sidebar.number_input("Orientasi / Azimuth (°)", value=180.0, min_value=0.0, max_value=360.0, step=5.0)

    if st.sidebar.button("Ambil Data Radiasi", use_container_width=True):
        if not ninja_token:
            st.sidebar.error("Token API Renewables.ninja diperlukan.")
        else:
            with st.sidebar.status("Menghubungi endpoint Renewables.ninja..."):
                try:
                    profile = fetch_pv_profile(ninja_token, c_lat, c_lon, tilt, azim)
                    st.session_state["solar_irr"] = {h: profile.get(h, 0.0) * 1000.0 for h in range(24)}
                    st.sidebar.success("Data radiasi berhasil diperbarui.")
                except Exception as e:
                    st.sidebar.error(f"Gagal mengambil data: {e}")
else:
    manual_solar_type = st.sidebar.selectbox(
        "Metode Input Radiasi",
        options=["Data Standar Default", "Input Nilai PSH Langsung", "Upload File CSV/Excel", "Input Per Jam Manual"]
    )
    if manual_solar_type == "Data Standar Default":
        st.session_state["solar_irr"] = {h: DEFAULT_SOLAR.get(h, 0.0) for h in range(24)}
        st.sidebar.caption("Memakai data radiasi standar pengujian (PSH ~4.50 Jam/Hari).")
    elif manual_solar_type == "Input Nilai PSH Langsung":
        psh_in = st.sidebar.number_input("Target PSH (Jam/Hari)", value=4.5, min_value=1.0, max_value=8.0, step=0.1)
        tot_weight = sum([math.sin(math.pi * (h - 6) / 12) for h in range(6, 19)])
        st.session_state["solar_irr"] = {
            h: ((psh_in * 1000.0) * math.sin(math.pi * (h - 6) / 12) / tot_weight) if 6 <= h <= 18 else 0.0
            for h in range(24)
        }
    elif manual_solar_type == "Upload File CSV/Excel":
        s_file = st.sidebar.file_uploader("Pilih File Radiasi", type=["csv", "xlsx", "xls"])
        if s_file is not None:
            try:
                st.session_state["solar_irr"] = parse_solar_profile(s_file)
                st.sidebar.success("File radiasi berhasil dimuat.")
            except Exception as e:
                st.sidebar.error(f"Kesalahan file radiasi: {e}")
    else:
        with st.sidebar.expander("Tabel Iradiansi Per Jam (W/m²)", expanded=False):
            t_irr = {}
            for h in range(24):
                def_val = float(st.session_state["solar_irr"].get(h, 0.0))
                t_irr[h] = st.number_input(f"Jam {h:02d}:00", value=def_val, min_value=0.0, step=10.0, key=f"irr_h_{h}")
            st.session_state["solar_irr"] = t_irr

st.sidebar.markdown("---")
st.sidebar.markdown("### Parameter Rekayasa & Finansial")
pr_val = st.sidebar.number_input("Performance Ratio (PR)", value=0.80, min_value=0.5, max_value=1.0, step=0.01)
tmin_val = st.sidebar.number_input("Suhu Minimum Desain (°C)", value=18.0, step=1.0)
tmax_sel_val = st.sidebar.number_input("Suhu Maksimum Sel PV (°C)", value=50.0, step=1.0)

with st.sidebar.expander("Parameter Biaya & Nilai Uang", expanded=False):
    tarif_pln = st.number_input("Tarif Listrik PLN (Rp/kWh)", value=1444.70, step=10.0)
    disc_rate = st.number_input("Suku Diskonto (%)", value=8.0, step=0.5) / 100.0
    degrad_rate = st.number_input("Laju Degradasi Modul (%/Tahun)", value=0.7, step=0.1) / 100.0
    bos_cost_pct = st.number_input("Biaya BoS & Instalasi (%)", value=15.0, step=1.0) / 100.0
    opex_pct = st.number_input("Biaya OPEX Tahunan (% CAPEX)", value=1.5, step=0.1) / 100.0

# ==============================================================================
# HALAMAN UTAMA
# ==============================================================================
psh_current = sum(st.session_state["solar_irr"].values()) / 1000.0
st.title("Sistem Perancangan PLTS Multi-Topologi")
st.caption(f"Topologi aktif: {topology} | Nilai PSH radiasi: {psh_current:.2f} Jam/Hari")

# ------------------------------------------------------------------------------
# BAGIAN 1: PROFIL BEBAN
# ------------------------------------------------------------------------------
st.header("1. Profil Beban 24 Jam")
load_tab1, load_tab2 = st.tabs(["Tabel Blok Waktu", "Unggah Berkas CSV / Excel"])

load_hourly = [0.0] * 24

with load_tab1:
    st.write("Masukkan konsumsi daya rata-rata (kW) berdasarkan blok waktu operasional:")
    default_blocks = [
        {"Mulai": 0, "Selesai": 6, "Daya_kW": 89.0},
        {"Mulai": 6, "Selesai": 9, "Daya_kW": 98.0},
        {"Mulai": 9, "Selesai": 12, "Daya_kW": 180.0},
        {"Mulai": 12, "Selesai": 15, "Daya_kW": 208.0},
        {"Mulai": 15, "Selesai": 18, "Daya_kW": 167.0},
        {"Mulai": 18, "Selesai": 21, "Daya_kW": 79.0},
        {"Mulai": 21, "Selesai": 24, "Daya_kW": 59.0},
    ]
    block_df = st.data_editor(pd.DataFrame(default_blocks), num_rows="dynamic", use_container_width=True)
    try:
        raw_blocks = [(int(r["Mulai"]), int(r["Selesai"]), float(r["Daya_kW"])) for _, r in block_df.iterrows()]
        load_hourly = blocks_to_hourly(raw_blocks)
        st.info(f"Total energi beban harian: {sum(load_hourly):,.1f} kWh/hari")
    except Exception as e:
        st.error(f"Konfigurasi beban belum valid: {e}")

with load_tab2:
    st.write("Unggah berkas beban 24 jam (atau interval 15 menit):")
    up_load_file = st.file_uploader("Pilih Berkas CSV atau Excel", type=["csv", "xlsx", "xls"], key="uploader_load")
    
    st.download_button(
        label="Unduh Format Template CSV",
        data=generate_load_template_csv(),
        file_name="template_beban.csv",
        mime="text/csv"
    )
    if up_load_file is not None:
        try:
            if up_load_file.name.endswith((".xlsx", ".xls")):
                load_hourly = parse_load_profile_excel(up_load_file)
            else:
                load_hourly = parse_load_profile_csv(up_load_file)
            st.success(f"Berkas berhasil dimuat. Total energi beban harian: {sum(load_hourly):,.1f} kWh/hari")
        except Exception as e:
            st.error(f"Gagal memproses berkas beban: {e}")

# ------------------------------------------------------------------------------
# BAGIAN 2: SPESIFIKASI KOMPONEN
# ------------------------------------------------------------------------------
st.header("2. Spesifikasi Komponen Sistem")

col_mod, col_inv = st.columns(2)

with col_mod:
    st.subheader("Modul PV")
    mod_presets = PRESETS.get("modules", [])
    mod_names = [m["name"] for m in mod_presets]
    sel_mod_name = st.selectbox("Pilih Model Modul", options=mod_names, index=0)
    sel_mod = next(m for m in mod_presets if m["name"] == sel_mod_name)
    
    c_m1, c_m2 = st.columns(2)
    pmax_in = c_m1.number_input("Daya Nominal Pmax (Wp)", value=float(sel_mod["pmax"]), step=5.0)
    voc_in = c_m2.number_input("Tegangan Rangkaian Terbuka Voc (V)", value=float(sel_mod["voc"]), step=0.1)
    vmp_in = c_m1.number_input("Tegangan Daya Puncak Vmp (V)", value=float(sel_mod["vmp"]), step=0.1)
    isc_in = c_m2.number_input("Arus Hubung Singkat Isc (A)", value=float(sel_mod["isc"]), step=0.1)
    kvoc_in = c_m1.number_input("Koefisien Suhu Voc (%/°C)", value=float(sel_mod["kvoc"]), step=0.01)
    kvmp_in = c_m2.number_input("Koefisien Suhu Vmp (%/°C)", value=float(sel_mod["kvmp"]), step=0.01)
    len_in = c_m1.number_input("Panjang Fisik (mm)", value=float(sel_mod["length_mm"]), step=10.0)
    wid_in = c_m2.number_input("Lebar Fisik (mm)", value=float(sel_mod["width_mm"]), step=10.0)
    cost_wp_in = c_m1.number_input("Harga Modul (Rp/Wp)", value=float(sel_mod.get("cost_per_wp", 3500)), step=100.0)

    mod_spec = {
        "name": sel_mod_name, "pmax": pmax_in, "voc": voc_in, "vmp": vmp_in, "isc": isc_in,
        "kvoc": kvoc_in, "kvmp": kvmp_in, "length_mm": len_in, "width_mm": wid_in, "cost_per_wp": cost_wp_in
    }

with col_inv:
    st.subheader("Inverter")
    inv_presets = PRESETS.get("inverters", [])
    inv_names = [i["name"] for i in inv_presets]
    sel_inv_name = st.selectbox("Pilih Model Inverter", options=inv_names, index=0)
    sel_inv = next(i for i in inv_presets if i["name"] == sel_inv_name)
    
    c_i1, c_i2 = st.columns(2)
    pac_in = c_i1.number_input("Kapasitas AC Nominal (kW)", value=float(sel_inv["pac_kw"]), step=5.0)
    vdc_max_in = c_i2.number_input("Tegangan DC Maksimum (V)", value=float(sel_inv["vdc_max"]), step=50.0)
    mppt_min_in = c_i1.number_input("Batas Bawah MPPT (V)", value=float(sel_inv["mppt_min"]), step=20.0)
    mppt_max_in = c_i2.number_input("Batas Atas MPPT (V)", value=float(sel_inv["mppt_max"]), step=20.0)
    n_mppt_in = c_i1.number_input("Jumlah MPPT per Unit", value=int(sel_inv["n_mppt"]), step=1)
    imax_in = c_i2.number_input("Arus Maksimum per MPPT (A)", value=float(sel_inv["imax_mppt"]), step=1.0)
    str_per_mppt_in = c_i1.number_input("Maksimum String per MPPT", value=int(sel_inv["string_per_mppt"]), step=1)
    inv_cost_w_in = c_i2.number_input("Harga Inverter (Rp/W)", value=float(sel_inv.get("cost_per_w", 1200)), step=50.0)

    inv_spec = {
        "name": sel_inv_name, "pac_kw": pac_in, "vdc_max": vdc_max_in,
        "mppt_min": mppt_min_in, "mppt_max": mppt_max_in, "n_mppt": n_mppt_in,
        "imax_mppt": imax_in, "string_per_mppt": str_per_mppt_in,
        "efficiency": float(sel_inv.get("efficiency", 0.98)), "cost_per_w": inv_cost_w_in
    }

bat_spec = None
autonomy_days = 1.0
dod_val = 0.85
v_sys_val = 48.0

if topology in ["Off-Grid", "Hybrid"]:
    st.subheader("Penyimpanan Energi (Bank Baterai)")
    bat_presets = PRESETS.get("batteries", [])
    bat_names = [b["name"] for b in bat_presets]
    sel_bat_name = st.selectbox("Pilih Model Baterai", options=bat_names, index=0)
    sel_bat = next(b for b in bat_presets if b["name"] == sel_bat_name)
    
    cb1, cb2, cb3, cb4 = st.columns(4)
    autonomy_days = cb1.number_input("Hari Otonomi", value=1.0, min_value=0.1, step=0.5)
    dod_val = cb2.number_input("DoD Maksimum (%)", value=float(sel_bat.get("dod_max", 0.85) * 100.0), min_value=10.0, max_value=100.0, step=5.0) / 100.0
    v_sys_val = cb3.number_input("Tegangan Sistem DC (V)", value=float(sel_bat.get("voltage_nominal", 48.0)), step=12.0)
    bat_cost_in = cb4.number_input("Harga Baterai (Rp/kWh)", value=float(sel_bat.get("cost_per_kwh", 3500000)), step=100000.0)
    
    bat_spec = {
        "name": sel_bat_name,
        "voltage_nominal": float(sel_bat.get("voltage_nominal", 48.0)),
        "capacity_ah": float(sel_bat.get("capacity_ah", 100.0)),
        "dod_max": dod_val,
        "efficiency": float(sel_bat.get("efficiency", 0.95)),
        "cost_per_kwh": bat_cost_in
    }

st.subheader("Batasan Luas Area")
available_area = st.number_input("Luas Atap atau Lahan Tersedia (m²) [Isi 0 jika tidak dibatasi]", value=0.0, step=50.0)

# ------------------------------------------------------------------------------
# BAGIAN 3: TARGET SIZING
# ------------------------------------------------------------------------------
st.header("3. Kriteria Sizing")
cs1, cs2 = st.columns(2)
kwp_input = cs1.number_input(
    "Target Kapasitas PV (kWp) [Isi 0 untuk Auto-Sizing]",
    value=1350.0,
    min_value=0.0,
    step=25.0,
    help="Ketik 0 jika ingin sistem menghitung kapasitas optimal berdasarkan target self-consumption."
)
target_sc_input = cs2.number_input(
    "Target Minimum Self Consumption (%) [Mode Auto]",
    value=40.0,
    min_value=5.0,
    max_value=100.0,
    step=5.0
)

st.write("")
if st.button("Kalkulasi Sizing & Kinerja", type="primary", use_container_width=True):
    try:
        kwp_calc = kwp_input
        if kwp_calc <= 0:
            with st.spinner("Menghitung kapasitas optimal..."):
                kwp_calc = auto_size_capacity(
                    load_hourly,
                    st.session_state["solar_irr"],
                    pr_val,
                    target_sc_input,
                    step=50.0
                )
                st.info(f"Kapasitas hasil optimasi: {kwp_calc:.1f} kWp")

        pv_res = size_pv_system(kwp_calc, mod_spec, inv_spec, tmin_val, tmax_sel_val)
        dims = calc_dimensions(pv_res["n_modul"], mod_spec["length_mm"], mod_spec["width_mm"])
        dims["available_area_m2"] = available_area

        bat_res = None
        battery_cap = 0.0
        if topology in ["Off-Grid", "Hybrid"] and bat_spec is not None:
            daily_energy = sum(load_hourly)
            bat_res = size_battery_bank(
                daily_kwh=daily_energy,
                autonomy_days=autonomy_days,
                dod=dod_val,
                v_sys=v_sys_val,
                battery_spec=bat_spec,
                inv_eff=inv_spec["efficiency"]
            )
            battery_cap = bat_res["capacity_kwh"]

        top_param = topology.lower()
        dispatch_rows, dispatch_summary = dispatch_simulation(
            load=load_hourly,
            solar_irr=st.session_state["solar_irr"],
            pr=pr_val,
            kwp=kwp_calc,
            topology=top_param,
            battery_cap_kwh=battery_cap,
            battery_dod_max=dod_val,
            battery_eff=bat_spec.get("efficiency", 0.95) if bat_spec else 0.95
        )

        annual_energy = dispatch_summary["total_used"] * 365.0
        econ = calc_financial_metrics(
            kwp=kwp_calc,
            battery_kwh=battery_cap,
            annual_energy_kwh=annual_energy,
            tarif_pln=tarif_pln,
            mod_cost_wp=mod_spec["cost_per_wp"],
            inv_cost_w=inv_spec["cost_per_w"],
            battery_cost_kwh=bat_spec.get("cost_per_kwh", 0.0) if bat_spec else 0.0,
            bos_cost_pct=bos_cost_pct,
            opex_pct=opex_pct,
            discount_rate=disc_rate,
            degradation_rate=degrad_rate,
            years=25
        )

        st.session_state["calc_results"] = {
            "topology": topology,
            "kwp": kwp_calc,
            "pr": pr_val,
            "tmin": tmin_val,
            "tmax_sel": tmax_sel_val,
            "psh": dispatch_summary["psh"],
            "module_spec": mod_spec,
            "inverter_spec": inv_spec,
            "battery_spec": bat_spec,
            "battery_res": bat_res,
            "pv_res": pv_res,
            "dims": dims,
            "dispatch_rows": dispatch_rows,
            "dispatch_summary": dispatch_summary,
            "solar_irr": st.session_state["solar_irr"],
            "economics": econ
        }
    except Exception as e:
        st.error(f"Perhitungan gagal: {e}")

# ------------------------------------------------------------------------------
# AREA HASIL & LAPORAN
# ------------------------------------------------------------------------------
res = st.session_state["calc_results"]

if res is None:
    # Empty State informatif
    st.markdown("""
    <div style="background-color: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 8px; padding: 32px; text-align: center; margin-top: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #334155;">Sistem Belum Dihitung</h4>
        <p style="margin: 0; color: #64748B; font-size: 0.9rem;">
            Tentukan profil beban dan spesifikasi komponen di atas, lalu tekan tombol <strong>Kalkulasi Sizing & Kinerja</strong> untuk melihat hasil analisis lengkap.
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.header("Ringkasan Hasil Perancangan")

    # Panel 1: Kinerja Daya & Energi
    st.subheader("Indikator Kinerja Listrik")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kapasitas Terpasang", f"{res['kwp']:,.1f} kWp")
    m2.metric("Rasio DC / AC", f"{res['pv_res']['dc_ac_ratio']:.2f}")
    m3.metric("Self Consumption", f"{res['dispatch_summary']['self_consumption_pct']:.1f}%")
    m4.metric("Solar Fraction", f"{res['dispatch_summary']['solar_fraction_pct']:.1f}%")

    # Panel 2: Konfigurasi Komponen Fisik
    st.subheader("Konfigurasi Peralatan Fisik")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Modul Surya", f"{res['pv_res']['n_modul']:,} Unit")
    c2.metric("Total Unit Inverter", f"{res['pv_res']['n_inverter']:,} Unit")
    
    if res["battery_res"]:
        c3.metric("Kapasitas Bank Baterai", f"{res['battery_res']['capacity_kwh']:.0f} kWh", f"{res['battery_res']['total_units']} unit")
    else:
        c3.metric("Bank Baterai", "Tidak Digunakan")

    avail_area = res["dims"]["available_area_m2"]
    bruto_area = res["dims"]["area_bruto_m2"]
    label_area = f"{bruto_area:,.0f} m²" if avail_area == 0 else f"{bruto_area:,.0f} / {avail_area:,.0f} m²"
    delta_area = "Cukup" if (avail_area == 0 or bruto_area <= avail_area) else "Lahan Kurang"
    c4.metric("Estimasi Luas Area", label_area, delta_area)

    # Verifikasi Batas Teknis Inverter
    st.subheader("Verifikasi Batas Teknis Inverter")
    pv_r = res["pv_res"]
    inv_s = res["inverter_spec"]
    
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        stat_vdc = "MEMENUHI" if pv_r["status_vdc"] else "MELEBIHI BATAS"
        col_t1.metric("Tegangan Voc Suhu Dingin", f"{pv_r['voc_max_act']:.1f} V", f"Maks {inv_s['vdc_max']:.0f} V ({stat_vdc})")
    with col_t2:
        stat_mppt = "MEMENUHI" if pv_r["status_mppt"] else "DI LUAR RENTANG"
        col_t2.metric("Rentang Operasi Vmp", f"{pv_r['mppt_lo_act']:.1f} - {pv_r['voc_max_act']:.1f} V", f"MPPT: {inv_s['mppt_min']:.0f}-{inv_s['mppt_max']:.0f} V ({stat_mppt})")
    with col_t3:
        stat_arus = "MEMENUHI" if pv_r["status_arus"] else "MELEBIHI BATAS"
        col_t3.metric("Arus Masuk per MPPT", f"{pv_r['arus_mppt_act']:.1f} A", f"Maks {inv_s['imax_mppt']:.1f} A ({stat_arus})")

    # Visualisasi Kurva 24 Jam
    st.subheader("Kurva Aliran Daya Harian")
    df_disp = pd.DataFrame(res["dispatch_rows"])
    
    fig = go.Figure()
    # Warna disiplin keteknikan: Slate-700 untuk beban, Amber-600 untuk PV, Emerald untuk energi bersih
    fig.add_trace(go.Scatter(
        x=df_disp["hour"], y=df_disp["load"], mode="lines+markers",
        name="Beban (kW)", line=dict(color="#334155", width=2.2)
    ))
    fig.add_trace(go.Scatter(
        x=df_disp["hour"], y=df_disp["pv"], mode="lines",
        name="Produksi PV (kW)", line=dict(color="#D97706", width=2.5, dash="dash")
    ))
    fig.add_trace(go.Scatter(
        x=df_disp["hour"], y=df_disp["used"], mode="lines",
        name="Daya PV Terpakai Sendiri (kW)", fill="tozeroy",
        line=dict(color="#059669", width=1.5), fillcolor="rgba(5, 150, 105, 0.15)"
    ))
    fig.add_trace(go.Scatter(
        x=df_disp["hour"], y=df_disp["surplus"], mode="lines",
        name="Surplus Ekspor (kW)", line=dict(color="#2563EB", width=1.5)
    ))
    fig.add_trace(go.Scatter(
        x=df_disp["hour"], y=df_disp["deficit"], mode="lines",
        name="Defisit Impor Grid (kW)", line=dict(color="#DC2626", width=1.5)
    ))

    fig.update_layout(
        xaxis=dict(title="Jam Operasional", tickmode="linear", tick0=0, dtick=1, gridcolor="#F1F5F9"),
        yaxis=dict(title="Daya Aktif (kW)", gridcolor="#F1F5F9"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        margin=dict(l=30, r=30, t=30, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Kurva SOC jika menggunakan baterai
    if res["topology"] in ["Off-Grid", "Hybrid"] and res["battery_res"]:
        st.subheader("Kurva State of Charge (SOC) Baterai")
        fig_soc = go.Figure()
        fig_soc.add_trace(go.Scatter(
            x=df_disp["hour"],
            y=df_disp["soc_pct"],
            mode="lines+markers",
            name="SOC (%)",
            line=dict(color="#0284C7", width=2.0),
            fill="tozeroy",
            fillcolor="rgba(2, 132, 199, 0.12)"
        ))
        fig_soc.update_layout(
            xaxis=dict(title="Jam Operasional", tickmode="linear", tick0=0, dtick=1, gridcolor="#F1F5F9"),
            yaxis=dict(title="Persentase Kapasitas SOC (%)", range=[0, 105], gridcolor="#F1F5F9"),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            hovermode="x unified",
            margin=dict(l=30, r=30, t=30, b=30)
        )
        st.plotly_chart(fig_soc, use_container_width=True)

    # Tabel Rincian String
    st.subheader("Konfigurasi String per Unit Inverter")
    layout_data = []
    for row in pv_r.get("layout", []):
        layout_data.append({
            "Unit Inverter": f"Inverter {row['inv_idx']:02d}",
            "String Pola A": row["str_p"],
            "Modul/String A": row["mod_p"],
            "String Pola B": row["str_k"],
            "Modul/String B": row["mod_k"],
            "Total Modul Terhubung": (row["str_p"] * row["mod_p"]) + (row["str_k"] * row["mod_k"])
        })
    st.dataframe(pd.DataFrame(layout_data), use_container_width=True)

    # Analisis Kelayakan Finansial
    st.header("Analisis Finansial Sistem")
    econ_res = res["economics"]
    
    f1, f2, f3, f4, f5 = st.columns(5)
    f1.metric("Investasi Awal (CAPEX)", f"Rp {econ_res['capex']:,.0f}")
    f2.metric("Penghematan Tahun 1", f"Rp {econ_res['first_year_saving']:,.0f}")
    
    pb = econ_res["payback_years"]
    pb_str = f"{pb:.1f} Tahun" if (isinstance(pb, (int, float)) and not math.isinf(pb)) else "> 25 Tahun"
    f3.metric("Payback Period", pb_str)
    f4.metric("Nilai Bersih (NPV 25 Thn)", f"Rp {econ_res['npv']:,.0f}")
    f5.metric("Biaya Energi Rata-Rata (LCOE)", f"Rp {econ_res['lcoe_per_kwh']:,.1f}/kWh")

    # Grafik Arus Kas Kumulatif
    cashflows = econ_res.get("cashflows", [])
    if cashflows:
        cf_df = pd.DataFrame(cashflows)
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(
            x=cf_df["year"],
            y=cf_df["cum_cash"],
            mode="lines+markers",
            name="Kas Kumulatif",
            line=dict(color="#059669", width=2.0)
        ))
        fig_cf.add_hline(y=0, line_dash="dash", line_color="#EF4444", annotation_text="Titik Impas (BEP)")
        fig_cf.update_layout(
            xaxis=dict(title="Tahun Operasional", tickmode="linear", tick0=0, dtick=1, gridcolor="#F1F5F9"),
            yaxis=dict(title="Arus Kas Kumulatif (Rp)", gridcolor="#F1F5F9"),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            hovermode="x unified",
            margin=dict(l=30, r=30, t=30, b=30)
        )
        st.plotly_chart(fig_cf, use_container_width=True)

    # Unduh Berkas Hasil
    st.subheader("Ekspor Dokumen Laporan")
    excel_buf = io.BytesIO()
    export_to_excel(res, excel_buf)
    excel_buf.seek(0)
    
    st.download_button(
        label="Unduh Laporan Format Excel (.xlsx)",
        data=excel_buf,
        file_name=f"Laporan_Sizing_PLTS_{res['topology']}_{int(res['kwp'])}kWp.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
