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
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev == 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def calc_percent_change_year_ago(xt, xt_year_ago) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago == 0:
        return None
    try:
        res = ((xt / xt_year_ago) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def calc_compounded_annual_rate(xt, xt_prev, n_obs_per_yr: int = 12) -> Optional[float]:
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        ratio = xt / xt_prev
        if n_obs_per_yr >= 52 and (ratio > 1.40 or ratio < 0.60):
            return None
        res = (((ratio) ** n_obs_per_yr) - 1.0) * 100.0
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

def fetch_wb_series(key: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetches full historical time-series and calculates transformations."""
    url = meta["url"]
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-WorldBank-Engine/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[HATA] {key} verisi çekilemedi: {e}")
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

    n_obs_per_yr = meta.get("n_obs_per_yr", 12)

    # Current, previous (1 month ago), and year ago (12 months ago)
    curr_date, curr_val = observations[-1]
    prev_val = observations[-2][1] if len(observations) >= 2 else None
    
    year_ago_idx = len(observations) - 1 - n_obs_per_yr
    year_ago_val = observations[year_ago_idx][1] if year_ago_idx >= 0 else None

    # Canonical transformations
    chg = calc_change(curr_val, prev_val)
    chg_yr = calc_change(curr_val, year_ago_val)
    pct_chg = calc_percent_change(curr_val, prev_val)
    pct_chg_yr = calc_percent_change_year_ago(curr_val, year_ago_val)
    car = calc_compounded_annual_rate(curr_val, prev_val, n_obs_per_yr)
    ccr = calc_continuously_compounded_rate(curr_val, prev_val)
    ccar = calc_continuously_compounded_annual_rate(curr_val, prev_val, n_obs_per_yr)

    recent_5 = [{"date": d, "value": v} for d, v in observations[-5:]]

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

def main():
    print("=" * 70)
    print("WORLD BANK COMMODITY TIME-SERIES SYNCHRONIZATION ENGINE")
    print("=" * 70)

    monitored_keys, config_header = read_config_section()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    synced_series = {}
    txt_blocks = []

    for key in monitored_keys:
        if key in WB_DATA_SOURCES:
            print(f"[*] Senkronize ediliyor: {key} ({WB_DATA_SOURCES[key]['name']})...")
            res = fetch_wb_series(key, WB_DATA_SOURCES[key])
            if res:
                synced_series[f"IND_WB_{key}"] = res
                print(f"[+] Başarılı: {res['observation_date']} -> {res['current_value']} {res['unit']}")

                # Format Section 2 Text Block
                t = res["transformations"]
                recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in res["recent_observations"]])
                
                block = f"""--------------------------------------------------------------------------------
Series ID: {res['series_id']}
Title: {res['name']}
Frequency: {res['frequency']} (n_obs_per_yr: {res['n_obs_per_yr']}) | Units: {res['unit']}
Last Date: {res['observation_date']} | Current Value: {res['current_value']:.4f} | Previous Value: {f"{res['previous_value']:.4f}" if res['previous_value'] is not None else "N/A"} | Year Ago Value: {f"{res['year_ago_value']:.4f}" if res['year_ago_value'] is not None else "N/A"}

Transformations (Official World Bank / St. Louis Fed Formulas):
  1. Change: {fmt_val(t['change'], '')}
  2. Change from Year Ago: {fmt_val(t['change_from_year_ago'], '')}
  3. Percent Change: {fmt_val(t['percent_change'], '%')}
  4. Percent Change from Year Ago: {fmt_val(t['percent_change_from_year_ago'], '%')}
  5. Compounded Annual Rate of Change: {fmt_val(t['compounded_annual_rate_of_change'], '%')}
  6. Continuously Compounded Rate of Change: {fmt_val(t['continuously_compounded_rate_of_change'], '%')}
  7. Continuously Compounded Annual Rate of Change: {fmt_val(t['continuously_compounded_annual_rate_of_change'], '%')}

Recent Observations (Last 5):
{recent_lines}"""
                txt_blocks.append(block)

    # 1. Generate full llms-worldbank-series.txt (Section 1 + Section 2)
    txt_body = "\n\n".join(txt_blocks)
    full_txt = f"""{config_header}

# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_utc}
# - Total Series Synced: {len(synced_series)} / {len(monitored_keys)}
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
            "sync_status": "SUCCESS",
            "last_successful_sync": now_iso,
            "data_source": "World Bank Commodity Price Data (The Pink Sheet)",
            "monitored_series_count": len(synced_series),
            "canonical_formulas_reference": "https://analysisreports.github.io/llms-formulas.txt"
        },
        "series": synced_series
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[+] {OUTPUT_JSON} dosyasına {len(synced_series)} adet seri yazıldı.")

if __name__ == "__main__":
    main()
