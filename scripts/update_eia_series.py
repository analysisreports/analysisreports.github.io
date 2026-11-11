#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_eia_series.py
---------------------
Autonomous U.S. Energy Information Administration (EIA API v2) Time-Series
Ingestion, Strategic Petroleum Reserve (SPR) Tracking & Canonical Transformation Engine.

Fetches official energy data from the U.S. Department of Energy / EIA:
1. PET.WCSSTUS1.W : Weekly U.S. Ending Stocks of Crude Oil in Strategic Petroleum Reserve (SPR)
2. PET.WCESTUS1.W : Weekly U.S. Ending Stocks of Crude Oil Excluding SPR (Commercial)
3. PET.WCRFPUS2.W : Weekly U.S. Field Production of Crude Oil
4. PET.WGTSTUS1.W : Weekly U.S. Ending Stocks of Total Gasoline
5. NG.NW2_EPG0_SWO_R48_BCF.W : Weekly Lower 48 States Working Gas in Underground Storage

Features:
- Smart TTL Caching (WEEKLY: 8 days TTL)
- Non-Destructive Fallback Retention: If API call fails or times out, valid existing snapshots are preserved.
- Negative-Base Shielded Percent Change: Avoids misleading inverted signs on non-positive bases.
- Dual Outputs: Synchronizes text twin (llms-eia-series.txt) and machine-readable JSON twin (llms-eia-series.json).

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/llms-eia-series.txt
JSON Twin: https://analysisreports.github.io/llms-eia-series.json
"""

import os
import re
import sys
import json
import math
import time
import datetime
import urllib.request
from typing import Dict, Any, Optional, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(ROOT_DIR, "llms-eia-series.txt")
OUTPUT_JSON = os.path.join(ROOT_DIR, "llms-eia-series.json")
OUTPUT_TXT = os.path.join(ROOT_DIR, "llms-eia-series.txt")

EIA_API_V2_BASE = "https://api.eia.gov/v2"

# Canonical Metadata Registry for Core EIA Series
SERIES_METADATA: Dict[str, Dict[str, Any]] = {
    "PET.WCSSTUS1.W": {
        "title": "Weekly U.S. Ending Stocks of Crude Oil in Strategic Petroleum Reserve (SPR)",
        "frequency": "Weekly",
        "n_obs_per_yr": 52,
        "units": "Thousand Barrels",
        "description": "Crude oil stocks held in the federal Strategic Petroleum Reserve emergency caverns."
    },
    "PET.WCESTUS1.W": {
        "title": "Weekly U.S. Ending Stocks of Crude Oil Excluding SPR (Commercial Stocks)",
        "frequency": "Weekly",
        "n_obs_per_yr": 52,
        "units": "Thousand Barrels",
        "description": "Domestic commercial crude oil inventories held at refineries, bulk terminals, and pipelines."
    },
    "PET.WCRFPUS2.W": {
        "title": "Weekly U.S. Field Production of Crude Oil",
        "frequency": "Weekly",
        "n_obs_per_yr": 52,
        "units": "Thousand Barrels per Day",
        "description": "Aggregate domestic crude extraction rate across US shale and conventional basins."
    },
    "PET.WGTSTUS1.W": {
        "title": "Weekly U.S. Ending Stocks of Total Gasoline",
        "frequency": "Weekly",
        "n_obs_per_yr": 52,
        "units": "Thousand Barrels",
        "description": "Finished motor gasoline and blending components held in commercial storage."
    },
    "NG.NW2_EPG0_SWO_R48_BCF.W": {
        "title": "Weekly Lower 48 States Working Gas in Underground Natural Gas Storage",
        "frequency": "Weekly",
        "n_obs_per_yr": 52,
        "units": "Billion Cubic Feet",
        "description": "Volume of working natural gas in underground storage facilities across the Lower 48 states."
    }
}

FREQ_N_MAP = {
    "DAILY": 260,
    "WEEKLY": 52,
    "MONTHLY": 12,
    "ANNUAL": 1
}

CACHE_TTL_DAYS = {
    "DAILY": 3,
    "WEEKLY": 8,
    "MONTHLY": 32,
    "ANNUAL": 365
}

def _is_num(val: Any) -> bool:
    if val is None or isinstance(val, bool):
        return False
    try:
        f = float(val)
        return math.isfinite(f)
    except (ValueError, TypeError):
        return False

def eia_change(xt: float, xt_prev: float) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_prev)):
        return None
    try:
        res = xt - xt_prev
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def eia_percent_change(xt: float, xt_prev: float) -> Optional[float]:
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev <= 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def fetch_eia_series_observations(series_id: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """Fetches series observations from EIA API v2 with robust route and seriesid fallbacks."""
    if not api_key:
        return None

    # Primary EIA v2 seriesid route:
    url = f"{EIA_API_V2_BASE}/seriesid/{series_id}?api_key={api_key}"
    headers = {"User-Agent": "AnalysisReports-EIA-Engine/2.0"}
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode('utf-8'))
                    response_data = payload.get("response", {})
                    data_list = response_data.get("data", [])
                    if data_list:
                        clean_obs = []
                        for row in data_list:
                            period = str(row.get("period", "")).strip()
                            raw_val = row.get("value")
                            if period and _is_num(raw_val):
                                clean_obs.append({"date": period, "value": float(raw_val)})
                        # Sort chronological (oldest to newest)
                        clean_obs.sort(key=lambda x: x["date"])
                        return clean_obs
        except Exception as e:
            err_msg = str(e)
            if "10013" in err_msg or "Permission denied" in err_msg:
                print(f"  [NETWORK SANDBOX] {url}: {e}")
                return None
            if attempt < 2:
                time.sleep(2)
            else:
                print(f"  [WARNING] EIA API error for {series_id}: {e}")
    return None

def read_config_section() -> Tuple[Dict[str, List[str]], str]:
    if not os.path.exists(CONFIG_FILE):
        default_cfg = f"""# Ersoy Toptaş Canonical EIA Time-Series Registry (llms-eia-series.txt)
