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
    initial_sidebar_state="collapsed"
)

# Custom CSS untuk gaya Engineering-Clean & Modern UX
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }
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
        font-size: 1.35rem;
        font-weight: 700;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
    }
    h1 {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }
    h2 {
        font-size: 1.25rem !important;
        font-weight: 600 !important;
        color: #1E293B !important;
        border-bottom: 1px solid #E2E8F0;
        padding-bottom: 6px;
        margin-top: 1.2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Muat Basis Data Komponen
PRESET_PATH = os.path.join(os.path.dirname(__file__), "presets.json")
with open(PRESET_PATH, "r") as f:
    PRESETS = json.load(f)

INDONESIA_CITIES = {
    "Jakarta": (-6.2088, 106.8456),
    "Surabaya": (-7.2575, 112.7521),
    "Kupang": (-10.1772, 123.6070),
    "Medan": (3.5952, 98.6722),
    "Makassar": (-5.1477, 119.4327),
    "Denpasar": (-8.6705, 115.2126),
    "Kustom": (0.0, 0.0)
}

DEFAULT_SOLAR = {
    7: 153.33, 8: 296.22, 9: 418.92, 10: 513.06, 11: 572.25,
    12: 592.44, 13: 572.25, 14: 513.06, 15: 418.92, 16: 296.22, 17: 153.33
}

if "solar_irr" not in st.session_state:
    st.session_state["solar_irr"] = {h: DEFAULT_SOLAR.get(h, 0.0) for h in range(24)}
if "calc_results" not in st.session_state:
    st.session_state["calc_results"] = None

st.title("☀️ Aplikasi Perancangan & Sizing PLTS Multi-Topologi")
st.caption("Platform Analisis Tekno-Ekonomi Standar Industri (On-Grid, Off-Grid, Hybrid)")

# ==============================================================================
# WIZARD-STYLE MULTI-STEP NAVIGATION (Peningkatan UX Utama)
# ==============================================================================
step_tab1, step_tab2, step_tab3, step_tab4 = st.tabs([
    "1️⃣ Topologi & Profil Beban",
    "2️⃣ Spesifikasi Komponen & Sizing",
    "3️⃣ Hasil Teknis & Stringing",
    "4️⃣ Analisis Finansial & Laporan"
])

# ------------------------------------------------------------------------------
# TAB 1: TOPOLOGI & PROFIL BEBAN
# ------------------------------------------------------------------------------
with step_tab1:
    st.header("Konfigurasi Topologi & Sumber Radiasi")
    
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        topology = st.selectbox(
            "Topologi Sistem PLTS",
            options=["On-Grid", "Off-Grid", "Hybrid"],
            index=0,
            help="On-Grid: Tanpa baterai | Off-Grid: Sistem mandiri | Hybrid: Grid dengan cadangan baterai"
        )
    with t_col2:
        solar_source = st.selectbox(
            "Sumber Data Radiasi Matahari",
            options=["Data Standar Default Indonesia Timur", "API Renewables.ninja", "Input PSH Langsung", "Upload CSV/Excel", "Input Per Jam Manual"],
            index=0
        )

    if solar_source == "API Renewables.ninja":
        st.subheader("Pengaturan API Renewables.ninja")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        ninja_token = r_col1.text_input("API Token", type="password")
        city_choice = r_col2.selectbox("Lokasi Referensi", options=list(INDONESIA_CITIES.keys()), index=2)
        if city_choice == "Kustom":
            c_lat = r_col3.number_input("Latitude", value=-6.2088, format="%.4f")
            c_lon = r_col4.number_input("Longitude", value=106.8456, format="%.4f")
        else:
            c_lat, c_lon = INDONESIA_CITIES[city_choice]
            r_col3.metric("Latitude", f"{c_lat:.4f}")
            r_col4.metric("Longitude", f"{c_lon:.4f}")

        tilt = st.slider("Sudut Kemiringan Modul / Tilt (°)", 0.0, 90.0, 15.0, 1.0)
        azim = st.slider("Orientasi / Azimuth (°)", 0.0, 360.0, 180.0, 5.0)

        if st.button("Ambil Data Radiasi dari API", type="primary"):
            if not ninja_token:
                st.error("Token API Renewables.ninja wajib diisi.")
            else:
                with st.spinner("Mengambil data radiasi..."):
                    try:
                        profile = fetch_pv_profile(ninja_token, c_lat, c_lon, tilt, azim)
                        st.session_state["solar_irr"] = {h: profile.get(h, 0.0) * 1000.0 for h in range(24)}
                        st.success("Data radiasi berhasil diperbarui dari API.")
                    except Exception as e:
                        st.error(f"Gagal mengambil data: {e}")

    elif solar_source == "Input PSH Langsung":
        psh_in = st.slider("Target Peak Sun Hours (PSH / Jam/Hari)", 1.0, 8.0, 4.5, 0.1)
        tot_weight = sum([math.sin(math.pi * (h - 6) / 12) for h in range(6, 19)])
        st.session_state["solar_irr"] = {
            h: ((psh_in * 1000.0) * math.sin(math.pi * (h - 6) / 12) / tot_weight) if 6 <= h <= 18 else 0.0
            for h in range(24)
        }
        st.info(f"Profil iradiasi disesuaikan untuk target PSH: {psh_in} Jam/Hari.")

    elif solar_source == "Upload CSV/Excel":
        s_file = st.file_uploader("Pilih Berkas Iradiasi (CSV/Excel)", type=["csv", "xlsx", "xls"])
        if s_file is not None:
            try:
                st.session_state["solar_irr"] = parse_solar_profile(s_file)
                st.success("Berkas iradiasi berhasil dimuat.")
            except Exception as e:
                st.error(f"Gagal memuat berkas: {e}")

    elif solar_source == "Input Per Jam Manual":
        with st.expander("Pengaturan Nilai Iradiansi Per Jam (W/m²)", expanded=True):
            t_irr = {}
            cols_h = st.columns(6)
            for h in range(24):
                def_val = float(st.session_state["solar_irr"].get(h, 0.0))
                c_idx = h % 6
                with cols_h[c_idx]:
                    t_irr[h] = st.number_input(f"Jam {h:02d}:00", value=def_val, min_value=0.0, step=10.0, key=f"irr_h_{h}")
            st.session_state["solar_irr"] = t_irr

    st.markdown("---")
    st.header("Profil Beban 24 Jam")
    load_sub1, load_sub2 = st.tabs(["Tabel Blok Waktu Operasional", "Unggah Berkas Beban"])

    load_hourly = [0.0] * 24
    with load_sub1:
        st.write("Tentukan konsumsi daya rata-rata (kW) berdasarkan blok waktu:")
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
            st.success(f"Total Energi Beban Harian: **{sum(load_hourly):,.1f} kWh/hari**")
        except Exception as e:
            st.error(f"Format blok beban belum valid: {e}")

    with load_sub2:
        up_load_file = st.file_uploader("Pilih Berkas CSV atau Excel Profil Beban", type=["csv", "xlsx", "xls"], key="up_load_tab1")
        st.download_button("Unduh Template CSV Beban", data=generate_load_template_csv(), file_name="template_beban.csv", mime="text/csv")
        if up_load_file is not None:
            try:
                load_hourly = parse_load_profile_excel(up_load_file) if up_load_file.name.endswith((".xlsx", ".xls")) else parse_load_profile_csv(up_load_file)
                st.success(f"Berhasil memuat beban. Total: {sum(load_hourly):,.1f} kWh/hari")
            except Exception as e:
                st.error(f"Gagal memuat berkas: {e}")

# ------------------------------------------------------------------------------
# TAB 2: SPESIFIKASI KOMPONEN & SIZING
# ------------------------------------------------------------------------------
with step_tab2:
    st.header("Spesifikasi Komponen & Kriteria Sizing")

    c_mod_col, c_inv_col = st.columns(2)
    with c_mod_col:
        st.subheader("Modul PV")
        mod_presets = PRESETS.get("modules", [])
        mod_names = [m["name"] for m in mod_presets]
        sel_mod_name = st.selectbox("Pilih Model Modul", options=mod_names, index=0)
        sel_mod = next(m for m in mod_presets if m["name"] == sel_mod_name)
        
        # Tampilkan badge ringkas spesifikasi utama
        st.info(f"**Pmax:** {sel_mod['pmax']} Wp | **Voc:** {sel_mod['voc']}V | **Vmp:** {sel_mod['vmp']}V | **Efisiensi:** ~21%")

        with st.expander("⚙️ Edit Parameter Teknis Lanjutan Modul", expanded=False):
            c_m1, c_m2 = st.columns(2)
            pmax_in = c_m1.number_input("Daya Pmax (Wp)", value=float(sel_mod["pmax"]), step=5.0)
            voc_in = c_m2.number_input("Voc (V)", value=float(sel_mod["voc"]), step=0.1)
            vmp_in = c_m1.number_input("Vmp (V)", value=float(sel_mod["vmp"]), step=0.1)
            isc_in = c_m2.number_input("Isc (A)", value=float(sel_mod["isc"]), step=0.1)
            kvoc_in = c_m1.number_input("Koef. Voc (%/°C)", value=float(sel_mod["kvoc"]), step=0.01)
            kvmp_in = c_m2.number_input("Koef. Vmp (%/°C)", value=float(sel_mod["kvmp"]), step=0.01)
            len_in = c_m1.number_input("Panjang (mm)", value=float(sel_mod["length_mm"]), step=10.0)
            wid_in = c_m2.number_input("Lebar (mm)", value=float(sel_mod["width_mm"]), step=10.0)
            cost_wp_in = c_m1.number_input("Harga Modul (Rp/Wp)", value=float(sel_mod.get("cost_per_wp", 3500)), step=100.0)
        
        mod_spec = {
            "name": sel_mod_name, "pmax": sel_mod["pmax"] if 'pmax_in' not in locals() else pmax_in,
            "voc": sel_mod["voc"] if 'voc_in' not in locals() else voc_in,
            "vmp": sel_mod["vmp"] if 'vmp_in' not in locals() else vmp_in,
            "isc": sel_mod["isc"] if 'isc_in' not in locals() else isc_in,
            "kvoc": sel_mod["kvoc"] if 'kvoc_in' not in locals() else kvoc_in,
            "kvmp": sel_mod["kvmp"] if 'kvmp_in' not in locals() else kvmp_in,
            "length_mm": sel_mod["length_mm"] if 'len_in' not in locals() else len_in,
            "width_mm": sel_mod["width_mm"] if 'wid_in' not in locals() else wid_in,
            "cost_per_wp": sel_mod.get("cost_per_wp", 3500) if 'cost_wp_in' not in locals() else cost_wp_in
        }

    with c_inv_col:
        st.subheader("Inverter")
        inv_presets = PRESETS.get("inverters", [])
        inv_names = [i["name"] for i in inv_presets]
        sel_inv_name = st.selectbox("Pilih Model Inverter", options=inv_names, index=0)
        sel_inv = next(i for i in inv_presets if i["name"] == sel_inv_name)

        st.info(f"**Kapasitas AC:** {sel_inv['pac_kw']} kW | **Max Vdc:** {sel_inv['vdc_max']}V | **MPPT Range:** {sel_inv['mppt_min']}-{sel_inv['mppt_max']}V")

        with st.expander("⚙️ Edit Parameter Teknis Lanjutan Inverter", expanded=False):
            c_i1, c_i2 = st.columns(2)
            pac_in = c_i1.number_input("Kapasitas AC (kW)", value=float(sel_inv["pac_kw"]), step=5.0)
            vdc_max_in = c_i2.number_input("Vdc Maks (V)", value=float(sel_inv["vdc_max"]), step=50.0)
            mppt_min_in = c_i1.number_input("MPPT Min (V)", value=float(sel_inv["mppt_min"]), step=20.0)
            mppt_max_in = c_i2.number_input("MPPT Max (V)", value=float(sel_inv["mppt_max"]), step=20.0)
            n_mppt_in = c_i1.number_input("Jumlah MPPT", value=int(sel_inv["n_mppt"]), step=1)
            imax_in = c_i2.number_input("Arus Max/MPPT (A)", value=float(sel_inv["imax_mppt"]), step=1.0)
            str_per_mppt_in = c_i1.number_input("Maks String/MPPT", value=int(sel_inv["string_per_mppt"]), step=1)
            inv_cost_w_in = c_i2.number_input("Harga Inverter (Rp/W)", value=float(sel_inv.get("cost_per_w", 1200)), step=50.0)

        inv_spec = {
            "name": sel_inv_name, "pac_kw": sel_inv["pac_kw"] if 'pac_in' not in locals() else pac_in,
            "vdc_max": sel_inv["vdc_max"] if 'vdc_max_in' not in locals() else vdc_max_in,
            "mppt_min": sel_inv["mppt_min"] if 'mppt_min_in' not in locals() else mppt_min_in,
            "mppt_max": sel_inv["mppt_max"] if 'mppt_max_in' not in locals() else mppt_max_in,
            "n_mppt": sel_inv["n_mppt"] if 'n_mppt_in' not in locals() else n_mppt_in,
            "imax_mppt": sel_inv["imax_mppt"] if 'imax_in' not in locals() else imax_in,
            "string_per_mppt": sel_inv["string_per_mppt"] if 'str_per_mppt_in' not in locals() else str_per_mppt_in,
            "efficiency": float(sel_inv.get("efficiency", 0.98)),
            "cost_per_w": sel_inv.get("cost_per_w", 1200) if 'inv_cost_w_in' not in locals() else inv_cost_w_in
        }

    bat_spec = None
    autonomy_days = 1.0
    dod_val = 0.85
    v_sys_val = 48.0

    if topology in ["Off-Grid", "Hybrid"]:
        st.subheader("Bank Baterai Penyimpanan")
        bat_presets = PRESETS.get("batteries", [])
        bat_names = [b["name"] for b in bat_presets]
        sel_bat_name = st.selectbox("Pilih Model Baterai", options=bat_names, index=0)
        sel_bat = next(b for b in bat_presets if b["name"] == sel_bat_name)

        cb1, cb2, cb3, cb4 = st.columns(4)
        autonomy_days = cb1.number_input("Hari Otonomi", value=1.0, min_value=0.1, step=0.5)
        dod_val = cb2.number_input("DoD Maks (%)", value=float(sel_bat.get("dod_max", 0.85) * 100.0), step=5.0) / 100.0
        v_sys_val = cb3.number_input("Tegangan Sistem (V)", value=float(sel_bat.get("voltage_nominal", 48.0)), step=12.0)
        bat_cost_in = cb4.number_input("Harga Baterai (Rp/kWh)", value=float(sel_bat.get("cost_per_kwh", 3500000)), step=100000.0)

        bat_spec = {
            "name": sel_bat_name, "voltage_nominal": v_sys_val, "capacity_ah": float(sel_bat.get("capacity_ah", 100.0)),
            "dod_max": dod_val, "efficiency": float(sel_bat.get("efficiency", 0.95)), "cost_per_kwh": bat_cost_in
        }

    st.subheader("Kriteria & Target Sizing Sistem")
    ks1, ks2, ks3 = st.columns(3)
    sizing_mode = ks1.radio("Metode Penentuan Kapasitas", options=["Otomatis (Berdasarkan Target Self-Consumption)", "Manual (Input kWp Langsung)"], index=0)
    
    kwp_input = 0.0
    target_sc_input = 40.0
    if sizing_mode == "Manual (Input kWp Langsung)":
        kwp_input = ks2.number_input("Target Kapasitas PV (kWp)", value=1350.0, min_value=10.0, step=25.0)
    else:
        target_sc_input = ks2.slider("Target Minimum Self-Consumption (%)", 10.0, 100.0, 40.0, 5.0)

    available_area = ks3.number_input("Batasan Luas Lahan/Atap (m²) [0 = Tanpa Batas]", value=0.0, step=50.0)

    with st.expander("⚙️ Parameter Rekayasa & Finansial Lanjutan", expanded=False):
        fp1, fp2, fp3, fp4, fp5, fp6 = st.columns(6)
        pr_val = fp1.number_input("Performance Ratio (PR)", value=0.80, min_value=0.5, max_value=1.0, step=0.01)
        tmin_val = fp2.number_input("Suhu Min (°C)", value=18.0, step=1.0)
        tmax_sel_val = fp3.number_input("Suhu Maks Sel (°C)", value=50.0, step=1.0)
        tarif_pln = fp4.number_input("Tarif PLN (Rp/kWh)", value=1444.70, step=10.0)
        disc_rate = fp5.number_input("Suku Diskonto (%)", value=8.0, step=0.5) / 100.0
        degrad_rate = fp6.number_input("Laju Degradasi (%/thn)", value=0.7, step=0.1) / 100.0
        
        bp1, bp2 = st.columns(2)
        bos_cost_pct = bp1.number_input("Biaya BoS & Instalasi (% dari Kapasitas)", value=15.0, step=1.0) / 100.0
        opex_pct = bp2.number_input("Biaya OPEX (% dari CAPEX/tahun)", value=1.5, step=0.1) / 100.0

    st.write("")
    if st.button("🚀 Jalankan Kalkulasi Sizing & Kinerja", type="primary", use_container_width=True):
        try:
            kwp_calc = kwp_input
            if sizing_mode.startswith("Otomatis") or kwp_calc <= 0:
                with st.spinner("Menghitung kapasitas optimal berbasis self-consumption..."):
                    kwp_calc = auto_size_capacity(load_hourly, st.session_state["solar_irr"], pr_val, target_sc_input, step=50.0)
            
            pv_res = size_pv_system(kwp_calc, mod_spec, inv_spec, tmin_val, tmax_sel_val)
            dims = calc_dimensions(pv_res["n_modul"], mod_spec["length_mm"], mod_spec["width_mm"])
            dims["available_area_m2"] = available_area

            bat_res = None
            battery_cap = 0.0
            if topology in ["Off-Grid", "Hybrid"] and bat_spec is not None:
                bat_res = size_battery_bank(sum(load_hourly), autonomy_days, dod_val, v_sys_val, bat_spec, inv_spec["efficiency"])
                battery_cap = bat_res["capacity_kwh"]

            dispatch_rows, dispatch_summary = dispatch_simulation(
                load=load_hourly, solar_irr=st.session_state["solar_irr"], pr=pr_val,
                kwp=kwp_calc, topology=topology.lower(), battery_cap_kwh=battery_cap,
                battery_dod_max=dod_val, battery_eff=bat_spec.get("efficiency", 0.95) if bat_spec else 0.95
            )

            annual_energy = dispatch_summary["total_used"] * 365.0
            econ = calc_financial_metrics(
                kwp=kwp_calc, battery_kwh=battery_cap, annual_energy_kwh=annual_energy,
                tarif_pln=tarif_pln, mod_cost_wp=mod_spec["cost_per_wp"], inv_cost_w=inv_spec["cost_per_w"],
                battery_cost_kwh=bat_spec.get("cost_per_kwh", 0.0) if bat_spec else 0.0,
                bos_cost_pct=bos_cost_pct, opex_pct=opex_pct, discount_rate=disc_rate,
                degradation_rate=degrad_rate, years=25
            )

            st.session_state["calc_results"] = {
                "topology": topology, "kwp": kwp_calc, "pr": pr_val, "tmin": tmin_val, "tmax_sel": tmax_sel_val,
                "psh": dispatch_summary["psh"], "module_spec": mod_spec, "inverter_spec": inv_spec,
                "battery_spec": bat_spec, "battery_res": bat_res, "pv_res": pv_res, "dims": dims,
                "dispatch_rows": dispatch_rows, "dispatch_summary": dispatch_summary,
                "solar_irr": st.session_state["solar_irr"], "economics": econ
            }
            st.success("Kalkulasi berhasil! Silakan pindah ke tab ke-3 dan ke-4 untuk melihat hasil.")
        except Exception as e:
            st.error(f"Perhitungan gagal: {e}")

# ------------------------------------------------------------------------------
# TAB 3: HASIL TEKNIS & STRINGING
# ------------------------------------------------------------------------------
with step_tab3:
    res = st.session_state["calc_results"]
    if res is None:
        st.info("⚠️ Silakan jalankan kalkulasi pada Tab 2 terlebih dahulu.")
    else:
        st.header("Ringkasan Kinerja Listrik & Fisik")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Kapasitas Terpasang", f"{res['kwp']:,.1f} kWp")
        m2.metric("Rasio DC / AC", f"{res['pv_res']['dc_ac_ratio']:.2f}")
        m3.metric("Self Consumption", f"{res['dispatch_summary']['self_consumption_pct']:.1f}%")
        m4.metric("Solar Fraction", f"{res['dispatch_summary']['solar_fraction_pct']:.1f}%")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Modul Surya", f"{res['pv_res']['n_modul']:,} Unit")
        c2.metric("Total Unit Inverter", f"{res['pv_res']['n_inverter']:,} Unit")
        if res["battery_res"]:
            c3.metric("Bank Baterai", f"{res['battery_res']['capacity_kwh']:.0f} kWh", f"{res['battery_res']['total_units']} unit")
        else:
            c3.metric("Bank Baterai", "Tidak Digunakan")
        
        bruto_area = res["dims"]["area_bruto_m2"]
        avail_area = res["dims"]["available_area_m2"]
        c4.metric("Estimasi Luas Area", f"{bruto_area:,.0f} m²", "Cukup" if avail_area == 0 or bruto_area <= avail_area else "Lahan Kurang")

        st.subheader("Verifikasi Batas Teknis Inverter")
        pv_r = res["pv_res"]
        inv_s = res["inverter_spec"]
        vt1, vt2, vt3 = st.columns(3)
        vt1.metric("Voc Suhu Dingin", f"{pv_r['voc_max_act']:.1f} V", f"Maks {inv_s['vdc_max']:.0f} V ({'MEMENUHI' if pv_r['status_vdc'] else 'MELEBIHI'})")
        vt2.metric("Rentang Vmp Operasi", f"{pv_r['mppt_lo_act']:.1f} - {pv_r['voc_max_act']:.1f} V", f"MPPT: {inv_s['mppt_min']}-{inv_s['mppt_max']}V")
        vt3.metric("Arus Masuk / MPPT", f"{pv_r['arus_mppt_act']:.1f} A", f"Maks {inv_s['imax_mppt']}A ({'MEMENUHI' if pv_r['status_arus'] else 'MELEBIHI'})")

        st.subheader("Kurva Aliran Daya Harian (24 Jam)")
        df_disp = pd.DataFrame(res["dispatch_rows"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["load"], mode="lines+markers", name="Beban (kW)", line=dict(color="#334155", width=2.2)))
        fig.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["pv"], mode="lines", name="Produksi PV (kW)", line=dict(color="#D97706", width=2.5, dash="dash")))
        fig.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["used"], mode="lines", name="Daya Terpakai (kW)", fill="tozeroy", line=dict(color="#059669", width=1.5), fillcolor="rgba(5, 150, 105, 0.15)"))
        fig.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["surplus"], mode="lines", name="Ekspor Grid (kW)", line=dict(color="#2563EB", width=1.5)))
        fig.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["deficit"], mode="lines", name="Impor Grid (kW)", line=dict(color="#DC2626", width=1.5)))
        fig.update_layout(xaxis=dict(title="Jam", dtick=1), yaxis=dict(title="Daya (kW)"), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", hovermode="x unified", margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.05, x=1, xanchor="right"))
        st.plotly_chart(fig, use_container_width=True)

        if res["topology"] in ["Off-Grid", "Hybrid"] and res["battery_res"]:
            st.subheader("Kurva State of Charge (SOC) Baterai")
            fig_soc = go.Figure()
            fig_soc.add_trace(go.Scatter(x=df_disp["hour"], y=df_disp["soc_pct"], mode="lines+markers", name="SOC (%)", line=dict(color="#0284C7", width=2.0), fill="tozeroy", fillcolor="rgba(2, 132, 199, 0.12)"))
            fig_soc.update_layout(xaxis=dict(title="Jam", dtick=1), yaxis=dict(title="SOC (%)", range=[0, 105]), plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", hovermode="x unified", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_soc, use_container_width=True)

        st.subheader("Konfigurasi String per Unit Inverter")
        layout_data = []
        for row in pv_r.get("layout", []):
            layout_data.append({
                "Inverter": f"Inv #{row['inv_idx']:02d}",
                "String Utama (N)": row["str_p"],
                "Modul/String Utama": row["mod_p"],
                "String Sekunder (M)": row["str_k"],
                "Modul/String Sekunder": row["mod_k"],
                "Total Modul": (row["str_p"] * row["mod_p"]) + (row["str_k"] * row["mod_k"])
            })
        st.dataframe(pd.DataFrame(layout_data), use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 4: ANALISIS FINANSIAL & LAPORAN
# ------------------------------------------------------------------------------
with step_tab4:
    res = st.session_state["calc_results"]
    if res is None:
        st.info("⚠️ Silakan jalankan kalkulasi pada Tab 2 terlebih dahulu.")
    else:
        st.header("Analisis Kelayakan Finansial (25 Tahun)")
        econ = res["economics"]

        # Fungsi Helper format Rupiah Ringkas tanpa Ellipsis
        def fmt_miliar_juta(val):
            if val >= 1e9:
                return f"Rp {val / 1e9:,.2f} M"
            elif val >= 1e6:
                return f"Rp {val / 1e6:,.1f} Jt"
            else:
                return f"Rp {val:,.0f}"

        # Grid Finansial 2 Baris untuk Menghindari Ellipsis
        f_row1_1, f_row1_2, f_row1_3 = st.columns(3)
        f_row1_1.metric("Investasi Awal (CAPEX)", fmt_miliar_juta(econ['capex']), help=f"Rp {econ['capex']:,.0f}")
        
        pb = econ['payback_years']
        pb_str = f"{pb:.1f} Tahun" if (isinstance(pb, (int, float)) and not math.isinf(pb)) else "> 25 Tahun"
        f_row1_2.metric("Payback Period (BEP)", pb_str)
        
        f_row1_3.metric("Nilai Bersih (NPV 25 Thn)", fmt_miliar_juta(econ['npv']), help=f"Rp {econ['npv']:,.0f}")

        f_row2_1, f_row2_2, f_row2_3 = st.columns(3)
        f_row2_1.metric("Penghematan Tahun 1", fmt_miliar_juta(econ['first_year_saving']), help=f"Rp {econ['first_year_saving']:,.0f}")
        f_row2_2.metric("Biaya Energi Rata-Rata (LCOE)", f"Rp {econ['lcoe_per_kwh']:,.1f} / kWh")
        f_row2_3.metric("Total Produksi Energi Tahunan", f"{econ.get('annual_energy_kwh', 0):,.0f} kWh/thn")

        # Grafik Combo Finansial (Bar Arus Kas Tahunan + Line Kas Kumulatif) yang Jelas
        st.subheader("Grafik Arus Kas Tahunan & Kas Kumulatif")
        cashflows = econ.get("cashflows", [])
        if cashflows:
            cf_df = pd.DataFrame(cashflows)
            fig_cf = go.Figure()
            
            # Bar Arus Kas Net Tahunan
            fig_cf.add_trace(go.Bar(
                x=cf_df["year"], y=cf_df["net_cash"],
                name="Arus Kas Tahunan", marker_color="#0284C7", opacity=0.7
            ))
            # Line Kas Kumulatif
            fig_cf.add_trace(go.Scatter(
                x=cf_df["year"], y=cf_df["cum_cash"],
                mode="lines+markers", name="Kas Kumulatif",
                line=dict(color="#059669", width=2.5)
            ))
            fig_cf.add_hline(y=0, line_dash="dash", line_color="#EF4444", annotation_text="Titik Impas (BEP)")
            fig_cf.update_layout(
                xaxis=dict(title="Tahun Operasional", dtick=1, gridcolor="#F1F5F9"),
                yaxis=dict(title="Nilai Rupiah (Rp)", gridcolor="#F1F5F9"),
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", hovermode="x unified",
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", y=1.05, x=1, xanchor="right")
            )
            st.plotly_chart(fig_cf, use_container_width=True)

        st.subheader("Unduh Dokumen Laporan Lengkap")
        excel_buf = io.BytesIO()
        export_to_excel(res, excel_buf)
        excel_buf.seek(0)
        st.download_button(
            label="📥 Unduh Laporan Format Excel (.xlsx)",
            data=excel_buf,
            file_name=f"Laporan_Sizing_PLTS_{res['topology']}_{int(res['kwp'])}kWp.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
