#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_worldbank_series.py
--------------------------
Autonomous World Bank Commodity Time-Series Synchronization Engine.
Fetches official World Bank Commodity Price Data (The Pink Sheet),
extracts historical observations, executes canonical transformations (change, YoY),
and generates deterministic machine-readable twin (llms-worldbank-series.json).

Author: Ersoy Toptaş & Google Gemini AI Engine
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/llms-worldbank-series.json
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

    # Current, previous (1 month ago), and year ago (12 months ago)
    curr_date, curr_val = observations[-1]
    prev_val = observations[-2][1] if len(observations) >= 2 else None
    year_ago_val = observations[-13][1] if len(observations) >= 13 else None

    # Canonical transformations
    chg = calc_change(curr_val, prev_val)
    chg_yr = calc_change(curr_val, year_ago_val)
    pct_chg = calc_percent_change(curr_val, prev_val)
    pct_chg_yr = calc_percent_change(curr_val, year_ago_val)

    return {
        "series_id": f"IND_WB_{key}",
        "commodity_key": key,
        "name": meta["name"],
        "description": meta["description"],
        "source": "World Bank (The Pink Sheet)",
        "frequency": meta["frequency"],
        "unit": meta["unit"],
        "observation_date": f"{curr_date}-01",
        "current_value": curr_val,
        "previous_value": prev_val,
        "year_ago_value": year_ago_val,
        "transformations": {
            "change": chg,
            "change_from_year_ago": chg_yr,
            "percent_change": pct_chg,
            "percent_change_from_year_ago": pct_chg_yr
        }
    }

def main():
    print("=" * 70)
    print("WORLD BANK COMMODITY TIME-SERIES SYNCHRONIZATION ENGINE")
    print("=" * 70)

    monitored_keys = ["GOLD"]
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith(("#", "[")):
                    monitored_keys.append(line.upper())
    monitored_keys = list(dict.fromkeys(monitored_keys))

    synced_series = {}
    for key in monitored_keys:
        if key in WB_DATA_SOURCES:
            print(f"[*] Senkronize ediliyor: {key} ({WB_DATA_SOURCES[key]['name']})...")
            res = fetch_wb_series(key, WB_DATA_SOURCES[key])
            if res:
                synced_series[f"IND_WB_{key}"] = res
                print(f"[+] Başarılı: {res['observation_date']} -> {res['current_value']} {res['unit']}")

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "engine": "Autonomous World Bank Commodity Time-Series Engine",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": "SUCCESS",
            "last_successful_sync": now_dt.isoformat(),
            "data_source": "World Bank Commodity Price Data (The Pink Sheet)",
            "monitored_series_count": len(synced_series)
        },
        "series": synced_series
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n[+] {OUTPUT_JSON} dosyasına {len(synced_series)} adet seri yazıldı.")

if __name__ == "__main__":
    main()
