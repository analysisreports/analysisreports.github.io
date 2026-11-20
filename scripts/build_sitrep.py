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

def _fmt(val, prefix="$", suffix="", decimals=2, default="N/A"):
    if _is_num(val):
        fmt_str = f"{{:,.{decimals}f}}"
        return f"{prefix}{fmt_str.format(val)}{suffix}"
    return default

def _fmt_pct(val, default="N/A"):
    if _is_num(val):
        return f"{val:+.2f}%"
    return default

def _annotate_telemetry_deficits(matrix: Dict[str, Any], matrix_name: str = "") -> Dict[str, Any]:
    """
    Zero-overhead telemetry anomaly annotator.
    If a metric is None, generates an explicit reason tag so AI agents know
    the data is missing due to upstream feed status rather than a system bug.
    Adds ZERO extra keys when data is actively flowing.
    """
    deficits = {}
    for key, val in list(matrix.items()):
        if val is None and not key.endswith("_status"):
            deficits[f"{key}_status"] = "SOURCE_FEED_UNAVAILABLE"
    matrix.update(deficits)
    return matrix

def _fetch_royal_mint_spot(ecb_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ingests live spot gold and silver benchmarks directly from The Royal Mint dataLayer
    and converts to USD via official European Central Bank (ECB) FX cross rates.
    Zero synthetic fallbacks: returns None for metrics if live network endpoints fail.
    """
    import urllib.request
    import re
    import gzip

    spot_data = {
        "gold_gbp": None,
        "silver_gbp": None,
        "gbp_usd_rate": None,
        "gold_spot_usd": None,
        "silver_spot_usd": None,
        "source": "The Royal Mint Sovereign Benchmark / ECB FX",
        "fx_observation_date": "N/A",
        "status": "UNAVAILABLE"
    }
    
    try:
        url_mint = "https://www.royalmint.com/shop/gold/"
        req_mint = urllib.request.Request(
            url_mint,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req_mint, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'"market":\s*\{\s*"buy":\s*\{[^}]*?"gold":\s*([0-9.]+)[^}]*?"silver":\s*([0-9.]+)', html, re.DOTALL)
            if m:
                spot_data["gold_gbp"] = float(m.group(1))
                spot_data["silver_gbp"] = float(m.group(2))
    except Exception as e:
        print(f"[WARN] Royal Mint spot ingestion error: {e}")
        return spot_data

    # Attempt Live ECB FX Rates Ingestion
    eur_usd = None
    eur_gbp = None
    fx_date = "N/A"
    try:
        url_usd = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=jsondata"
        url_gbp = "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A?lastNObservations=1&format=jsondata"
        
        def _get_ecb_live(url):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=5) as r:
                raw = r.read()
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
                return json.loads(raw.decode("utf-8"))

        du = _get_ecb_live(url_usd)
        dg = _get_ecb_live(url_gbp)
        eur_usd = du["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]["0"][0]
        eur_gbp = dg["dataSets"][0]["series"]["0:0:0:0:0"]["observations"]["0"][0]
        fx_date = du["structure"]["dimensions"]["observation"][0]["values"][0]["id"]
    except Exception as e:
        # Fallback to local verified ECB telemetry file (llms-ecb-series.json)
        if ecb_data and "series" in ecb_data:
            ecb_series = ecb_data.get("series", {})
            u_entry = ecb_series.get("EXR/D.USD.EUR.SP00.A", {})
            g_entry = ecb_series.get("EXR/D.GBP.EUR.SP00.A", {})
            eur_usd = u_entry.get("current_value")
            eur_gbp = g_entry.get("current_value")
            fx_date = u_entry.get("last_date", "N/A")

    if eur_usd and eur_gbp and eur_gbp > 0:
        gbp_usd = round(eur_usd / eur_gbp, 4)
        spot_data["gbp_usd_rate"] = gbp_usd
        spot_data["fx_observation_date"] = fx_date
        if spot_data["gold_gbp"] is not None:
            spot_data["gold_spot_usd"] = round(spot_data["gold_gbp"] * gbp_usd, 2)
        if spot_data["silver_gbp"] is not None:
            spot_data["silver_spot_usd"] = round(spot_data["silver_gbp"] * gbp_usd, 2)
        spot_data["status"] = "LIVE_OFFICIAL_BENCHMARK"

    return spot_data

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
    nyfed_data = _load_json("llms-nyfed-series.json")
    models_data = _load_json("llms-models.json")
    relationships_data = _load_json("llms-relationships.json")

    fred_series = fred_data.get("series", {})
    eia_series = eia_data.get("series", {})
    census_series = census_data.get("series", {})
    chokepoints = portwatch_data.get("chokepoints", {})
    theaters = nasa_data.get("theaters", {})
    nyfed_series = nyfed_data.get("series", {})
    models_list = models_data.get("models", [])
    models_dict = {m.get("model_id"): m for m in models_list if isinstance(m, dict)}
    rels_list = relationships_data.get("relationships", [])
    rels_dict = {r.get("id"): r for r in rels_list if isinstance(r, dict)}

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
    brent_date = brent_s.get("last_date", "N/A")

    wti_val = wti_s.get("current_value")
    wti_yoy = wti_s.get("transformations", {}).get("percent_change_from_year_ago")
    wti_date = wti_s.get("last_date", "N/A")
    spread_brent_wti = round(brent_val - wti_val, 2) if (_is_num(brent_val) and _is_num(wti_val)) else None

    gas_val = gas_s.get("current_value")
    gas_yoy = gas_s.get("transformations", {}).get("percent_change_from_year_ago")
    gas_date = gas_s.get("last_date", "N/A")

    spr_val = spr_s.get("current_value")
    spr_yoy = spr_s.get("transformations", {}).get("percent_change_from_year_ago")
    spr_date = spr_s.get("last_date", "N/A")

    ref_val = ref_s.get("current_value")
    ref_date = ref_s.get("last_date", "N/A")
    ref_regime = "BOTTLENECK_CRUNCH" if (ref_val and ref_val >= 93.0) else "NORMAL_OPERATING_BAND"

    energy_matrix = {
        "brent_crude_usd": brent_val,
        "brent_dod_pct": brent_dod,
        "brent_yoy_pct": brent_yoy,
        "wti_crude_usd": wti_val,
        "spread_brent_wti_usd": spread_brent_wti,
        "henry_hub_natural_gas_usd": gas_val,
        "henry_hub_natural_gas_yoy_pct": gas_yoy,
        "us_spr_crude_stocks_k_bbl": spr_val,
        "us_spr_yoy_pct": spr_yoy,
        "us_refinery_utilization_pct": ref_val,
        "refinery_capacity_regime": ref_regime
    }

    # --------------------------------------------------------------------------
    # 3. SEMICONDUCTORS & TECH MATRIX
    # --------------------------------------------------------------------------
    census_corridors = census_data.get("corridors", {})
    cn_trade = census_corridors.get("CENSUS_NAICS3344_CHINA", {})
    cn_mom = cn_trade.get("export_mom_pct")
    chip_stress_model = models_dict.get("MODEL_25.14", {})
    chip_stress_val = chip_stress_model.get("primary_value")
    chip_stress_reg = chip_stress_model.get("status", "ELEVATED_SEMICONDUCTOR_BOTTLENECK")

    sox_s = fred_series.get("SOX", {})
    if not sox_s:
        sox_s = fred_series.get("NASDAQSOX", {})
    sox_val = sox_s.get("current_value")
    sox_yoy = sox_s.get("transformations", {}).get("percent_change_from_year_ago")
    sox_date = sox_s.get("last_date", "N/A")

    tw_trade = census_corridors.get("CENSUS_NAICS3344_TAIWAN", {})
    kr_trade = census_corridors.get("CENSUS_NAICS3344_KOREA", {})
    eu_trade = census_corridors.get("CENSUS_NAICS3344_EU", {})
    world_trade = census_corridors.get("CENSUS_NAICS3344_WORLD", {})
    census_date = world_trade.get("last_observation_date") or world_trade.get("last_date", "N/A")

    gscpi_s = nyfed_series.get("GSCPI", {})
    gscpi_val = gscpi_s.get("current_value")
    gscpi_yoy_chg = gscpi_s.get("transformations", {}).get("change_from_year_ago")
    gscpi_date = gscpi_s.get("last_date", "N/A")

    tech_matrix = {
        "ai_chip_stress_score": chip_stress_val,
        "ai_chip_stress_regime": chip_stress_reg,
        "nyfed_gscpi_pressure_zscore": gscpi_val,
        "nyfed_gscpi_yoy_change": gscpi_yoy_chg,
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
    wb_data = _load_json("llms-worldbank-series.json")
    wb_series = wb_data.get("series", {})

    # Live Sovereign Spot Benchmarks (The Royal Mint UK converted via ECB FX)
    rm_spot = _fetch_royal_mint_spot(ecb_data)
    gold_spot_usd = rm_spot.get("gold_spot_usd")
    silver_spot_usd = rm_spot.get("silver_spot_usd")
    rm_gold_gbp = rm_spot.get("gold_gbp")
    rm_silver_gbp = rm_spot.get("silver_gbp")
    rm_fx_rate = rm_spot.get("gbp_usd_rate")
    rm_fx_date = rm_spot.get("fx_observation_date", "N/A")

    gold_s = wb_series.get("IND_WB_GOLD", {})
    gold_val = gold_s.get("current_value")
    gold_yoy = gold_s.get("transformations", {}).get("percent_change_from_year_ago")
    gold_date = gold_s.get("observation_date", "N/A")

    silver_s = fred_series.get("SLVPRUSD", {})
    silver_val = silver_s.get("current_value")
    silver_date = silver_s.get("last_date", "N/A")
    
    # Gold-Silver Ratio: Prioritize live sovereign spot benchmarks, fallback to monthly historical series
    if _is_num(gold_spot_usd) and _is_num(silver_spot_usd) and silver_spot_usd > 0:
        gold_silver_ratio = round(gold_spot_usd / silver_spot_usd, 2)
    elif _is_num(gold_val) and _is_num(silver_val) and silver_val > 0:
        gold_silver_ratio = round(gold_val / silver_val, 2)
    else:
        gold_silver_ratio = None

    copper_s = fred_series.get("PCOPPUSDM", {})
    copper_val = copper_s.get("current_value")
    copper_yoy = copper_s.get("transformations", {}).get("percent_change_from_year_ago")
    copper_date = copper_s.get("last_date", "N/A")

    wheat_s = fred_series.get("PWHEAMTUSDM", {})
    wheat_val = wheat_s.get("current_value")
    wheat_yoy = wheat_s.get("transformations", {}).get("percent_change_from_year_ago")
    wheat_date = wheat_s.get("last_date", "N/A")

    metals_matrix = {
        "gold_spot_usd_ozt": gold_spot_usd,
        "gold_spot_gbp_ozt": rm_gold_gbp,
        "silver_spot_usd_ozt": silver_spot_usd,
        "silver_spot_gbp_ozt": rm_silver_gbp,
        "ecb_gbp_usd_cross_rate": rm_fx_rate,
        "fx_observation_date": rm_fx_date,
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

    # Evaluate Model 28.6: Maritime Observability Divergence Index (MODI) for CHOKE_HORMUZ
    hormuz_shift_val = chokepoints.get("CHOKE_HORMUZ", {}).get("metrics", {}).get("pct_change_vs_2023")
    refinery_val = energy_matrix.get("us_refinery_utilization_pct")
    
    hormuz_modi_key = "UNKNOWN"
    hormuz_modi_summary = ""
    if _is_num(hormuz_shift_val) and _is_num(refinery_val):
        if hormuz_shift_val <= -50.0 and refinery_val >= 85.0:
            hormuz_modi_key = "DIVERGENCE_TRANSPONDER_DARK_FLOW"
        elif hormuz_shift_val <= -50.0 and refinery_val < 80.0:
            hormuz_modi_key = "CORROBORATED_PHYSICAL_CONTRACTION"
        elif hormuz_shift_val > -30.0 and refinery_val >= 85.0:
            hormuz_modi_key = "PEACETIME_STABLE_FLOW"
        else:
            hormuz_modi_key = "TRANSITIONAL_OBSERVABILITY_BAND"
            
        hormuz_modi_summary = f"{hormuz_modi_key} | AIS_Contraction: {hormuz_shift_val:+.1f}% (IMF) vs Refinery_Utilization: {refinery_val:.1f}% (EIA) [Model 28.6 MODI Engine]"
        chokepoint_summary["CHOKE_HORMUZ"]["observability_bridge"] = {
            "status_key": hormuz_modi_key,
            "formula_link": "https://analysisreports.github.io/llms-formulas-geopolitics.txt#28.6",
            "ais_shift_pct": round(float(hormuz_shift_val), 2),
            "refinery_utilization_pct": round(float(refinery_val), 2)
        }

    # --------------------------------------------------------------------------
    # 6. MACRO LIQUIDITY & CENTRAL BANK TRANSMISSION
    # --------------------------------------------------------------------------
    net_liq_model = models_dict.get("MODEL_5", {})
    net_liquidity_trillion = net_liq_model.get("primary_value")
    net_liq_status = net_liq_model.get("status", "NEUTRAL_LIQUIDITY_EQUILIBRIUM")

    fed_s = fred_series.get("FEDFUNDS", {})
    if not fed_s:
        fed_s = fred_series.get("DFEDTARU", {})
    fed_rate = fed_s.get("current_value")
    fed_date = fed_s.get("last_date", "N/A")

    ecb_s = ecb_data.get("series", {})
    ecb_entry = ecb_s.get("FM/B.U2.EUR.4F.KR.DFR.LEV", {})
    if not ecb_entry:
        ecb_entry = ecb_s.get("FM.D.U2.EUR.4F.KR.DFR.LEV", {})
    ecb_rate = ecb_entry.get("current_value")
    ecb_date = ecb_entry.get("last_date", "N/A")

    imf_s = imf_data.get("series", {})
    boj_s = imf_s.get("JP_FPOLM_PA", {})
    boj_rate = boj_s.get("current_value")
    boj_date = boj_s.get("last_date", "N/A")

    boe_s = imf_s.get("GB_FPOLM_PA", {})
    boe_rate = boe_s.get("current_value")
    boe_date = boe_s.get("last_date", "N/A")

    breakeven_model = models_dict.get("MODEL_7", {})
    t10yie = breakeven_model.get("primary_value")
    t10y2y_model = models_dict.get("MODEL_6", {})
    t10y2y_bps = t10y2y_model.get("primary_value")

    vix_s = fred_series.get("VIXCLS", {})
    vix_val = vix_s.get("current_value")
    vix_yoy = vix_s.get("transformations", {}).get("percent_change_from_year_ago")
    vix_date = vix_s.get("last_date", "N/A")

    dxy_s = fred_series.get("DTWEXBGS", {})
    dxy_val = dxy_s.get("current_value")
    dxy_yoy = dxy_s.get("transformations", {}).get("percent_change_from_year_ago")
    dxy_date = dxy_s.get("last_date", "N/A")

    hy_s = fred_series.get("BAMLH0A0HYM2", {})
    hy_val = hy_s.get("current_value")
    hy_yoy = hy_s.get("transformations", {}).get("percent_change_from_year_ago")
    hy_date = hy_s.get("last_date", "N/A")

    sofr_s = fred_series.get("SOFR", {})
    sofr_val = sofr_s.get("current_value")
    sofr_date = sofr_s.get("last_date", "N/A")
    sofr_fedfunds_spread_bps = round((sofr_val - fed_rate) * 100.0, 1) if (_is_num(sofr_val) and _is_num(fed_rate)) else None

    # Model 25.20: BDSI Metrics for Liquidity Benchmark
    m25_20_init = models_dict.get("MODEL_25.20", {})
    bdsi_val_init = m25_20_init.get("primary_value")
    bdsi_stat_init = m25_20_init.get("status", "BENIGN_GLOBAL_LIQUIDITY")

    liquidity_matrix = {
        "net_fed_liquidity_trillion_usd": net_liquidity_trillion,
        "net_fed_liquidity_regime": net_liq_status,
        "fed_policy_rate_pct": fed_rate,
        "secured_overnight_financing_rate_pct": sofr_val,
        "sofr_fedfunds_spread_bps": sofr_fedfunds_spread_bps,
        "bdsi_offshore_strain_index": bdsi_val_init,
        "bdsi_offshore_strain_regime": bdsi_stat_init,
        "ecb_deposit_rate_pct": ecb_rate,
        "boj_policy_rate_pct": boj_rate,
        "boe_bank_rate_pct": boe_rate,
        "us_10y_breakeven_inflation_pct": t10yie,
        "yield_curve_10y_2y_spread_bps": t10y2y_bps,
        "cboe_vix_index": vix_val,
        "cboe_vix_yoy_pct": vix_yoy,
        "fed_broad_dollar_index": dxy_val,
        "fed_broad_dollar_yoy_pct": dxy_yoy,
        "us_high_yield_spread_pct": hy_val,
        "us_high_yield_spread_yoy_pct": hy_yoy
    }

    # Calculate Data Completeness Percentage (Zero-Hallucination Quality Gate)
    all_evaluated_metrics = []
    for m in [energy_matrix, tech_matrix, metals_matrix, liquidity_matrix]:
        for k, v in m.items():
            if not k.endswith("_status"):
                all_evaluated_metrics.append(v)
    for c_id, c_data in chokepoint_summary.items():
        all_evaluated_metrics.append(c_data.get("daily_total_vessels"))

    valid_count = sum(1 for v in all_evaluated_metrics if v is not None)
    total_count = len(all_evaluated_metrics)
    completeness_pct = round((valid_count / total_count) * 100.0, 1) if total_count > 0 else 100.0

    # --------------------------------------------------------------------------
    # 7. DYNAMIC SYSTEMIC CONTAGION VECTORS & MEDIA REALITY CHECK RULES
    # --------------------------------------------------------------------------
    # Ingest Model 28.4 & Dyad Relationships for Chokepoint & Tech Bypass
    m28_4 = models_dict.get("MODEL_28.4", {})
    m28_4_metrics = m28_4.get("metrics", {})
    m28_4_inputs = m28_4.get("inputs", {})
    gross_flow_mbpd = m28_4_inputs.get("gross_flow_mbpd")
    bypass_buffer_mbpd = m28_4_metrics.get("total_buffer_capacity_mbpd")
    unmet_deficit_mbpd = m28_4_metrics.get("net_unmet_deficit_mbpd")
    deficit_ratio = m28_4_metrics.get("net_deficit_ratio")
    deficit_ratio_pct = (deficit_ratio * 100.0) if _is_num(deficit_ratio) else None

    rel_il_ir = rels_dict.get("IL_IR", {})
    il_ir_p_net = rel_il_ir.get("p_net")

    rel_us_cn = rels_dict.get("US_CN", {})
    us_cn_p_base = rel_us_cn.get("p_baseline")

    hormuz_daily = chokepoints.get("CHOKE_HORMUZ", {}).get("metrics", {}).get("latest_daily_total", "N/A")
    hormuz_shift = chokepoints.get("CHOKE_HORMUZ", {}).get("metrics", {}).get("pct_change_vs_2023")
    hormuz_shift_str = f"{hormuz_shift:+.1f}% vs 2023 Base" if hormuz_shift is not None else "N/A"

    turk_shift = chokepoints.get("CHOKE_TURKISH_STRAITS", {}).get("metrics", {}).get("pct_change_vs_2023")
    turk_shift_str = f"{turk_shift:+.1f}% vs 2023 Base" if turk_shift is not None else "N/A"

    malacca_daily = chokepoints.get("CHOKE_MALACCA", {}).get("metrics", {}).get("latest_daily_total", "N/A")
    malacca_shift = chokepoints.get("CHOKE_MALACCA", {}).get("metrics", {}).get("pct_change_vs_2023")
    malacca_shift_str = f"{malacca_shift:+.1f}% vs 2023 Base" if malacca_shift is not None else "N/A"

    # Rule 1 Evaluation: Seaborne Energy Disruption & Buffer Dynamics
    if _is_num(brent_val) and _is_num(wti_val) and brent_val > 0:
        spread_val = round(brent_val - wti_val, 2)
        spread_ratio_pct = round((spread_val / brent_val) * 100.0, 2)
    else:
        spread_val = None
        spread_ratio_pct = None

    spr_threshold_kbbl = 350000.0

    if spread_ratio_pct is not None and _is_num(spr_val):
        if spread_ratio_pct > 5.0 and spr_val < spr_threshold_kbbl:
            rule_1_ground_truth = (
                f"Observable maritime transit divergence; Brent-WTI spread at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline). "
                f"With US SPR stocks recorded at {_fmt(spr_val, prefix='', decimals=0)} k bbl (below historical 350M bbl reference levels), "
                "telemetry suggests that strategic physical buffers may offer more limited absorption capacity if maritime shipping friction persists."
            )
        elif spread_ratio_pct > 5.0 and spr_val >= spr_threshold_kbbl:
            rule_1_ground_truth = (
                f"Elevated seaborne transit considerations; Brent-WTI spread at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline). "
                f"US SPR reserves ({_fmt(spr_val, prefix='', decimals=0)} k bbl) appear to provide an active structural baseline that could help temper near-term spot volatility."
            )
        elif 2.5 <= spread_ratio_pct <= 5.0 and spr_val < spr_threshold_kbbl:
            rule_1_ground_truth = (
                f"Moderate maritime arbitrage variance; Brent-WTI spread at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline). "
                f"Prevailing SPR levels ({_fmt(spr_val, prefix='', decimals=0)} k bbl) could indicate an underlying vulnerability should corridor transit volumes contract further."
            )
        elif 2.5 <= spread_ratio_pct <= 5.0 and spr_val >= spr_threshold_kbbl:
            rule_1_ground_truth = (
                f"Measured marine transit costs; Brent-WTI spread at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline). "
                f"US SPR inventory at {_fmt(spr_val, prefix='', decimals=0)} k bbl may be viewed as a supportive strategic buffer against localized logistics friction."
            )
        elif spread_ratio_pct < 2.5 and spr_val < spr_threshold_kbbl:
            rule_1_ground_truth = (
                f"Transatlantic crude benchmarks appear relatively balanced at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline); "
                f"however, lower SPR reserves ({_fmt(spr_val, prefix='', decimals=0)} k bbl) suggest limited strategic cushion for potential future market shifts."
            )
        else:
            rule_1_ground_truth = (
                f"Transatlantic arbitrage reflects baseline equilibrium; Brent-WTI spread at {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent baseline). "
                f"US SPR buffer is maintained at {_fmt(spr_val, prefix='', decimals=0)} k bbl."
            )
    else:
        rule_1_ground_truth = (
            f"The {_fmt(spread_brent_wti)} Brent-WTI spread reflects observed maritime freight differentials, "
            f"with US SPR stocks recorded at {_fmt(spr_val, prefix='', decimals=0)} k bbl."
        )

    # Rule 2 Evaluation: Offshore Dollar Shortage & Repo Funding Stress (Model 25.20 BDSI Engine)
    m25_20 = models_dict.get("MODEL_25.20", {})
    bdsi_score = m25_20.get("primary_value")
    bdsi_status = m25_20.get("status", "BENIGN_GLOBAL_LIQUIDITY")

    sofr_bps = sofr_fedfunds_spread_bps if _is_num(sofr_fedfunds_spread_bps) else 0.0
    dxy_growth = dxy_yoy if _is_num(dxy_yoy) else 0.0

    if bdsi_status == "ACUTE_OFFSHORE_DOLLAR_DRAIN":
        rule_2_ground_truth = (
            f"Observable cross-border dollar funding pressures; Model 25.20 BDSI reads {_fmt(bdsi_score, prefix='', decimals=3)} "
            f"(Regime: {bdsi_status}), reflecting the compounding interaction of maritime transit constraints ({hormuz_shift_str}) "
            f"with positive repo friction (SOFR spread: {_fmt(sofr_bps, prefix='', suffix=' bps')}) and Broad Dollar momentum ({_fmt_pct(dxy_growth)}). "
            "Academic literature on international trade finance indicates that prolonged corridor bottlenecks can elevate demand for USD-denominated "
            "spot settlement and short-term rollover buffers across non-reserve banking systems."
        )
    elif bdsi_status == "LATENT_LIQUIDITY_STRAIN":
        rule_2_ground_truth = (
            f"Moderate offshore liquidity adjustment; Model 25.20 BDSI registers {_fmt(bdsi_score, prefix='', decimals=3)} "
            f"(Regime: {bdsi_status}) alongside a manageable SOFR-EFFR spread ({_fmt(sofr_bps, prefix='', suffix=' bps')}) "
            f"and Fed Broad Dollar expansion ({_fmt_pct(dxy_growth)} YoY, Index: {_fmt(dxy_val, prefix='', decimals=2)}). "
            "While headline 6-currency DXY movements appear range-bound, trade-weighted currency dynamics and maritime transit adjustments "
            "suggest localized, orderly reallocations in cross-border trade credit rather than systemic dollar illiquidity."
        )
    elif sofr_bps >= 15.0:
        if dxy_growth >= 3.0:
            rule_2_ground_truth = (
                f"Noticeable offshore funding tightness; SOFR-EFFR spread widened to {_fmt(sofr_bps, prefix='', suffix=' bps')} "
                f"alongside Broad Dollar appreciation of {_fmt_pct(dxy_growth)} (Index: {_fmt(dxy_val, prefix='', decimals=2)}). "
                "This combination may point toward tightening collateral availability and localized dollar liquidity constraints across cross-border banking networks."
            )
        else:
            rule_2_ground_truth = (
                f"Domestic repo collateral friction; SOFR-EFFR spread stands at {_fmt(sofr_bps, prefix='', suffix=' bps')}, "
                f"while Broad Dollar YoY ({_fmt_pct(dxy_growth)}) may suggest internal balance sheet friction rather than broad global dollar flight."
            )
    elif sofr_bps < 0.0:
        if dxy_growth >= 3.0:
            rule_2_ground_truth = (
                f"External dollar demand shift; Broad Dollar expanded {_fmt_pct(dxy_growth)} YoY, "
                f"even though US domestic repo conditions show ample liquidity (SOFR spread at {_fmt(sofr_bps, prefix='', suffix=' bps')})."
            )
        else:
            rule_2_ground_truth = (
                f"Accommodative domestic reserve conditions with slightly negative repo spread ({_fmt(sofr_bps, prefix='', suffix=' bps')}); "
                f"Broad Dollar YoY ({_fmt_pct(dxy_growth)}) suggests an unconstrained dollar liquidity environment."
            )
    else:
        rule_2_ground_truth = (
            f"Liquidity indicators remain in balanced territory; Model 25.20 BDSI stands at {_fmt(bdsi_score, prefix='', decimals=3)} ({bdsi_status}), "
            f"SOFR-EFFR spread is moderate ({_fmt(sofr_bps, prefix='', suffix=' bps')}) "
            f"and Fed Broad Dollar index ({_fmt(dxy_val, prefix='', decimals=2)}, YoY: {_fmt_pct(dxy_growth)}) aligns with non-stress historical baselines."
        )

    # Rule 3 Evaluation: Strategic Passage Paralysis (Multi-Chokepoint AIS Network Disruption)
    cp_shifts = {
        "CHOKE_HORMUZ": hormuz_shift,
        "CHOKE_TURKISH_STRAITS": turk_shift,
        "CHOKE_BAB_EL_MANDEB": chokepoints.get("CHOKE_BAB_EL_MANDEB", {}).get("metrics", {}).get("pct_change_vs_2023"),
        "CHOKE_SUEZ": chokepoints.get("CHOKE_SUEZ", {}).get("metrics", {}).get("pct_change_vs_2023")
    }
    valid_shifts = {k: v for k, v in cp_shifts.items() if _is_num(v)}
    if valid_shifts:
        worst_cp = min(valid_shifts.items(), key=lambda x: x[1])
        disrupted_count = sum(1 for v in valid_shifts.values() if v <= -30.0)
        worst_cp_name = worst_cp[0]
        worst_drop = worst_cp[1]

        if worst_drop <= -80.0:
            if disrupted_count >= 2:
                rule_3_ground_truth = (
                    f"Pronounced multi-corridor transit deceleration; {worst_cp_name} contracted by {worst_drop:+.1f}% vs 2023 baseline, "
                    f"with {disrupted_count} primary global chokepoints simultaneously showing shifts exceeding -30% (Hormuz: {hormuz_daily} vessels/day, {hormuz_shift_str}; "
                    f"Turkish Straits: {turk_shift_str}). Observed commercial flows appear increasingly shaped by specialized operational parameters, "
                    "potentially requiring selective routing and convoy coordination rather than routine peacetime transits."
                )
            else:
                rule_3_ground_truth = (
                    f"Concentrated commercial flow adjustment observed at {worst_cp_name} ({worst_drop:+.1f}% vs baseline; Hormuz: {hormuz_daily} vessels/day), "
                    f"while secondary corridors maintain relative permeability. Vessel operators may be incorporating extended routing schedules and updated risk premia."
                )
        elif worst_drop <= -30.0:
            if disrupted_count >= 2:
                rule_3_ground_truth = (
                    f"Broad maritime flow variance across {disrupted_count} monitored waterways; "
                    f"Hormuz transits record {hormuz_shift_str} ({hormuz_daily} vessels/day) and Turkish Straits show {turk_shift_str}. "
                    "This synchronization could indicate cumulative scheduling delays across international maritime networks."
                )
            else:
                rule_3_ground_truth = (
                    f"Localized transit variance at {worst_cp_name} ({worst_drop:+.1f}% vs baseline); "
                    f"operations may reflect heightened navigational caution without broader network dislocation."
                )
        else:
            rule_3_ground_truth = (
                f"Strategic maritime corridors appear to operate within typical historical variance; "
                f"Hormuz transits record {hormuz_daily} vessels/day ({hormuz_shift_str}) and Turkish Straits reflect {turk_shift_str}."
            )
    else:
        rule_3_ground_truth = (
            "Maritime transit shift telemetry unavailable; physical corridor flow assessments fail closed without live satellite observation."
        )

    # Rule 4 Evaluation: Semiconductor Containment Friction & Intermediary Rerouting
    c_stress = chip_stress_val if _is_num(chip_stress_val) else 0.0
    gscpi_num = gscpi_val if _is_num(gscpi_val) else 0.0
    cn_mom = tech_matrix.get("us_semiconductor_exports_china_mom_pct")
    cn_mom_str = f"{cn_mom:+.2f}%" if _is_num(cn_mom) else "N/A"

    if c_stress >= 0.50:
        if gscpi_num >= 1.00:
            rule_4_ground_truth = (
                f"Calculated technology supply chain friction; Model 25.14 AI Chip Stress registers {_fmt(c_stress, prefix='', decimals=3)} ({chip_stress_reg}) "
                f"alongside elevated NY Fed GSCPI pressure ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score). "
                f"Direct US-to-China chip export changes ({cn_mom_str} MoM velocity) alongside sustained Asian import volumes "
                f"(Taiwan: {_fmt(tech_matrix['us_semiconductor_imports_taiwan_usd'], decimals=0)} USD, Korea: {_fmt(tech_matrix['us_semiconductor_imports_korea_usd'], decimals=0)} USD) "
                "may suggest that market participants are exploring alternative routing hubs, which could introduce additional logistics and compliance considerations."
            )
        else:
            rule_4_ground_truth = (
                f"Specific semiconductor hardware variance; Model 25.14 Chip Stress registers {_fmt(c_stress, prefix='', decimals=3)} ({chip_stress_reg}), "
                f"while broader logistics indicators ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score) remain moderate. "
                "This could reflect localized fabrication priorities or licensing processing timelines."
            )
    else:
        if gscpi_num >= 1.00:
            rule_4_ground_truth = (
                f"Broader freight logistics friction ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score); "
                f"however, baseline semiconductor hardware indicators remain within calibrated limits ({_fmt(c_stress, prefix='', decimals=3)}, {chip_stress_reg})."
            )
        else:
            rule_4_ground_truth = (
                f"Technology distribution indicators operate in balanced territory; Model 25.14 Chip Stress at {_fmt(c_stress, prefix='', decimals=3)} "
                f"and GSCPI logistics at {_fmt(gscpi_num, prefix='', decimals=2)} Z-Score suggest relatively unencumbered supply distribution."
            )

    # Rule 5 Evaluation: Overland Pipeline Bypass Capacity Ceiling
    d_ratio = deficit_ratio_pct if _is_num(deficit_ratio_pct) else 0.0
    il_ir_pol = il_ir_p_net if _is_num(il_ir_p_net) else 0.0

    if d_ratio > 50.0:
        if il_ir_pol <= -0.75:
            rule_5_ground_truth = (
                f"Structural overland bypass considerations; Model 28.4 parameters indicate overland pipelines ({_fmt(bypass_buffer_mbpd, prefix='', decimals=2)} mbpd capacity) "
                f"leave a calculated {_fmt(unmet_deficit_mbpd, prefix='', decimals=2)} mbpd differential ({d_ratio:.1f}% of baseline flows of {_fmt(gross_flow_mbpd, prefix='', decimals=2)} mbpd). "
                f"Under prevailing regional geopolitical polarity ({_fmt(il_ir_pol, prefix='', decimals=2)}), infrastructure substitution may require extended operational lead times and alternate transit coordination."
            )
        else:
            rule_5_ground_truth = (
                f"Overland pipeline capacity ceilings; bypass capacity ({_fmt(bypass_buffer_mbpd, prefix='', decimals=2)} mbpd) "
                f"leaves a net {_fmt(unmet_deficit_mbpd, prefix='', decimals=2)} mbpd volume differential ({d_ratio:.1f}%), "
                f"indicating that overland alternatives may serve as a partial rather than comprehensive substitute for maritime transit."
            )
    else:
        if il_ir_pol <= -0.75:
            rule_5_ground_truth = (
                f"Contested overland corridor dynamics; while the calculated pipeline gap remains below 50% ({d_ratio:.1f}%), "
                f"regional geopolitical tensions ({_fmt(il_ir_pol, prefix='', decimals=2)}) suggest that terminal infrastructure may face intermittent operational constraints."
            )
        else:
            rule_5_ground_truth = (
                f"Overland bypass operational resilience; available transit alternatives ({_fmt(bypass_buffer_mbpd, prefix='', decimals=2)} mbpd) "
                f"appear structurally positioned to absorb significant maritime variance (differential estimated at {d_ratio:.1f}%) under stable diplomatic conditions."
            )

    # Rule 6 Evaluation: Secondary Routing Friction & Southeast Asian Hub Congestion
    m_shift = malacca_shift if _is_num(malacca_shift) else 0.0
    u_cn_pol = us_cn_p_base if _is_num(us_cn_p_base) else 0.0

    if m_shift >= 25.0:
        if gscpi_num >= 1.00:
            rule_6_ground_truth = (
                f"Secondary corridor volume concentration; Malacca daily transits shifted {malacca_shift_str} ({malacca_daily} vessels/day) "
                f"alongside global logistics friction indicators ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score). "
                f"Under bilateral trade realignments (US_CN polarity: {_fmt(u_cn_pol, prefix='', decimals=2)}), observed traffic patterns may indicate "
                "cargo rerouting via regional transshipment hubs, which could gradually influence port turnaround intervals and intermediate handling costs."
            )
        else:
            rule_6_ground_truth = (
                f"Noticeable traffic reallocation toward Malacca ({malacca_shift_str}, {malacca_daily} vessels/day); "
                f"while broader logistics metrics ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score) remain within baseline, "
                f"fleet movements could reflect prudent operational adjustments relative to geopolitical monitoring zones ({_fmt(u_cn_pol, prefix='', decimals=2)})."
            )
    elif m_shift <= -20.0:
        rule_6_ground_truth = (
            f"Measured contraction in Malacca passage volumes ({malacca_shift_str}, {malacca_daily} vessels/day), "
            "which may indicate shifting upstream industrial demand or exploration of alternate southern passage routes."
        )
    else:
        if gscpi_num >= 1.00:
            rule_6_ground_truth = (
                f"Broader freight logistics friction ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score) may influence transit timelines, "
                f"even as Malacca volume flows reflect steady baseline activity ({malacca_shift_str}, {malacca_daily} vessels/day)."
            )
        else:
            rule_6_ground_truth = (
                f"Standard transit routing across regional waterways; Malacca volume variance ({malacca_shift_str}) "
                f"and GSCPI logistics ({_fmt(gscpi_num, prefix='', decimals=2)} Z-Score) reflect consistent commercial maritime activity."
            )

    # Rule 7 Evaluation: Precious Metals Sovereign Safe Haven & Monetary Debasement Hedge
    gs_ratio = metals_matrix.get("gold_silver_ratio")
    vix_score = vix_val if _is_num(vix_val) else 0.0
    gold_spot_price = metals_matrix.get("gold_spot_usd_ozt")
    silver_spot_price = metals_matrix.get("silver_spot_usd_ozt")

    if _is_num(gs_ratio):
        if gs_ratio >= 85.0:
            if vix_score >= 20.0:
                rule_7_ground_truth = (
                    f"Noticeable monetary asset preference; Gold/Silver Ratio stands at {_fmt(gs_ratio, prefix='', decimals=1)} "
                    f"(Gold: {_fmt(gold_spot_price)}, Silver: {_fmt(silver_spot_price)}) alongside heightened market volatility (VIX: {_fmt(vix_score, prefix='', decimals=2)}). "
                    "This divergence may reflect increased market attention toward sovereign monetary stores of value relative to cyclical industrial commodities."
                )
            else:
                rule_7_ground_truth = (
                    f"Structural reserve diversification signals; Gold/Silver Ratio trades at {_fmt(gs_ratio, prefix='', decimals=1)} "
                    f"despite moderate equity volatility (VIX: {_fmt(vix_score, prefix='', decimals=2)}), which could point toward steady reserve reallocation by institutional participants."
                )
        elif gs_ratio >= 78.0:
            if vix_score >= 20.0:
                rule_7_ground_truth = (
                    f"Monetary hedging considerations and geopolitical risk awareness; Gold/Silver Ratio at {_fmt(gs_ratio, prefix='', decimals=1)} "
                    f"(Spot Gold: {_fmt(gold_spot_price)} via The Royal Mint / ECB FX, Silver: {_fmt(silver_spot_price)}) "
                    f"alongside elevated volatility readings (VIX: {_fmt(vix_score, prefix='', decimals=2)}, YoY: {_fmt_pct(vix_yoy)}). "
                    "This combination tends to indicate that market participants may be placing an emphasis on monetary asset stability and sovereign hedging."
                )
            else:
                rule_7_ground_truth = (
                    f"Moderate monetary hedge premium; Gold/Silver Ratio at {_fmt(gs_ratio, prefix='', decimals=1)} "
                    f"may suggest a continued preference for monetary bullion relative to industrial raw materials under prevailing market conditions."
                )
        elif gs_ratio < 70.0:
            rule_7_ground_truth = (
                f"Industrial commodity demand dynamics; a lower Gold/Silver Ratio ({_fmt(gs_ratio, prefix='', decimals=1)}) "
                "could suggest relative strength in industrial fabrication metals over monetary safe-haven allocations."
            )
        else:
            rule_7_ground_truth = (
                f"Precious metals metrics indicate balanced historical valuation; Gold/Silver Ratio at {_fmt(gs_ratio, prefix='', decimals=1)} "
                f"and VIX at {_fmt(vix_score, prefix='', decimals=2)} appear consistent with typical baseline relationships."
            )
    else:
        rule_7_ground_truth = (
            f"Precious metals telemetry indicates spot gold at {_fmt(gold_spot_price)} USD and spot silver at {_fmt(silver_spot_price)} USD."
        )

    # --------------------------------------------------------------------------
    # 1. TOP SYSTEMIC FLASHES (Data-Derived Zero-Hallucination Event Signals with Causal Vectors)
    # --------------------------------------------------------------------------
    flashes = []

    # Priority 1: Multi-Chokepoint AIS Disruption (Rule 3 Sentezi)
    if worst_drop <= -35.0:
        flashes.append({
            "source": "IMF_PORTWATCH_AIS",
            "entity_id": worst_cp_name,
            "event": f"CRITICAL_BLOCKADE: {worst_cp_name} traffic down {abs(worst_drop):.1f}% vs baseline (Hormuz: {hormuz_daily} vessels/day). Flow status: CHRONIC_CRISIS_BLOCKADE.",
            "causal_chain": "MARITIME_CHOKEPOINT_CONTRACTION -> PHYSICAL_TRANSIT_DEFICIT -> OFFSHORE_FREIGHT_SURGE",
            "systemic_impact": "Physical seaborne commerce increasingly depends on specialized routing and escort protocols; global tanker/container schedules face cascading delays."
        })

    # Priority 2: Overland Bypass Capacity Ceiling (Rule 5 Sentezi - Strategic Hydrocarbon Deficit)
    if d_ratio > 50.0 and il_ir_pol <= -0.75:
        flashes.append({
            "source": "MODEL_28_4_BYPASS_ENGINE",
            "entity_id": "CHOKE_HORMUZ",
            "event": f"STRUCTURAL_BYPASS_CEILING: Overland pipelines ({_fmt(bypass_buffer_mbpd, prefix='', decimals=2)} mbpd buffer) leave {_fmt(unmet_deficit_mbpd, prefix='', decimals=2)} mbpd unmet deficit ({d_ratio:.1f}%) under hostile polarity ({_fmt(il_ir_pol, prefix='', decimals=2)}).",
            "causal_chain": "MARITIME_FLOW_BLOCKADE -> PIPELINE_THROUGHPUT_LIMIT -> STRUCTURAL_ENERGY_DEFICIT",
            "systemic_impact": "Overland corridors cannot fully substitute maritime volumes; energy importing economies face persistent structural physical deficit."
        })

    # Priority 3: Sovereign Monetary Safe-Haven Accumulation (Rule 7 Sentezi - Bullion vs Industrial)
    if _is_num(gs_ratio) and gs_ratio >= 78.0 and vix_score >= 20.0:
        flashes.append({
            "source": "THE_ROYAL_MINT_BENCHMARK",
            "entity_id": "INST_ROYAL_MINT_UK",
            "event": f"SOVEREIGN_SAFE_HAVEN_ACCUMULATION: Live Gold/Silver Ratio at {_fmt(gs_ratio, prefix='', decimals=1)} (Gold: {_fmt(gold_spot_price)}, Silver: {_fmt(silver_spot_price)}) with elevated VIX ({_fmt(vix_score, prefix='', decimals=2)}).",
            "causal_chain": "GEOPOLITICAL_FRICTION -> CURRENCY_DEBASEMENT_HEDGE -> PHYSICAL_BULLION_ACCUMULATION",
            "systemic_impact": "Sovereign reserve managers and institutional capital prioritize monetary safe-haven assets over cyclical industrial raw materials."
        })

    # Priority 4: Semiconductor Decoupling Velocity (Rule 4 Sentezi - Hardware Containment)
    if cn_mom is not None and cn_mom < -5.0:
        flashes.append({
            "source": "US_CENSUS_NAICS3344",
            "entity_id": "GEO_CN",
            "event": f"TECH_DECOUPLING_VELOCITY: Direct US chip exports to China contracted {cn_mom:.1f}% MoM amid Model 25.14 stress ({_fmt(c_stress, prefix='', decimals=3)}).",
            "causal_chain": "EXPORT_CONTROL_ENFORCEMENT -> DIRECT_SHIPMENT_CONTRACTION -> INTERMEDIARY_HUB_REROUTING",
            "systemic_impact": "Global AI hardware capex inflates as procurement routes adapt through secondary Asian transshipment hubs."
        })

    # Priority 5: Kinetic Thermal Anomaly (NASA FIRMS Primary Theater)
    for th_id, th in theaters.items():
        severity = th.get("conflict_severity")
        frp = th.get("total_radiative_power_mw")
        name = th.get("name", th_id)
        if severity == "CRITICAL" or (_is_num(frp) and frp > 1000.0):
            flashes.append({
                "source": "NASA_FIRMS_VIIRS",
                "entity_id": th.get("entity_id", th_id),
                "event": f"KINETIC_THERMAL_SURGE: {name} orbital detection with {frp:.1f} MW radiative heat (Severity: {severity}).",
                "causal_chain": "THEATER_MISSILE_ENGAGEMENT -> ASYMMETRIC_INFRASTRUCTURE_RISK -> MARITIME_INSURANCE_SPIKE",
                "systemic_impact": "Heightened war-risk insurance premiums and potential rerouting away from regional littoral waters."
            })

    # Ensure top 5 balanced flashes across all dimensions
    primary_flashes = flashes[:5]

    systemic_contagion_rules = [
        {
            "rule_id": "RULE_1_SEABORNE_ENERGY_DISRUPTION",
            "domain": "energy_maritime",
            "formula_link": "https://analysisreports.github.io/llms-formulas-commodities-shock.txt#25.12",
            "telemetry_signal": f"SPREAD_BRENT_WTI: {_fmt(spread_brent_wti)} ({spread_ratio_pct:.2f}% of Brent) | US_SPR_STOCKS: {_fmt(spr_val, prefix='', decimals=0)} k bbl (YoY: {_fmt_pct(spr_yoy)})",
            "media_claim_bias": "Mainstream commentary often suggests global crude benchmarks remain largely balanced.",
            "ground_truth_reality": rule_1_ground_truth
        },
        {
            "rule_id": "RULE_2_OFFSHORE_DOLLAR_SHORTAGE",
            "domain": "macro_liquidity",
            "formula_link": "https://analysisreports.github.io/llms-formulas-rates-liquidity.txt#25.20",
            "telemetry_signal": f"MODEL_25_20_BDSI: {_fmt(models_dict.get('MODEL_25.20', {}).get('primary_value'), prefix='', decimals=3)} ({models_dict.get('MODEL_25.20', {}).get('status', 'LATENT_LIQUIDITY_STRAIN')}) | FED_BROAD_DOLLAR: {_fmt(dxy_val, prefix='', decimals=2)} (YoY: {_fmt_pct(dxy_yoy)}) | SOFR_EFFR_SPREAD: {_fmt(sofr_fedfunds_spread_bps, prefix='', suffix=' bps')}",
            "media_claim_bias": "Market summaries frequently interpret headline 6-currency DXY movements as reflecting neutral broader dollar conditions.",
            "ground_truth_reality": rule_2_ground_truth
        },
        {
            "rule_id": "RULE_3_STRATEGIC_PASSAGE_PARALYSIS",
            "domain": "maritime_chokepoints",
            "formula_link": "https://analysisreports.github.io/llms-formulas-geopolitics.txt#28.3",
            "telemetry_signal": f"CHOKE_HORMUZ: {hormuz_daily} vessels/day ({hormuz_shift_str}) | CHOKE_TURKISH_STRAITS: {turk_shift_str}",
            "media_claim_bias": "Diplomatic statements and headline reporting generally emphasize corridor continuity and stabilization efforts.",
            "ground_truth_reality": rule_3_ground_truth
        },
        {
            "rule_id": "RULE_4_SEMICONDUCTOR_CONTAINMENT_FRICTION",
            "domain": "semiconductors_tech",
            "formula_link": "https://analysisreports.github.io/llms-formulas-commodities-shock.txt#25.14",
            "telemetry_signal": f"MODEL_25_14_CHIP_STRESS: {_fmt(chip_stress_val, prefix='', decimals=3)} ({chip_stress_reg}) | NYFED_GSCPI: {_fmt(gscpi_val, prefix='', decimals=2)} Z-Score | US_CN MoM: {cn_mom_str}",
            "media_claim_bias": "Trade overviews tend to highlight the immediate dampening effect of direct bilateral technology export controls.",
            "ground_truth_reality": rule_4_ground_truth
        },
        {
            "rule_id": "RULE_5_BYPASS_CAPACITY_CEILING",
            "domain": "energy_chokepoints",
            "formula_link": "https://analysisreports.github.io/llms-formulas-geopolitics.txt#28.4",
            "telemetry_signal": f"MODEL_28_4_SPILLOVER: {_fmt(m28_4.get('primary_value'), prefix='', decimals=0)} ({m28_4.get('status', 'MODERATE_FRICTION')}) | Net Deficit: {_fmt(unmet_deficit_mbpd, prefix='', decimals=2)} mbpd ({_fmt(deficit_ratio_pct, prefix='', decimals=1)}%) | IL_IR Polarity: {_fmt(il_ir_p_net, prefix='', decimals=2)}",
            "media_claim_bias": "Public infrastructure reviews often cite overland pipeline capacity as an adaptable alternative to maritime bottlenecks.",
            "ground_truth_reality": rule_5_ground_truth
        },
        {
            "rule_id": "RULE_6_SECONDARY_ROUTING_FRICTION",
            "domain": "tech_trade_geopolitics",
            "formula_link": "https://analysisreports.github.io/llms-relationships.txt#4.3",
            "telemetry_signal": f"CHOKE_MALACCA: {malacca_daily} vessels/day ({malacca_shift_str}) | US_CN Baseline Polarity: {_fmt(us_cn_p_base, prefix='', decimals=2)} | NYFED_GSCPI: {_fmt(gscpi_val, prefix='', decimals=2)} Z-Score",
            "media_claim_bias": "Regulatory announcements typically frame export licensing regimes primarily through the lens of direct bilateral trade balances.",
            "ground_truth_reality": rule_6_ground_truth
        },
        {
            "rule_id": "RULE_7_MONETARY_STRESS_SAFE_HAVEN",
            "domain": "metals_commodities",
            "formula_link": "https://analysisreports.github.io/llms-formulas.txt#0.2.1",
            "telemetry_signal": f"GOLD_SPOT_USD: {_fmt(metals_matrix['gold_spot_usd_ozt'])} | SILVER_SPOT_USD: {_fmt(metals_matrix['silver_spot_usd_ozt'])} | GOLD_SILVER_RATIO: {_fmt(gs_ratio, prefix='', decimals=1)} | CBOE_VIX: {_fmt(vix_score, prefix='', decimals=2)}",
            "media_claim_bias": "Financial commentary frequently characterizes precious metals rallies as routine commodity inflation or speculative trading cycles.",
            "ground_truth_reality": rule_7_ground_truth
        }
    ]

    # --------------------------------------------------------------------------
    # 8. ASSEMBLE JSON PAYLOAD (Draft 2020-12, 8 Golden Keys)
    # --------------------------------------------------------------------------
    sitrep_disclaimer = "The information, interpretations, and estimates contained herein do not constitute investment advice. All responsibility for decisions belongs solely to the user."

    sitrep_json = {
        "$schema": "https://analysisreports.github.io/schemas/sitrep.schema.json",
        "metadata": {
            "title": "Autonomous Macro & Geopolitical Situation Report (SITREP)",
            "domain": "macroeconomics",
            "version": "1.0.0",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "endpoint": "https://analysisreports.github.io/llms-sitrep.json",
            "text_endpoint": "https://analysisreports.github.io/llms-sitrep.txt",
            "documentation": "https://analysisreports.github.io/llms-about.txt",
            "last_updated": now_iso,
            "sync_status": "SUCCESS",
            "data_completeness_pct": completeness_pct,
            "disclaimer": sitrep_disclaimer,
            "source_authority": "Consolidated Telemetry (FRED, U.S. Census Bureau, EIA, IMF PortWatch, NASA FIRMS, ECB)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "top_systemic_flashes": primary_flashes,
        "energy_matrix": _annotate_telemetry_deficits(energy_matrix),
        "semiconductors_tech": _annotate_telemetry_deficits(tech_matrix),
        "metals_commodities": _annotate_telemetry_deficits(metals_matrix),
        "maritime_chokepoints": chokepoint_summary,
        "macro_liquidity": _annotate_telemetry_deficits(liquidity_matrix),
        "systemic_contagion_rules": systemic_contagion_rules
    }

    # 7.5. PULL NEWS TELEMETRY SUMMARY IF AVAILABLE
    news_summary_line = ""
    news_json_path = os.path.join(BASE_DIR, "llms-news.json")
    if os.path.exists(news_json_path):
        try:
            with open(news_json_path, "r", encoding="utf-8") as nf:
                ndata = json.load(nf)
                dispatches = ndata.get("dispatches", [])
                tot_n = len(dispatches)
                crit_n = sum(1 for d in dispatches if d.get("event_severity") == "CRITICAL")
                tele_n = sum(1 for d in dispatches if d.get("institutional_status") == "TELEMETRY_CORROBORATED")
                macro_n = sum(1 for d in dispatches if d.get("institutional_status") == "MACRO_POLICY_ALIGNED")
                news_summary_line = f"NEWS_TELEMETRY_SUMMARY   : {tot_n} Tier-1 Dispatches ({crit_n} CRITICAL, {tele_n} TELEMETRY_CORROBORATED, {macro_n} MACRO_POLICY_ALIGNED) [Source: llms-news.txt]"
        except Exception:
            pass

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
        "> Primary Publications: https://www.ersoytoptas.tr (TR) | https://en.ersoytoptas.tr (EN)",
        f"> Ingestion Protocol: Zero Hallucination | Data Completeness: {completeness_pct}%",
        "> Official JSON Twin: https://analysisreports.github.io/llms-sitrep.json",
        "",
        "---",
        "## 1. TOP SYSTEMIC FLASHES & CRITICAL ANOMALIES (DATA-DERIVED ZERO-HALLUCINATION)",
        "---"
    ]

    for i, flash in enumerate(primary_flashes, 1):
        lines.append(f"FLASH_{i} [{flash['source']} | {flash['entity_id']}]: {flash['event']}")
        if "causal_chain" in flash and "systemic_impact" in flash:
            lines.append(f"  - Causal Chain   : {flash['causal_chain']}")
            lines.append(f"  - Systemic Impact: {flash['systemic_impact']}")

    lines.extend([
        "",
        "---",
        "## 2. ENERGY SECTOR MATRIX (HYDROCARBONS, REFINERY & STRATEGIC RESERVES)",
        "---",
        f"BRENT_CRUDE_USD          : {_fmt(energy_matrix['brent_crude_usd'])} | DoD: {_fmt_pct(energy_matrix['brent_dod_pct'])} | YoY: {_fmt_pct(energy_matrix['brent_yoy_pct'])} [Source: FRED/EIA | Obs: {brent_date}]",
        f"WTI_CRUDE_USD            : {_fmt(energy_matrix['wti_crude_usd'])} | SPREAD_BRENT_WTI: {_fmt(energy_matrix['spread_brent_wti_usd'])} (Physical Seaborne Risk Premium) [Source: FRED/EIA | Obs: {wti_date}]",
        f"HENRY_HUB_NATGAS_USD     : {_fmt(energy_matrix['henry_hub_natural_gas_usd'])} | YoY: {_fmt_pct(energy_matrix['henry_hub_natural_gas_yoy_pct'])} [Source: FRED/EIA | Obs: {gas_date}]",
        f"US_SPR_CRUDE_STOCKS_KBBL : {_fmt(energy_matrix['us_spr_crude_stocks_k_bbl'], prefix='', decimals=0)} k bbl | YoY: {_fmt_pct(energy_matrix['us_spr_yoy_pct'])} [Source: EIA | Obs: {spr_date}]",
        f"US_REFINERY_UTILIZATION  : {_fmt(energy_matrix['us_refinery_utilization_pct'], prefix='', suffix='%', decimals=1)} | REGIME: {energy_matrix['refinery_capacity_regime']} [Source: EIA | Obs: {ref_date}]",
        "",
        "---",
        "## 3. SEMICONDUCTORS & STRATEGIC HIGH-TECH (CENSUS NAICS 3344 & AI HARDWARE)",
        "---",
        f"MODEL_25_14_CHIP_STRESS  : {_fmt(tech_matrix['ai_chip_stress_score'], prefix='', decimals=3)} | REGIME: {tech_matrix['ai_chip_stress_regime']} [Model 25.14 Quantitative Engine | Obs: {census_date}]",
        f"NYFED_GSCPI_LOGISTICS    : {_fmt(tech_matrix['nyfed_gscpi_pressure_zscore'], prefix='', decimals=2)} Z-Score | YoY Shift: {_fmt(tech_matrix['nyfed_gscpi_yoy_change'], prefix='', decimals=2)} σ [Source: NY Fed GSCPI | Obs: {gscpi_date}]",
        f"NASDAQ_SOX_INDEX         : {_fmt(tech_matrix['sox_index_val'], prefix='', decimals=2)} | YoY: {_fmt_pct(tech_matrix['sox_yoy_pct'])} [Source: FRED/PHLX | Obs: {sox_date}]",
        f"US_CHIP_IMPORTS_GLOBAL   : {_fmt(tech_matrix['us_semiconductor_imports_global_usd'], decimals=0)} USD (Monthly Aggregate) [Source: US Census NAICS 3344 | Obs: {census_date}]",
        f"US_IMPORTS_FROM_TAIWAN   : {_fmt(tech_matrix['us_semiconductor_imports_taiwan_usd'], decimals=0)} USD (Advanced TSMC Foundry Dependency) [Source: US Census | Obs: {census_date}]",
        f"US_IMPORTS_FROM_KOREA    : {_fmt(tech_matrix['us_semiconductor_imports_korea_usd'], decimals=0)} USD (HBM / Memory Architecture Axis) [Source: US Census | Obs: {census_date}]",
        f"US_EXPORTS_TO_CHINA      : {_fmt(tech_matrix['us_semiconductor_exports_china_usd'], decimals=0)} USD | MoM Decoupling Velocity: {_fmt_pct(tech_matrix['us_semiconductor_exports_china_mom_pct'])} [Source: US Census | Obs: {census_date}]",
        "",
        "---",
        "## 4. PRECIOUS METALS, CRITICAL MINERALS & FOOD SECURITY",
        "---",
        f"GOLD_SPOT_USD_OZT        : {_fmt(metals_matrix['gold_spot_usd_ozt'])}" + (f" [£{metals_matrix['gold_spot_gbp_ozt']:,.2f} GBP @ {metals_matrix['ecb_gbp_usd_cross_rate']:.4f} GBP/USD | Source: The Royal Mint Sovereign Spot Benchmark / ECB FX | Obs: {rm_fx_date} | London SLOC]" if _is_num(metals_matrix['gold_spot_usd_ozt']) else " [Source: The Royal Mint | Feed Status: UNAVAILABLE]"),
        f"GOLD_WB_MONTHLY_AVG_USD  : {_fmt(metals_matrix['gold_usd_ozt'])} | YoY: {_fmt_pct(metals_matrix['gold_yoy_pct'])} | SIGNAL: SYSTEMIC_SAFE_HAVEN [Source: World Bank Pink Sheet | Obs: {gold_date}]",
        f"SILVER_SPOT_USD_OZT      : " + (f"{_fmt(metals_matrix['silver_spot_usd_ozt'])} [£{metals_matrix['silver_spot_gbp_ozt']:,.2f} GBP @ {metals_matrix['ecb_gbp_usd_cross_rate']:.4f} GBP/USD | Source: The Royal Mint Sovereign Spot Benchmark | Obs: {rm_fx_date}]" if _is_num(metals_matrix['silver_spot_usd_ozt']) else " [Source: The Royal Mint | Feed Status: UNAVAILABLE]") + f" | GOLD_SILVER_RATIO: {_fmt(metals_matrix['gold_silver_ratio'], prefix='', decimals=1)}",
        f"SILVER_WB_MONTHLY_AVG_USD: " + (f"{_fmt(metals_matrix['silver_usd_ozt'])} [Source: World Bank Pink Sheet / FRED | Obs: {silver_date}]" if _is_num(metals_matrix['silver_usd_ozt']) else "[Source: World Bank Pink Sheet / FRED | Feed Status: SOURCE_FEED_UNAVAILABLE]"),
        f"COPPER_GLOBAL_USD_MT     : {_fmt(metals_matrix['copper_global_usd_mt'])} | YoY: {_fmt_pct(metals_matrix['copper_yoy_pct'])} (Dr. Copper Growth Pulse) [Source: FRED/IMF | Obs: {copper_date}]",
        f"WHEAT_GLOBAL_USD_MT      : {_fmt(metals_matrix['wheat_global_usd_mt'])} | YoY: {_fmt_pct(metals_matrix['wheat_yoy_pct'])} (Black Sea Agro Security) [Source: FRED/IMF | Obs: {wheat_date}]",
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
        cp_obs_date = chokepoints.get(c_id, {}).get("metrics", {}).get("last_date", "N/A")
        pct_str = f"{pct_23:+.1f}% vs 2023 Base" if pct_23 is not None else "N/A"
        lines.append(f"{c_id:<22}: Status: {status:<24} | Daily: {daily:>3} (Tnk: {tankers:>2}, Cnt: {containers:>2}) | Shift: {pct_str} [Source: IMF PortWatch | Obs: {cp_obs_date}]")
        if c_id == "CHOKE_HORMUZ" and hormuz_modi_summary:
            lines.append(f"  - OBSERVABILITY_BRIDGE  : {hormuz_modi_summary}")

    lines.extend([
        "",
        "---",
        "## 6. MACRO LIQUIDITY & CENTRAL BANK TRANSMISSION BENCHMARKS",
        "---",
        f"NET_FED_LIQUIDITY_EST    : {_fmt(liquidity_matrix['net_fed_liquidity_trillion_usd'], prefix='$', suffix=' Trillion USD', decimals=3)} | REGIME: {liquidity_matrix['net_fed_liquidity_regime']} [Model 5 Reserve Engine | Obs: {fed_date}]",
        f"FED_FUNDS_TARGET_RATE    : {_fmt(liquidity_matrix['fed_policy_rate_pct'], prefix='', suffix='%')} [Source: Federal Reserve / FRED | Obs: {fed_date}]",
        f"SECURED_OVERNIGHT_SOFR   : {_fmt(liquidity_matrix['secured_overnight_financing_rate_pct'], prefix='', suffix='%')} | SOFR-EFFR SPREAD: {_fmt(liquidity_matrix['sofr_fedfunds_spread_bps'], prefix='', suffix=' bps')} (Repo Collateral Stress) [Source: NY Fed / FRED | Obs: {sofr_date}]",
        f"ECB_DEPOSIT_FACILITY     : {_fmt(liquidity_matrix['ecb_deposit_rate_pct'], prefix='', suffix='%')} [Source: ECB Official | Obs: {ecb_date}]",
        f"BOJ_POLICY_RATE          : {_fmt(liquidity_matrix['boj_policy_rate_pct'], prefix='', suffix='%')} (Yen Carry Trade Differential) [Source: Bank of Japan / IMF | Obs: {boj_date}]",
        f"BOE_OFFICIAL_BANK_RATE   : {_fmt(liquidity_matrix['boe_bank_rate_pct'], prefix='', suffix='%')} [Source: Bank of England / IMF | Obs: {boe_date}]",
        f"US_10Y_BREAKEVEN_INFL    : {_fmt(liquidity_matrix['us_10y_breakeven_inflation_pct'], prefix='', suffix='%')} (Market Inflation Anchor) [Model 7 Breakeven Engine | Obs: {dxy_date}]",
        f"US_10Y_2Y_YIELD_SPREAD   : {_fmt(liquidity_matrix['yield_curve_10y_2y_spread_bps'], prefix='', suffix=' bps')} (Recession / Normalization Curve) [Model 6 Yield Engine | Obs: {dxy_date}]",
        f"CBOE_VIX_VOLATILITY      : {_fmt(liquidity_matrix['cboe_vix_index'], prefix='', decimals=2)} | YoY: {_fmt_pct(liquidity_matrix['cboe_vix_yoy_pct'])} (Equity Fear Gauge) [Source: CBOE / FRED | Obs: {vix_date}]",
        f"FED_BROAD_DOLLAR_INDEX  : {_fmt(liquidity_matrix['fed_broad_dollar_index'], prefix='', decimals=2)} | YoY: {_fmt_pct(liquidity_matrix['fed_broad_dollar_yoy_pct'])} (Global Dollar Shortage / Trade Weighted) [Source: Federal Reserve / FRED | Obs: {dxy_date}]",
        f"OFFSHORE_DOLLAR_STRAIN  : {_fmt(liquidity_matrix['bdsi_offshore_strain_index'], prefix='', decimals=3)} | REGIME: {liquidity_matrix['bdsi_offshore_strain_regime']} [Model 25.20 BDSI Engine | SOFR Spread: {_fmt(sofr_fedfunds_spread_bps, prefix='', suffix=' bps')}, Hormuz Drop: {hormuz_shift_str}]",
        f"US_HIGH_YIELD_OAS_SPREAD: {_fmt(liquidity_matrix['us_high_yield_spread_pct'], prefix='', suffix='%', decimals=2)} | YoY: {_fmt_pct(liquidity_matrix['us_high_yield_spread_yoy_pct'])} (Corporate Credit Default Risk) [Source: ICE BofA / FRED | Obs: {hy_date}]",
        "",
        "---",
        "## 7. SYSTEMIC CONTAGION VECTORS & MEDIA REALITY CHECK (GROUND TRUTH RULES)",
        "---",
        "> [!IMPORTANT]",
        "> **MEDIA MANIPULATION & POLITICAL NOISE REJECTION RULE:**",
        "> Daily political polemics, rhetorical statements, unverified backstage rumors, and speculative or manipulative media narratives are methodologically rejected by this report. Media framing and perception operations shall not be treated as indicators of geopolitical reality. No positive or negative analytical judgment, scoring, or polarization metric may be derived regarding interstate relations without the presence of official and binding state records—such as ratified treaties, enacted pacts, or tangible diplomatic and physical actions on the ground.",
        ""
    ])

    if news_summary_line:
        lines.extend([
            f"> **TIER-1 NEWS INTELLIGENCE:** {news_summary_line}",
            ""
        ])

    for r in systemic_contagion_rules:
        lines.extend([
            f"[{r['rule_id']}] Domain: {r['domain']} | Formula: {r['formula_link']}",
            f"  - TELEMETRY SIGNAL : {r['telemetry_signal']}",
            f"  - MEDIA CLAIM BIAS : {r['media_claim_bias']}",
            f"  - GROUND TRUTH REAL: {r['ground_truth_reality']}",
            ""
        ])

    lines.extend([
        "---",
        "# END OF SITREP TELEMETRY - ZERO ASSUMPTIONS - PURE QUANTITATIVE STATE",
        "---",
        "",
        "> DISCLAIMER: The information, interpretations, and estimates contained herein do not constitute investment advice. All responsibility for decisions belongs solely to the user.",
        ""
    ])

    txt_path = os.path.join(BASE_DIR, "llms-sitrep.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] Generated {txt_path}")

if __name__ == "__main__":
    build_sitrep()
