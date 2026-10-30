# tests/test_ninja_client.py
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ninja_client import get_cache_key, parse_ninja_response

def test_parse_ninja_response():
    sample = {
        "data": {
            "2026-01-01 06:00:00": {"electricity": 0.1},
            "2026-01-01 07:00:00": {"electricity": 0.3},
            "2026-01-01T12:00:00": {"electricity": 0.8},
            "2026-01-01 18:00:00": {"electricity": 0.0}
        }
    }
    hourly = parse_ninja_response(sample)
    assert isinstance(hourly, dict)
    assert len(hourly) == 24
    assert hourly[6] == 0.1
    assert hourly[12] == 0.8
    assert hourly[0] == 0.0

def test_get_cache_key():
    key1 = get_cache_key(-6.2, 106.8, 15.0, 180.0, "merra2")
    key2 = get_cache_key(-6.2, 106.8, 15.0, 180.0, "merra2")
    key3 = get_cache_key(-6.2, 106.8, 20.0, 180.0, "merra2")
    assert key1 == key2
    assert key1 != key3

if __name__ == "__main__":
    test_parse_ninja_response()
    test_get_cache_key()
    print("ALL TESTS PASSED")