> Official U.S. Energy Information Administration (EIA) Time-Series Snapshots & Strategic Petroleum Reserve Engine.
> Author: Ersoy Toptaş | Version: 2026-Q4 | License: CC BY 4.0
> Endpoint: https://analysisreports.github.io/llms-eia-series.txt
> JSON Twin Endpoint: https://analysisreports.github.io/llms-eia-series.json
> Root Index: https://analysisreports.github.io/llms.txt

# ==============================================================================
# 1. MONITORED TIME-SERIES CONFIGURATION (USER REGISTRY)
# ==============================================================================
[WEEKLY]
PET.WCSSTUS1.W
PET.WCESTUS1.W
PET.WCRFPUS2.W
PET.WGTSTUS1.W
NG.NW2_EPG0_SWO_R48_BCF.W

[MONTHLY]
"""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(default_cfg)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    split_marker = "# ==============================================================================\n# 2. CANONICAL OBSERVATIONS"
    if split_marker in content:
        config_part = content.split(split_marker)[0]
    else:
        config_part = content

    frequencies: Dict[str, List[str]] = {"DAILY": [], "WEEKLY": [], "MONTHLY": [], "ANNUAL": []}
    curr_freq = None
    for line in config_part.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#") or line_clean.startswith(">"):
            continue
        freq_match = re.match(r"^\[([A-Z]+)\]$", line_clean)
        if freq_match:
            curr_freq = freq_match.group(1).upper()
            continue
        if curr_freq and curr_freq in frequencies:
            sid = line_clean.split("#")[0].strip()
            if sid and sid not in frequencies[curr_freq]:
                frequencies[curr_freq].append(sid)

    return frequencies, config_part.rstrip()

def format_eia_txt_block(entry: Dict[str, Any]) -> str:
    s_id = entry.get("series_id", "")
    title = entry.get("title", "")
    freq = entry.get("frequency", "")
    n_obs = entry["n_obs_per_yr"]
    units = entry.get("units", "")
    last_date = entry.get("last_date", "")
    xt = entry.get("current_value")
    xt_prev = entry.get("previous_value")
    xt_year_ago = entry.get("year_ago_value")
    t = entry.get("transformations", {})

    def fmt_val(v, suffix=""):
        return f"{v:+.4f}{suffix}" if v is not None else "N/A"

    recent_5 = entry.get("recent_observations", [])
    recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in recent_5])

    xt_str = f"{xt:.4f}" if xt is not None else "N/A"
    xt_prev_str = f"{xt_prev:.4f}" if xt_prev is not None else "N/A"
    xt_yr_str = f"{xt_year_ago:.4f}" if xt_year_ago is not None else "N/A"

    return f"""--------------------------------------------------------------------------------
Series ID: {s_id}
Title: {title}
Frequency: {freq} (n_obs_per_yr: {n_obs}) | Units: {units}
Last Date: {last_date} | Current Value: {xt_str} | Previous Value: {xt_prev_str} | Year Ago Value: {xt_yr_str}

Transformations (Official U.S. EIA Methodology):
  1. Change: {fmt_val(t.get("change"))}
  2. Change from Year Ago: {fmt_val(t.get("change_from_year_ago"))}
  3. Percent Change: {fmt_val(t.get("percent_change"), "%")}
  4. Percent Change from Year Ago: {fmt_val(t.get("percent_change_from_year_ago"), "%")}

