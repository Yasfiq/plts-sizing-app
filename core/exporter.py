import io
import math
from typing import Union
import xlsxwriter

def export_to_excel(data: dict, target: Union[str, io.BytesIO]) -> None:
    """Ekspor multi-sheet hasil sizing ke file atau buffer Excel menggunakan XlsxWriter."""
    workbook = xlsxwriter.Workbook(
        target if isinstance(target, str) else target,
        {"in_memory": True, "nan_inf_to_errors": True}
    )
    
    # Formats
    title_fmt = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1E3A8A"})
    section_fmt = workbook.add_format({"bold": True, "font_size": 11, "bg_color": "#E2E8F0", "border": 1})
    hdr_fmt = workbook.add_format({"bold": True, "bg_color": "#2563EB", "font_color": "white", "border": 1, "align": "center"})
    bold_fmt = workbook.add_format({"bold": True})
    num_fmt = workbook.add_format({"num_format": "#,##0.00", "border": 1})
    curr_fmt = workbook.add_format({"num_format": "Rp #,##0", "border": 1})
    pct_fmt = workbook.add_format({"num_format": "0.0%", "border": 1})
    int_fmt = workbook.add_format({"num_format": "#,##0", "border": 1})
    txt_fmt = workbook.add_format({"border": 1})
    pass_fmt = workbook.add_format({"bold": True, "font_color": "#166534", "bg_color": "#DCFCE7", "border": 1, "align": "center"})
    fail_fmt = workbook.add_format({"bold": True, "font_color": "#991B1B", "bg_color": "#FEE2E2", "border": 1, "align": "center"})

    # ==========================================
    # SHEET 1: Ringkasan Sizing
    # ==========================================
    ws1 = workbook.add_worksheet("Ringkasan Sizing")
    ws1.set_column("A:A", 32)
    ws1.set_column("B:B", 25)
    ws1.set_column("C:C", 15)
    ws1.set_column("D:D", 20)
    ws1.set_column("E:E", 15)

    ws1.write(0, 0, "LAPORAN SIZING SISTEM PLTS", title_fmt)
    ws1.write(1, 0, f"Topologi Sistem: {data.get('topology', 'On-Grid')}", bold_fmt)

    # 1. Parameter Dasar
    r = 3
    ws1.merge_range(r, 0, r, 2, "1. PARAMETER DASAR SISTEM", section_fmt)
    r += 1
    params = [
        ("Kapasitas Terpasang (kWp)", data.get("kwp", 0.0), num_fmt),
        ("Performance Ratio (PR)", data.get("pr", 0.8), pct_fmt),
        ("Suhu Min Lingkungan (°C)", data.get("tmin", 18.0), num_fmt),
        ("Suhu Maks Sel PV (°C)", data.get("tmax_sel", 50.0), num_fmt),
        ("Peak Sun Hours (PSH / hari)", data.get("psh", 0.0), num_fmt),
    ]
    for lbl, val, fmt in params:
        ws1.write(r, 0, lbl, txt_fmt)
        ws1.write(r, 1, val, fmt)
        r += 1

    # 2. Hasil Sizing Modul & Inverter
    r += 1
    ws1.merge_range(r, 0, r, 2, "2. HASIL SIZING PV & INVERTER", section_fmt)
    r += 1
    pv_res = data.get("pv_res", {})
    m_spec = data.get("module_spec", {})
    inv_spec = data.get("inverter_spec", {})

    sizing_rows = [
        ("Tipe Modul PV", m_spec.get("name", "-"), txt_fmt),
        ("Daya per Modul (Wp)", m_spec.get("pmax", 0.0), num_fmt),
        ("Total Modul PV (unit)", pv_res.get("n_modul", 0), int_fmt),
        ("Tipe Inverter", inv_spec.get("name", "-"), txt_fmt),
        ("Kapasitas Inverter (kW AC)", inv_spec.get("pac_kw", 0.0), num_fmt),
        ("Jumlah Inverter (unit)", pv_res.get("n_inverter", 0), int_fmt),
        ("Total String", pv_res.get("total_strings", 0), int_fmt),
        ("Rentang String Diizinkan (N_min - N_max)", f"{pv_res.get('n_min_string', 0)} - {pv_res.get('n_max_string', 0)}", txt_fmt),
        ("DC / AC Ratio", pv_res.get("dc_ac_ratio", 0.0), num_fmt),
    ]
    for lbl, val, fmt in sizing_rows:
        ws1.write(r, 0, lbl, txt_fmt)
        ws1.write(r, 1, val, fmt)
        r += 1

    # 3. Verifikasi Batas Teknis
    r += 1
    ws1.merge_range(r, 0, r, 3, "3. VERIFIKASI BATAS TEKNIS INVERTER", section_fmt)
    r += 1
    ws1.write(r, 0, "Parameter", hdr_fmt)
    ws1.write(r, 1, "Nilai Sistem", hdr_fmt)
    ws1.write(r, 2, "Batas Inverter", hdr_fmt)
    ws1.write(r, 3, "Status", hdr_fmt)
    r += 1

    tech_checks = [
        (
            "Tegangan Voc Cold (V)",
            pv_res.get("voc_max_act", 0.0),
            f"Maks {inv_spec.get('vdc_max', 0.0)} V",
            pv_res.get("status_vdc", False)
        ),
        (
            "Rentang Vmp String (V)",
            f"{pv_res.get('mppt_lo_act', 0.0):.1f} - {pv_res.get('voc_max_act', 0.0):.1f} V",
            f"{inv_spec.get('mppt_min', 0.0)} - {inv_spec.get('mppt_max', 0.0)} V",
            pv_res.get("status_mppt", False)
        ),
        (
            "Arus per MPPT (A)",
            pv_res.get("arus_mppt_act", 0.0),
            f"Maks {inv_spec.get('imax_mppt', 0.0)} A",
            pv_res.get("status_arus", False)
        ),
    ]
    for lbl, val, lim, stat in tech_checks:
        ws1.write(r, 0, lbl, txt_fmt)
        if isinstance(val, (int, float)):
            ws1.write(r, 1, val, num_fmt)
        else:
            ws1.write(r, 1, str(val), txt_fmt)
        ws1.write(r, 2, lim, txt_fmt)
        ws1.write(r, 3, "LOLOS" if stat else "GAGAL", pass_fmt if stat else fail_fmt)
        r += 1

    # 4. Dimensi & Kebutuhan Luas
    r += 1
    ws1.merge_range(r, 0, r, 2, "4. KEBUTUHAN LUAS AREA", section_fmt)
    r += 1
    dims = data.get("dims", {})
    area_tersedia = dims.get("available_area_m2", 0.0)
    area_bruto = dims.get("area_bruto_m2", 0.0)
    area_ok = (area_tersedia == 0.0) or (area_bruto <= area_tersedia)

    dim_rows = [
        ("Luas Bersih Modul (m²)", dims.get("area_netto_m2", 0.0), num_fmt),
        ("Luas Bruto Termasuk Pitch (m²)", area_bruto, num_fmt),
        ("Luas Atap/Lahan Tersedia (m²)", area_tersedia if area_tersedia > 0 else "Tidak dibatasi", txt_fmt if area_tersedia == 0 else num_fmt),
        ("Kecukupan Luas Lahan", "CUKUP" if area_ok else "TIDAK CUKUP", pass_fmt if area_ok else fail_fmt),
    ]
    for lbl, val, fmt in dim_rows:
        ws1.write(r, 0, lbl, txt_fmt)
        ws1.write(r, 1, val, fmt)
        r += 1

    # 5. Konfigurasi Baterai (jika ada)
    bat_res = data.get("battery_res")
    if bat_res:
        r += 1
        ws1.merge_range(r, 0, r, 2, "5. BANK BATERAI", section_fmt)
        r += 1
        bat_spec = data.get("battery_spec", {})
        bat_rows = [
            ("Tipe Baterai", bat_spec.get("name", "-"), txt_fmt),
            ("Kapasitas Energi Total (kWh)", bat_res.get("capacity_kwh", 0.0), num_fmt),
            ("Kapasitas Muatan Total (Ah)", bat_res.get("capacity_ah", 0.0), num_fmt),
            ("Total Unit Baterai", bat_res.get("total_units", 0), int_fmt),
        ]
        for lbl, val, fmt in bat_rows:
            ws1.write(r, 0, lbl, txt_fmt)
            ws1.write(r, 1, val, fmt)
            r += 1

    # 6. Distribusi Layout String Inverter
    layout = pv_res.get("layout", [])
    if layout:
        r += 1
        ws1.merge_range(r, 0, r, 4, "DISTRIBUSI STRING PER INVERTER", section_fmt)
        r += 1
        ws1.write(r, 0, "No Inverter", hdr_fmt)
        ws1.write(r, 1, "String Pola A", hdr_fmt)
        ws1.write(r, 2, "Modul/String A", hdr_fmt)
        ws1.write(r, 3, "String Pola B", hdr_fmt)
        ws1.write(r, 4, "Modul/String B", hdr_fmt)
        r += 1
        for row in layout:
            ws1.write(r, 0, f"Inverter {row.get('inv_idx', 1)}", txt_fmt)
            ws1.write(r, 1, row.get("str_p", 0), int_fmt)
            ws1.write(r, 2, row.get("mod_p", 0), int_fmt)
            ws1.write(r, 3, row.get("str_k", 0), int_fmt)
            ws1.write(r, 4, row.get("mod_k", 0), int_fmt)
            r += 1

    # ==========================================
    # SHEET 2: Dispatch 24 Jam
    # ==========================================
    ws2 = workbook.add_worksheet("Dispatch 24 Jam")
    headers_ws2 = [
        "Jam", "Beban (kW)", "Radiasi (W/m²)", "Produksi PV (kW)",
        "Energi Terpakai (kW)", "Surplus PV (kW)", "Defisit Beban (kW)",
        "Cas Baterai (kW)", "Discharge Baterai (kW)", "SOC Baterai (%)"
    ]
    for c, h in enumerate(headers_ws2):
        ws2.set_column(c, c, 18)
        ws2.write(0, c, h, hdr_fmt)

    dispatch_rows = data.get("dispatch_rows", [])
    solar_irr = data.get("solar_irr", {})
    for i, row in enumerate(dispatch_rows):
        hr = row.get("hour", i)
        ws2.write(i + 1, 0, f"{hr:02d}:00", txt_fmt)
        ws2.write(i + 1, 1, row.get("load", 0.0), num_fmt)
        ws2.write(i + 1, 2, solar_irr.get(hr, 0.0), num_fmt)
        ws2.write(i + 1, 3, row.get("pv", 0.0), num_fmt)
        ws2.write(i + 1, 4, row.get("used", 0.0), num_fmt)
        ws2.write(i + 1, 5, row.get("surplus", 0.0), num_fmt)
        ws2.write(i + 1, 6, row.get("deficit", 0.0), num_fmt)
        ws2.write(i + 1, 7, row.get("batt_charge", 0.0), num_fmt)
        ws2.write(i + 1, 8, row.get("batt_discharge", 0.0), num_fmt)
        ws2.write(i + 1, 9, row.get("soc_pct", 0.0) / 100.0, pct_fmt)

    # Baris Total Ringkasan Dispatch
    r_sum = len(dispatch_rows) + 2
    ws2.write(r_sum, 0, "TOTAL HARIAN", bold_fmt)
    disp_summary = data.get("dispatch_summary", {})
    ws2.write(r_sum, 1, disp_summary.get("total_load", 0.0), num_fmt)
    ws2.write(r_sum, 3, disp_summary.get("total_pv", 0.0), num_fmt)
    ws2.write(r_sum, 4, disp_summary.get("total_used", 0.0), num_fmt)
    ws2.write(r_sum, 5, disp_summary.get("total_surplus", 0.0), num_fmt)
    ws2.write(r_sum, 6, disp_summary.get("total_deficit", 0.0), num_fmt)

    r_sum += 2
    ws2.write(r_sum, 0, "Self Consumption (%)", bold_fmt)
    ws2.write(r_sum, 1, disp_summary.get("self_consumption_pct", 0.0) / 100.0, pct_fmt)
    ws2.write(r_sum + 1, 0, "Solar Fraction (%)", bold_fmt)
    ws2.write(r_sum + 1, 1, disp_summary.get("solar_fraction_pct", 0.0) / 100.0, pct_fmt)

    # ==========================================
    # SHEET 3: Analisis Finansial
    # ==========================================
    ws3 = workbook.add_worksheet("Analisis Finansial")
    ws3.set_column("A:A", 15)
    ws3.set_column("B:G", 22)

    econ = data.get("economics", {})
    ws3.write(0, 0, "RINGKASAN KELAYAKAN FINANSIAL", title_fmt)

    payback_val = econ.get("payback_years", 0.0)
    if isinstance(payback_val, (int, float)) and (math.isinf(payback_val) or math.isnan(payback_val)):
        payback_display = "> 25 Tahun"
        payback_format = txt_fmt
    else:
        payback_display = payback_val
        payback_format = num_fmt

    kpis = [
        ("Total Investasi (CAPEX)", econ.get("capex", 0.0), curr_fmt),
        ("OPEX Tahunan", econ.get("annual_opex", 0.0), curr_fmt),
        ("Penghematan Tahun ke-1", econ.get("first_year_saving", 0.0), curr_fmt),
        ("Payback Period (Tahun)", payback_display, payback_format),
        ("Net Present Value (NPV)", econ.get("npv", 0.0), curr_fmt),
        ("Levelized Cost of Energy (LCOE)", econ.get("lcoe_per_kwh", 0.0), curr_fmt),
    ]
    for idx, (lbl, val, fmt) in enumerate(kpis):
        ws3.write(idx + 2, 0, lbl, txt_fmt)
        ws3.write(idx + 2, 1, val, fmt)

    r_cf = len(kpis) + 4
    ws3.merge_range(r_cf, 0, r_cf, 6, "PROYEKSI ARUS KAS 25 TAHUN", section_fmt)
    r_cf += 1

    headers_ws3 = [
        "Tahun", "Energi (kWh)", "Penghematan (Rp)", "OPEX (Rp)",
        "Arus Kas Bersih (Rp)", "Arus Kas Kumulatif (Rp)", "Arus Kas Terdiskon (Rp)"
    ]
    for c, h in enumerate(headers_ws3):
        ws3.write(r_cf, c, h, hdr_fmt)
    r_cf += 1

    cashflows = econ.get("cashflows", [])
    for row in cashflows:
        ws3.write(r_cf, 0, row.get("year", 0), int_fmt)
        ws3.write(r_cf, 1, row.get("energy_kwh", 0.0), num_fmt)
        ws3.write(r_cf, 2, row.get("savings", 0.0), curr_fmt)
        ws3.write(r_cf, 3, row.get("opex", 0.0), curr_fmt)
        ws3.write(r_cf, 4, row.get("net_cash", 0.0), curr_fmt)
        ws3.write(r_cf, 5, row.get("cum_cash", 0.0), curr_fmt)
        ws3.write(r_cf, 6, row.get("discounted_net_cash", 0.0), curr_fmt)
        r_cf += 1

    workbook.close()
