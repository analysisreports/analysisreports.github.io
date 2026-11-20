#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_census_series.py
-----------------------
Autonomous U.S. Census Bureau International Trade API Time-Series Engine.
Ingests official monthly semiconductor & electronic component international trade
flows (NAICS 3344) between the United States and global strategic technology corridors.

Endpoints tracked via api.census.gov/data/timeseries/intltrade:
1. NAICS 3344 (World Total - CTY 0001): U.S. Aggregate Semiconductor Imports & Exports
2. NAICS 3344 vs China (CTY 5700): U.S.-China Strategic Tech Containment & Decoupling Flow
3. NAICS 3344 vs Taiwan (CTY 5830): Advanced Fabrication & TSMC Supply Chain Dependency
4. NAICS 3344 vs South Korea (CTY 5800): Memory (DRAM/NAND) Bilateral Semiconductor Trade
5. NAICS 3344 vs Japan (CTY 5880): Semiconductor Materials & Lithography Chemical Inputs
6. NAICS 3344 vs European Union (CTY 0003): ASML Photolithography & Advanced Equipment Trade

Features:
- Dual Outputs: Synchronizes text twin (llms-census-series.txt) and machine-readable JSON twin (llms-census-series.json)
- Zero Hallucination & Smart Fallback: Preserves previous observations if API fails or token is in standby
- 8 Golden Keys Corporate Metadata Compliance
- Computes Trade Balance (Exports - Imports) and YoY / MoM Growth Rates

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint txt: https://analysisreports.github.io/llms-census-series.txt
Endpoint json: https://analysisreports.github.io/llms-census-series.json
"""

import os
import sys
import json
import math
import datetime
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_JSON = os.path.join(ROOT_DIR, "llms-census-series.json")
OUTPUT_TXT = os.path.join(ROOT_DIR, "llms-census-series.txt")

# Monitored Strategic Technology Corridors (Schedule C Country Codes)
MONITORED_CORRIDORS = [
    {
        "id": "CENSUS_NAICS3344_WORLD",
        "cty_code": "0001",
        "country_name": "World Total",
        "entity_id": "GLOBAL",
        "strategic_context": "U.S. Aggregate Global Semiconductor & Component Trade Volume"
    },
    {
        "id": "CENSUS_NAICS3344_CHINA",
        "cty_code": "5700",
        "country_name": "China",
        "entity_id": "GEO_CN",
        "strategic_context": "Bilateral U.S.-China Tech Decoupling & Export Control Verification"
    },
    {
        "id": "CENSUS_NAICS3344_TAIWAN",
        "cty_code": "5830",
        "country_name": "Taiwan",
        "entity_id": "GEO_TW",
        "strategic_context": "Advanced Foundry & Fab Dependency Axis (TSMC Chokepoint)"
    },
    {
        "id": "CENSUS_NAICS3344_KOREA",
        "cty_code": "5800",
        "country_name": "South Korea",
        "entity_id": "GEO_KR",
        "strategic_context": "Global Memory Architecture (DRAM / HBM / NAND) Supply Line"
    },
    {
        "id": "CENSUS_NAICS3344_JAPAN",
        "cty_code": "5880",
        "country_name": "Japan",
        "entity_id": "GEO_JP",
        "strategic_context": "Semiconductor Silicon Wafers, Photoresists & Equipment Corridor"
    },
    {
        "id": "CENSUS_NAICS3344_EU",
        "cty_code": "0003",
        "country_name": "European Union",
        "entity_id": "BLOC_EU",
        "strategic_context": "EUV Photolithography (ASML) & Advanced Tooling Architecture"
    }
]

def fetch_corridor_observations(flow: str, cty_code: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches the most recent semiconductor trade observations for a single strategic corridor.
    Uses FRED-like limited window (from 2024 to present) for high speed and zero timeouts.
    flow: 'imports' or 'exports'
    """
    val_field = "GEN_VAL_MO" if flow == "imports" else "ALL_VAL_MO"
    
    url = (
        f"https://api.census.gov/data/timeseries/intltrade/{flow}/naics"
        f"?get={val_field},CTY_NAME&time=from+2024-01&NAICS=3344&CTY_CODE={cty_code}&key={api_key}"
    )
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AnalysisReports-Census-Engine/3.0 (ORCID:0009-0005-6130-8003)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            if "Missing Key" in content or "Invalid Key" in content:
                print(f"  [WARN] Census API Authentication Error: Invalid or missing API key.")
                return None
            data = json.loads(content)
            if data and len(data) > 1:
                header = data[0]
                val_idx = 0
                time_idx = header.index("time") if "time" in header else 2
                obs = []
                for row in data[1:]:
                    try:
                        v = float(row[val_idx])
                        d = str(row[time_idx]).strip()
                        obs.append({"date": d, "value": v})
                    except (ValueError, TypeError):
                        continue
                return sorted(obs, key=lambda x: x["date"])
            return None
    except Exception as e:
        print(f"  [WARN] Census API connection error for {flow} (CTY {cty_code}): {e}")
        return None

