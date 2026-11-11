#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_ecb_series.py
---------------------
Canonical European Central Bank (ECB Data Portal) Time-Series Synchronization
& Official Transformation Engine. Strictly adheres to Section 0.5 of llms-formulas.txt.

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint txt: https://analysisreports.github.io/llms-ecb-series.txt
Endpoint json: https://analysisreports.github.io/llms-ecb-series.json
Methodology: https://analysisreports.github.io/llms-formulas.txt#0.5
"""

import os
import re
import csv
import ssl
import json
import math
import io
import datetime
import urllib.request
from typing import Dict, List, Optional, Any, Tuple

# ==============================================================================
# 1. CORE CANONICAL FORMULAS (FROM llms-formulas.txt Section 0.5)
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

def ecb_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)):
        return None
    try:
        res = xt - xt_prev
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def ecb_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)):
        return None
    try:
        res = xt - xt_year_ago
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def ecb_percent_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev == 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def ecb_percent_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago == 0:
        return None
    try:
        res = ((xt / xt_year_ago) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def ecb_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        ratio = xt / xt_prev
        # Economic Boundary Guard: Prevents asymptotic explosion on extreme volatility jumps
        if n_obs_per_yr >= 52 and (ratio > 1.40 or ratio < 0.60):
            return None
        res = (((ratio) ** n_obs_per_yr) - 1.0) * 100.0
        # Strict Plausibility Filter: Cap between -100% and +10,000%
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def ecb_continuously_compounded_rate(xt, xt_prev):
    if not all(_is_pos(v) for v in (xt, xt_prev)):
        return None
    try:
        res = (math.log(xt) - math.log(xt_prev)) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def ecb_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
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

SERIES_METADATA = {
    "EXR/D.USD.EUR.SP00.A": {
        "title": "Euro / US Dollar Spot Exchange Rate",
        "units": "USD per 1 EUR",
        "category": "Foreign Exchange"
    },
    "EXR/D.GBP.EUR.SP00.A": {
        "title": "Euro / UK Pound Sterling Spot Exchange Rate",
        "units": "GBP per 1 EUR",
        "category": "Foreign Exchange"
    },
    "EXR/D.CHF.EUR.SP00.A": {
        "title": "Euro / Swiss Franc Spot Exchange Rate",
        "units": "CHF per 1 EUR",
        "category": "Foreign Exchange"
    },
    "EXR/D.JPY.EUR.SP00.A": {
        "title": "Euro / Japanese Yen Spot Exchange Rate",
        "units": "JPY per 1 EUR",
        "category": "Foreign Exchange"
    },
    "EST/B.EU000A2X2A25.WT": {
        "title": "Euro Short-Term Rate (€STR) Benchmark",
        "units": "Percent per Annum",
        "category": "Money Market Benchmark"
    },
    "ILM/W.U2.C.T000000.Z5.Z01": {
        "title": "Eurosystem Consolidated Balance Sheet - Total Assets",
        "units": "Millions of EUR",
        "category": "Central Bank Liquidity"
    },
    "FM/B.U2.EUR.4F.KR.MRR_FR.LEV": {
        "title": "ECB Main Refinancing Operations (MRO) Fixed Rate",
        "units": "Percent per Annum",
        "category": "Policy Benchmark Rate"
    },
    "FM/B.U2.EUR.4F.KR.DFR.LEV": {
        "title": "ECB Deposit Facility Rate (DFR - Primary Policy Rate)",
        "units": "Percent per Annum",
        "category": "Policy Benchmark Rate"
    },
    "FM/B.U2.EUR.4F.KR.MLFR.LEV": {
        "title": "ECB Marginal Lending Facility Rate (MLFR)",
        "units": "Percent per Annum",
        "category": "Policy Benchmark Rate"
    },
    "ICP/M.U2.N.000000.4.ANR": {
        "title": "Euro Area HICP Headline Inflation Rate",
        "units": "Annual Rate of Change (%)",
        "category": "Consumer Prices"
    },
    "ICP/M.U2.N.XEF000.4.ANR": {
        "title": "Euro Area Core HICP Inflation Rate (Excl. Energy & Food)",
        "units": "Annual Rate of Change (%)",
        "category": "Consumer Prices"
    }
}

# ==============================================================================
# 2. ECB DATA PORTAL REST API INGESTION
# ==============================================================================

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_ecb_observations(series_ref: str, n_obs_per_yr: int) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches raw CSV observations directly from the ECB Data Portal REST API.
    Syntax: DATAFLOW/KEY
    """
    parts = series_ref.strip().split('/')
    if len(parts) != 2:
        return None
    
    flow, key = parts[0], parts[1]
    limit = max(35, n_obs_per_yr + 15)
    url = f"https://data-api.ecb.europa.eu/service/data/{flow}/{key}?lastNObservations={limit}&format=csvdata&detail=dataonly"
    
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-ECB-Engine/1.0"})
    ctx = get_ssl_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            if resp.status == 200:
                csv_text = resp.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(csv_text))
                raw_obs = []
                for row in reader:
                    tp = row.get("TIME_PERIOD", "").strip()
                    val_str = row.get("OBS_VALUE", "").strip()
                    if tp and val_str and val_str != ".":
                        try:
                            f_val = float(val_str)
                            raw_obs.append({"date": tp, "value": f_val})
                        except ValueError:
                            continue
                return raw_obs
    except Exception as e:
        print(f"Error fetching ECB series {series_ref}: {e}")
        return None

