#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_fred_series.py
---------------------
Canonical FRED Time-Series Synchronization & Official Transformation Engine.
Strictly adheres to Section 0.3 of llms-formulas.txt.

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint txt: https://analysisreports.github.io/llms-fred-series.txt
Endpoint json: https://analysisreports.github.io/llms-fred-series.json
"""

import os
import re
import json
import math
import datetime
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Any, Tuple

# ==============================================================================
# 1. CORE CANONICAL FORMULAS (FROM llms-formulas.txt Section 0.3)
# ==============================================================================

def _is_num(val):
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(val)
    except (OverflowError, ValueError, TypeError):
        return False

def _is_pos(val):
    if not _is_num(val):
        return False
    return min(val, 0) != val

def fred_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)):
        return None
    try:
        res = xt - xt_prev
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def fred_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)):
        return None
    try:
        res = xt - xt_year_ago
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def fred_percent_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev == 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def fred_percent_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago == 0:
        return None
    try:
        res = ((xt / xt_year_ago) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def fred_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        ratio = xt / xt_prev
        # Economic Boundary Guard: Prevents asymptotic exponential explosion on extreme daily volatility jumps (e.g. VIX)
        if n_obs_per_yr >= 52 and (ratio > 1.40 or ratio < 0.60):
            return None
        res = (((ratio) ** n_obs_per_yr) - 1.0) * 100.0
        # Strict Plausibility Filter: Cap between -100% and +10,000%
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def fred_continuously_compounded_rate(xt, xt_prev):
    if not all(_is_pos(v) for v in (xt, xt_prev)):
        return None
    try:
        res = (math.log(xt) - math.log(xt_prev)) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def fred_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        res = ((math.log(xt) - math.log(xt_prev)) * 100.0) * n_obs_per_yr
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

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
# 2. FRED API FETCHING UTILITIES
# ==============================================================================

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-FRED-Engine/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def get_series_data_api(series_id: str, api_key: str, n_obs_per_yr: int) -> Optional[Dict[str, Any]]:
    meta_url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={api_key}&file_type=json"
    meta_json = fetch_json(meta_url)
    if not meta_json or "seriess" not in meta_json or not meta_json["seriess"]:
        return None
    s_meta = meta_json["seriess"][0]

    limit = max(30, n_obs_per_yr + 15)
    obs_url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit={limit}"
    obs_json = fetch_json(obs_url)
    if not obs_json or "observations" not in obs_json:
        return None

    raw_obs = obs_json["observations"]
    cleaned_obs = []
    for o in raw_obs:
        val_str = o.get("value", "").strip()
        if val_str and val_str != ".":
            try:
                f_val = float(val_str)
                cleaned_obs.append({"date": o["date"], "value": f_val})
            except ValueError:
                continue

    cleaned_obs.reverse()

    if len(cleaned_obs) < 2:
        return None

    return {
        "metadata": {
            "title": s_meta.get("title", ""),
            "units": s_meta.get("units", ""),
            "source_institution": s_meta.get("source_institution", s_meta.get("units", "FRED"))
        },
        "observations": cleaned_obs
    }

# ==============================================================================
# 3. REGISTRY PARSER & OUTPUT BUILDER
# ==============================================================================

def parse_registry(txt_path: str) -> Tuple[Dict[str, List[str]], str]:
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"{txt_path} not found.")

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    sec2_marker = "# ==============================================================================\n# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)"
    if sec2_marker in content:
        config_part = content.split(sec2_marker)[0]
    else:
        config_part = content

    frequencies = {"DAILY": [], "WEEKLY": [], "MONTHLY": [], "QUARTERLY": [], "SEMIANNUAL": [], "ANNUAL": []}
    curr_freq = None

    for line in config_part.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue
        
        freq_match = re.match(r"^\[(DAILY|WEEKLY|MONTHLY|QUARTERLY|SEMIANNUAL|ANNUAL)\]$", line_clean, re.IGNORECASE)
        if freq_match:
            curr_freq = freq_match.group(1).upper()
            continue
        
        if curr_freq:
            series_id = line_clean.split("#")[0].strip().upper()
            if series_id and series_id not in frequencies[curr_freq]:
                frequencies[curr_freq].append(series_id)

    return frequencies, config_part.rstrip()

def build_outputs(frequencies: Dict[str, List[str]], api_key: str) -> Tuple[str, Dict[str, Any]]:
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_date = now_dt.strftime("%Y-%m-%d")

    txt_blocks = []
    json_series_dict = {}
    total_series = sum(len(v) for v in frequencies.values())

    for freq, s_list in frequencies.items():
        n_obs_per_yr = FREQ_N_MAP.get(freq, 12)
        for s_id in s_list:
            print(f"Fetching: {s_id} ({freq})...")
            data = get_series_data_api(s_id, api_key, n_obs_per_yr)
            if not data:
                print(f"Warning: Could not fetch data for {s_id}")
                continue

            meta = data["metadata"]
            obs = data["observations"]

            t_curr = obs[-1]
            t_prev = obs[-2]
            
            year_ago_idx = len(obs) - 1 - n_obs_per_yr
            t_year_ago = obs[year_ago_idx] if year_ago_idx >= 0 else None

            xt = t_curr["value"]
            xt_prev = t_prev["value"]
            xt_year_ago = t_year_ago["value"] if t_year_ago else None

            c_chg = fred_change(xt, xt_prev)
            c_chg_yr = fred_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_pct = fred_percent_change(xt, xt_prev)
            c_pct_yr = fred_percent_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_car = fred_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)
            c_ccr = fred_continuously_compounded_rate(xt, xt_prev)
            c_ccar = fred_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)

            recent_5 = obs[-5:]

            json_series_dict[s_id] = {
                "series_id": s_id,
                "title": meta.get("title", ""),
                "frequency": freq.capitalize(),
                "n_obs_per_yr": n_obs_per_yr,
                "units": meta.get("units", ""),
                "source": meta.get("source_institution", meta.get("units", "FRED")),
                "last_date": t_curr["date"],
                "current_value": xt,
                "previous_value": xt_prev,
                "year_ago_value": xt_year_ago,
                "transformations": {
                    "change": c_chg,
                    "change_from_year_ago": c_chg_yr,
                    "percent_change": c_pct,
                    "percent_change_from_year_ago": c_pct_yr,
                    "compounded_annual_rate_of_change": c_car,
                    "continuously_compounded_rate_of_change": c_ccr,
                    "continuously_compounded_annual_rate_of_change": c_ccar
                },
                "recent_observations": recent_5
            }

            def fmt(v):
                return f"{v:+.4f}" if v is not None else "N/A"

            recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in recent_5])

            block = f"""--------------------------------------------------------------------------------
