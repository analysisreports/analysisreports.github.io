#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_imf_series.py
--------------------
Canonical International Monetary Fund (IMF) Time-Series Synchronization
& Official Transformation Engine. Strictly adheres to Section 0.3 of llms-formulas.txt.

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint txt: https://analysisreports.github.io/llms-imf-series.txt
Endpoint json: https://analysisreports.github.io/llms-imf-series.json
Methodology: https://analysisreports.github.io/llms-formulas.txt#0.3
"""

import os
import re
import io
import csv
import ssl
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

def imf_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)):
        return None
    try:
        res = xt - xt_prev
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def imf_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)):
        return None
    try:
        res = xt - xt_year_ago
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def imf_percent_change(xt, xt_prev):
    if not (_is_num(xt) and _is_num(xt_prev)) or xt_prev <= 0:
        return None
    try:
        res = ((xt / xt_prev) - 1.0) * 100.0
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def imf_percent_change_year_ago(xt, xt_year_ago):
    if not (_is_num(xt) and _is_num(xt_year_ago)) or xt_year_ago <= 0:
        return None
    try:
        res = ((xt / xt_year_ago) - 1.0) * 100.0
        if not math.isfinite(res) or res > 10000.0 or res < -100.0:
            return None
        return round(res, 4)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None

def imf_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
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

def imf_continuously_compounded_rate(xt, xt_prev):
    if not all(_is_pos(v) for v in (xt, xt_prev)):
        return None
    try:
        res = (math.log(xt) - math.log(xt_prev)) * 100.0
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

def imf_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr):
    if not all(_is_pos(v) for v in (xt, xt_prev, n_obs_per_yr)):
        return None
    try:
        res = ((math.log(xt) - math.log(xt_prev)) * 100.0) * n_obs_per_yr
        return round(res, 4) if math.isfinite(res) else None
    except (OverflowError, ValueError):
        return None

# ==============================================================================
# 2. DATA INGESTION UTILITIES (IMF API & FRED MIRROR)
# ==============================================================================

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TXT_FILE = os.path.join(ROOT_DIR, "llms-imf-series.txt")
JSON_FILE = os.path.join(ROOT_DIR, "llms-imf-series.json")

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
    "daily": 3,
    "weekly": 8,
    "biweekly": 16,
    "monthly": 32,
    "quarterly": 95,
    "semiannual": 185,
    "annual": 365,
    "DAILY": 3,
    "WEEKLY": 8,
    "BIWEEKLY": 16,
    "MONTHLY": 32,
    "QUARTERLY": 95,
    "SEMIANNUAL": 185,
    "ANNUAL": 365
}

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-IMF-Engine/1.0"})
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
                import time; time.sleep(2)
            else:
                pass
    return None

def get_series_data_live(series_id: str, api_key: Optional[str], n_obs_per_yr: int) -> Optional[Dict[str, Any]]:
    # Strategy 1: If FRED_API_KEY is present, query FRED IMF mirror
    if api_key:
        meta_url = f"https://api.stlouisfed.org/fred/series?series_id={series_id}&api_key={api_key}&file_type=json"
        meta_json = fetch_json(meta_url)
        if meta_json and "seriess" in meta_json and meta_json["seriess"]:
            s_meta = meta_json["seriess"][0]
            limit = max(30, n_obs_per_yr + 15)
            obs_url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit={limit}"
            obs_json = fetch_json(obs_url)
            if obs_json and "observations" in obs_json:
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
                if len(cleaned_obs) >= 2:
                    return {
                        "metadata": {
                            "title": s_meta.get("title", ""),
                            "units": s_meta.get("units", ""),
                            "source_institution": "International Monetary Fund (IMF)"
                        },
                        "observations": cleaned_obs
                    }

    return None

# ==============================================================================
# 3. REGISTRY PARSER & PROCESSING PIPELINE
# ==============================================================================

def parse_registry(txt_path: str) -> Tuple[Dict[str, List[str]], str]:
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"{txt_path} not found.")

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    sec2_marker = "# ==============================================================================\n# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)"
    if sec2_marker in content:
        config_part = content.split(sec2_marker)[0].rstrip()
    else:
        sec2_idx = content.find("# 2. CANONICAL OBSERVATIONS")
        if sec2_idx != -1:
            raw = content[:sec2_idx].rstrip()
            while raw.endswith("# =============================================================================="):
                raw = raw[:-80].rstrip()
            config_part = raw
        else:
            config_part = content.rstrip()

    frequencies = {"daily": [], "weekly": [], "monthly": [], "quarterly": [], "semiannual": [], "annual": []}
    curr_freq = None

    for line in config_part.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        freq_match = re.match(r"^\[(DAILY|WEEKLY|MONTHLY|QUARTERLY|SEMIANNUAL|ANNUAL)\]$", line_clean, re.I)
        if freq_match:
            curr_freq = freq_match.group(1).lower()
        elif curr_freq:
            series_id = line_clean.split()[0].strip()
            if series_id and series_id not in frequencies[curr_freq]:
                frequencies[curr_freq].append(series_id)

    return frequencies, config_part

def format_imf_txt_block(entry: Dict[str, Any]) -> str:
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

    return f"""--------------------------------------------------------------------------------
