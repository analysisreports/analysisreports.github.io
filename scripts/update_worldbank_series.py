#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_worldbank_series.py
--------------------------
Autonomous World Bank Commodity Time-Series Synchronization Engine.
Fetches official World Bank Commodity Price Data (The Pink Sheet),
extracts historical observations, executes canonical transformations (change, YoY, CAR, CCR),
and generates both deterministic machine-readable twin (llms-worldbank-series.json)
and official text registry snapshot (llms-worldbank-series.txt Section 2).

Includes Rate & Yield Financial Guard: Percentage rates are already annualized.
Compounding an already annualized rate is a category error and produces misleading exponential distortions;
in such cases, CAR and CCAR return None and display as N/A (Rate is already annualized).

Author: Ersoy Toptaş & Google Gemini AI Engine
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/llms-worldbank-series.txt
JSON Twin: https://analysisreports.github.io/llms-worldbank-series.json
"""

import os
import io
import csv
import json
import math
import datetime
import urllib.request
from typing import Dict, Any, Optional, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(ROOT_DIR, "llms-worldbank-series.txt")
OUTPUT_JSON = os.path.join(ROOT_DIR, "llms-worldbank-series.json")

# Official World Bank Open Commodity Data Sources
WB_DATA_SOURCES = {
    "GOLD": {
        "url": "https://raw.githubusercontent.com/datasets/gold-prices/master/data/monthly.csv",
        "name": "World Bank Official Gold Price (The Pink Sheet)",
        "unit": "USD per Troy Ounce",
        "description": "Gold (USD/troy oz), 99.5% fine, London afternoon fixing, average of daily rates",
        "frequency": "Monthly",
        "n_obs_per_yr": 12
    }
}

FREQ_N_MAP = {
    "DAILY": 260,
    "WEEKLY": 52,
    "BIWEEKLY": 26,
    "MONTHLY": 12,
    "QUARTERLY": 4,
    "SEMIANNUAL": 2,
    "ANNUAL": 1
}

# ==============================================================================
# SMART TTL CACHE SPECIFICATION (USER MANDATE & BEST PRACTICES)
# - DAILY: 3 days TTL
# - WEEKLY: 8 days TTL
# - MONTHLY: 32 days TTL
# - QUARTERLY: 95 days TTL
# - SEMIANNUAL: 185 days TTL
# - ANNUAL: 365 days TTL
# Strict Zero-Loss Mandate: If TTL expires and API fails/times out, existing snapshot is 100% retained.
# ==============================================================================
CACHE_TTL_DAYS = {
    "DAILY": 3,
    "WEEKLY": 8,
    "BIWEEKLY": 16,
    "MONTHLY": 32,
    "QUARTERLY": 95,
    "SEMIANNUAL": 185,
    "ANNUAL": 365
}

# ==============================================================================
# CANONICAL TRANSFORMATION FUNCTIONS (ST. LOUIS FED / WB COMPLIANT)
# ==============================================================================

def _is_num(val) -> bool:
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(val)
    except (OverflowError, ValueError, TypeError):
        return False

def _is_pos(val) -> bool:
    return _is_num(val) and val > 0.0

def calc_change(xt, xt_prev) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_prev)):
        return None
    try:
        res = xt - xt_prev
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def calc_percent_change(xt, xt_prev) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev <= 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def calc_percent_change_year_ago(xt, xt_year_ago) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago <= 0:
        return None
    try:
        res = ((xt / xt_year_ago) - 1.0) * 100.0
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def calc_compounded_annual_rate(xt, xt_prev, n_obs_per_yr: int = 12) -> Optional[float]:
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        ratio = xt / xt_prev
        # Economic Boundary Guard: Prevents asymptotic exponential explosion on extreme volatility jumps
        if n_obs_per_yr >= 52 and (ratio > 1.40 or ratio < 0.60):
            return None
        res = (((ratio) ** n_obs_per_yr) - 1.0) * 100.0
        # Strict Plausibility Filter: Cap between -100% and +10,000%
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def calc_continuously_compounded_rate(xt, xt_prev) -> Optional[float]:
    if not all(_is_pos(v) for v in (xt, xt_prev)):
        return None
    try:
        res = (math.log(xt) - math.log(xt_prev)) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def calc_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr: int = 12) -> Optional[float]:
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        res = ((math.log(xt) - math.log(xt_prev)) * 100.0) * n_obs_per_yr
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def fetch_wb_series(key: str, meta: Dict[str, Any], now_iso: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetches full historical time-series and calculates transformations."""
    url = meta["url"]
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-WorldBank-Engine/1.0"})
    
    content = None
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read().decode("utf-8")
                break
        except Exception as e:
            err_msg = str(e)
            if "10013" in err_msg or "Permission denied" in err_msg:
                print(f"  [NETWORK SANDBOX] {url}: {e}")
                return None
            if attempt < 2:
                import time; time.sleep(2)
            else:
                print(f"[HATA] {key} verisi çekilemedi: {e}")
                return None

    if not content:
        return None

    reader = csv.reader(io.StringIO(content.strip()))
    header = next(reader, None)
    
    observations: List[Tuple[str, float]] = []
    for row in reader:
        if len(row) >= 2 and row[1].strip():
            try:
                date_str = row[0].strip()
                val = float(row[1].strip())
                if math.isfinite(val):
                    observations.append((date_str, val))
            except ValueError:
                continue

    if not observations:
        return None

    n_obs_per_yr = meta["n_obs_per_yr"]

    # Current, previous (1 month ago), and year ago (12 months ago)
    curr_date, curr_val = observations[-1]
    prev_val = observations[-2][1] if len(observations) >= 2 else None
    
    year_ago_idx = len(observations) - 1 - n_obs_per_yr
    year_ago_val = observations[year_ago_idx][1] if year_ago_idx >= 0 else None

    # Rate & Yield Financial Guard: Percentage rates are already annualized.
    # Compounding an already annualized rate is a category error and produces misleading exponential distortions.
    units_str = meta.get("unit", "")
    is_rate = "Percent" in units_str or "%" in units_str

    # Canonical transformations
    chg = calc_change(curr_val, prev_val)
    chg_yr = calc_change(curr_val, year_ago_val)
    pct_chg = calc_percent_change(curr_val, prev_val)
    pct_chg_yr = calc_percent_change_year_ago(curr_val, year_ago_val)
    car = None if is_rate else calc_compounded_annual_rate(curr_val, prev_val, n_obs_per_yr)
    ccr = calc_continuously_compounded_rate(curr_val, prev_val)
    ccar = None if is_rate else calc_continuously_compounded_annual_rate(curr_val, prev_val, n_obs_per_yr)

    recent_5 = [{"date": d, "value": v} for d, v in observations[-5:]]

    if not now_iso:
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "series_id": f"IND_WB_{key}",
        "commodity_key": key,
        "name": meta["name"],
        "description": meta["description"],
        "source": "World Bank (The Pink Sheet)",
        "frequency": meta["frequency"],
        "n_obs_per_yr": n_obs_per_yr,
        "unit": meta["unit"],
        "observation_date": f"{curr_date}-01" if len(curr_date) == 7 else curr_date,
        "last_synced_utc": now_iso,
        "current_value": curr_val,
        "previous_value": prev_val,
        "year_ago_value": year_ago_val,
        "transformations": {
            "change": chg,
            "change_from_year_ago": chg_yr,
            "percent_change": pct_chg,
            "percent_change_from_year_ago": pct_chg_yr,
            "compounded_annual_rate_of_change": car,
            "continuously_compounded_rate_of_change": ccr,
            "continuously_compounded_annual_rate_of_change": ccar
        },
        "recent_observations": recent_5
    }

