# tests/test_sizing.py
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

def test_dimensions():
    # 2455 modul, 2278 mm x 1134 mm, pitch factor 1.25
    dim = calc_dimensions(2455, 2278, 1134, pitch_factor=1.25)
    area_netto = 2455 * 2.278 * 1.134
    assert round(dim["area_netto_m2"], 2) == round(area_netto, 2)
    assert round(dim["area_bruto_m2"], 2) == round(area_netto * 1.25, 2)

if __name__ == "__main__":
    test_pv_sizing_reference()
    test_battery_sizing()
    test_dimensions()
    print("ALL TESTS PASSED")
