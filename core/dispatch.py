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