def read_config_section() -> Tuple[List[str], str]:
    """Reads Section 1 (Configuration) of llms-worldbank-series.txt."""
    if not os.path.exists(CONFIG_FILE):
        return ["GOLD"], ""

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by Section 2 marker if present
    marker = "# ==============================================================================\n# 2. CANONICAL OBSERVATIONS"
    if marker in content:
        config_part = content.split(marker)[0].rstrip()
    else:
        config_part = content.rstrip()

    keys = []
    in_freq = False
    for line in config_part.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("[") and line_clean.endswith("]"):
            in_freq = True
            continue
        if in_freq and line_clean and not line_clean.startswith("#"):
            k = line_clean.split("#")[0].strip().upper()
            if k:
                keys.append(k)

    if not keys:
        keys = ["GOLD"]
    return list(dict.fromkeys(keys)), config_part

def fmt_val(v, suffix=""):
    return f"{v:+.4f}{suffix}" if v is not None else "N/A"

def format_wb_txt_block(res: Dict[str, Any]) -> str:
    s_id = res.get("series_id", "")
    name = res.get("name", "")
    freq = res.get("frequency", "")
    n_obs_per_yr = res["n_obs_per_yr"]
    unit = res.get("unit", "")
    obs_date = res.get("observation_date", "")
    xt = res.get("current_value")
    xt_prev = res.get("previous_value")
    xt_year_ago = res.get("year_ago_value")
    t = res.get("transformations", {})

    units_str = unit
    is_rate = "Percent" in units_str or "%" in units_str
    car_str = "N/A (Rate is already annualized)" if is_rate else fmt_val(t.get('compounded_annual_rate_of_change'), '%')
    ccar_str = "N/A (Rate is already annualized)" if is_rate else fmt_val(t.get('continuously_compounded_annual_rate_of_change'), '%')
    recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in res.get("recent_observations", [])])

    xt_str = f"{xt:.4f}" if xt is not None else "N/A"
    xt_prev_str = f"{xt_prev:.4f}" if xt_prev is not None else "N/A"
    xt_yr_str = f"{xt_year_ago:.4f}" if xt_year_ago is not None else "N/A"

    return f"""--------------------------------------------------------------------------------
Series ID: {s_id}
Title: {name}
Frequency: {freq} (n_obs_per_yr: {n_obs_per_yr}) | Units: {unit}
Last Date: {obs_date} | Current Value: {xt_str} | Previous Value: {xt_prev_str} | Year Ago Value: {xt_yr_str}

Transformations (Official World Bank / St. Louis Fed Formulas):
  1. Change: {fmt_val(t.get('change'), '')}
  2. Change from Year Ago: {fmt_val(t.get('change_from_year_ago'), '')}
  3. Percent Change: {fmt_val(t.get('percent_change'), '%')}
  4. Percent Change from Year Ago: {fmt_val(t.get('percent_change_from_year_ago'), '%')}
  5. Compounded Annual Rate of Change: {car_str}
  6. Continuously Compounded Rate of Change: {fmt_val(t.get('continuously_compounded_rate_of_change'), '%')}
  7. Continuously Compounded Annual Rate of Change: {ccar_str}

Recent Observations (Last 5):
{recent_lines}"""