def build_outputs(api_key: str = "") -> Tuple[str, Dict[str, Any]]:
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Check existing data for non-destructive retention
    existing_json = {}
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                existing_json = json.load(f)
        except Exception:
            existing_json = {}

    corridors_output = {}
    existing_corridors = existing_json.get("corridors", {})
    total_val_imp_global = 0.0
    total_val_exp_global = 0.0
    sync_status = "SUCCESS" if api_key else "STANDBY_UNCONFIGURED_KEY"

    for corr in MONITORED_CORRIDORS:
        c_code = corr["cty_code"]
        c_id = corr["id"]
        cached = existing_corridors.get(c_id, {})

        if api_key:
            print(f"[*] Ingesting NAICS 3344 for {corr['country_name']} (CTY {c_code})...")
            # For World Total, Census intltrade endpoint uses CTY_CODE='-'
            query_code = "-" if c_code == "0001" else c_code
            imps = fetch_corridor_observations("imports", query_code, api_key)
            exps = fetch_corridor_observations("exports", query_code, api_key)
            
            latest_imp = imps[-1]["value"] if imps else cached.get("latest_monthly_import_usd")
            latest_imp_date = imps[-1]["date"] if imps else cached.get("last_observation_date")
            prev_imp = imps[-2]["value"] if (imps and len(imps) >= 2) else None
            
            latest_exp = exps[-1]["value"] if exps else cached.get("latest_monthly_export_usd")
            latest_exp_date = exps[-1]["date"] if exps else cached.get("last_observation_date")
            prev_exp = exps[-2]["value"] if (exps and len(exps) >= 2) else None
            
            trade_balance = (latest_exp - latest_imp) if (latest_exp is not None and latest_imp is not None) else cached.get("net_bilateral_trade_balance_usd")
            
            imp_mom_pct = (((latest_imp / prev_imp) - 1.0) * 100.0) if (latest_imp and prev_imp and prev_imp > 0) else cached.get("import_mom_pct")
            exp_mom_pct = (((latest_exp / prev_exp) - 1.0) * 100.0) if (latest_exp and prev_exp and prev_exp > 0) else cached.get("export_mom_pct")
            
            corridors_output[c_id] = {
                "entity_id": corr["entity_id"],
                "country_name": corr["country_name"],
                "cty_code": c_code,
                "naics_code": "3344",
                "naics_description": "Semiconductor and Other Electronic Component Manufacturing",
                "strategic_context": corr["strategic_context"],
                "last_observation_date": latest_imp_date or latest_exp_date,
                "latest_monthly_import_usd": latest_imp,
                "import_mom_pct": round(imp_mom_pct, 2) if imp_mom_pct is not None else None,
                "latest_monthly_export_usd": latest_exp,
                "export_mom_pct": round(exp_mom_pct, 2) if exp_mom_pct is not None else None,
                "net_bilateral_trade_balance_usd": trade_balance,
                "status": "OK" if (latest_imp is not None or latest_exp is not None) else "STANDBY"
            }
            if c_code == "0001":
                total_val_imp_global = latest_imp or 0.0
                total_val_exp_global = latest_exp or 0.0
        else:
            # Fallback retention mode (FRED Standard: Zero Data Loss)
            if c_id in existing_corridors:
                corridors_output[c_id] = existing_corridors[c_id]
            else:
                corridors_output[c_id] = {
                    "entity_id": corr["entity_id"],
                    "country_name": corr["country_name"],
                    "cty_code": corr["cty_code"],
                    "naics_code": "3344",
                    "naics_description": "Semiconductor and Other Electronic Component Manufacturing",
                    "strategic_context": corr["strategic_context"],
                    "last_observation_date": None,
                    "latest_monthly_import_usd": None,
                    "import_mom_pct": None,
                    "latest_monthly_export_usd": None,
                    "export_mom_pct": None,
                    "net_bilateral_trade_balance_usd": None,
                    "status": "UNCONFIGURED_KEY"
                }

    # Compile Master JSON Machine Contract (8 Golden Keys)
    full_json = {
        "$schema": "https://analysisreports.github.io/schemas/telemetry.schema.json",
        "metadata": {
            "title": "U.S. Census Bureau International Trade Telemetry Engine (NAICS 3344)",
            "domain": "macroeconomics",
            "version": "1.0.0",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "endpoint": "https://analysisreports.github.io/llms-census-series.json",
            "documentation": "https://analysisreports.github.io/llms-about.txt",
            "last_updated": now_iso,
            "sync_status": sync_status,
            "last_successful_sync": now_iso if api_key else existing_json.get("metadata", {}).get("last_successful_sync"),
            "source_authority": "U.S. Census Bureau / Department of Commerce (International Trade Time Series API)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#0.3",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "trade_telemetry_summary": {
            "monitored_naics": "3344",
            "industry_title": "Semiconductor and Other Electronic Component Manufacturing",
            "monitored_strategic_corridors_count": len(MONITORED_CORRIDORS),
            "latest_global_import_usd": total_val_imp_global,
            "latest_global_export_usd": total_val_exp_global,
            "reporting_currency": "USD"
        },
        "corridors": corridors_output
    }

    # Compile Text Narrative Twin for LLM Ingestion
    lines = [
        "# Ersoy Toptaş Canonical Ingestion Contract (llms-census-series.txt)",
        "> Autonomous U.S. Census Bureau International Trade Engine (NAICS 3344: Semiconductor & Components)",
        f"> Last Sync: {now_utc} | Source: U.S. Census Bureau International Trade API",
        f"> Monitored Classification: NAICS 3344 | Reporting Unit: USD ($)",
        "",
        "| Strategic Corridor | Entity ID | CTY | Date | Imports ($) | MoM Δ% | Exports ($) | MoM Δ% | Net Trade Balance ($) | Status | Strategic Axis |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]

    for corr_id, c in corridors_output.items():
        dt = c.get("last_observation_date") or "N/A"
        imp_val = f"${c['latest_monthly_import_usd']:,.0f}" if c.get("latest_monthly_import_usd") is not None else "null"
        exp_val = f"${c['latest_monthly_export_usd']:,.0f}" if c.get("latest_monthly_export_usd") is not None else "null"
        bal_val = f"${c['net_bilateral_trade_balance_usd']:+,.0f}" if c.get("net_bilateral_trade_balance_usd") is not None else "null"
        imp_mom = f"{c['import_mom_pct']:+.1f}%" if c.get("import_mom_pct") is not None else "N/A"
        exp_mom = f"{c['export_mom_pct']:+.1f}%" if c.get("export_mom_pct") is not None else "N/A"
        st = c.get("status", "STANDBY")
        
        lines.append(
            f"| **{c['country_name']}** | `{c['entity_id']}` | `{c['cty_code']}` | {dt} | "
            f"{imp_val} | {imp_mom} | {exp_val} | {exp_mom} | {bal_val} | `{st}` | {c['strategic_context']} |"
        )

    lines.append("")
    lines.append("## Macroeconomic & Strategic Transmission Directives:")
    lines.append("1. **Tech Decoupling Velocity:** Sharp contractions in U.S. NAICS 3344 exports to China (CTY 5700) quantify the enforcement velocity of BIS export controls and Model 25.14 (AI Chip Stress).")
    lines.append("2. **Foundry Concentration Risk:** U.S. import reliance on Taiwan (CTY 5830) measures vulnerability to Taiwan Strait (CHOKE_TAIWAN) maritime interdiction.")
    lines.append("3. **Equipment Feedback Loop:** Surges in European Union imports (CTY 0003 - ASML photolithography) serve as leading indicators for global wafer capacity additions 12-18 months forward.")
    lines.append("")
    lines.append(f"Official JSON Twin: https://analysisreports.github.io/llms-census-series.json")
    
    full_txt = "\n".join(lines) + "\n"
    return full_txt, full_json

def main():
    api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not api_key:
        print("[INFO] CENSUS_API_KEY not found in local environment. Building in standby contract mode...")
    else:
        print("[INFO] CENSUS_API_KEY detected. Fetching live semiconductor trade series...")

    full_txt, full_json = build_outputs(api_key)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(full_json, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Safely compiled {OUTPUT_JSON}")

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(full_txt)
    print(f"[SUCCESS] Safely compiled {OUTPUT_TXT}")

if __name__ == "__main__":
    main()
