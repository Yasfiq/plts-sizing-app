import hashlib
import json
import os
from typing import Optional
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")

def get_cache_key(lat: float, lon: float, tilt: float, azim: float, dataset: str, token: str = "") -> str:
    raw = f"{lat:.4f}_{lon:.4f}_{tilt:.1f}_{azim:.1f}_{dataset}_{token.strip()[:8]}"
    return hashlib.md5(raw.encode()).hexdigest()

from datetime import datetime, timezone, timedelta

def parse_ninja_response(data_json: dict, utc_offset_hours: float = 7.0) -> dict[int, float]:
    """
    Mengolah data time-series ninja menjadi profil rata-rata 24 jam dict {jam: kwh/kwp}.
    Mendukung format key epoch millisecond dan string datetime.
    Default timezone offset UTC+7 (WIB / Indonesia Barat).
    """
    data_dict = data_json.get("data")
    if not data_dict or not isinstance(data_dict, dict):
        raise ValueError("Data response Renewables.ninja tidak valid atau kosong.")

    buckets = {h: [] for h in range(24)}
    tz = timezone(timedelta(hours=utc_offset_hours))

    for time_key, entry in data_dict.items():
        val = float(entry.get("electricity", 0.0))
        hour = None

        # Jika key adalah integer / string epoch millisecond
        try:
            ts_ms = int(time_key)
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).astimezone(tz)
            hour = dt.hour
        except (ValueError, TypeError):
            # Fallback ke format string "YYYY-MM-DD HH:MM:SS"
            time_str = str(time_key)
            try:
                hour = int(time_str.split(" ")[1].split(":")[0])
            except Exception:
                try:
                    hour = int(time_str.split("T")[1].split(":")[0])
                except Exception:
                    continue

        if hour is not None and 0 <= hour < 24:
            buckets[hour].append(val)
    
    hourly_dict = {h: 0.0 for h in range(24)}
    for h in range(24):
        if buckets[h]:
            hourly_dict[h] = sum(buckets[h]) / len(buckets[h])
    return hourly_dict

def fetch_pv_profile(
    api_token: str,
    lat: float,
    lon: float,
    tilt: float = 15.0,
    azim: float = 180.0,
    dataset: str = "merra2",
    use_cache: bool = True
) -> dict[int, float]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not api_token:
        raise ValueError("API Token Renewables.ninja tidak boleh kosong.")
    ckey = get_cache_key(lat, lon, tilt, azim, dataset, token=api_token)
    cpath = os.path.join(CACHE_DIR, f"{ckey}.json")
    
    # Hitung offset zona waktu otomatis dari longitude
    if lon < 115.0:
        tz_offset = 7.0   # WIB
    elif lon < 125.0:
        tz_offset = 8.0   # WITA
    else:
        tz_offset = 9.0   # WIT
    
    if use_cache and os.path.exists(cpath):
        with open(cpath, "r") as f:
            return parse_ninja_response(json.load(f), utc_offset_hours=tz_offset)
            
    if not api_token:
        raise ValueError("API Token Renewables.ninja tidak boleh kosong.")

    url = "https://www.renewables.ninja/api/data/pv"
    headers = {"Authorization": f"Token {api_token.strip()}"}
    params = {
        "lat": lat,
        "lon": lon,
        "date_from": "2022-01-01",
        "date_to": "2022-01-07",
        "dataset": dataset,
        "capacity": 1.0,
        "system_loss": 0.1,
        "tracking": 0,
        "tilt": tilt,
        "azim": azim,
        "format": "json"
    }
    
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Gagal mengambil data Ninja API ({resp.status_code}): {resp.text}")
        
    data = resp.json()
    with open(cpath, "w") as f:
        json.dump(data, f)
        
    return parse_ninja_response(data, utc_offset_hours=tz_offset)