Series ID: {s_id}
Title: {title}
Frequency: {freq} (n_obs_per_yr: {n_obs_per_yr}) | Units: {units}
Last Date: {last_date} | Current Value: {xt_str} | Previous Value: {xt_prev_str} | Year Ago Value: {xt_yr_str}

Transformations (Official IMF / St. Louis Fed Formulas):
  1. Change: {fmt(t.get("change"), '')}
  2. Change from Year Ago: {fmt(t.get("change_from_year_ago"), '')}
  3. Percent Change: {fmt(t.get("percent_change"), '%')}
  4. Percent Change from Year Ago: {fmt(t.get("percent_change_from_year_ago"), '%')}
  5. Compounded Annual Rate of Change: {car_str}
  6. Continuously Compounded Rate of Change: {fmt(t.get("continuously_compounded_rate_of_change"), '%')}
  7. Continuously Compounded Annual Rate of Change: {ccar_str}

Recent Observations (Last 5):
{recent_lines}"""

def main():
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("[NOTICE] FRED_API_KEY environment variable is not set. Cache retrieval & retention will operate.")

    registry, header_part = parse_registry(TXT_FILE)

    freq_n_map = {
        "daily": 260,
        "weekly": 52,
        "biweekly": 26,
        "monthly": 12,
        "quarterly": 4,
        "semiannual": 2,
        "annual": 1
    }

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_display = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")

    existing_series = {}
    fallback_sync_str = None
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                existing_series = d.get("series", {})
                fallback_sync_str = d.get("metadata", {}).get("last_successful_sync")
        except Exception:
            existing_series = {}

    json_series_dict: Dict[str, Any] = {}
    txt_blocks: List[str] = []
    stale_series: List[str] = []

    for freq, series_ids in registry.items():
        if not series_ids:
            continue
        if freq not in freq_n_map:
            raise ValueError(f"Unknown IMF frequency '{freq}'")
        n_obs_per_yr = freq_n_map[freq]
        ttl_days = CACHE_TTL_DAYS[freq] if freq in CACHE_TTL_DAYS else 3

        for s_id in series_ids:
            cached_entry = existing_series.get(s_id)
            is_cache_valid = False
            elapsed_days = 9999.0

            if cached_entry and isinstance(cached_entry, dict):
                last_sync_str = cached_entry.get("last_synced_utc") or fallback_sync_str
                if last_sync_str:
                    try:
                        clean_sync = last_sync_str.replace("Z", "+00:00")
                        sync_dt = datetime.datetime.fromisoformat(clean_sync)
                        elapsed_days = (utc_now - sync_dt).total_seconds() / 86400.0
                        if elapsed_days < ttl_days:
                            is_cache_valid = True
                    except Exception:
                        is_cache_valid = False

            # 1. Cache HIT: Süresi dolmamışsa API'ye dokunma, mevcut doğrulanmış veriyi koru
            if is_cache_valid:
                print(f"  [CACHE HIT] {s_id} [{freq.upper()}]: Son çekilmeden bu yana {elapsed_days:.1f} gün geçti (TTL: {ttl_days} gün). API isteği atlanıyor.")
                json_series_dict[s_id] = cached_entry
                txt_blocks.append(format_imf_txt_block(cached_entry))
                continue

            # 2. Süresi dolmuşsa API'den yeni veriyi çek
            print(f"  [FETCHING] {s_id} [{freq.upper()}] (TTL doldu veya yeni seri, IMF/FRED mirror'a bağlanılıyor)...")
            data = None
            if api_key:
                data = get_series_data_live(s_id, api_key, n_obs_per_yr)
            else:
                print(f"  [WARNING] FRED_API_KEY bulunamadı, API isteği yapılamıyor.")

            # 3. API Hata / Zaman Aşımı Sigortası: Asla eski veriyi silme!
            if not data or len(data.get("observations", [])) < 2:
                if cached_entry and isinstance(cached_entry, dict):
                    print(f"  [API TIMEOUT - RETAINED] {s_id} [{freq.upper()}]: API yanıt vermedi veya anahtar yok. Mevcut resmi snapshot korundu!")
                    stale_series.append(s_id)
                    if not cached_entry.get("last_synced_utc") and fallback_sync_str:
                        cached_entry["last_synced_utc"] = fallback_sync_str
                    json_series_dict[s_id] = cached_entry
                    txt_blocks.append(format_imf_txt_block(cached_entry))
                    continue
                else:
                    print(f"[UYARI] {s_id} için yeterli veri alınamadı ve önbellek mevcut değil.")
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
            # Rate & Yield Financial Guard
            is_rate = "Percent" in units_str or "%" in units_str

            c_chg = imf_change(xt, xt_prev)
            c_chg_yr = imf_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_pct = imf_percent_change(xt, xt_prev)
            c_pct_yr = imf_percent_change_year_ago(xt, xt_year_ago) if xt_year_ago is not None else None
            c_car = None if is_rate else imf_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)
            c_ccr = imf_continuously_compounded_rate(xt, xt_prev)
            c_ccar = None if is_rate else imf_continuously_compounded_annual_rate(xt, xt_prev, n_obs_per_yr)

            recent_5 = obs[-5:]

            entry_dict = {
                "series_id": s_id,
                "title": meta.get("title", ""),
                "frequency": freq.capitalize(),
                "n_obs_per_yr": n_obs_per_yr,
                "units": meta.get("units", ""),
                "source": meta.get("source_institution", "International Monetary Fund (IMF)"),
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
            txt_blocks.append(format_imf_txt_block(entry_dict))

    total_registered = sum(len(v) for v in registry.values())
    missing_series = [
        s_id for series_ids in registry.values() for s_id in series_ids
        if s_id not in json_series_dict
    ]
    if not missing_series and not stale_series:
        sync_status = "SUCCESS"
    elif json_series_dict:
        sync_status = "PARTIAL_SUCCESS"
    else:
        sync_status = "FAILED"

    txt_body = "\n\n".join(txt_blocks)

    full_txt = f"""{header_part}

