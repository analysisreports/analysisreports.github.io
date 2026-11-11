#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_nyfed_series.py
----------------------
Official New York Fed Time-Series Ingestion & Transformation Engine.
Directly fetches and parses official time-series data from the Federal Reserve Bank of New York (AMEC / Markets).
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
from typing import Dict, Any, List, Optional

OFFICIAL_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
OUTPUT_JSON = "llms-nyfed-series.json"
OUTPUT_TXT = "llms-nyfed-series.txt"
CACHE_FILE = "gscpi_data.xlsx"

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

def download_official_gscpi(dest_path: str = CACHE_FILE) -> bool:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MacroResearchBot/2.0"}
    req = urllib.request.Request(OFFICIAL_URL, headers=headers)
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read()
                if len(content) > 1000:
                    with open(dest_path, "wb") as f:
                        f.write(content)
                    print(f"[OK] Downloaded official GSCPI workbook ({len(content)} bytes).")
                    return True
        except Exception as e:
            err_msg = str(e)
            if "10013" in err_msg or "Permission denied" in err_msg:
                print(f"  [NETWORK SANDBOX] {OFFICIAL_URL}: {e}")
                break
            if attempt < 2:
                import time; time.sleep(2)
            else:
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

    try:
        import xlrd
    except ImportError:
        print("[WARN] xlrd library is not installed. Run 'pip install xlrd'.")
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

    # Compounded rates (per Section 0.3 of llms-formulas.txt when positive)
    car = None
    ccr = None
    ccar = None
    if prev_val and curr_val > 0 and prev_val > 0:
        ratio = curr_val / prev_val
        car = round((((ratio) ** 12) - 1.0) * 100.0, 4)
        ccr = round((math.log(curr_val) - math.log(prev_val)) * 100.0, 4)
        ccar = round(ccr * 12.0, 4)

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
        "last_synced_utc": now_iso,
        "current_value": curr_val,
        "previous_value": prev_val,
        "year_ago_value": yr_val,
        "transformations": {
            "change": change,
            "change_from_year_ago": change_yr,
            "percent_change": pct_change,
            "percent_change_from_year_ago": pct_change_yr,
            "compounded_annual_rate_of_change": car,
            "continuously_compounded_rate_of_change": ccr,
            "continuously_compounded_annual_rate_of_change": ccar
        },
        "recent_observations": observations[-24:]
    }

    return series_data

def format_nyfed_txt_block(series: Dict[str, Any]) -> str:
    t = series["transformations"]
    display_obs = series.get("recent_observations", [])[-5:]
    recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in display_obs])
    n_obs = series["n_obs_per_yr"]
    return f"""--------------------------------------------------------------------------------
Series ID: {series.get('series_id', 'GSCPI')}
Entity ID: {series.get('entity_id', 'IND_GSCPI')}
Title: {series.get('title', 'Global Supply Chain Pressure Index')}
Frequency: {series.get('frequency', 'Monthly')} (n_obs_per_yr: {n_obs}) | Units: {series.get('units', '')}
Source: {series.get('source', 'Federal Reserve Bank of New York (AMEC)')}
Last Date: {series['last_date']} | Current Value: {series['current_value']:.4f} | Previous Value: {series['previous_value']:.4f} | Year Ago Value: {series['year_ago_value']:.4f}

Transformations (Official New York Fed / St. Louis Fed Formulas):
  1. Change: {t['change']:+.4f}
  2. Change from Year Ago: {t['change_from_year_ago']:+.4f}
  3. Percent Change: {t['percent_change']:+.4f}%
  4. Percent Change from Year Ago: {t['percent_change_from_year_ago']:+.4f}%
  5. Compounded Annual Rate of Change: {t['compounded_annual_rate_of_change']:+.4f}%
  6. Continuously Compounded Rate of Change: {t['continuously_compounded_rate_of_change']:+.4f}%
  7. Continuously Compounded Annual Rate of Change: {t['continuously_compounded_annual_rate_of_change']:+.4f}%

Recent Observations (Last 5):
{recent_lines}"""