# ==============================================================================
# 3. REGISTRY PARSING & OUTPUT BUILDER
# ==============================================================================

def parse_registry(txt_path: str) -> Tuple[Dict[str, List[str]], str]:
    frequencies: Dict[str, List[str]] = {
        "DAILY": [],
        "WEEKLY": [],
        "BIWEEKLY": [],
        "MONTHLY": [],
        "QUARTERLY": [],
        "SEMIANNUAL": [],
        "ANNUAL": []
    }
    
    if not os.path.exists(txt_path):
        return frequencies, ""
        
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    split_marker = "# ==============================================================================\n# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)"
    if split_marker not in content:
        split_marker = "# 2. CANONICAL OBSERVATIONS"
    
    parts = content.split(split_marker)
    config_header = parts[0].strip()

    current_freq = None
    for line in config_header.split("\n"):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue
        m = re.match(r"^\[([A-Z]+)\]$", line_clean)
        if m:
            freq_candidate = m.group(1)
            if freq_candidate in frequencies:
                current_freq = freq_candidate
            else:
                current_freq = None
        elif current_freq and "/" in line_clean:
            frequencies[current_freq].append(line_clean)

    return frequencies, config_header

def build_outputs(frequencies: Dict[str, List[str]]) -> Tuple[str, Dict[str, Any]]:
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    txt_blocks = []
    json_series_dict = {}
    total_series = sum(len(s_list) for s_list in frequencies.values())

    for freq, s_list in frequencies.items():
        if not s_list:
            continue
        if freq not in FREQ_N_MAP:
            raise ValueError(f"Unknown ECB frequency '{freq}' for series {code}")
    n_obs_per_yr = FREQ_N_MAP[freq]

        for s_ref in s_list:
            print(f"Processing ECB series: {s_ref} [{freq}]...")
            obs = fetch_ecb_observations(s_ref, n_obs_per_yr)
            if not obs:
                print(f"  Warning: No observations returned for {s_ref}")
                continue

            t_curr = obs[-1]
            t_prev = obs[-2] if len(obs) >= 2 else None
            t_year_ago = obs[-n_obs_per_yr - 1] if len(obs) > n_obs_per_yr else None

            xt = t_curr["value"]
            xt_prev = t_prev["value"] if t_prev else None
            xt_year_ago = t_year_ago["value"] if t_year_ago else None

            meta = SERIES_METADATA.get(s_ref, {
                "title": f"European Central Bank Monitored Indicator ({s_ref})",
                "units": "Raw Level Units",
                "category": "ECB Monetary Series"
            })

            # Central Bank Rate Guard: Interest rates and percentages are already annualized.
            # Compounding an already annualized percentage is a category error and produces misleading distortions.
            is_rate = "Percent per Annum" in meta.get("units", "") or "%" in meta.get("units", "")

            # Compute transformations
            c_chg = ecb_change(xt, xt_prev)
            c_chg_yr = ecb_change_year_ago(xt, xt_year_ago)
            c_pct = ecb_percent_change(xt, xt_prev)
            c_pct_yr = ecb_percent_change_year_ago(xt, xt_year_ago)
            c_car = None if is_rate else ecb_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)
            c_ccr = ecb_continuously_compounded_rate(xt, xt_prev)
            c_ccar = None if is_rate else ecb_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)

            recent_5 = obs[-5:]

            json_series_dict[s_ref] = {
                "series_ref": s_ref,
                "title": meta.get("title", ""),
                "frequency": freq.capitalize(),
                "n_obs_per_yr": n_obs_per_yr,
                "units": meta.get("units", ""),
                "category": meta.get("category", ""),
                "source": "European Central Bank (ECB Data Portal)",
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

            def fmt(v, suffix="%"):
                return f"{v:+.4f}{suffix}" if v is not None else "N/A"

            car_str = "N/A (Rate is already annualized)" if is_rate else fmt(c_car, "%")
            ccar_str = "N/A (Rate is already annualized)" if is_rate else fmt(c_ccar, "%")

            recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in recent_5])

            block = f"""--------------------------------------------------------------------------------
Series Ref: {s_ref}
Title: {meta.get('title', '')}
Frequency: {freq.capitalize()} (n_obs_per_yr: {n_obs_per_yr}) | Units: {meta.get('units', '')}
Last Date: {t_curr['date']} | Current Value: {xt:.4f} | Previous Value: {f"{xt_prev:.4f}" if xt_prev is not None else "N/A"} | Year Ago Value: {f"{xt_year_ago:.4f}" if xt_year_ago is not None else "N/A"}

Transformations (Official ECB Formulation - Section 0.5):
  1. Change: {fmt(c_chg, '')}
  2. Change from Year Ago: {fmt(c_chg_yr, '')}
  3. Percent Change: {fmt(c_pct, '%')}
  4. Percent Change from Year Ago: {fmt(c_pct_yr, '%')}
  5. Compounded Annual Rate of Change: {car_str}
  6. Continuously Compounded Rate of Change: {fmt(c_ccr, '%')}
  7. Continuously Compounded Annual Rate of Change: {ccar_str}

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
# - Source Authority: European Central Bank (ECB Data Portal REST API)
# - Canonical Formulas Reference: Section 0.5 of https://analysisreports.github.io/llms-formulas.txt
# - Zero-Hallucination Directive: Values below represent immutable ground truth.

{txt_body}
"""

    full_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical European Central Bank (ECB) Monitored Series & Official Transformations",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": "SUCCESS",
            "last_successful_sync": now_iso,
            "total_series": len(json_series_dict),
            "source_authority": "European Central Bank (ECB Data Portal)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#0.5",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "series": json_series_dict
    }

    return full_txt, full_json

# ==============================================================================
# 4. ENTRYPOINT
# ==============================================================================

def main():
    txt_path = "llms-ecb-series.txt"
    json_path = "llms-ecb-series.json"

    print("Parsing monitored ECB series configuration from llms-ecb-series.txt...")
    frequencies, config_header = parse_registry(txt_path)

    print("Fetching ECB series and computing official Section 0.5 transformations...")
    auto_txt, auto_json = build_outputs(frequencies)

    full_txt_content = config_header + "\n\n" + auto_txt

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_txt_content)
    print(f"Successfully generated {txt_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(auto_json, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {json_path}")

if __name__ == "__main__":
    main()
