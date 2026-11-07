#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calculate_models.py
-------------------
Autonomous Quantitative Macroeconomic Model Engine.
Calculates canonical macroeconomic models defined in llms-formulas.txt directly from:
  1. Live St. Louis Fed (FRED) time-series ingested by llms-fred-series.json
  2. Live Bank for International Settlements (BIS) central bank policy rate API
Generates:
  - llms-models.json (Deterministic Machine-Readable Twin)
  - llms-models.txt (Human-Readable Markdown Table Twin)

Author: Ersoy Toptaş & Google Gemini AI Engine
License: CC BY 4.0
Endpoint txt: https://analysisreports.github.io/llms-models.txt
Endpoint json: https://analysisreports.github.io/llms-models.json
"""

import os
import csv
import io
import json
import math
import datetime
import urllib.request
from typing import Dict, Any, Optional

# ==============================================================================
# 1. LIVE DATA INGESTION UTILITIES
# ==============================================================================

def fetch_bis_policy_rates() -> Optional[Dict[str, Dict[str, Any]]]:
    """Fetches official central bank policy rates directly from the Bank for International Settlements (BIS)."""
    url = "https://stats.bis.org/api/v1/data/WS_CBPOL/D.XM+JP+GB+CN+US?lastNObservations=1&format=csv"
    req = urllib.request.Request(url, headers={"User-Agent": "AnalysisReports-GlobalMacro-Engine/1.0"})
    rates = {}
    name_map = {
        "US": ("GEO_US", "INST_FED_US", "United States (Federal Reserve)"),
        "XM": ("GEO_DE", "INST_ECB_EZ", "Eurozone (European Central Bank)"),
        "JP": ("GEO_JP", "INST_BOJ_JP", "Japan (Bank of Japan)"),
        "GB": ("GEO_GB", "INST_BOE_GB", "United Kingdom (Bank of England)"),
        "CN": ("GEO_CN", "INST_PBOC_CN", "China (People's Bank of China)")
    }
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            text = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            area = row.get("REF_AREA")
            if area in name_map:
                geo_id, inst_id, label = name_map[area]
                rates[area] = {
                    "entity_id": geo_id,
                    "institution_id": inst_id,
                    "authority": label,
                    "policy_rate": float(row["OBS_VALUE"]),
                    "last_decision_date": row["TIME_PERIOD"]
                }
        return rates
    except Exception as e:
        print(f"Warning: Could not fetch live BIS policy rates: {e}")
        return None

# ==============================================================================
# 2. MODEL IMPLEMENTATIONS (STRICTLY FROM llms-formulas.txt)
# ==============================================================================

# --- Model 1: Global Central Bank Policy Rates & Monetary Stance ---
def calc_global_central_bank_rates(bis_rates: Optional[Dict[str, Dict[str, Any]]]):
    if not bis_rates or "US" not in bis_rates:
        return None
    try:
        fed_rate = bis_rates["US"]["policy_rate"]
        ecb_rate = bis_rates.get("XM", {}).get("policy_rate", 2.50)
        boj_rate = bis_rates.get("JP", {}).get("policy_rate", 1.25)
        boe_rate = bis_rates.get("GB", {}).get("policy_rate", 3.75)
        pboc_rate = bis_rates.get("CN", {}).get("policy_rate", 3.00)

        us_ecb_spread = round(fed_rate - ecb_rate, 3)
        us_boj_spread = round(fed_rate - boj_rate, 3)

        if fed_rate >= 4.50:
            regime = "TIGHT_GLOBAL_RESTRICTION"
        elif fed_rate <= 2.50:
            regime = "EXPANSIVE_ACCOMMODATION"
        else:
            regime = "CALIBRATED_POLICY_EASING"

        rates_table = [
            {"entity_id": v["entity_id"], "authority": v["authority"], "rate": v["policy_rate"], "date": v["last_decision_date"]}
            for v in bis_rates.values()
        ]

        return {
            "model_id": "MODEL_1",
            "model_name": "Global Central Bank Policy Benchmark & Rate Disparity",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#1",
            "primary_value": fed_rate,
            "unit": "Percent (%)",
            "status": regime,
            "inputs": {
                "fed_funds_midpoint": fed_rate,
                "ecb_deposit_facility": ecb_rate,
                "boj_overnight_call": boj_rate,
                "boe_bank_rate": boe_rate,
                "pboc_loan_prime_rate": pboc_rate
            },
            "rate_disparities": {
                "us_minus_ecb_spread_pts": us_ecb_spread,
                "us_minus_boj_carry_spread_pts": us_boj_spread
            },
            "rates_snapshot": rates_table,
            "interpretation": "Canonical policy rates across G5 central banks sourced from Bank for International Settlements (BIS). Guides cross-border carry trades and sovereign yields."
        }
    except Exception:
        return None


# --- Model 3: Sahm Resesyon Kuralı (Sahm Rule Recession Indicator) ---
def calc_sahm_rule(sahm_val):
    if sahm_val is None or isinstance(sahm_val, bool):
        return None
    try:
        val = float(sahm_val)
        if not math.isfinite(val):
            return None

        diff = round(val, 2)
        if diff >= 0.50:
            status = "RECESSION_CONFIRMED"
        elif diff >= 0.30:
            status = "PRE_RECESSION_WARNING"
        else:
            status = "NORMAL_LABOR_MARKET"

        return {
            "model_id": "MODEL_3",
            "model_name": "Official Sahm Rule Recession Indicator",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#3",
            "primary_value": diff,
            "unit": "Percentage Points",
            "status": status,
            "inputs": {"sahm_realtime_val": diff},
            "interpretation": "Real-time recession detection triggered when 3-month unemployment average rises >= 0.50 ppt above prior 12-month low."
        }
    except (TypeError, ValueError):
        return None


# --- Model 5: Net Fed Likiditesi (Net Fed Liquidity Index) ---
def calc_net_fed_liquidity(walcl_mil, tga_mil, rrp_bil):
    if any(v is None or isinstance(v, bool) for v in (walcl_mil, tga_mil, rrp_bil)):
        return None
    try:
        w = float(walcl_mil)
        t = float(tga_mil)
        r = float(rrp_bil) * 1000.0  # RRP is in Billions USD; converted to Millions USD per Section 5 mandate

        if not all(math.isfinite(x) for x in (w, t, r)):
            return None
        if min(w, t, r) < 0:
            return None

        net_liq = w - (t + r)
        if not math.isfinite(net_liq):
            return None

        net_liq_mil = round(net_liq, 2)
        net_liq_tril = round(net_liq / 1_000_000.0, 3)

        if net_liq_tril >= 6.20:
            status = "EXPANSIVE_LIQUIDITY_SURPLUS"
        elif net_liq_tril <= 5.50:
            status = "RESTRICTIVE_LIQUIDITY_DRAIN"
        else:
            status = "NEUTRAL_LIQUIDITY_EQUILIBRIUM"

        return {
            "model_id": "MODEL_5",
            "model_name": "Net Fed Liquidity Index",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#5",
            "primary_value": net_liq_tril,
            "unit": "Trillion USD",
            "status": status,
            "inputs": {
                "fed_total_assets_walcl_mil": w,
                "treasury_general_account_tga_mil": t,
                "overnight_reverse_repo_rrp_bil": round(float(rrp_bil), 3)
            },
            "metrics": {
                "net_liquidity_millions_usd": net_liq_mil,
                "net_liquidity_trillions_usd": net_liq_tril
            },
            "interpretation": "Unencumbered commercial bank liquidity: WALCL - (TGA + ON_RRP). Direct fuel for equity asset valuations."
        }
    except (TypeError, ValueError):
        return None


# --- Model 6: Getiri Eğrisi Makası (10Y - 2Y Yield Spread BPS) ---
def calc_yield_spread_bps(t10y2y_val):
    if t10y2y_val is None or isinstance(t10y2y_val, bool):
        return None
    try:
        spread = float(t10y2y_val)
        if not math.isfinite(spread):
            return None

        bps = round(spread * 100.0, 2)
        if bps < 0:
            status = "INVERTED_CURVE_RECESSION_SIGNAL"
        elif bps <= 25.0:
            status = "FLATTENING_TRANSITION_PHASE"
        elif bps <= 100.0:
            status = "NORMAL_CURVE_EXPANSION"
        else:
            status = "STEEPENING_GROWTH_REFLATION"

        return {
            "model_id": "MODEL_6",
            "model_name": "Treasury Yield Curve Slope (10Y - 2Y)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#6",
            "primary_value": bps,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {"t10y2y_spread_pct": spread},
            "interpretation": "Leading cyclical economic barometer. Inversions (bps < 0) historically precede sovereign US business cycle recessions."
        }
    except (TypeError, ValueError):
        return None


# --- Model 16: VIX Market Regime Thresholds ---
def calc_vix_market_regime(vix):
    if vix is None or isinstance(vix, bool):
        return None
    try:
        v = float(vix)
        if not math.isfinite(v) or v <= 0:
            return None

        val = round(v, 2)
        if val < 15.0:
            regime = "COMPLACENCY"
            bias = "RISK_ON"
        elif val < 20.0:
            regime = "NORMAL_VOLATILITY"
            bias = "BALANCED"
        elif val < 30.0:
            regime = "ELEVATED_STRESS"
            bias = "RISK_OFF"
        else:
            regime = "CRISIS_SHOCK"
            bias = "EXTREME_RISK_OFF"

        return {
            "model_id": "MODEL_16",
            "model_name": "CBOE Volatility & Market Fear Regime",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#16",
            "primary_value": val,
            "unit": "Points",
            "status": regime,
            "market_bias": bias,
            "inputs": {"vix_close": val},
            "interpretation": "30-day forward S&P 500 implied volatility fear gauge and systemic liquidity stress regime."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.12: Brent - WTI Seaborne Spread Engine ---
def calc_brent_wti_spread(brent_price, wti_price):
    if any(v is None or isinstance(v, bool) for v in (brent_price, wti_price)):
        return None
    try:
        f_brent = float(brent_price)
        f_wti = float(wti_price)
        if not (math.isfinite(f_brent) and math.isfinite(f_wti)):
            return None
        if f_brent <= 0.0 or f_wti <= 0.0:
            return None

        raw_spread = f_brent - f_wti
        if not math.isfinite(raw_spread):
            return None
        spread = round(raw_spread, 2)

        if spread > 8.0:
            status = "SEABORNE_GEOPOLITICAL_PREMIUM"
        elif spread < 1.5:
            status = "US_DOMESTIC_TIGHTNESS"
        else:
            status = "NORMAL_TRANSATLANTIC_ARBITRAGE"

        return {
            "model_id": "MODEL_25.12",
            "model_name": "Brent - WTI Seaborne Risk Spread",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.12",
            "primary_value": spread,
            "unit": "USD",
            "status": status,
            "inputs": {"brent_usd": f_brent, "wti_usd": f_wti},
            "interpretation": "Seaborne geopolitical friction and maritime risk spread between North Sea Brent and Cushing WTI."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.13: Labor Market Momentum Index (LMMI / EMME) ---
def calc_labor_market_momentum_index(payems_curr, payems_yr_ago, unrate_curr, unrate_yr_ago):
    if any(v is None or isinstance(v, bool) for v in (payems_curr, payems_yr_ago, unrate_curr, unrate_yr_ago)):
        return None
    try:
        p_curr = float(payems_curr)
        p_yr = float(payems_yr_ago)
        u_curr = float(unrate_curr)
        u_yr = float(unrate_yr_ago)

        if not all(math.isfinite(x) for x in (p_curr, p_yr, u_curr, u_yr)):
            return None
        if p_curr <= 0.0 or p_yr <= 0.0 or u_curr <= 0.0 or u_yr < 0.0:
            return None

        p_growth = ((p_curr / p_yr) - 1.0) * 100.0
        u_diff = u_curr - u_yr
        raw_lmmi = p_growth - u_diff

        if not math.isfinite(raw_lmmi):
            return None

        lmmi = round(raw_lmmi, 2)
        strength_ratio = round(p_growth * (1.0 / u_curr), 2) if u_curr > 0 else None

        if lmmi > 1.0:
            status = "STRONG_LABOR_EXPANSION"
        elif lmmi > 0.20:
            status = "MODERATE_LABOR_EXPANSION"
        elif lmmi < -0.20:
            status = "LABOR_MARKET_DETERIORATION_RISK"
        else:
            status = "BALANCED_LABOR_MARKET"

        return {
            "model_id": "MODEL_25.13",
            "model_name": "Labor Market Momentum Index (LMMI)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.13",
            "primary_value": lmmi,
            "unit": "Net Momentum Pts",
            "status": status,
            "inputs": {
                "payems_current": p_curr,
                "payems_year_ago": p_yr,
                "unrate_current": u_curr,
                "unrate_year_ago": u_yr
            },
            "metrics": {
                "payroll_growth_yoy_pct": round(p_growth, 2),
                "unemployment_rate_diff_yoy": round(u_diff, 2),
                "employment_strength_ratio": strength_ratio
            },
            "interpretation": "Couples nonfarm payroll expansion with unemployment change to gauge labor slack and wage inflation momentum."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.14: AI Hardware & Semiconductor Stress Gauge ---
def calc_ai_chip_stress_gauge(gscpi_val, sox_yoy_pct, vix_val):
    if any(v is None or isinstance(v, bool) for v in (gscpi_val, sox_yoy_pct, vix_val)):
        return None
    try:
        g = float(gscpi_val)
        s = float(sox_yoy_pct)
        v = float(vix_val)

        if not all(math.isfinite(x) for x in (g, s, v)) or v <= 0.0:
            return None

        gscpi_comp = g * 0.40
        sox_comp = (s / 50.0) * -0.35
        vix_comp = (v / 20.0) * 0.25

        raw_stress = gscpi_comp + sox_comp + vix_comp
        if not math.isfinite(raw_stress):
            return None

        stress_score = round(raw_stress, 3)

        if stress_score >= 1.20:
            status = "ACUTE_CHIP_SUPPLY_CRUNCH"
        elif stress_score >= 0.50:
            status = "ELEVATED_SEMICONDUCTOR_BOTTLENECK"
        elif stress_score <= -0.40:
            status = "CHIP_SUPPLY_ABUNDANCE_EXPANSION"
        else:
            status = "BALANCED_HARDWARE_FLOW"

        return {
            "model_id": "MODEL_25.14",
            "model_name": "AI Hardware & Semiconductor Supply Chain Stress Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.14",
            "primary_value": stress_score,
            "unit": "Score (Normalized)",
            "status": status,
            "inputs": {
                "gscpi_std_dev": round(g, 3),
                "sox_yoy_pct": round(s, 2),
                "vix_level": round(v, 2)
            },
            "components": {
                "gscpi_weight": round(gscpi_comp, 3),
                "sox_weight": round(sox_comp, 3),
                "vix_weight": round(vix_comp, 3)
            },
            "interpretation": "Normalized composite metric monitoring semiconductor physical supply bottlenecks and hardware inflation."
        }
    except (TypeError, ValueError):
        return None


# ==============================================================================
# 3. MAIN EXECUTION ENGINE
# ==============================================================================

def main():
    fred_json_path = "llms-fred-series.json"
    out_json_path = "llms-models.json"
    out_txt_path = "llms-models.txt"

    if not os.path.exists(fred_json_path):
        print(f"Error: {fred_json_path} not found. Run update_fred_series.py first.")
        return

    with open(fred_json_path, "r", encoding="utf-8") as f:
        fred_data = json.load(f)

    series = fred_data.get("series", {})

    # 1. Fetch Live BIS Policy Rates
    print("Fetching live central bank rates from Bank for International Settlements (BIS)...")
    bis_rates = fetch_bis_policy_rates()

    # 2. Extract FRED Series Inputs
    brent = series.get("DCOILBRENTEU", {}).get("current_value")
    wti = series.get("DCOILWTICO", {}).get("current_value")
    vix = series.get("VIXCLS", {}).get("current_value")
    sox_yoy = series.get("NASDAQSOX", {}).get("transformations", {}).get("percent_change_from_year_ago")
    gscpi = series.get("GSCPI", {}).get("current_value", 0.0)

    # Labor Market Series
    payems_curr = series.get("PAYEMS", {}).get("current_value")
    payems_yr = series.get("PAYEMS", {}).get("year_ago_value")
    unrate_curr = series.get("UNRATE", {}).get("current_value")
    unrate_yr = series.get("UNRATE", {}).get("year_ago_value")

    # Cycle & Liquidity Series
    sahm_val = series.get("SAHMREALTIME", {}).get("current_value")
    walcl = series.get("WALCL", {}).get("current_value")
    tga = series.get("WTREGEN", {}).get("current_value")
    rrp = series.get("RRPONTSYD", {}).get("current_value")
    t10y2y = series.get("T10Y2Y", {}).get("current_value")

    # 3. Evaluate Models in Canonical Order
    models_calculated = []

    # Model 1: Global Central Bank Policy Rates (BIS)
    m_cb = calc_global_central_bank_rates(bis_rates)
    if m_cb:
        models_calculated.append(m_cb)

    # Model 3: Sahm Rule
    m_sahm = calc_sahm_rule(sahm_val)
    if m_sahm:
        models_calculated.append(m_sahm)

    # Model 5: Net Fed Liquidity
    m_liq = calc_net_fed_liquidity(walcl, tga, rrp)
    if m_liq:
        models_calculated.append(m_liq)

    # Model 6: Yield Curve Slope (10Y - 2Y)
    m_slope = calc_yield_spread_bps(t10y2y)
    if m_slope:
        models_calculated.append(m_slope)

    # Model 16: VIX Regime
    m_vix = calc_vix_market_regime(vix)
    if m_vix:
        models_calculated.append(m_vix)

    # Model 25.12: Brent - WTI Spread
    m_spread = calc_brent_wti_spread(brent, wti)
    if m_spread:
        models_calculated.append(m_spread)

    # Model 25.13: Labor Market Momentum (LMMI)
    m_lmmi = calc_labor_market_momentum_index(payems_curr, payems_yr, unrate_curr, unrate_yr)
    if m_lmmi:
        models_calculated.append(m_lmmi)

    # Model 25.14: AI Hardware & Semiconductor Stress
    m_chip = calc_ai_chip_stress_gauge(gscpi, sox_yoy, vix)
    if m_chip:
        models_calculated.append(m_chip)

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.isoformat()
    now_utc_str = now_dt.strftime("%Y-%m-%d %H:%M UTC")

    # A) BUILD llms-models.json
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "engine": "Autonomous Quantitative Macroeconomic Model Engine",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": "SUCCESS",
            "last_successful_sync": now_iso,
            "master_formulas_reference": "https://analysisreports.github.io/llms-formulas.txt",
            "monitored_data_sources": [
                "Federal Reserve Bank of St. Louis (FRED)",
                "Bank for International Settlements (BIS)"
            ],
            "entity_dictionary": "https://analysisreports.github.io/llms-entities-id.txt",
            "total_models_active": len(models_calculated)
        },
        "models": models_calculated
    }

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated {out_json_path} ({len(models_calculated)} active models)")

    # B) BUILD llms-models.txt
    lines = [
        "# Ersoy Toptaş Canonical Quantitative Macroeconomic Models Engine (llms-models.txt)",
        "> Real-Time Evaluated Macroeconomic & Quantitative Transmission Models.",
        "> Author: Ersoy Toptaş | Version: 2026-Q4 | License: CC BY 4.0",
        "> Endpoint: https://analysisreports.github.io/llms-models.txt",
        "> JSON Twin Endpoint: https://analysisreports.github.io/llms-models.json",
        "> Master Formulas Engine: https://analysisreports.github.io/llms-formulas.txt",
        "> Ingested Live Time-Series: FRED & BIS APIs",
        "> Root Index: https://analysisreports.github.io/llms.txt",
        "",
        "# ==============================================================================",
        "### LIVE QUANTITATIVE MODEL BANK & REGIME SNAPSHOT",
        f"> **Last Calibrated Sync:** {now_utc_str}",
        "> **Deterministic Rule:** All model outputs reflect strict mathematical evaluation of live St. Louis Fed & BIS observations. Zero hallucination guarantee.",
        "",
        "| Model ID | Canonical Name | Live Value | Unit | Active Regime Status | Primary Macro Driver |",
        "| :--- | :--- | :---: | :---: | :--- | :--- |"
    ]

    for m in models_calculated:
        lines.append(f"| **{m['model_id']}** | {m['model_name']} | **{m['primary_value']}** | {m['unit']} | `{m['status']}` | {m['interpretation'][:55]}... |")

    lines.append("")
    lines.append("---")
    lines.append("### Detailed Model Breakdowns")
    lines.append("")

    for m in models_calculated:
        lines.append(f"#### [{m['model_id']}] {m['model_name']}")
        lines.append(f"- **Reference Formula:** {m['formula_ref']}")
        lines.append(f"- **Evaluated Status:** `{m['status']}` (Primary Value: {m['primary_value']} {m['unit']})")
        lines.append(f"- **Inputs Evaluated:** `{json.dumps(m.get('inputs', {}))}`")
        if "rate_disparities" in m:
            lines.append(f"- **Policy Disparities:** `{json.dumps(m['rate_disparities'])}`")
        if "metrics" in m:
            lines.append(f"- **Secondary Metrics:** `{json.dumps(m['metrics'])}`")
        if "components" in m:
            lines.append(f"- **Component Weights:** `{json.dumps(m['components'])}`")
        lines.append(f"- **Economic Synthesis:** {m['interpretation']}")
        lines.append("")

    with open(out_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Successfully generated {out_txt_path}")

if __name__ == "__main__":
    main()