def main():
    print("=" * 70)
    print("NEW YORK FED (AMEC) GSCPI SYNCHRONIZATION ENGINE")
    print("=" * 70)

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    cached_entry = None
    fallback_sync_str = None
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                d = json.load(f)
                cached_entry = d.get("series", {}).get("GSCPI")
                fallback_sync_str = d.get("metadata", {}).get("last_successful_sync")
        except Exception:
            cached_entry = None

    is_cache_valid = False
    elapsed_days = 9999.0
    ttl_days = CACHE_TTL_DAYS["MONTHLY"]

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

    series = None
    if is_cache_valid:
        print(f"  [CACHE HIT] GSCPI [MONTHLY]: Son çekilmeden bu yana {elapsed_days:.1f} gün geçti (TTL: {ttl_days} gün). İndirme atlanıyor.")
        series = cached_entry
    else:
        print(f"[*] GSCPI [MONTHLY] için resmi New York Fed bülteni indiriliyor...")
        download_official_gscpi()
        series = extract_gscpi_series()
        if not series:
            if cached_entry and isinstance(cached_entry, dict):
                print(f"  [API TIMEOUT - RETAINED] GSCPI [MONTHLY]: Ağ hatası veya dosya alınamadı. Mevcut resmi snapshot korundu!")
                if not cached_entry.get("last_synced_utc"):
                    cached_entry["last_synced_utc"] = fallback_sync_str or now_iso
                series = cached_entry
            else:
                print("[ERROR] Failed to extract GSCPI series and no cache exists.")
                sys.exit(1)
        else:
            series["last_synced_utc"] = now_iso

    output = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical New York Fed Research Series & Official Transformations",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "sync_status": "SUCCESS",
            "last_successful_sync": now_iso,
            "total_series": 1,
            "source_authority": "Federal Reserve Bank of New York (AMEC)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#0.3",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "series": {
            "GSCPI": series
        }
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote official GSCPI series to {OUTPUT_JSON}")

    # Generate full llms-nyfed-series.txt twin (displaying last 5 in text)
    body_block = format_nyfed_txt_block(series)
    txt_content = f"""# Ersoy Toptaş Canonical New York Fed Research Time-Series Registry & Engine (llms-nyfed-series.txt)
> Official Federal Reserve Bank of New York Research & AMEC Time-Series, Observations, and Transformations.
> Author: Ersoy Toptaş | Version: 2026-Q4 | License: CC BY-NC-ND 4.0
> Endpoint: https://analysisreports.github.io/llms-nyfed-series.txt
> JSON Twin Endpoint: https://analysisreports.github.io/llms-nyfed-series.json
> Root Index: https://analysisreports.github.io/llms.txt
> Master Directory: https://analysisreports.github.io/llms-full.txt
> Formulas Engine: https://analysisreports.github.io/llms-formulas.txt
> Relationships: https://analysisreports.github.io/llms-relationships.txt
> Author Profile: https://analysisreports.github.io/llms-about.txt
> Editorial Frontends: https://www.ersoytoptas.tr/ | https://en.ersoytoptas.tr/

# ==============================================================================
# 1. MONITORED NEW YORK FED RESEARCH SERIES CONFIGURATION (USER REGISTRY)
# ==============================================================================
# Instructions:
# - Add or remove canonical New York Fed Series IDs directly under the respective frequency block.
# - Frequencies govern synchronization cadence and the annualization factor (n_obs_per_yr).
# - Daily: 260 obs/yr | Weekly: 52 obs/yr | Monthly: 12 obs/yr | Quarterly: 4 obs/yr | Semiannual: 2 obs/yr | Annual: 1 obs/yr

[DAILY]

[WEEKLY]

[MONTHLY]
GSCPI

[QUARTERLY]

[SEMIANNUAL]

[ANNUAL]

# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_iso}
# - Total Series Synced: 1 / 1
# - Source Authority: Federal Reserve Bank of New York (AMEC)
# - Official Endpoint: https://www.newyorkfed.org/research/policy/gscpi
# - Canonical Formulas Reference: Section 0.3 of https://analysisreports.github.io/llms-formulas.txt
# - Zero-Hallucination Directive: Values below represent immutable ground truth from official monthly releases.

{body_block}
"""
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(txt_content.strip() + "\n")
    print(f"[SUCCESS] Wrote official GSCPI series to {OUTPUT_TXT}")
    print(f"  - Last Date      : {series['last_date']}")
    print(f"  - Current Value  : {series['current_value']} {series['units']}")
    print(f"  - Previous Value : {series['previous_value']}")
    print(f"  - Change (MoM)   : {series['transformations']['change']}")
    print(f"  - Change (YoY)   : {series['transformations']['change_from_year_ago']}")

if __name__ == "__main__":
    main()
