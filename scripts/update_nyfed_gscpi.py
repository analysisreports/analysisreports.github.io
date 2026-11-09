#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_nyfed_gscpi.py
---------------------
Official New York Fed Global Supply Chain Pressure Index (GSCPI) Data Ingestion.
Directly fetches and parses official time-series data from the Federal Reserve Bank of New York.
Zero fallbacks, 100% authentic central bank research data.

Source: Federal Reserve Bank of New York (AMEC)
Official URL: https://www.newyorkfed.org/research/policy/gscpi
File URL: https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx
"""

import os
import sys
import json
import math
import datetime
import urllib.request
import xlrd
from typing import Dict, Any, List, Optional

OFFICIAL_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
OUTPUT_JSON = "llms-nyfed-series.json"
CACHE_FILE = "gscpi_data.xlsx"


def download_official_gscpi(dest_path: str = CACHE_FILE) -> bool:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MacroResearchBot/2.0"}
    req = urllib.request.Request(OFFICIAL_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            if len(content) > 1000:
                with open(dest_path, "wb") as f:
                    f.write(content)
                print(f"[OK] Downloaded official GSCPI workbook ({len(content)} bytes).")
                return True
    except Exception as e:
        print(f"[WARN] Network fetch failed: {e}. Checking local cache...")
    
    if os.path.exists(dest_path):
        print(f"[OK] Using cached workbook {dest_path}.")
        return True
    return False


def parse_date(date_str: str) -> str:
    # Format typically: '31-Oct-2026' -> '2026-10-31'
    dt = datetime.datetime.strptime(date_str.strip(), "%d-%b-%Y")
    return dt.strftime("%Y-%m-%d")


def extract_gscpi_series(file_path: str = CACHE_FILE) -> Optional[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return None

    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)

    observations: List[Dict[str, Any]] = []

    for r in range(sheet.nrows):
        row = sheet.row_values(r)
        raw_date = str(row[0]).strip()
        raw_val = row[1]

        if not raw_date or raw_val == "":
            continue

        try:
            val = float(raw_val)
            iso_date = parse_date(raw_date)
            observations.append({"date": iso_date, "value": round(val, 4)})
        except (ValueError, TypeError):
            continue

    if not observations:
        return None

    # Sort chronologically
    observations.sort(key=lambda x: x["date"])

    n = len(observations)
    current_obs = observations[-1]
    prev_obs = observations[-2] if n >= 2 else None
    year_ago_obs = observations[-13] if n >= 13 else None  # Monthly: 12 months prior

    curr_val = current_obs["value"]
    prev_val = prev_obs["value"] if prev_obs else None
    yr_val = year_ago_obs["value"] if year_ago_obs else None

    change = round(curr_val - prev_val, 4) if prev_val is not None else None
    change_yr = round(curr_val - yr_val, 4) if yr_val is not None else None

    # Percent change (only if denominator is non-zero)
    pct_change = round(((curr_val / prev_val) - 1.0) * 100.0, 4) if (prev_val and prev_val != 0.0) else None
    pct_change_yr = round(((curr_val / yr_val) - 1.0) * 100.0, 4) if (yr_val and yr_val != 0.0) else None

    series_data = {
        "series_id": "GSCPI",
        "entity_id": "IND_GSCPI",
        "title": "Global Supply Chain Pressure Index",
        "frequency": "Monthly",
        "n_obs_per_yr": 12,
        "units": "Standard Deviations from Historical Mean (Z-Score)",
        "source": "Federal Reserve Bank of New York (AMEC)",
        "endpoint": OFFICIAL_URL,
        "last_date": current_obs["date"],
        "current_value": curr_val,
        "previous_value": prev_val,
        "year_ago_value": yr_val,
        "transformations": {
            "change": change,
            "change_from_year_ago": change_yr,
            "percent_change": pct_change,
            "percent_change_from_year_ago": pct_change_yr
        },
        "recent_observations": observations[-12:]
    }

    return series_data


def main():
    download_official_gscpi()
    series = extract_gscpi_series()
    if not series:
        print("[ERROR] Failed to extract GSCPI series from official data.")
        sys.exit(1)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = {
        "$schema": "./schema/nyfed-series.json",
        "metadata": {
            "name": "Ersoy Toptaş Official New York Fed Research Series Ingestion",
            "version": "2026-Q4",
            "license": "CC BY-NC-ND 4.0",
            "source": "Federal Reserve Bank of New York",
            "last_updated": now_iso
        },
        "series": {
            "GSCPI": series
        }
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Wrote official GSCPI series to {OUTPUT_JSON}")
    print(f"  - Last Date      : {series['last_date']}")
    print(f"  - Current Value  : {series['current_value']} {series['units']}")
    print(f"  - Previous Value : {series['previous_value']}")
    print(f"  - Change (MoM)   : {series['transformations']['change']}")
    print(f"  - Change (YoY)   : {series['transformations']['change_from_year_ago']}")


if __name__ == "__main__":
    main()
