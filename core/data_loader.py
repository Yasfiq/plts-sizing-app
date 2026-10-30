import io
import pandas as pd

def blocks_to_hourly(blocks: list[tuple[int, int, float]]) -> list[float]:
    """Mengubah list blok (start_hour, end_hour, kw) menjadi 24 jam daya rata-rata."""
    hourly = [0.0] * 24
    covered = [0] * 24
    for start, end, kw in blocks:
        if not (0 <= start < end <= 24):
            raise ValueError(f"Rentang jam tidak valid: {start}-{end}")
        if kw < 0:
            raise ValueError(f"Daya beban tidak boleh negatif: {kw}")
        for h in range(start, end):
            covered[h] += 1
            hourly[h] = float(kw)
    
    missing = [h for h, c in enumerate(covered) if c == 0]
    overlap = [h for h, c in enumerate(covered) if c > 1]
    if missing or overlap:
        raise ValueError(f"Profil beban tidak menutup 24 jam (hilang: {missing}, overlap: {overlap})")
    return hourly

def parse_load_profile_csv(file_obj) -> list[float]:
    """Membaca CSV kolom [jam, beban_kw] atau file 24 baris data."""
    df = pd.read_csv(file_obj)
    return _extract_24h_from_df(df, target_col_keywords=["beban", "load", "kw", "power"])

def parse_load_profile_excel(file_obj) -> list[float]:
    """Membaca file Excel profil beban."""
    df = pd.read_excel(file_obj)
    return _extract_24h_from_df(df, target_col_keywords=["beban", "load", "kw", "power"])

def _extract_24h_from_df(df: pd.DataFrame, target_col_keywords: list[str]) -> list[float]:
    val_col = None
    for col in df.columns:
        if any(k in str(col).lower() for k in target_col_keywords):
            val_col = col
            break
    if val_col is None:
        # Fallback ke kolom numerik kedua atau pertama
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) >= 2:
            val_col = num_cols[1]
        elif len(num_cols) == 1:
            val_col = num_cols[0]
        else:
            raise ValueError("Tidak ditemukan kolom numerik beban dalam file.")
    
    vals = df[val_col].dropna().astype(float).tolist()
    if len(vals) == 24:
        return vals
    elif len(vals) == 96: # Interval 15-menit -> resample ke 24 jam
        return [sum(vals[i:i+4])/4.0 for i in range(0, 96, 4)]
    else:
        raise ValueError(f"Data harus berjumlah 24 jam (atau 96 baris untuk interval 15 menit). Ditemukan: {len(vals)}")

def generate_load_template_csv() -> str:
    lines = ["jam,beban_kw"]
    for h in range(24):
        lines.append(f"{h},0.0")
    return "\n".join(lines)

def parse_solar_profile(file_obj, factor: float = 1.0) -> dict[int, float]:
    """Membaca CSV/XLSX profil surya kolom [jam, irradiansi] menjadi dict {jam: nilai * factor}."""
    name = str(getattr(file_obj, "name", file_obj)).lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj)
    else:
        df = pd.read_csv(file_obj)
    vals = _extract_24h_from_df(
        df,
        target_col_keywords=["irradiansi", "radiasi", "irradiance", "surya", "kw", "w/m2", "power"],
    )
    return {h: v * factor for h, v in enumerate(vals)}
