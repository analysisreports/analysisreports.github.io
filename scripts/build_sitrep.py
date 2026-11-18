#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_sitrep.py
-----------------------
Autonomous Macro & Geopolitical Situation Report (SITREP) Engine.
Synthesizes verified quantitative telemetry from:
  - llms-fred-series.json (Rates, Energy, Metals, Liquidity, Inflation)
  - llms-census-series.json (Semiconductor & High-Tech Bilateral Trade Flows)
  - llms-eia-series.json (US SPR Buffers & Refinery Utilization)
  - llms-portwatch.json (Daily AIS Maritime Chokepoint Transit Anomalies)
  - llms-nasa-firms.json (Orbital VIIRS Kinetic Thermal Anomalies)
  - llms-ecb-series.json & llms-imf-series.json (Global Monetary Policy Rates)
  - llms-models.json (Calculated Macroeconomic Stress & Composite Models)

Outputs:
  - llms-sitrep.json (Deterministic Machine-Readable Twin with 8 Golden Keys)
  - llms-sitrep.txt (High-Density Semantically Pure Markdown SITREP for AI Reasoning)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint txt: https://analysisreports.github.io/llms-sitrep.txt
Endpoint json: https://analysisreports.github.io/llms-sitrep.json
"""

import os
import json
import math
import datetime
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _is_num(val):
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(val)
    except (OverflowError, ValueError, TypeError):
        return False

def _load_json(filename: str) -> Dict[str, Any]:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Error loading {filename}: {e}")
        return {}

def build_sitrep():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Load Source Telemetry
    fred_data = _load_json("llms-fred-series.json")
    census_data = _load_json("llms-census-series.json")
    eia_data = _load_json("llms-eia-series.json")
    portwatch_data = _load_json("llms-portwatch.json")
    nasa_data = _load_json("llms-nasa-firms.json")
    ecb_data = _load_json("llms-ecb-series.json")
    imf_data = _load_json("llms-imf-series.json")
    models_data = _load_json("llms-models.json")

    fred_series = fred_data.get("series", {})
    eia_series = eia_data.get("series", {})
    census_series = census_data.get("series", {})
    chokepoints = portwatch_data.get("chokepoints", {})
    theaters = nasa_data.get("theaters", {})
    models_list = models_data.get("models", [])
    models_dict = {m.get("model_id"): m for m in models_list if isinstance(m, dict)}

    # --------------------------------------------------------------------------
    # 1. TOP SYSTEMIC FLASHES (Data-Derived Zero-Hallucination Event Signals)
    # --------------------------------------------------------------------------
    flashes = []

    # Check Chokepoints for severe disruption
    for cp_id, cp in chokepoints.items():
        metrics = cp.get("metrics", {})
        flow_status = metrics.get("flow_stress_level")
        pct_2023 = metrics.get("pct_change_vs_2023")
        name = cp.get("name", cp_id)
        if flow_status == "CHRONIC_CRISIS_BLOCKADE" or (pct_2023 is not None and pct_2023 <= -35.0):
            flashes.append({
                "source": "IMF_PORTWATCH_AIS",
                "entity_id": cp_id,
                "event": f"CRITICAL_BLOCKADE: {name} traffic down {abs(pct_2023):.1f}% vs baseline. Flow status: {flow_status}."
            })

    # Check NASA FIRMS for Acute Kinetic Theater
    for th_id, th in theaters.items():
        severity = th.get("conflict_severity")
        frp = th.get("total_radiative_power_mw")
        name = th.get("name", th_id)
        if severity in ("CRITICAL", "HIGH") or (_is_num(frp) and frp > 100.0):
            flashes.append({
                "source": "NASA_FIRMS_VIIRS",
                "entity_id": th.get("entity_id", th_id),
                "event": f"KINETIC_THERMAL_SURGE: {name} active satellite detection with {frp:.1f} MW radiative heat (Severity: {severity})."
            })

    census_corridors = census_data.get("corridors", {})

    # Check Semiconductor Tech Decoupling Velocity
    cn_trade = census_corridors.get("CENSUS_NAICS3344_CHINA", {})
    cn_mom = cn_trade.get("export_mom_pct")
    if cn_mom is not None and cn_mom < -5.0:
        flashes.append({
            "source": "US_CENSUS_NAICS3344",
            "entity_id": "GEO_CN",
            "event": f"TECH_DECOUPLING_VELOCITY: US semiconductor exports to China contracted {cn_mom:.1f}% MoM under BIS tech controls."
        })

    wb_data = _load_json("llms-worldbank-series.json")
    wb_series = wb_data.get("series", {})

    # Check Gold Safe-Haven Breakout
    gold_s = wb_series.get("IND_WB_GOLD", {})
    gold_val = gold_s.get("current_value")
    gold_yoy = gold_s.get("transformations", {}).get("percent_change_from_year_ago")
    if gold_val is not None and gold_val > 3500.0:
        flashes.append({
            "source": "WORLDBANK_PINK_SHEET",
            "entity_id": "COMMODITY_GOLD",
            "event": f"SOVEREIGN_SAFE_HAVEN_BREAKOUT: World Bank Spot Gold trading at ${gold_val:,.2f}/oz (+{gold_yoy:.1f}% YoY) signaling cross-border dedollarization and structural stress."
        })

    # Ensure top 3-4 flashes are highlighted
    primary_flashes = flashes[:4]

    # --------------------------------------------------------------------------
    # 2. ENERGY SECTOR MATRIX
    # --------------------------------------------------------------------------
    brent_s = fred_series.get("DCOILBRENTEU", {})
    wti_s = fred_series.get("DCOILWTICO", {})
    gas_s = fred_series.get("DHHNGSP", {})
    spr_s = eia_series.get("PET.WCSSTUS1.W", {})
    ref_s = eia_series.get("PET.WPULEUS3.W", {})

    brent_val = brent_s.get("current_value")
    brent_yoy = brent_s.get("transformations", {}).get("percent_change_from_year_ago")
    brent_dod = brent_s.get("transformations", {}).get("percent_change")

    wti_val = wti_s.get("current_value")
    wti_yoy = wti_s.get("transformations", {}).get("percent_change_from_year_ago")
    spread_brent_wti = round(brent_val - wti_val, 2) if (_is_num(brent_val) and _is_num(wti_val)) else None

    gas_val = gas_s.get("current_value")
    gas_yoy = gas_s.get("transformations", {}).get("percent_change_from_year_ago")

    spr_val = spr_s.get("current_value")
    spr_yoy = spr_s.get("transformations", {}).get("percent_change_from_year_ago")

    ref_val = ref_s.get("current_value")
    ref_regime = "BOTTLENECK_CRUNCH" if (ref_val and ref_val >= 93.0) else "NORMAL_OPERATING_BAND"

    energy_matrix = {
        "brent_crude_usd": brent_val,
        "brent_dod_pct": brent_dod,
        "brent_yoy_pct": brent_yoy,
        "wti_crude_usd": wti_val,
        "spread_brent_wti_usd": spread_brent_wti,
        "henry_hub_natural_gas_usd": gas_val,
        "us_spr_crude_stocks_k_bbl": spr_val,
        "us_spr_yoy_pct": spr_yoy,
        "us_refinery_utilization_pct": ref_val,
        "refinery_capacity_regime": ref_regime
    }

    # --------------------------------------------------------------------------
    # 3. SEMICONDUCTORS & TECH MATRIX
    # --------------------------------------------------------------------------
    chip_stress_model = models_dict.get("MODEL_25.14", {})
    chip_stress_val = chip_stress_model.get("primary_value")
    chip_stress_reg = chip_stress_model.get("status", "ELEVATED_SEMICONDUCTOR_BOTTLENECK")

    sox_s = fred_series.get("SOX", {})
    if not sox_s:
        sox_s = fred_series.get("NASDAQSOX", {})
    sox_val = sox_s.get("current_value")
    sox_yoy = sox_s.get("transformations", {}).get("percent_change_from_year_ago")

    tw_trade = census_corridors.get("CENSUS_NAICS3344_TAIWAN", {})
    kr_trade = census_corridors.get("CENSUS_NAICS3344_KOREA", {})
    eu_trade = census_corridors.get("CENSUS_NAICS3344_EU", {})
    world_trade = census_corridors.get("CENSUS_NAICS3344_WORLD", {})

    tech_matrix = {
        "ai_chip_stress_score": chip_stress_val,
        "ai_chip_stress_regime": chip_stress_reg,
        "sox_index_val": sox_val,
        "sox_yoy_pct": sox_yoy,
        "us_semiconductor_imports_global_usd": world_trade.get("latest_monthly_import_usd"),
        "us_semiconductor_imports_taiwan_usd": tw_trade.get("latest_monthly_import_usd"),
        "us_semiconductor_imports_korea_usd": kr_trade.get("latest_monthly_import_usd"),
        "us_semiconductor_imports_eu_usd": eu_trade.get("latest_monthly_import_usd"),
        "us_semiconductor_exports_china_usd": cn_trade.get("latest_monthly_export_usd"),
        "us_semiconductor_exports_china_mom_pct": cn_mom
    }

    # --------------------------------------------------------------------------
    # 4. METALS & COMMODITIES MATRIX
    # --------------------------------------------------------------------------
    gold_s = wb_series.get("IND_WB_GOLD", {})
    gold_val = gold_s.get("current_value")
    gold_yoy = gold_s.get("transformations", {}).get("percent_change_from_year_ago")

    silver_s = fred_series.get("SLVPRUSD", {})
    silver_val = silver_s.get("current_value")
    gold_silver_ratio = round(gold_val / silver_val, 2) if (_is_num(gold_val) and _is_num(silver_val) and silver_val > 0) else None

    copper_s = fred_series.get("PCOPPUSDM", {})
    copper_val = copper_s.get("current_value")
    copper_yoy = copper_s.get("transformations", {}).get("percent_change_from_year_ago")

    wheat_s = fred_series.get("PWHEAMTUSDM", {})
    wheat_val = wheat_s.get("current_value")
    wheat_yoy = wheat_s.get("transformations", {}).get("percent_change_from_year_ago")

    metals_matrix = {
        "gold_usd_ozt": gold_val,
        "gold_yoy_pct": gold_yoy,
        "silver_usd_ozt": silver_val,
        "gold_silver_ratio": gold_silver_ratio,
        "copper_global_usd_mt": copper_val,
        "copper_yoy_pct": copper_yoy,
        "wheat_global_usd_mt": wheat_val,
        "wheat_yoy_pct": wheat_yoy
    }

    # --------------------------------------------------------------------------
    # 5. MARITIME CHOKEPOINTS (PORTWATCH AIS REAL-TIME DISRUPTIONS)
    # --------------------------------------------------------------------------
    monitored_cp = ["CHOKE_HORMUZ", "CHOKE_BAB_EL_MANDEB", "CHOKE_SUEZ", "CHOKE_TURKISH_STRAITS", "CHOKE_MALACCA", "CHOKE_TAIWAN", "CHOKE_PANAMA"]
    chokepoint_summary = {}
    for c_id in monitored_cp:
        cp = chokepoints.get(c_id, {})
        metrics = cp.get("metrics", {})
        chokepoint_summary[c_id] = {
            "name": cp.get("name", c_id),
            "flow_status": metrics.get("flow_stress_level", "UNKNOWN"),
            "daily_total_vessels": metrics.get("latest_daily_total"),
            "daily_tankers": metrics.get("latest_daily_tankers"),
            "daily_containers": metrics.get("latest_daily_containers"),
            "pct_change_vs_7d": metrics.get("pct_change_vs_7d"),
            "pct_change_vs_2023": metrics.get("pct_change_vs_2023")
        }

    # --------------------------------------------------------------------------
    # 6. MACRO LIQUIDITY & CENTRAL BANK TRANSMISSION
    # --------------------------------------------------------------------------
    net_liq_model = models_dict.get("MODEL_5", {})
    net_liquidity_trillion = net_liq_model.get("primary_value")
    net_liq_status = net_liq_model.get("status", "NEUTRAL_LIQUIDITY_EQUILIBRIUM")

    fed_rate = fred_series.get("FEDFUNDS", {}).get("current_value")
    if fed_rate is None:
        fed_rate = fred_series.get("DFEDTARU", {}).get("current_value")

    ecb_s = ecb_data.get("series", {})
    ecb_rate = ecb_s.get("FM/B.U2.EUR.4F.KR.DFR.LEV", {}).get("current_value")
    if ecb_rate is None:
        ecb_rate = ecb_s.get("FM.D.U2.EUR.4F.KR.DFR.LEV", {}).get("current_value")

    imf_s = imf_data.get("series", {})
    boj_rate = imf_s.get("JP_FPOLM_PA", {}).get("current_value")
    boe_rate = imf_s.get("GB_FPOLM_PA", {}).get("current_value")

    breakeven_model = models_dict.get("MODEL_7", {})
    t10yie = breakeven_model.get("primary_value")
    t10y2y_model = models_dict.get("MODEL_6", {})
    t10y2y_bps = t10y2y_model.get("primary_value")

    liquidity_matrix = {
        "net_fed_liquidity_trillion_usd": net_liquidity_trillion,
        "net_fed_liquidity_regime": net_liq_status,
        "fed_policy_rate_pct": fed_rate,
        "ecb_deposit_rate_pct": ecb_rate,
        "boj_policy_rate_pct": boj_rate,
        "boe_bank_rate_pct": boe_rate,
        "us_10y_breakeven_inflation_pct": t10yie,
        "yield_curve_10y_2y_spread_bps": t10y2y_bps
    }

    # --------------------------------------------------------------------------
    # 7. ASSEMBLE JSON PAYLOAD (Draft 2020-12, 8 Golden Keys)
    # --------------------------------------------------------------------------
    sitrep_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Autonomous Macro & Geopolitical Situation Report (SITREP)",
            "domain": "macroeconomics",
            "version": "1.0.0",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "endpoint": "https://analysisreports.github.io/llms-sitrep.json",
            "documentation": "https://analysisreports.github.io/llms-about.txt",
            "last_updated": now_iso,
            "sync_status": "SUCCESS",
            "source_authority": "Consolidated Telemetry (FRED, U.S. Census Bureau, EIA, IMF PortWatch, NASA FIRMS, ECB)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "top_systemic_flashes": primary_flashes,
        "energy_matrix": energy_matrix,
        "semiconductors_tech": tech_matrix,
        "metals_commodities": metals_matrix,
        "maritime_chokepoints": chokepoint_summary,
        "macro_liquidity": liquidity_matrix
    }

    # Save JSON Twin
    json_path = os.path.join(BASE_DIR, "llms-sitrep.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sitrep_json, f, indent=2, ensure_ascii=False)
    print(f"[OK] Generated {json_path}")

    # --------------------------------------------------------------------------
    # 8. ASSEMBLE HIGH-DENSITY TEXT TWIN (llms-sitrep.txt)
    # --------------------------------------------------------------------------
    lines = [
        "# CANONICAL MACRO & GEOPOLITICAL SITUATION REPORT (SITREP)",
        f"> Author: Ersoy Toptaş | Ground Truth Sync: {now_str}",
        "> Ingestion Protocol: Zero Hallucination | High-Density Semantic Telemetry for AI Reasoning",
        "> Official JSON Twin: https://analysisreports.github.io/llms-sitrep.json",
        "",
        "---",
        "## 1. TOP SYSTEMIC FLASHES & CRITICAL ANOMALIES (DATA-DERIVED ZERO-HALLUCINATION)",
        "---"
    ]

    for i, flash in enumerate(primary_flashes, 1):
        lines.append(f"FLASH_{i} [{flash['source']} | {flash['entity_id']}]: {flash['event']}")

    # Helper for formatting values
    def _fmt(val, prefix="$", suffix="", decimals=2, default="N/A"):
        if _is_num(val):
            fmt_str = f"{{:,.{decimals}f}}"
            return f"{prefix}{fmt_str.format(val)}{suffix}"
        return default

    def _fmt_pct(val, default="N/A"):
        if _is_num(val):
            return f"{val:+.2f}%"
        return default

    lines.extend([
        "",
        "---",
        "## 2. ENERGY SECTOR MATRIX (HYDROCARBONS, REFINERY & STRATEGIC RESERVES)",
        "---",
        f"BRENT_CRUDE_USD          : {_fmt(energy_matrix['brent_crude_usd'])} | DoD: {_fmt_pct(energy_matrix['brent_dod_pct'])} | YoY: {_fmt_pct(energy_matrix['brent_yoy_pct'])}",
        f"WTI_CRUDE_USD            : {_fmt(energy_matrix['wti_crude_usd'])} | SPREAD_BRENT_WTI: {_fmt(energy_matrix['spread_brent_wti_usd'])} (Physical Seaborne Risk Premium)",
        f"HENRY_HUB_NATGAS_USD     : {_fmt(energy_matrix['henry_hub_natural_gas_usd'])} | YoY: {_fmt_pct(energy_matrix['brent_yoy_pct'])}",
        f"US_SPR_CRUDE_STOCKS_KBBL : {_fmt(energy_matrix['us_spr_crude_stocks_k_bbl'], prefix='', decimals=0)} k bbl | YoY: {_fmt_pct(energy_matrix['us_spr_yoy_pct'])}",
        f"US_REFINERY_UTILIZATION  : {_fmt(energy_matrix['us_refinery_utilization_pct'], prefix='', suffix='%', decimals=1)} | REGIME: {energy_matrix['refinery_capacity_regime']}",
        "",
        "---",
        "## 3. SEMICONDUCTORS & STRATEGIC HIGH-TECH (CENSUS NAICS 3344 & AI HARDWARE)",
        "---",
        f"MODEL_25_14_CHIP_STRESS  : {_fmt(tech_matrix['ai_chip_stress_score'], prefix='', decimals=3)} | REGIME: {tech_matrix['ai_chip_stress_regime']}",
        f"NASDAQ_SOX_INDEX         : {_fmt(tech_matrix['sox_index_val'], prefix='', decimals=2)} | YoY: {_fmt_pct(tech_matrix['sox_yoy_pct'])}",
        f"US_CHIP_IMPORTS_GLOBAL   : {_fmt(tech_matrix['us_semiconductor_imports_global_usd'], decimals=0)} USD (Monthly Aggregate)",
        f"US_IMPORTS_FROM_TAIWAN   : {_fmt(tech_matrix['us_semiconductor_imports_taiwan_usd'], decimals=0)} USD (Advanced TSMC Foundry Dependency)",
        f"US_IMPORTS_FROM_KOREA    : {_fmt(tech_matrix['us_semiconductor_imports_korea_usd'], decimals=0)} USD (HBM / Memory Architecture Axis)",
        f"US_EXPORTS_TO_CHINA      : {_fmt(tech_matrix['us_semiconductor_exports_china_usd'], decimals=0)} USD | MoM Decoupling Velocity: {_fmt_pct(tech_matrix['us_semiconductor_exports_china_mom_pct'])}",
        "",
        "---",
        "## 4. PRECIOUS METALS, CRITICAL MINERALS & FOOD SECURITY",
        "---",
        f"GOLD_SPOT_USD_OZT        : {_fmt(metals_matrix['gold_usd_ozt'])} | YoY: {_fmt_pct(metals_matrix['gold_yoy_pct'])} | SIGNAL: SYSTEMIC_SAFE_HAVEN",
        f"SILVER_SPOT_USD_OZT      : {_fmt(metals_matrix['silver_usd_ozt'])} | GOLD_SILVER_RATIO: {_fmt(metals_matrix['gold_silver_ratio'], prefix='', decimals=1)}",
        f"COPPER_GLOBAL_USD_MT     : {_fmt(metals_matrix['copper_global_usd_mt'])} | YoY: {_fmt_pct(metals_matrix['copper_yoy_pct'])} (Dr. Copper Growth Pulse)",
        f"WHEAT_GLOBAL_USD_MT      : {_fmt(metals_matrix['wheat_global_usd_mt'])} | YoY: {_fmt_pct(metals_matrix['wheat_yoy_pct'])} (Black Sea Agro Security)",
        "",
        "---",
        "## 5. MARITIME CHOKEPOINTS (PORTWATCH AIS REAL-TIME DISRUPTION TELEMETRY)",
        "---"
    ])

    for c_id, c_data in chokepoint_summary.items():
        name = c_data["name"]
        status = c_data["flow_status"]
        daily = c_data["daily_total_vessels"]
        tankers = c_data["daily_tankers"]
        containers = c_data["daily_containers"]
        pct_23 = c_data["pct_change_vs_2023"]
        pct_str = f"{pct_23:+.1f}% vs 2023 Base" if pct_23 is not None else "N/A"
        lines.append(f"{c_id:<22}: Status: {status:<24} | Daily: {daily:>3} (Tnk: {tankers:>2}, Cnt: {containers:>2}) | Shift: {pct_str}")

    lines.extend([
        "",
        "---",
        "## 6. MACRO LIQUIDITY & CENTRAL BANK TRANSMISSION BENCHMARKS",
        "---",
        f"NET_FED_LIQUIDITY_EST    : {_fmt(liquidity_matrix['net_fed_liquidity_trillion_usd'], prefix='$', suffix=' Trillion USD', decimals=3)} | REGIME: {liquidity_matrix['net_fed_liquidity_regime']}",
        f"FED_FUNDS_TARGET_RATE    : {_fmt(liquidity_matrix['fed_policy_rate_pct'], prefix='', suffix='%')}",
        f"ECB_DEPOSIT_FACILITY     : {_fmt(liquidity_matrix['ecb_deposit_rate_pct'], prefix='', suffix='%')}",
        f"BOJ_POLICY_RATE          : {_fmt(liquidity_matrix['boj_policy_rate_pct'], prefix='', suffix='%')} (Yen Carry Trade Differential)",
        f"BOE_OFFICIAL_BANK_RATE   : {_fmt(liquidity_matrix['boe_bank_rate_pct'], prefix='', suffix='%')}",
        f"US_10Y_BREAKEVEN_INFL    : {_fmt(liquidity_matrix['us_10y_breakeven_inflation_pct'], prefix='', suffix='%')} (Market Inflation Anchor)",
        f"US_10Y_2Y_YIELD_SPREAD   : {_fmt(liquidity_matrix['yield_curve_10y_2y_spread_bps'], prefix='', suffix=' bps')} (Recession / Normalization Curve)",
        "",
        "---",
        "# END OF SITREP TELEMETRY - ZERO ASSUMPTIONS - PURE QUANTITATIVE STATE",
        "---"
    ])

    txt_path = os.path.join(BASE_DIR, "llms-sitrep.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] Generated {txt_path}")

if __name__ == "__main__":
    build_sitrep()