# ==============================================================================
# 2. CANONICAL OBSERVATIONS & OFFICIAL TRANSFORMATIONS (AUTO-GENERATED)
# ==============================================================================
# Ingestion Contract & Epistemological Directives:
# - Synced At: {now_display}
# - Sync Status: {sync_status}
# - Total Series Synced: {len(json_series_dict)} / {total_registered}
# - Missing Series: {", ".join(missing_series) if missing_series else "None"}
# - Retained Stale Series: {", ".join(stale_series) if stale_series else "None"}
# - Source Authority: International Monetary Fund (IMF)
# - Canonical Formulas Reference: Section 0.3 of https://analysisreports.github.io/llms-formulas.txt
# - Zero-Hallucination Directive: Values below represent immutable ground truth.

{txt_body}
"""

    with open(TXT_FILE, "w", encoding="utf-8") as f:
        f.write(full_txt)

    output_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical IMF Monitored Series & Official Transformations",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": sync_status,
            "last_successful_sync": now_iso if sync_status == "SUCCESS" else fallback_sync_str,
            "total_series": len(json_series_dict),
            "total_registered_series": total_registered,
            "missing_series": missing_series,
            "stale_series": stale_series,
            "source_authority": "International Monetary Fund (IMF)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#0.3",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "series": json_series_dict
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2, ensure_ascii=False)

    print(f"Successfully synchronized {len(json_series_dict)} IMF series to {TXT_FILE} and {JSON_FILE}")

if __name__ == "__main__":
    main()
