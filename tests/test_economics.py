import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
        bos_cost_pct=0.15,
        opex_pct=0.015,
        discount_rate=0.08,
        degradation_rate=0.007,
        years=25
    )
    assert res["capex"] > 0
    assert res["annual_opex"] > 0
    assert res["payback_years"] > 0
    assert res["npv"] > 0
    assert res["lcoe_per_kwh"] > 0
    assert abs(res["capex"] - (100*1000*3500.0 + 100*1000*1200.0) * 1.15) < 1e-6
    assert abs(res["annual_opex"] - res["capex"] * 0.015) < 1e-6
    assert abs(res["first_year_saving"] - 140000.0 * 1444.7) < 1e-6

if __name__ == "__main__":
    test_financial_metrics()
    print("ALL TESTS PASSED")