Recent Observations (Last 5):
{recent_lines}"""

def main():
    print("=" * 70)
    print("U.S. ENERGY INFORMATION ADMINISTRATION (EIA API v2) SYNC ENGINE")
    print("=" * 70)

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        print("[NOTICE] EIA_API_KEY environment variable is not set. Cache retrieval & retention will operate.")

    frequencies, config_header = read_config_section()

    existing_series: Dict[str, Any] = {}
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                cached_doc = json.load(f)
                existing_series = cached_doc.get("series", {})
                print(f"[OK] Loaded {len(existing_series)} series from existing JSON cache.")
        except Exception as e:
            print(f"[WARN] Failed to read existing JSON cache: {e}")

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    txt_blocks = []
    json_series_dict: Dict[str, Any] = {}
    total_registered = sum(len(sids) for sids in frequencies.values())

    for freq, s_list in frequencies.items():
        if freq not in FREQ_N_MAP or freq not in CACHE_TTL_DAYS:
            continue
        n_obs = FREQ_N_MAP[freq]
        ttl_days = CACHE_TTL_DAYS[freq]

        for s_id in s_list:
            meta = SERIES_METADATA.get(s_id, {
                "title": f"EIA Series {s_id}",
                "frequency": freq.capitalize(),
                "n_obs_per_yr": n_obs,
                "units": "Units",
                "description": "EIA API time-series dataset."
            })

            cached_entry = existing_series.get(s_id)
            is_cache_valid = False

            if cached_entry and cached_entry.get("last_synced_utc"):
                try:
                    last_dt = datetime.datetime.fromisoformat(cached_entry["last_synced_utc"].replace("Z", "+00:00"))
                    elapsed_days = (now_dt - last_dt).total_seconds() / 86400.0
                    if elapsed_days < ttl_days:
                        is_cache_valid = True
                except Exception:
                    is_cache_valid = False

            if is_cache_valid:
                print(f"  [CACHE HIT] {s_id} [{freq}]: Snapshot fresh. Using cached entry.")
                json_series_dict[s_id] = cached_entry
                txt_blocks.append(format_eia_txt_block(cached_entry))
                continue

            observations = None
            if api_key:
                print(f"  [FETCHING] {s_id} [{freq}]: Connecting to EIA API v2...")
                observations = fetch_eia_series_observations(s_id, api_key)

            if not observations:
                if cached_entry:
                    print(f"  [RETAINED] {s_id} [{freq}]: API call unfulfilled. Retaining valid existing snapshot.")
                    json_series_dict[s_id] = cached_entry
                    txt_blocks.append(format_eia_txt_block(cached_entry))
                    continue
                else:
                    print(f"  [PENDING] {s_id} [{freq}]: No cache available and API unfulfilled.")
                    continue

            # Process observations
            current_obs = observations[-1]
            prev_obs = observations[-2] if len(observations) >= 2 else None
            yr_ago_idx = max(0, len(observations) - 1 - n_obs) if len(observations) > n_obs else None
            yr_ago_obs = observations[yr_ago_idx] if yr_ago_idx is not None else None

            xt = current_obs["value"]
            xt_prev = prev_obs["value"] if prev_obs else None
            xt_yr = yr_ago_obs["value"] if yr_ago_obs else None

            chg = eia_change(xt, xt_prev)
            chg_yr = eia_change(xt, xt_yr)
            pct = eia_percent_change(xt, xt_prev)
            pct_yr = eia_percent_change(xt, xt_yr)

            entry_dict = {
                "series_id": s_id,
                "title": meta["title"],
                "frequency": meta["frequency"],
                "n_obs_per_yr": meta["n_obs_per_yr"],
                "units": meta["units"],
                "description": meta["description"],
                "last_date": current_obs["date"],
                "last_synced_utc": now_iso,
                "current_value": xt,
                "previous_value": xt_prev,
                "year_ago_value": xt_yr,
                "transformations": {
                    "change": chg,
                    "change_from_year_ago": chg_yr,
                    "percent_change": pct,
                    "percent_change_from_year_ago": pct_yr
                },
                "recent_observations": observations[-24:]
            }

            json_series_dict[s_id] = entry_dict
            txt_blocks.append(format_eia_txt_block(entry_dict))

    synced_count = len(json_series_dict)
    all_sids = [s for s_list in frequencies.values() for s in s_list]
    missing_sids = [s for s in all_sids if s not in json_series_dict]
    sync_status = "SUCCESS" if synced_count == total_registered and total_registered > 0 else ("PARTIAL_SUCCESS" if synced_count > 0 else "PENDING_INITIAL_PULL")
    missing_line = f"\n# - Inactive / Pending Series: {', '.join(missing_sids)}" if missing_sids else ""

    txt_body = "\n\n".join(txt_blocks)

    full_txt = f"""{config_header}

# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_utc}
# - Sync Status: {sync_status} ({synced_count} / {total_registered} series active)
# - Total Series Synced: {synced_count} / {total_registered}{missing_line}
# - Source Authority: U.S. Energy Information Administration (EIA Open Data API v2)
# - Zero-Hallucination Directive: Values below represent immutable ground truth.

{txt_body}
"""

    full_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical U.S. Energy Information Administration (EIA) Series Registry",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": sync_status,
            "last_successful_sync": now_iso,
            "total_series": synced_count,
            "total_registered": total_registered,
            "missing_series": missing_sids,
            "source_authority": "U.S. Energy Information Administration (EIA API v2)",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "series": json_series_dict
    }

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(full_txt)
    print(f"Successfully generated {OUTPUT_TXT}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(full_json, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
