# tests/test_core.py
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data_loader import blocks_to_hourly
from core.sizing import size_pv_system, calc_dimensions
from core.dispatch import dispatch_simulation
from core.economics import calc_financial_metrics

def test_full_pipeline_on_grid():
    blocks = [
        (0, 6, 89.0), (6, 9, 98.0), (9, 12, 180.0),
        (12, 15, 208.0), (15, 18, 167.0), (18, 21, 79.0), (21, 24, 59.0)
    ]
    load = blocks_to_hourly(blocks)
    assert round(sum(load)) == 2907

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
    assert pv_res["status_mppt"] is True

    rows, summary = dispatch_simulation(load, solar, pr=0.8, kwp=1350.0, topology="on-grid")
    assert round(summary["total_load"]) == 2907
    assert round(summary["total_pv"]) == 4860

    dims = calc_dimensions(pv_res["n_modul"], modul["length_mm"], modul["width_mm"])
    assert dims["area_bruto_m2"] > 0

    econ = calc_financial_metrics(1350.0, 0.0, summary["total_used"] * 365.0)
    assert econ["capex"] > 0
    assert econ["lcoe_per_kwh"] > 0

if __name__ == "__main__":
    test_full_pipeline_on_grid()
    print("INTEGRATION SUITE PASSED")
