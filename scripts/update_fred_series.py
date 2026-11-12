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
import csv
import io
import math
import time
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
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev <= 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def fred_percent_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago <= 0:
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
# SMART TTL CACHE SPECIFICATION (USER MANDATE & BEST PRACTICES)
# - DAILY: 3 days TTL (avoids noisy redundant daily pulls)
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
# 2. FRED API FETCHING UTILITIES
# ==============================================================================

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-FRED-Engine/1.0"})
    for attempt in range(1, 3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            err_msg = str(e)
            if "10013" in err_msg or "Permission denied" in err_msg:
                # Sandbox network restriction, break immediately without useless retries
                print(f"  [NETWORK SANDBOX] {url}: {e}")
                return None
            if attempt < 2:
                time.sleep(2)
            else:
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

def fetch_gdppot_for_quarter(observation_date: str) -> Optional[Dict[str, Any]]:
    try:
        quarter = datetime.date.fromisoformat(observation_date)
        if quarter.isoformat() != observation_date or quarter.day != 1 or quarter.month not in (1, 4, 7, 10):
            raise ValueError("GDPC1 observation date is not a quarterly period start")
        query = urllib.parse.urlencode({
            "id": "GDPPOT",
            "cosd": observation_date,
            "coed": observation_date,
        })
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-FRED-Engine/1.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            rows = list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))
        if len(rows) != 1 or rows[0].get("observation_date") != observation_date:
            raise ValueError("FRED did not return exactly the requested GDPPOT quarter")
        value = float(rows[0]["GDPPOT"])
        if not math.isfinite(value) or value <= 1.0:
            raise ValueError("FRED returned an invalid GDPPOT value")
        return {"date": observation_date, "value": value, "source": url}
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, csv.Error) as e:
        print(f"  [ERROR] Could not fetch GDPPOT for GDPC1 quarter {observation_date!r}: {e}")
        return None

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

def format_fred_txt_block(entry: Dict[str, Any]) -> str:
    s_id = entry.get("series_id", "")
    title = entry.get("title", "")
    freq = entry.get("frequency", "")
    n_obs_per_yr = entry["n_obs_per_yr"]
    units = entry.get("units", "")
    last_date = entry.get("last_date", "")
    xt = entry.get("current_value")
    xt_prev = entry.get("previous_value")
    xt_year_ago = entry.get("year_ago_value")
    t = entry.get("transformations", {})

    is_rate = "Percent" in units or "%" in units

    def fmt(v, suffix="%"):
        return f"{v:+.4f}{suffix}" if v is not None else "N/A"

    car_str = "N/A (Rate is already annualized)" if is_rate else fmt(t.get("compounded_annual_rate_of_change"), "%")
    ccar_str = "N/A (Rate is already annualized)" if is_rate else fmt(t.get("continuously_compounded_annual_rate_of_change"), "%")

    recent_5 = entry.get("recent_observations", [])
    recent_lines = "\n".join([f"  {r['date']}: {r['value']:.4f}" for r in recent_5])

    xt_str = f"{xt:.4f}" if xt is not None else "N/A"
    xt_prev_str = f"{xt_prev:.4f}" if xt_prev is not None else "N/A"
    xt_yr_str = f"{xt_year_ago:.4f}" if xt_year_ago is not None else "N/A"

    observation_line = f"Last Date: {last_date} | Current Value: {xt_str}"
    if s_id == "GDPPOT":
        observation_line = f"Latest Observation Date (may be a projection): {last_date} | Latest Observation Value: {xt_str}"

    return f"""--------------------------------------------------------------------------------
Series ID: {s_id}
Title: {title}
Frequency: {freq} (n_obs_per_yr: {n_obs_per_yr}) | Units: {units}
{observation_line} | Previous Value: {xt_prev_str} | Year Ago Value: {xt_yr_str}

Transformations (Official St. Louis Fed Formulas):
  1. Change: {fmt(t.get("change"), '')}
  2. Change from Year Ago: {fmt(t.get("change_from_year_ago"), '')}
  3. Percent Change: {fmt(t.get("percent_change"), '%')}
  4. Percent Change from Year Ago: {fmt(t.get("percent_change_from_year_ago"), '%')}
  5. Compounded Annual Rate of Change: {car_str}
  6. Continuously Compounded Rate of Change: {fmt(t.get("continuously_compounded_rate_of_change"), '%')}
  7. Continuously Compounded Annual Rate of Change: {ccar_str}

Recent Observations (Last 5):
{recent_lines}"""

def recompute_entry_transformations(entry: Dict[str, Any], n_obs_per_yr: int):
    units_str = entry.get("units", "")
    is_rate = "Percent" in units_str or "%" in units_str
    xt = entry.get("current_value")
    xt_prev = entry.get("previous_value")
    xt_year_ago = entry.get("year_ago_value")
    entry["transformations"] = {
        "change": fred_change(xt, xt_prev),
        "change_from_year_ago": fred_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None,
        "percent_change": fred_percent_change(xt, xt_prev),
        "percent_change_from_year_ago": fred_percent_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None,
        "compounded_annual_rate_of_change": None if is_rate else fred_compounded_annual_rate(xt, xt_prev, n_obs_per_yr),
        "continuously_compounded_rate_of_change": fred_continuously_compounded_rate(xt, xt_prev),
        "continuously_compounded_annual_rate_of_change": None if is_rate else fred_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)
    }

