import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