def main():
    print("=" * 70)
    print("WORLD BANK COMMODITY TIME-SERIES SYNCHRONIZATION ENGINE")
    print("=" * 70)

    monitored_keys, config_header = read_config_section()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_series = {}
    fallback_sync_str = None
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                d = json.load(f)
                existing_series = d.get("series", {})
                fallback_sync_str = d.get("metadata", {}).get("last_successful_sync")
        except Exception:
            existing_series = {}

    synced_series = {}
    txt_blocks = []
    stale_series = []
    unsupported_series = []

    for key in monitored_keys:
        if key not in WB_DATA_SOURCES:
            unsupported_series.append(key)
            continue
        meta = WB_DATA_SOURCES[key]
        freq_upper = meta.get("frequency", "Monthly").upper()
        ttl_days = CACHE_TTL_DAYS[freq_upper] if freq_upper in CACHE_TTL_DAYS else CACHE_TTL_DAYS["MONTHLY"]
        s_id = f"IND_WB_{key}"

        cached_entry = existing_series.get(s_id)
        is_cache_valid = False
        elapsed_days = 9999.0

        if cached_entry and isinstance(cached_entry, dict):
            last_sync_str = cached_entry.get("last_synced_utc") or fallback_sync_str
            if last_sync_str:
                try:
                    clean_sync = last_sync_str.replace("Z", "+00:00")
                    sync_dt = datetime.datetime.fromisoformat(clean_sync)
                    elapsed_days = (now_dt - sync_dt).total_seconds() / 86400.0
                    if elapsed_days < ttl_days:
                        is_cache_valid = True
                except Exception:
                    is_cache_valid = False

        # 1. Cache HIT: Süresi dolmamışsa API'ye dokunma, mevcut doğrulanmış veriyi koru
        if is_cache_valid:
            print(f"  [CACHE HIT] {s_id} [{freq_upper}]: Son çekilmeden bu yana {elapsed_days:.1f} gün geçti (TTL: {ttl_days} gün). API isteği atlanıyor.")
            synced_series[s_id] = cached_entry
            txt_blocks.append(format_wb_txt_block(cached_entry))
            continue

        # 2. Süresi dolmuşsa yeni veriyi çek
        print(f"[*] Senkronize ediliyor: {key} ({meta['name']})...")
        res = fetch_wb_series(key, meta, now_iso)

        # 3. API Hata / Zaman Aşımı Sigortası: Asla eski veriyi silme!
        if not res:
            if cached_entry and isinstance(cached_entry, dict):
                print(f"  [API TIMEOUT - RETAINED] {s_id} [{freq_upper}]: Veri kaynağı yanıt vermedi. Mevcut resmi snapshot korundu!")
                stale_series.append(s_id)
                if not cached_entry.get("last_synced_utc") and fallback_sync_str:
                    cached_entry["last_synced_utc"] = fallback_sync_str
                synced_series[s_id] = cached_entry
                txt_blocks.append(format_wb_txt_block(cached_entry))
                continue
            else:
                print(f"[UYARI] {key} verisi çekilemedi ve önbellek mevcut değil.")
                continue

        synced_series[s_id] = res
        print(f"[+] Başarılı: {res['observation_date']} -> {res['current_value']} {res['unit']}")
        txt_blocks.append(format_wb_txt_block(res))

    missing_series = [
        f"IND_WB_{key}" for key in monitored_keys
        if key not in WB_DATA_SOURCES or f"IND_WB_{key}" not in synced_series
    ]
    if not missing_series and not stale_series:
        sync_status = "SUCCESS"
    elif synced_series:
        sync_status = "PARTIAL_SUCCESS"
    else:
        sync_status = "FAILED"

    # 1. Generate full llms-worldbank-series.txt (Section 1 + Section 2)
    txt_body = "\n\n".join(txt_blocks)
    full_txt = f"""{config_header}

# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_utc}
# - Sync Status: {sync_status}
# - Total Series Synced: {len(synced_series)} / {len(monitored_keys)}
# - Missing Series: {", ".join(missing_series) if missing_series else "None"}
# - Retained Stale Series: {", ".join(stale_series) if stale_series else "None"}
# - Source Authority: World Bank Commodity Price Data (The Pink Sheet)
# - Canonical Formulas Reference: Section 0.3 of https://analysisreports.github.io/llms-formulas.txt
# - Zero-Hallucination Directive: Values below represent immutable ground truth.

{txt_body}
"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(full_txt.strip() + "\n")
    print(f"\n[+] {CONFIG_FILE} dosyasına Bölüm 2 (hesaplamalar ve son gözlemler) yazıldı.")

    # 2. Generate full llms-worldbank-series.json
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "engine": "Autonomous World Bank Commodity Time-Series Engine",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": sync_status,
            "last_successful_sync": now_iso if sync_status == "SUCCESS" else fallback_sync_str,
            "data_source": "World Bank Commodity Price Data (The Pink Sheet)",
            "monitored_series_count": len(synced_series),
            "total_registered_series": len(monitored_keys),
            "missing_series": missing_series,
            "stale_series": stale_series,
            "unsupported_series": unsupported_series,
            "canonical_formulas_reference": "https://analysisreports.github.io/llms-formulas.txt"
        },
        "series": synced_series
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[+] {OUTPUT_JSON} dosyasına {len(synced_series)} adet seri yazıldı.")

if __name__ == "__main__":
    main()