def build_outputs(frequencies: Dict[str, List[str]], api_key: str, existing_series: Optional[Dict[str, Any]] = None, fallback_sync_str: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    if existing_series is None:
        existing_series = {}

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_utc = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    txt_blocks = []
    json_series_dict = {}
    total_series = sum(len(v) for v in frequencies.values())

    for freq, s_list in frequencies.items():
        if freq not in FREQ_N_MAP:
            raise ValueError(f"Unknown FRED frequency '{freq}'")
        n_obs_per_yr = FREQ_N_MAP[freq]
        ttl_days = CACHE_TTL_DAYS[freq] if freq in CACHE_TTL_DAYS else 3

        for s_id in s_list:
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
                print(f"  [CACHE HIT] {s_id} [{freq}]: Son çekilmeden bu yana {elapsed_days:.1f} gün geçti (TTL: {ttl_days} gün). API isteği atlanıyor.")
                recompute_entry_transformations(cached_entry, n_obs_per_yr)
                json_series_dict[s_id] = cached_entry
                txt_blocks.append(format_fred_txt_block(cached_entry))
                continue

            # 2. Süresi dolmuşsa veya yeni seriyse FRED API'den çek
            print(f"  [FETCHING] {s_id} [{freq}] (TTL doldu veya yeni seri, FRED API'sine bağlanılıyor)...")
            data = None
            if api_key:
                data = get_series_data_api(s_id, api_key, n_obs_per_yr)
            else:
                print(f"  [WARNING] FRED_API_KEY bulunamadı, API isteği yapılamıyor.")

            # 3. API Hata / Zaman Aşımı Koruma Sigortası: Asla eski veriyi silme!
            if not data:
                if cached_entry and isinstance(cached_entry, dict):
                    print(f"  [API TIMEOUT - RETAINED] {s_id} [{freq}]: API yanıt vermedi veya anahtar yok. Mevcut resmi snapshot korundu!")
                    if not cached_entry.get("last_synced_utc"):
                        cached_entry["last_synced_utc"] = fallback_sync_str or now_iso
                    recompute_entry_transformations(cached_entry, n_obs_per_yr)
                    json_series_dict[s_id] = cached_entry
                    txt_blocks.append(format_fred_txt_block(cached_entry))
                    continue
                else:
                    print(f"  Warning: Could not fetch data for {s_id} and no cached snapshot exists.")
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

            units_str = meta.get("units", "")
            # Rate & Yield Financial Guard: Percentage rates are already annualized.
            is_rate = "Percent" in units_str or "%" in units_str

            c_chg = fred_change(xt, xt_prev)
            c_chg_yr = fred_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_pct = fred_percent_change(xt, xt_prev)
            c_pct_yr = fred_percent_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_car = None if is_rate else fred_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)
            c_ccr = fred_continuously_compounded_rate(xt, xt_prev)
            c_ccar = None if is_rate else fred_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)

            recent_5 = obs[-5:]

            entry_dict = {
                "series_id": s_id,
                "title": meta.get("title", ""),
                "frequency": freq.capitalize(),
                "n_obs_per_yr": n_obs_per_yr,
                "units": meta.get("units", ""),
                "source": meta.get("source_institution", meta.get("units", "FRED")),
                "last_date": t_curr["date"],
                "last_synced_utc": now_iso,
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

            json_series_dict[s_id] = entry_dict
            txt_blocks.append(format_fred_txt_block(entry_dict))

    gdpc1 = json_series_dict.get("GDPC1")
    gdppot = json_series_dict.get("GDPPOT")
    if gdpc1 is not None and gdppot is not None:
        gdppot["gdpc1_quarter_observation"] = fetch_gdppot_for_quarter(gdpc1.get("last_date"))
        matched = gdppot["gdpc1_quarter_observation"]
        if matched is not None:
            txt_blocks.append(
                f"GDPPOT observation matched to GDPC1 quarter: {matched['date']} | "
                f"Value: {matched['value']:.4f} | Source: {matched['source']}"
            )
        else:
            txt_blocks.append("GDPPOT observation matched to GDPC1 quarter: N/A (fetch failed)")

    synced_count = len(json_series_dict)
    all_sids = [s for s_list in frequencies.values() for s in s_list]
    missing_sids = [s for s in all_sids if s not in json_series_dict]
    sync_status = "SUCCESS" if synced_count == total_series else ("PARTIAL_SUCCESS" if synced_count > 0 else "FAILED")
    missing_line = f"\n# - Inactive / Pending Series: {', '.join(missing_sids)}" if missing_sids else ""

    txt_body = "\n\n".join(txt_blocks)

    full_txt = f"""# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_utc}
# - Sync Status: {sync_status} ({synced_count} / {total_series} series active)
# - Total Series Synced: {synced_count} / {total_series}{missing_line}
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
            "sync_status": sync_status,
            "last_successful_sync": now_iso,
            "total_series": synced_count,
            "total_registered": total_series,
            "missing_series": missing_sids,
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
        print("[NOTICE] FRED_API_KEY environment variable is not set. Cache retrieval & retention will operate.")

    txt_path = "llms-fred-series.txt"
    json_path = "llms-fred-series.json"

    print("Parsing monitored series configuration...")
    frequencies, config_header = parse_registry(txt_path)

    existing_series = {}
    fallback_sync_str = None
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                existing_series = d.get("series", {})
                fallback_sync_str = d.get("metadata", {}).get("last_successful_sync")
        except Exception:
            existing_series = {}

    print("Processing FRED series with Smart TTL Cache & Non-Destructive Retention...")
    auto_txt, auto_json = build_outputs(frequencies, api_key, existing_series, fallback_sync_str)

    full_txt_content = config_header + "\n\n" + auto_txt

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(full_txt_content)
    print(f"Successfully generated {txt_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(auto_json, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {json_path}")

if __name__ == "__main__":
    main()