Series ID: {s_id}
Title: {meta.get('title', '')}
Frequency: {freq.capitalize()} (n_obs_per_yr: {n_obs_per_yr}) | Units: {meta.get('units', '')}
Last Date: {t_curr['date']} | Current Value: {xt:.4f} | Previous Value: {xt_prev:.4f} | Year Ago Value: {f"{xt_year_ago:.4f}" if xt_year_ago is not None else "N/A"}

Transformations (Official St. Louis Fed Formulas):
  1. Change: {fmt(c_chg)}
  2. Change from Year Ago: {fmt(c_chg_yr)}
  3. Percent Change: {fmt(c_pct)}%
  4. Percent Change from Year Ago: {fmt(c_pct_yr)}%
  5. Compounded Annual Rate of Change: {fmt(c_car)}%
  6. Continuously Compounded Rate of Change: {fmt(c_ccr)}%
  7. Continuously Compounded Annual Rate of Change: {fmt(c_ccar)}%

Recent Observations (Last 5):
{recent_lines}"""
            txt_blocks.append(block)

    txt_body = "\n\n".join(txt_blocks)

    full_txt = f"""# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_utc}
# - Total Series Synced: {len(json_series_dict)} / {total_series}
# - Source Authority: Federal Reserve Bank of St. Louis (FRED API)
# - Canonical Formulas Reference: Section 0.3 of https://analysisreports.github.io/llms-formulas.txt
# - Zero-Hallucination Directive: Values below represent immutable ground truth.

{txt_body}
"""

    full_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical FRED Monitored Series & Official Transformations",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": "SUCCESS",
            "last_successful_sync": now_iso,
            "total_series": len(json_series_dict),
            "source_authority": "Federal Reserve Bank of St. Louis (FRED)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#0.3",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "series": json_series_dict
    }

    return full_txt, full_json

# ==============================================================================
# 4. ENTRYPOINT
# ==============================================================================

def main():
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        print("Error: FRED_API_KEY environment variable is missing.")
        return

    txt_path = "llms-fred-series.txt"
    json_path = "llms-fred-series.json"

    print("Parsing monitored series configuration...")
    frequencies, config_header = parse_registry(txt_path)

    print("Fetching FRED series and computing official transformations...")
    auto_txt, auto_json = build_outputs(frequencies, api_key)

    full_txt_content = config_header + "\n\n" + auto_txt

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_txt_content)
    print(f"Successfully generated {txt_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(auto_json, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {json_path}")

if __name__ == "__main__":
    main()
