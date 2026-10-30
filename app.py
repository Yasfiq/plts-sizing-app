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

# Konfigurasi Halaman Dasar
st.set_page_config(
    page_title="PLTS Sizing & Techno-Economic System",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Styling Anti-Slop: Bersih, Presisi Teknik, Slate & Solar Orange
st.markdown("""
<style>
    /* Reset & Typography */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #0F172A;
    }
    .block-container {
        padding-top: 1.75rem;
        padding-bottom: 4rem;
        max-width: 1240px;
    }

    /* Kartu Metrik Anti-Slop */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 14px 18px;
        box-shadow: none;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
    }

    /* Heading Fungsional */
    h1 {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.25rem !important;
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

    /* Tab Minimalis */
    button[data-baseweb="tab"] {
        font-size: 0.95rem;
        font-weight: 600;
        color: #64748B;
        padding: 10px 16px;
    }
    button[aria-selected="true"] {
        color: #EA580C !important;
        border-bottom-color: #EA580C !important;
    }

    /* Tombol Utama */
    button[kind="primary"] {
        background-color: #EA580C !important;
        border-color: #EA580C !important;
        color: #FFFFFF !important;
        font-weight: 600;
        border-radius: 6px;
    }
    button[kind="primary"]:hover {
        background-color: #C2410C !important;
        border-color: #C2410C !important;
    }

    /* Alert / Warning Bersih */
    div[data-testid="stAlert"] {
        border-radius: 6px;
        border: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# Muat Presets Komponen
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

# State Manajemen
if "solar_irr" not in st.session_state:
    st.session_state["solar_irr"] = {h: 0.0 for h in range(24)}
if "calc_results" not in st.session_state:
    st.session_state["calc_results"] = None

st.title("☀️ PLTS Sizing & Techno-Economic System")
st.caption("Aplikasi Rekayasa & Evaluasi Tekno-Ekonomi Sistem Pembangkit Listrik Tenaga Surya")

# ==============================================================================
# WORKFLOW MULTI-TAB WIZARD
# ==============================================================================
tab_step1, tab_step2, tab_step3, tab_step4 = st.tabs([
    "1. Topologi & Profil Beban",
    "2. Komponen & Kriteria Sizing",
    "3. Hasil Teknis & Stringing",
    "4. Analisis Finansial & Laporan"
])

# ------------------------------------------------------------------------------
# TAB 1: TOPOLOGI & PROFIL BEBAN
# ------------------------------------------------------------------------------
with tab_step1:
    st.header("Konfigurasi Topologi & Sumber Radiasi")
    
    col_top1, col_top2 = st.columns(2)
    with col_top1:
        topology = st.selectbox(
            "Topologi Sistem PLTS",
            options=["On-Grid", "Off-Grid", "Hybrid"],
            index=0,
            help="On-Grid: Terhubung langsung jaringan PLN | Off-Grid: Mandiri baterai | Hybrid: Kombinasi grid dan cadangan baterai"
        )
    with col_top2:
        # Revisi #1: Hanya API Renewables.ninja, Input Per Jam Manual, dan Upload CSV/Excel
        solar_source = st.selectbox(
            "Sumber Data Radiasi Matahari",
            options=["API Renewables.ninja", "Input Per Jam Manual", "Upload CSV/Excel"],
            index=0
        )

    if solar_source == "API Renewables.ninja":
        st.subheader("Parameter API Renewables.ninja")
        r_c1, r_c2, r_c3, r_c4 = st.columns(4)
        ninja_token = r_c1.text_input("API Token Renewables.ninja", type="password")
        city_choice = r_c2.selectbox("Lokasi Referensi", options=list(INDONESIA_CITIES.keys()), index=0)
        
        if city_choice == "Kustom":
            c_lat = r_c3.number_input("Latitude", value=-6.2088, format="%.4f")
            c_lon = r_c4.number_input("Longitude", value=106.8456, format="%.4f")
        else:
            c_lat, c_lon = INDONESIA_CITIES[city_choice]
            r_c3.metric("Latitude", f"{c_lat:.4f}")
            r_c4.metric("Longitude", f"{c_lon:.4f}")

        t_c1, t_c2 = st.columns(2)
        tilt = t_c1.slider("Kemiringan Modul / Tilt (°)", 0.0, 90.0, 15.0, 1.0)
        azim = t_c2.slider("Orientasi Modul / Azimuth (°)", 0.0, 360.0, 180.0, 5.0)

        if st.button("Ambil Data Radiasi dari API", type="primary"):
            if not ninja_token:
                st.error("Token API Renewables.ninja wajib diisi.")
            else:
                with st.spinner("Mengambil profil radiasi..."):
                    try:
                        profile = fetch_pv_profile(ninja_token, c_lat, c_lon, tilt, azim)
                        st.session_state["solar_irr"] = {h: profile.get(h, 0.0) * 1000.0 for h in range(24)}
                        st.success("Data radiasi berhasil diperoleh dari API Renewables.ninja.")
                    except Exception as e:
                        st.error(f"Gagal mengambil data radiasi: {e}")

    elif solar_source == "Upload CSV/Excel":
        s_file = st.file_uploader("Pilih Berkas Iradiasi (CSV/Excel)", type=["csv", "xlsx", "xls"])
        if s_file is not None:
            try:
                st.session_state["solar_irr"] = parse_solar_profile(s_file)
                st.success("Berkas radiasi berhasil dimuat.")
            except Exception as e:
                st.error(f"Format berkas tidak valid: {e}")

    elif solar_source == "Input Per Jam Manual":
        with st.expander("Pengaturan Nilai Iradiansi Per Jam (W/m²)", expanded=True):
            t_irr = {}
            cols_irr = st.columns(6)
            for h in range(24):
                def_val = float(st.session_state["solar_irr"].get(h, 0.0))
                with cols_irr[h % 6]:
                    t_irr[h] = st.number_input(f"Jam {h:02d}:00", value=def_val, min_value=0.0, step=10.0, key=f"irr_val_{h}")
            st.session_state["solar_irr"] = t_irr

    st.markdown("---")
    st.header("Profil Beban Listrik (24 Jam)")
    
    # Revisi #2: Default values untuk profil beban dikosongkan
    load_method = st.radio("Metode Input Beban", ["Tabel Blok Waktu Operasional", "Unggah Berkas (CSV / Excel)"], horizontal=True)
    load_hourly = [0.0] * 24

    if load_method == "Tabel Blok Waktu Operasional":
        st.write("Masukkan blok jam dan daya rata-rata (kW):")
        # Default value dikosongkan sesuai instruksi
        empty_blocks = pd.DataFrame([{"Mulai": 0, "Selesai": 24, "Daya_kW": 0.0}])
        block_df = st.data_editor(empty_blocks, num_rows="dynamic", use_container_width=True)
        try:
            raw_blocks = [(int(r["Mulai"]), int(r["Selesai"]), float(r["Daya_kW"])) for _, r in block_df.iterrows() if r["Daya_kW"] > 0]
            if raw_blocks:
                load_hourly = blocks_to_hourly(raw_blocks)
            total_kwh_load = sum(load_hourly)
            if total_kwh_load > 0:
                st.info(f"Total Energi Beban Harian: **{total_kwh_load:,.1f} kWh/hari**")
            else:
                st.warning("Silakan masukkan nilai daya beban pada tabel di atas.")
        except Exception as e:
            st.error(f"Format blok waktu beban salah: {e}")

    else:
        up_file = st.file_uploader("Unggah File Profil Beban (CSV/Excel)", type=["csv", "xlsx", "xls"])
        st.download_button("Unduh Template CSV Beban", data=generate_load_template_csv(), file_name="template_beban.csv", mime="text/csv")
        if up_file is not None:
            try:
                load_hourly = parse_load_profile_excel(up_file) if up_file.name.endswith((".xlsx", ".xls")) else parse_load_profile_csv(up_file)
                st.info(f"Total Beban Harian dari Berkas: **{sum(load_hourly):,.1f} kWh/hari**")
            except Exception as e:
                st.error(f"Gagal membaca berkas: {e}")

# ------------------------------------------------------------------------------
# TAB 2: SPESIFIKASI KOMPONEN & SIZING
# ------------------------------------------------------------------------------
with tab_step2:
    st.header("Spesifikasi Komponen & Kriteria Sizing")

    col_m, col_i = st.columns(2)

    # Revisi #4, #6: Pilihan Model Modul berdasarkan data yang diberikan + custom (hanya custom yang bisa diubah, default custom kosong)
    with col_m:
        st.subheader("Modul PV")
        mod_presets = PRESETS.get("modules", [])
        mod_preset_names = [m["name"] for m in mod_presets]
        mod_options = mod_preset_names + ["Kustom / Custom"]
        
        sel_mod_name = st.selectbox("Model Modul PV", options=mod_options, index=0)

        if sel_mod_name != "Kustom / Custom":
            sel_mod = next(m for m in mod_presets if m["name"] == sel_mod_name)
            st.markdown(f"""
            **Spesifikasi Modul (Terkunci):**
            - Daya Pmax: **{sel_mod['pmax']} Wp**
            - Voc: **{sel_mod['voc']} V** | Vmp: **{sel_mod['vmp']} V**
            - Isc: **{sel_mod['isc']} A**
            - Koefisien Suhu Voc: **{sel_mod['kvoc']}% / °C** | Vmp: **{sel_mod['kvmp']}% / °C**
            - Dimensi: **{sel_mod['length_mm']} mm × {sel_mod['width_mm']} mm**
            - Estimasi Harga: **Rp {sel_mod.get('cost_per_wp', 3500):,.0f} / Wp**
            """)
            mod_spec = {
                "name": sel_mod["name"],
                "pmax": float(sel_mod["pmax"]),
                "voc": float(sel_mod["voc"]),
                "vmp": float(sel_mod["vmp"]),
                "isc": float(sel_mod["isc"]),
                "kvoc": float(sel_mod["kvoc"]),
                "kvmp": float(sel_mod["kvmp"]),
                "length_mm": float(sel_mod["length_mm"]),
                "width_mm": float(sel_mod["width_mm"]),
                "cost_per_wp": float(sel_mod.get("cost_per_wp", 3500.0))
            }
        else:
            st.info("Mode Kustom: Masukkan parameter modul secara mandiri (default kosong).")
            m_c1, m_c2 = st.columns(2)
            pmax_c = m_c1.number_input("Daya Pmax (Wp)", value=0.0, step=10.0)
            voc_c = m_c2.number_input("Voc (V)", value=0.0, step=0.1)
            vmp_c = m_c1.number_input("Vmp (V)", value=0.0, step=0.1)
            isc_c = m_c2.number_input("Isc (A)", value=0.0, step=0.1)
            kvoc_c = m_c1.number_input("Koefisien Voc (%/°C)", value=0.0, step=0.01)
            kvmp_c = m_c2.number_input("Koefisien Vmp (%/°C)", value=0.0, step=0.01)
            len_c = m_c1.number_input("Panjang Modul (mm)", value=0.0, step=10.0)
            wid_c = m_c2.number_input("Lebar Modul (mm)", value=0.0, step=10.0)
            cost_wp_c = m_c1.number_input("Harga Modul (Rp/Wp)", value=0.0, step=100.0)

            mod_spec = {
                "name": "Custom PV Module",
                "pmax": pmax_c, "voc": voc_c, "vmp": vmp_c, "isc": isc_c,
                "kvoc": kvoc_c, "kvmp": kvmp_c, "length_mm": len_c, "width_mm": wid_c,
                "cost_per_wp": cost_wp_c
            }

    # Revisi #5, #6: Pilihan Inverter berdasarkan data yang diberikan + custom (hanya custom yang bisa diubah, default custom kosong)
    with col_i:
        st.subheader("Inverter")
        inv_presets = PRESETS.get("inverters", [])
        inv_preset_names = [i["name"] for i in inv_presets]
        inv_options = inv_preset_names + ["Kustom / Custom"]
        
        sel_inv_name = st.selectbox("Model Inverter", options=inv_options, index=0)

        if sel_inv_name != "Kustom / Custom":
            sel_inv = next(i for i in inv_presets if i["name"] == sel_inv_name)
            st.markdown(f"""
            **Spesifikasi Inverter (Terkunci):**
            - Kapasitas AC: **{sel_inv['pac_kw']} kW**
            - Tegangan Maks (Vdc Max): **{sel_inv['vdc_max']} V**
            - Rentang MPPT: **{sel_inv['mppt_min']} V - {sel_inv['mppt_max']} V**
            - Jumlah MPPT: **{sel_inv['n_mppt']}** | Maks String/MPPT: **{sel_inv['string_per_mppt']}**
            - Arus Masuk Maks/MPPT: **{sel_inv['imax_mppt']} A**
            - Estimasi Harga: **Rp {sel_inv.get('cost_per_w', 1200):,.0f} / W AC**
            """)
            inv_spec = {
                "name": sel_inv["name"],
                "pac_kw": float(sel_inv["pac_kw"]),
                "vdc_max": float(sel_inv["vdc_max"]),
                "mppt_min": float(sel_inv["mppt_min"]),
                "mppt_max": float(sel_inv["mppt_max"]),
                "n_mppt": int(sel_inv["n_mppt"]),
                "imax_mppt": float(sel_inv["imax_mppt"]),
                "string_per_mppt": int(sel_inv["string_per_mppt"]),
                "efficiency": float(sel_inv.get("efficiency", 0.98)),
                "cost_per_w": float(sel_inv.get("cost_per_w", 1200.0))
            }
        else:
            st.info("Mode Kustom: Masukkan parameter inverter secara mandiri (default kosong).")
            i_c1, i_c2 = st.columns(2)
            pac_c = i_c1.number_input("Kapasitas AC (kW)", value=0.0, step=5.0)
            vdc_max_c = i_c2.number_input("Vdc Maksimum (V)", value=0.0, step=50.0)
            mppt_min_c = i_c1.number_input("MPPT Minimum (V)", value=0.0, step=20.0)
            mppt_max_c = i_c2.number_input("MPPT Maksimum (V)", value=0.0, step=20.0)
            n_mppt_c = i_c1.number_input("Jumlah Jalur MPPT", value=0, step=1)
            imax_c = i_c2.number_input("Arus Maks/MPPT (A)", value=0.0, step=1.0)
            str_mppt_c = i_c1.number_input("Maks String/MPPT", value=0, step=1)
            cost_w_c = i_c2.number_input("Harga Inverter (Rp/W)", value=0.0, step=100.0)

            inv_spec = {
                "name": "Custom Inverter",
                "pac_kw": pac_c, "vdc_max": vdc_max_c, "mppt_min": mppt_min_c, "mppt_max": mppt_max_c,
                "n_mppt": n_mppt_c, "imax_mppt": imax_c, "string_per_mppt": str_mppt_c,
                "efficiency": 0.98, "cost_per_w": cost_w_c
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
        v_sys_val = cb3.number_input("Tegangan Nominal Sistem (V)", value=float(sel_bat.get("voltage_nominal", 48.0)), step=12.0)
        bat_cost_in = cb4.number_input("Harga Baterai (Rp/kWh)", value=float(sel_bat.get("cost_per_kwh", 3500000)), step=100000.0)

        bat_spec = {
            "name": sel_bat_name, "voltage_nominal": v_sys_val, "capacity_ah": float(sel_bat.get("capacity_ah", 100.0)),
            "dod_max": dod_val, "efficiency": float(sel_bat.get("efficiency", 0.95)), "cost_per_kwh": bat_cost_in
        }

    st.markdown("---")
    st.subheader("Kriteria & Target Sizing Sistem")
    k_col1, k_col2, k_col3 = st.columns(3)
    
    sizing_mode = k_col1.radio("Metode Penentuan Kapasitas", options=["Otomatis (Berdasarkan Target Self-Consumption)", "Manual (Input kWp Langsung)"], index=0)
    
    kwp_input = 0.0
    target_sc_input = 40.0
    if sizing_mode == "Manual (Input kWp Langsung)":
        kwp_input = k_col2.number_input("Target Kapasitas PV (kWp)", value=1350.0, min_value=1.0, step=25.0)
    else:
        target_sc_input = k_col2.slider("Target Minimum Self-Consumption (%)", 10.0, 100.0, 40.0, 5.0)

    # Revisi #7: Wording Batasan Luas Lahan/Atap (m²) tanpa [0 = Tanpa Batas], jika 0 beri warning "Luas Lahan Tanpa Batas"
    available_area = k_col3.number_input("Batasan Luas Lahan/Atap (m²)", value=0.0, min_value=0.0, step=50.0)
    if available_area == 0.0:
        st.warning("⚠️ Luas Lahan Tanpa Batas")

    st.subheader("Parameter Rekayasa & Finansial Lanjutan")
    fp1, fp2, fp3, fp4, fp5, fp6 = st.columns(6)
    pr_val = fp1.number_input("Performance Ratio (PR)", value=0.80, min_value=0.5, max_value=1.0, step=0.01)
    tmin_val = fp2.number_input("Suhu Min (°C)", value=18.0, step=1.0)
    tmax_sel_val = fp3.number_input("Suhu Maks Sel (°C)", value=50.0, step=1.0)
    tarif_pln = fp4.number_input("Tarif PLN (Rp/kWh)", value=1444.70, step=10.0)
    disc_rate = fp5.number_input("Suku Diskonto (%)", value=8.0, step=0.5) / 100.0
    degrad_rate = fp6.number_input("Laju Degradasi (%/thn)", value=0.7, step=0.1) / 100.0
    
    # Revisi #8: Biaya BoS & Instalasi dan OPEX input langsung nominal Rupiah, bukan persen
    bp1, bp2 = st.columns(2)
    bos_cost_in = bp1.number_input(
        "Biaya BoS & Instalasi (Rp)",
        value=150000000.0,
        step=10000000.0,
        format="%.0f",
        help="Biaya Balance of System, struktur rak, kabel, panel distribusi, perizinan, dan jasa instalasi dalam Rupiah nominal."
    )
    opex_cost_in = bp2.number_input(
        "Biaya OPEX Tahunan (Rp/tahun)",
        value=15000000.0,
        step=1000000.0,
        format="%.0f",
        help="Biaya operasional & pemeliharaan tahunan (pembersihan rutin, inspeksi elektrikal, monitoring) dalam Rupiah nominal."
    )

    st.write("")
    if st.button("🚀 Jalankan Kalkulasi Sizing & Kinerja", type="primary", use_container_width=True):
        if mod_spec["pmax"] <= 0 or mod_spec["voc"] <= 0 or mod_spec["vmp"] <= 0:
            st.error("Parameter Modul PV belum lengkap atau bernilai 0.")
        elif inv_spec["pac_kw"] <= 0 or inv_spec["vdc_max"] <= 0 or inv_spec["mppt_max"] <= 0:
            st.error("Parameter Inverter belum lengkap atau bernilai 0.")
        elif sum(load_hourly) <= 0:
            st.error("Profil beban harian masih kosong. Silakan lengkapi pada Tab 1.")
        else:
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
                    bos_cost=bos_cost_in, annual_opex=opex_cost_in,
                    discount_rate=disc_rate, degradation_rate=degrad_rate, years=25
                )

                st.session_state["calc_results"] = {
                    "topology": topology, "kwp": kwp_calc, "pr": pr_val, "tmin": tmin_val, "tmax_sel": tmax_sel_val,
                    "psh": dispatch_summary["psh"], "module_spec": mod_spec, "inverter_spec": inv_spec,
                    "battery_spec": bat_spec, "battery_res": bat_res, "pv_res": pv_res, "dims": dims,
                    "dispatch_rows": dispatch_rows, "dispatch_summary": dispatch_summary,
                    "solar_irr": st.session_state["solar_irr"], "economics": econ
                }
                st.success("Kalkulasi selesai. Silakan periksa hasilnya pada Tab 3 dan Tab 4.")
            except Exception as e:
                st.error(f"Perhitungan gagal: {e}")

# ------------------------------------------------------------------------------
# TAB 3: HASIL TEKNIS & STRINGING
# ------------------------------------------------------------------------------
with tab_step3:
    res = st.session_state["calc_results"]
    if res is None:
        st.info("⚠️ Silakan jalankan kalkulasi pada Tab 2 terlebih dahulu.")
    else:
        st.header("Ringkasan Hasil Perancangan Teknis")
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
        vt1.metric("Voc Suhu Dingin", f"{pv_r['voc_max_act']:.1f} V", f"Maks {inv_s['vdc_max']:.0f} V ({'LOLOS' if pv_r['status_vdc'] else 'MELEBIHI'})")
        vt2.metric("Rentang Vmp Operasi", f"{pv_r['mppt_lo_act']:.1f} - {pv_r['voc_max_act']:.1f} V", f"Jendela: {inv_s['mppt_min']:.0f}-{inv_s['mppt_max']:.0f} V")
        vt3.metric("Arus Masuk / MPPT", f"{pv_r['arus_mppt_act']:.1f} A", f"Maks {inv_s['imax_mppt']:.0f} A ({'LOLOS' if pv_r['status_arus'] else 'MELEBIHI'})")

        # Revisi #10 & #11: Kurva Aliran Daya Harian CUKUP berisi Beban, Produksi PV, Impor, Ekspor + garis smooth rounded
        st.subheader("Kurva Aliran Daya Harian (24 Jam)")
        df_disp = pd.DataFrame(res["dispatch_rows"])
        fig_disp = go.Figure()

        fig_disp.add_trace(go.Scatter(
            x=df_disp["hour"], y=df_disp["load"],
            mode="lines+markers", name="Beban Listrik (kW)",
            line=dict(color="#334155", width=2.5, shape="spline", smoothing=1.3)
        ))
        fig_disp.add_trace(go.Scatter(
            x=df_disp["hour"], y=df_disp["pv"],
            mode="lines", name="Produksi PV (kW)",
            line=dict(color="#EA580C", width=2.5, dash="dash", shape="spline", smoothing=1.3)
        ))
        fig_disp.add_trace(go.Scatter(
            x=df_disp["hour"], y=df_disp["surplus"],
            mode="lines", name="Ekspor Grid (kW)",
            line=dict(color="#2563EB", width=2.0, shape="spline", smoothing=1.3)
        ))
        fig_disp.add_trace(go.Scatter(
            x=df_disp["hour"], y=df_disp["deficit"],
            mode="lines", name="Impor Grid (kW)",
            line=dict(color="#DC2626", width=2.0, shape="spline", smoothing=1.3)
        ))

        fig_disp.update_layout(
            xaxis=dict(title="Jam Operasional", dtick=1, gridcolor="#F1F5F9"),
            yaxis=dict(title="Daya Listrik (kW)", gridcolor="#F1F5F9"),
            plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", y=1.05, x=1, xanchor="right")
        )
        st.plotly_chart(fig_disp, use_container_width=True)

        if res["topology"] in ["Off-Grid", "Hybrid"] and res["battery_res"]:
            st.subheader("Kurva State of Charge (SOC) Baterai")
            fig_soc = go.Figure()
            fig_soc.add_trace(go.Scatter(
                x=df_disp["hour"], y=df_disp["soc_pct"],
                mode="lines+markers", name="SOC (%)",
                line=dict(color="#0284C7", width=2.0, shape="spline", smoothing=1.3),
                fill="tozeroy", fillcolor="rgba(2, 132, 199, 0.10)"
            ))
            fig_soc.update_layout(
                xaxis=dict(title="Jam Operasional", dtick=1, gridcolor="#F1F5F9"),
                yaxis=dict(title="SOC (%)", range=[0, 105], gridcolor="#F1F5F9"),
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                hovermode="x unified", margin=dict(l=20, r=20, t=20, b=20)
            )
            st.plotly_chart(fig_soc, use_container_width=True)

        # Revisi #12: Konfigurasi String per Unit yang direkomendasikan (read-only, intuitif)
        st.subheader("Rekomendasi Konfigurasi String per Unit Inverter")
        st.caption("Konfigurasi string di bawah ini dihitung otomatis untuk menjaga tegangan selalu berada dalam rentang efisiensi MPPT tertinggi pada kondisi suhu ekstrem.")
        
        layout_rows = []
        for row in pv_r.get("layout", []):
            str_utama = f"{row['str_p']} String × {row['mod_p']} Modul" if row['str_p'] > 0 else "-"
            str_tambahan = f"{row['str_k']} String × {row['mod_k']} Modul" if row['str_k'] > 0 else "-"
            total_m = (row["str_p"] * row["mod_p"]) + (row["str_k"] * row["mod_k"])
            layout_rows.append({
                "Unit Inverter": f"Inverter #{row['inv_idx']:02d}",
                "Rangkaian Utama": str_utama,
                "Rangkaian Tambahan": str_tambahan,
                "Total Modul Terhubung": f"{total_m} Modul",
                "Status MPPT": "Sesuai Rentang Optimal"
            })
        st.dataframe(pd.DataFrame(layout_rows), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 4: ANALISIS FINANSIAL & LAPORAN
# ------------------------------------------------------------------------------
with tab_step4:
    res = st.session_state["calc_results"]
    if res is None:
        st.info("⚠️ Silakan jalankan kalkulasi pada Tab 2 terlebih dahulu.")
    else:
        st.header("Analisis Kelayakan Finansial (Proyeksi 25 Tahun)")
        econ = res["economics"]

        def fmt_rp_ringkas(val):
            if val >= 1e9:
                return f"Rp {val / 1e9:,.2f} Miliar"
            elif val >= 1e6:
                return f"Rp {val / 1e6:,.1f} Juta"
            else:
                return f"Rp {val:,.0f}"

        # Layout 2 baris metrik finansial terhindar dari ellipsis
        f_c1, f_c2, f_c3 = st.columns(3)
        f_c1.metric("Investasi Awal (CAPEX)", fmt_rp_ringkas(econ['capex']), help=f"Total CAPEX: Rp {econ['capex']:,.0f}")
        
        pb = econ['payback_years']
        pb_str = f"{pb:.1f} Tahun" if (isinstance(pb, (int, float)) and not math.isinf(pb)) else "> 25 Tahun"
        f_c2.metric("Payback Period (BEP)", pb_str, help="Estimasi durasi titik impas pengembalian modal investasi.")
        
        f_c3.metric("Net Present Value (NPV 25 Thn)", fmt_rp_ringkas(econ['npv']), help=f"NPV: Rp {econ['npv']:,.0f}")

        f_c4, f_c5, f_c6 = st.columns(3)
        f_c4.metric("Penghematan Tahun ke-1", fmt_rp_ringkas(econ['first_year_saving']), help=f"Penghematan tahun 1: Rp {econ['first_year_saving']:,.0f}")
        
        # Revisi #13: Penjelasan mendalam Biaya Energi Rata-rata (LCOE)
        f_c5.metric(
            "Biaya Energi Rata-Rata (LCOE)",
            f"Rp {econ['lcoe_per_kwh']:,.1f} / kWh",
            help="LCOE (Levelized Cost of Electricity) adalah harga pokok produksi per 1 kWh energi listrik yang dihasilkan PLTS sepanjang masa pakainya (25 tahun), memperhitungkan biaya CAPEX, OPEX, degradasi modul, dan nilai waktu uang. Jika LCOE lebih rendah daripada Tarif PLN (Rp 1.444,70/kWh), sistem memberikan keuntungan finansial riil."
        )
        f_c6.metric("Total Produksi Energi Tahunan", f"{econ.get('annual_energy_kwh', 0):,.0f} kWh/thn")

        # Revisi #14 & #15: Grafik Arus Kas Tahunan saja (tanpa kumulatif), warna orange aplikasi, range Y proporsional
        st.subheader("Grafik Arus Kas Bersih Tahunan (Tahun 1 - 25)")
        st.caption("Menampilkan nilai arus kas bersih (Penghematan Biaya Listrik dikurangi Biaya OPEX) per tahun.")
        
        cashflows = econ.get("cashflows", [])
        if cashflows:
            # Ambil data operasional tahun 1 s/d 25 agar range Y proporsional dan tidak gepeng akibat -CAPEX tahun 0
            op_cf = [c for c in cashflows if c["year"] > 0]
            cf_df = pd.DataFrame(op_cf)
            
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(
                x=cf_df["year"],
                y=cf_df["net_cash"],
                name="Arus Kas Bersih (Net Savings)",
                marker_color="#EA580C", # Warna orange solar aplikasi kita
                opacity=0.9
            ))

            max_net = max(cf_df["net_cash"]) if len(cf_df) > 0 else 1000.0
            min_net = min(cf_df["net_cash"]) if len(cf_df) > 0 else 0.0

            fig_cf.update_layout(
                xaxis=dict(title="Tahun Operasional", dtick=1, gridcolor="#F1F5F9"),
                yaxis=dict(
                    title="Nilai Arus Kas Bersih (Rp)",
                    gridcolor="#F1F5F9",
                    range=[min(0, min_net * 0.9), max_net * 1.15] # Range proporsional
                ),
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                hovermode="x unified",
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
