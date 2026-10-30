# tests/test_data_loader.py
import io
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data_loader import (
    blocks_to_hourly,
    parse_load_profile_csv,
    parse_load_profile_excel,
    generate_load_template_csv,
)

def test_blocks_to_hourly():
    # 7 periode acuan user
    blocks = [
        (0, 6, 89.0),
        (6, 9, 98.0),
        (9, 12, 180.0),
        (12, 15, 208.0),
        (15, 18, 167.0),
        (18, 21, 79.0),
        (21, 24, 59.0)
    ]
    hourly = blocks_to_hourly(blocks)
    assert len(hourly) == 24
    assert hourly[0] == 89.0
    assert hourly[7] == 98.0
    assert hourly[12] == 208.0
    assert sum(hourly) == 2907.0

def test_blocks_to_hourly_validation():
    # Gap check
    try:
        blocks_to_hourly([(0, 12, 10.0)])
        assert False, "Harus gagal jika gap jam ada"
    except ValueError:
        pass

    # Overlap check
    try:
        blocks_to_hourly([(0, 12, 10.0), (10, 24, 10.0)])
        assert False, "Harus gagal jika ada overlap jam"
    except ValueError:
        pass

    # Negatif beban
    try:
        blocks_to_hourly([(0, 24, -5.0)])
        assert False, "Harus gagal jika beban negatif"
    except ValueError:
        pass

def test_parse_load_profile_csv():
    data = "jam,beban_kw\n" + "\n".join([f"{h},100" for h in range(24)])
    f = io.StringIO(data)
    hourly = parse_load_profile_csv(f)
    assert len(hourly) == 24
    assert sum(hourly) == 2400.0

def test_parse_load_profile_csv_96_intervals():
    data = "timestamp,power_kw\n" + "\n".join([f"{i},10" for i in range(96)])
    f = io.StringIO(data)
    hourly = parse_load_profile_csv(f)
    assert len(hourly) == 24
    assert hourly[0] == 10.0
    assert sum(hourly) == 240.0

def test_parse_load_profile_excel():
    df = pd.DataFrame({"jam": list(range(24)), "load_kw": [50.0] * 24})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    hourly = parse_load_profile_excel(buf)
    assert len(hourly) == 24
    assert sum(hourly) == 1200.0

def test_generate_load_template_csv():
    tmpl = generate_load_template_csv()
    lines = tmpl.strip().split("\n")
    assert lines[0] == "jam,beban_kw"
    assert len(lines) == 25
    assert lines[1] == "0,0.0"
    assert lines[-1] == "23,0.0"

if __name__ == "__main__":
    test_blocks_to_hourly()
    test_blocks_to_hourly_validation()
    test_parse_load_profile_csv()
    test_parse_load_profile_csv_96_intervals()
    test_parse_load_profile_excel()
    test_generate_load_template_csv()
    print("ALL TESTS PASSED")
