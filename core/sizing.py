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
    
    # ponytail: layout asimetris disederhanakan per string group; upgrade jika string imbalance per MPPT dibutuhkan
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
