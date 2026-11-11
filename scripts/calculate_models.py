#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calculate_models.py
-------------------
Autonomous Quantitative Macroeconomic Model Engine.
Calculates canonical macroeconomic models defined in llms-formulas.txt directly from:
  1. Live St. Louis Fed (FRED) time-series ingested by llms-fred-series.json
  2. Live European Central Bank (ECB) time-series ingested by llms-ecb-series.json
  3. Live World Bank (Pink Sheet) commodity prices ingested by llms-worldbank-series.json
  4. Live International Monetary Fund (IMF IFS) time-series ingested by llms-imf-series.json
Generates:
  - llms-models.json (Deterministic Machine-Readable Twin)
  - llms-models.txt (Human-Readable Markdown Table Twin)

Author: Ersoy Toptaş & Google Gemini AI Engine
License: CC BY 4.0
Endpoint txt: https://analysisreports.github.io/llms-models.txt
Endpoint json: https://analysisreports.github.io/llms-models.json
"""

import os
import json
import math
import datetime
from typing import Dict, Any, Optional

# ==============================================================================
# 1. MODEL 1: FED POLICY STANCE & MARKET PRESSURE GAUGE
# ==============================================================================

def calc_fed_policy_stance(dgs1mo_val, fed_rate_val):
    if any(v is None or isinstance(v, bool) for v in (dgs1mo_val, fed_rate_val)):
        return None
    try:
        dgs1mo = float(dgs1mo_val)
        fed_rate = float(fed_rate_val)
        if not (math.isfinite(dgs1mo) and math.isfinite(fed_rate)):
            return None
        if dgs1mo < 0.0 or fed_rate < 0.0:
            return None

        raw_spread = (dgs1mo - fed_rate) * 100.0
        if not math.isfinite(raw_spread):
            return None
        spread = round(raw_spread, 2)

        if spread > 4.0:
            status = "HAWKISH_MARKET_PRESSURE"
        elif spread <= -15.0:
            status = "AGGRESSIVE_EASING_PRESSURE"
        elif spread < -4.0:
            status = "MODERATE_EASING_BIAS"
        else:
            status = "BALANCED_POLICY_EQUILIBRIUM"

        return {
            "model_id": "MODEL_1",
            "model_name": "Fed Policy Stance & Market Pressure Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#1",
            "primary_value": spread,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {
                "treasury_1m_yield_dgs1mo": round(dgs1mo, 2),
                "fed_policy_rate": round(fed_rate, 2)
            },
            "metrics": {
                "spread_basis_points": spread,
                "dgs1mo_yield": round(dgs1mo, 2),
                "fed_funds_rate": round(fed_rate, 2)
            },
            "interpretation": "Spread between 1-Month Treasury yield and Fed Funds Rate. Measures market-implied rate cut pressure (<= -15 bps) or liquidity-driven hawkish stress (> +4 bps)."
        }
    except (TypeError, ValueError):
        return None

# ==============================================================================
# 2. MODEL IMPLEMENTATIONS (STRICTLY FROM llms-formulas.txt)
# ==============================================================================

# --- Model 2: Reel Politika Faizi (Real Policy Rate & Restrictiveness) ---
def calc_real_policy_rate(dff_val, cpi_yoy_val):
    if any(v is None or isinstance(v, bool) for v in (dff_val, cpi_yoy_val)):
        return None
    try:
        dff = float(dff_val)
        cpi_yoy = float(cpi_yoy_val)
        if not (math.isfinite(dff) and math.isfinite(cpi_yoy)):
            return None
        if dff < 0.0:
            return None

        raw_rate = dff - cpi_yoy
        if not math.isfinite(raw_rate):
            return None
        rate = round(raw_rate, 2)

        if rate > 1.50:
            status = "RESTRICTIVE"
        elif rate < 0.0:
            status = "ACCOMMODATIVE"
        else:
            status = "NEUTRAL"

        return {
            "model_id": "MODEL_2",
            "model_name": "Real Policy Rate & Restrictiveness",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#2",
            "primary_value": rate,
            "unit": "Percent (%)",
            "status": status,
            "inputs": {
                "fed_policy_rate_dff": round(dff, 2),
                "headline_cpi_yoy_pct": round(cpi_yoy, 2)
            },
            "metrics": {
                "real_interest_rate_pct": rate,
                "dff_nominal_rate": round(dff, 2),
                "inflation_cpi_yoy": round(cpi_yoy, 2)
            },
            "interpretation": "Measures the real stance of effective borrowing costs adjusted for headline inflation. Values > 1.5% reflect restrictive policy, < 0.0% accommodative."
        }
    except (TypeError, ValueError, OverflowError):
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
            "metrics": {
                "sahm_indicator": diff
            },
            "interpretation": "Real-time recession detection triggered when 3-month unemployment average rises >= 0.50 ppt above prior 12-month low."
        }
    except (TypeError, ValueError):
        return None


# --- Model 4: Ön Uç Hazine Bonosu Eğimi ve Likidite Makası (Front-End T-Bill Slope) ---
def calc_front_end_t_bill_slope(dgs3mo_val, dgs1mo_val):
    if any(v is None or isinstance(v, bool) for v in (dgs3mo_val, dgs1mo_val)):
        return None
    try:
        dgs3mo = float(dgs3mo_val)
        dgs1mo = float(dgs1mo_val)
        if not (math.isfinite(dgs3mo) and math.isfinite(dgs1mo)):
            return None
        if dgs3mo < 0.0 or dgs1mo < 0.0:
            return None

        raw_spread = (dgs3mo - dgs1mo) * 100.0
        if not math.isfinite(raw_spread):
            return None
        spread = round(raw_spread, 2)

        if spread < 0.0:
            status = "INVERTED_FRONT_END"
        else:
            status = "NORMAL_SLOPE"

        return {
            "model_id": "MODEL_4",
            "model_name": "Front-End T-Bill Slope & Liquidity Spread",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#4",
            "primary_value": spread,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {
                "treasury_3m_yield_dgs3mo": round(dgs3mo, 2),
                "treasury_1m_yield_dgs1mo": round(dgs1mo, 2)
            },
            "metrics": {
                "spread_basis_points": spread,
                "dgs3mo_yield": round(dgs3mo, 2),
                "dgs1mo_yield": round(dgs1mo, 2)
            },
            "interpretation": "Tracks the slope between 3-month and 1-month Treasury bills. Negative values indicate acute front-end cash collateral squeeze and inverted money market slope."
        }
    except (TypeError, ValueError, OverflowError):
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
            "metrics": {
                "yield_spread_bps": bps,
                "t10y2y_spread_pct": spread
            },
            "interpretation": "Leading cyclical economic barometer. Inversions (bps < 0) historically precede sovereign US business cycle recessions."
        }
    except (TypeError, ValueError):
        return None


# --- Model 7: 10-Year Breakeven Inflation Rate ---
def calc_breakeven_inflation(dgs10_val, dfii10_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dgs10_val, dfii10_val)):
        return None
    try:
        nom = float(dgs10_val)
        tips = float(dfii10_val)
        if not (math.isfinite(nom) and math.isfinite(tips)):
            return None
        if nom <= 0.0:
            return None

        raw_rate = nom - tips
        if not math.isfinite(raw_rate):
            return None
        rate = round(raw_rate, 2)

        if rate > 2.50:
            status = "DE_ANCHORING_RISK"
        elif rate < 2.00:
            status = "DEFLATION_RISK"
        else:
            status = "FED_ALIGNED_EQUILIBRIUM"

        return {
            "model_id": "MODEL_7",
            "model_name": "10-Year Breakeven Inflation Rate",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#7",
            "primary_value": rate,
            "unit": "Percent (%)",
            "status": status,
            "inputs": {
                "nominal_10y_yield_dgs10": round(nom, 2),
                "tips_10y_real_yield_dfii10": round(tips, 2)
            },
            "metrics": {
                "breakeven_inflation_rate_pct": rate,
                "dgs10_nominal": round(nom, 2),
                "dfii10_tips_real": round(tips, 2)
            },
            "interpretation": "Reflects the bond market's expected average annual inflation rate over the next 10 years by subtracting 10-year TIPS real yields from 10-year nominal Treasury yields."
        }
    except (TypeError, ValueError):
        return None


# --- Model 8: Beveridge Curve Labor Tightness ---
def calc_beveridge_labor_tightness(jtsjol_val, unemploy_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (jtsjol_val, unemploy_val)):
        return None
    try:
        j = float(jtsjol_val)
        u = float(unemploy_val)
        if not (math.isfinite(j) and math.isfinite(u)):
            return None
        if j <= 0.0 or u <= 0.0:
            return None

        raw_ratio = j / u
        if not math.isfinite(raw_ratio):
            return None
        ratio = round(raw_ratio, 2)

        if ratio > 1.50:
            status = "OVERHEATED_LABOR"
        elif ratio < 1.00:
            status = "COOLING_LABOR"
        else:
            status = "BALANCED_LABOR_TIGHTNESS"

        return {
            "model_id": "MODEL_8",
            "model_name": "Beveridge Curve Labor Tightness",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#8",
            "primary_value": ratio,
            "unit": "Ratio",
            "status": status,
            "inputs": {
                "job_openings_jtsjol_k": round(j, 2),
                "unemployed_persons_unemploy_k": round(u, 2)
            },
            "metrics": {
                "beveridge_ratio": ratio,
                "job_openings_k": round(j, 2),
                "unemployed_k": round(u, 2)
            },
            "interpretation": "Evaluates the ratio of job openings to unemployed job seekers. Ratios > 1.50 signal overheated wage pressure, < 1.00 signal loosening labor demand."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 9: Financial Repression Index ---
def calc_financial_repression_index(dgs10_val, cpi_yoy_val, debt_gdp_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dgs10_val, cpi_yoy_val, debt_gdp_val)):
        return None
    try:
        nom = float(dgs10_val)
        cpi = float(cpi_yoy_val)
        debt = float(debt_gdp_val)
        if not (math.isfinite(nom) and math.isfinite(cpi) and math.isfinite(debt)):
            return None
        if nom < 0.0 or debt <= 0.0:
            return None

        real_yield = round(nom - cpi, 2)
        raw_index = real_yield * (debt / 100.0)
        if not math.isfinite(raw_index):
            return None
        index = round(raw_index, 3)

        if index < 0.0:
            status = "REPRESSION_REGIME"
        elif index > 1.50:
            status = "DEBT_CRISIS_ALARM"
        else:
            status = "SUSTAINABLE_CYCLE"

        return {
            "model_id": "MODEL_9",
            "model_name": "Financial Repression Index",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#9",
            "primary_value": index,
            "unit": "Index Score",
            "status": status,
            "inputs": {
                "nominal_10y_yield_dgs10": round(nom, 2),
                "headline_cpi_yoy_pct": round(cpi, 2),
                "federal_debt_pct_gdp": round(debt, 2)
            },
            "metrics": {
                "debt_pressure_index": index,
                "real_10y_yield_pct": real_yield,
                "federal_debt_gdp_ratio": round(debt, 2)
            },
            "interpretation": "Scores the risk of eroding public debt in real terms under negative real yields versus triggering an explosive debt service crisis under high real yields and high sovereign debt ratios."
        }
    except (TypeError, ValueError):
        return None


# --- Model 10: Triffin External Balance ---
def calc_triffin_external_balance(dtwexbgs_val, bopgstb_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dtwexbgs_val, bopgstb_val)):
        return None
    try:
        dxy = float(dtwexbgs_val)
        trade = float(bopgstb_val)
        if not (math.isfinite(dxy) and math.isfinite(trade)):
            return None
        if dxy <= 0.0 or trade == 0.0:
            return None

        if trade > 0.0:
            surplus_bil = trade / 1000.0
            tension = round(dxy / surplus_bil, 4)
            return {
                "model_id": "MODEL_10",
                "model_name": "Triffin External Balance",
                "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#10",
                "primary_value": tension,
                "unit": "Surplus Tension Ratio",
                "status": "OFFSHORE_DOLLAR_DRAIN_SURPLUS",
                "inputs": {
                    "broad_dollar_index_dtwexbgs": round(dxy, 4),
                    "trade_balance_bopgstb_mil": round(trade, 2)
                },
                "metrics": {
                    "monthly_trade_surplus_bil": round(surplus_bil, 2),
                    "broad_dollar_index": round(dxy, 4)
                },
                "interpretation": "US trade surplus drains global offshore dollar reserves, reversing Triffin deficit expansion."
            }

        deficit_bil = -trade / 1000.0
        raw_tension = dxy / deficit_bil
        if not math.isfinite(raw_tension):
            return None
        tension = round(raw_tension, 4)

        if tension > 1.25:
            status = "RESERVE_CURRENCY_STRAIN"
        elif tension < 1.00:
            status = "ABUNDANT_OFFSHORE_LIQUIDITY"
        else:
            status = "BALANCED_TRIFFIN_EQUILIBRIUM"

        return {
            "model_id": "MODEL_10",
            "model_name": "Triffin External Balance",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#10",
            "primary_value": tension,
            "unit": "Tension Ratio",
            "status": status,
            "inputs": {
                "broad_dollar_index_dtwexbgs": round(dxy, 4),
                "trade_balance_bopgstb_mil": round(trade, 2)
            },
            "metrics": {
                "dxy_deficit_tension": tension,
                "monthly_trade_deficit_bil": round(deficit_bil, 2),
                "broad_dollar_index": round(dxy, 4)
            },
            "interpretation": "Tracks global liquidity imbalances between the US dollar's reserve currency status and the US external trade deficit. Rising ratios signal offshore dollar shortage and structural funding stress."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 11: Taylor Rule Policy Gap ---
def calc_taylor_policy_gap(
    dff_val,
    cpi_yoy_val,
    gdpc1_val,
    gdppot_val,
    gdpc1_units=None,
    gdppot_units=None
) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dff_val, cpi_yoy_val, gdpc1_val, gdppot_val)):
        return None
    try:
        dff = float(dff_val)
        cpi = float(cpi_yoy_val)
        gdp = float(gdpc1_val)
        pot = float(gdppot_val)
        if not (math.isfinite(dff) and math.isfinite(cpi) and math.isfinite(gdp) and math.isfinite(pot)):
            return None
        if dff < 0.0 or gdp <= 0.0 or pot <= 1.0:
            return None

        expected_units = "billions of chained 2017 dollars"
        normalize_units = lambda value: " ".join(str(value).casefold().split())
        if (
            gdpc1_units is None
            or gdppot_units is None
            or normalize_units(gdpc1_units) != expected_units
            or normalize_units(gdppot_units) != expected_units
        ):
            return None

        output_gap_raw = ((gdp / pot) - 1.0) * 100.0
        if not math.isfinite(output_gap_raw) or abs(output_gap_raw) > 50.0:
            return None
        output_gap = round(output_gap_raw, 2)
        optimal_rate = round(2.0 + cpi + 0.5 * (cpi - 2.0) + 0.5 * output_gap, 2)
        raw_gap = dff - optimal_rate
        if not math.isfinite(raw_gap):
            return None
        gap = round(raw_gap, 2)

        if gap < -1.00:
            status = "BEHIND_THE_CURVE"
        elif gap > 1.00:
            status = "OVER_RESTRICTIVE"
        else:
            status = "OPTIMAL_ALIGNMENT"

        return {
            "model_id": "MODEL_11",
            "model_name": "Taylor Rule Policy Gap",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#11",
            "primary_value": gap,
            "unit": "Percentage Points (ppt)",
            "status": status,
            "inputs": {
                "fed_policy_rate_dff": round(dff, 2),
                "headline_cpi_yoy_pct": round(cpi, 2),
                "real_gdp_gdpc1_bil": round(gdp, 2),
                "real_potential_gdp_gdppot_bil": round(pot, 2)
            },
            "metrics": {
                "policy_gap_ppt": gap,
                "taylor_optimal_rate_pct": optimal_rate,
                "output_gap_pct": output_gap,
                "equilibrium_real_neutral_rate_pct": 2.0,
                "target_inflation_pct": 2.0
            },
            "interpretation": "Computes the Federal Reserve optimal policy rate prescribed by the standard Taylor (1993) rule and quantifies policy divergence. Gaps < -1.0 ppt reflect an accommodative central bank behind the curve; > +1.0 ppt reflect excessive restrictiveness."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 12: Financial Conditions Tightness (Chicago Fed NFCI) ---
def calc_financial_conditions_tightness(nfci_val, anfci_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (nfci_val, anfci_val)):
        return None
    try:
        n = float(nfci_val)
        a = float(anfci_val)
        if not (math.isfinite(n) and math.isfinite(a)):
            return None

        nfci = round(n, 3)
        anfci = round(a, 3)
        macro_div = round(nfci - anfci, 3)

        if nfci > 0.0:
            status = "TIGHT_FINANCIAL_CONDITIONS"
        elif nfci == 0.0:
            status = "BALANCED_FINANCIAL_CONDITIONS"
        else:
            status = "LOOSE_FINANCIAL_CONDITIONS"

        return {
            "model_id": "MODEL_12",
            "model_name": "Financial Conditions Tightness (Chicago Fed NFCI)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#12",
            "primary_value": nfci,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "chicago_fed_nfci": nfci,
                "adjusted_anfci": anfci
            },
            "metrics": {
                "nfci_stress_level": nfci,
                "adjusted_anfci": anfci,
                "macroeconomic_divergence": macro_div
            },
            "interpretation": "Monitors monetary policy transmission into financial markets across debt, equity, and leverage risk premiums. Values < 0 indicate looser than average financial conditions; > 0 indicates restrictive financial conditions."
        }
    except (TypeError, ValueError):
        return None


# --- Model 13: High Yield Credit Spread / OAS ---
def calc_high_yield_credit_stress(hy_spread_val) -> Optional[Dict[str, Any]]:
    if hy_spread_val is None or isinstance(hy_spread_val, bool):
        return None
    try:
        hy = float(hy_spread_val)
        if not math.isfinite(hy):
            return None
        # Credit spread must be strictly positive
        if hy <= 0.0:
            return None

        bps = int(round(hy * 100.0))

        if bps >= 500:
            status = "CREDIT_CRUNCH_ALARM"
        elif bps >= 350:
            status = "ELEVATED_RISK"
        else:
            status = "RISK_APPETITE_HEALTHY"

        return {
            "model_id": "MODEL_13",
            "model_name": "High Yield Credit Spread / OAS",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#13",
            "primary_value": bps,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {
                "high_yield_oas_bamlh0a0hym2": round(hy, 2)
            },
            "metrics": {
                "spread_bps": bps,
                "bamlh0a0hym2_pct": round(hy, 2)
            },
            "interpretation": "Measures corporate credit default risk and risk appetite contraction. Spreads above 500 bps signal acute default and refinancing distress; below 350 bps reflect healthy risk appetite."
        }
    except (TypeError, ValueError):
        return None


# --- Model 14: Real M2 Money Momentum ---
def calc_real_m2_momentum(m2_yoy_val, cpi_yoy_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (m2_yoy_val, cpi_yoy_val)):
        return None
    try:
        m2 = float(m2_yoy_val)
        cpi = float(cpi_yoy_val)
        if not (math.isfinite(m2) and math.isfinite(cpi)):
            return None

        diff = round(m2 - cpi, 2)
        if not math.isfinite(diff):
            return None

        if diff == 0.0:
            status = "NEUTRAL"
        elif diff < 0.0:
            status = "LIQUIDITY_CONTRACTION"
        else:
            status = "MONETARY_EXPANSION"

        return {
            "model_id": "MODEL_14",
            "model_name": "Real M2 Money Momentum",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#14",
            "primary_value": diff,
            "unit": "Percentage Points (ppt)",
            "status": status,
            "inputs": {
                "m2_money_growth_yoy_pct": round(m2, 2),
                "headline_cpi_yoy_pct": round(cpi, 2)
            },
            "metrics": {
                "real_m2_growth_ppt": diff,
                "m2_yoy_pct": round(m2, 2),
                "cpi_yoy_pct": round(cpi, 2)
            },
            "interpretation": "Detects aggregate demand and monetary impulse by calculating the real expansion or contraction rate of broad money supply (M2) relative to headline CPI inflation. Values < 0 indicate monetary contraction; > 0 indicate broad liquidity expansion."
        }
    except (TypeError, ValueError):
        return None


# --- Model 15: NY Fed ACM 10-Year Term Premium ---
def calc_acm_term_premium(dgs10_val, threefytp10_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dgs10_val, threefytp10_val)):
        return None
    try:
        nom = float(dgs10_val)
        tp = float(threefytp10_val)
        if not (math.isfinite(nom) and math.isfinite(tp)):
            return None
        # Nominal 10Y yield sanity bounds [0.0%, 25.0%]
        if nom < 0.0 or nom > 25.0:
            return None
        # Term premium quality & unit guard: reject bps vs pct confusion (must be within [-5.0%, +5.0%])
        if tp < -5.0 or tp > 5.0:
            return None

        # Harmonize with llms-formulas.txt threshold rules: >= 0.50 and <= -0.50
        if tp >= 0.50:
            status = "FISCAL_SUPPLY_PRESSURE"
        elif tp <= -0.50:
            status = "FLIGHT_TO_SAFETY"
        else:
            status = "BALANCED_PREMIUM"

        term_prem = round(tp, 2)
        exp_rate = round(nom - term_prem, 2)
        if not math.isfinite(exp_rate):
            return None

        return {
            "model_id": "MODEL_15",
            "model_name": "NY Fed ACM 10-Year Term Premium",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#15",
            "primary_value": term_prem,
            "unit": "Percent (%)",
            "status": status,
            "inputs": {
                "nominal_10y_yield_dgs10": round(nom, 2),
                "acm_10y_term_premium_threefytp10": term_prem
            },
            "metrics": {
                "term_premium_pct": term_prem,
                "expected_average_short_rate_pct": exp_rate,
                "nominal_10y_yield_pct": round(nom, 2)
            },
            "interpretation": "Decomposes 10-year Treasury yields via the Adrian, Crump & Moench (ACM) model. Term premium >= +0.50% reflects duration risk, fiscal supply pressure, or inflation uncertainty; <= -0.50% reflects safe-haven duration demand or central bank asset purchases."
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
            "metrics": {
                "vix_level": val,
                "regime": regime,
                "market_bias": bias
            },
            "interpretation": "30-day forward S&P 500 implied volatility fear gauge and systemic liquidity stress regime."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.12: Brent - WTI Seaborne Spread Engine ---
def calc_brent_wti_spread(
    brent_price,
    wti_price,
    commercial_crude_stocks_kbbl=None,
    us_crude_prod_kbpd=None
):
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

        inputs_dict: Dict[str, Any] = {"brent_usd": f_brent, "wti_usd": f_wti}
        metrics_dict: Dict[str, Any] = {
            "brent_wti_spread_usd": spread,
            "brent_usd": f_brent,
            "wti_usd": f_wti
        }

        interp = "Seaborne geopolitical friction and maritime risk spread between North Sea Brent and Cushing WTI."

        if commercial_crude_stocks_kbbl is not None and not isinstance(commercial_crude_stocks_kbbl, bool):
            try:
                f_comm = float(commercial_crude_stocks_kbbl)
                if math.isfinite(f_comm):
                    comm_mbbl = round(f_comm / 1000.0, 2)
                    inputs_dict["commercial_crude_stocks_mbbl"] = comm_mbbl
                    metrics_dict["commercial_crude_stocks_mbbl"] = comm_mbbl
                    interp += f" Live EIA commercial crude stocks: {comm_mbbl} mbbl."
            except (ValueError, TypeError):
                pass

        if us_crude_prod_kbpd is not None and not isinstance(us_crude_prod_kbpd, bool):
            try:
                f_prod = float(us_crude_prod_kbpd)
                if math.isfinite(f_prod):
                    prod_mbpd = round(f_prod / 1000.0, 2)
                    inputs_dict["us_crude_production_mbpd"] = prod_mbpd
                    metrics_dict["us_crude_production_mbpd"] = prod_mbpd
                    interp += f" Live EIA US crude field production: {prod_mbpd} mbpd."
            except (ValueError, TypeError):
                pass

        return {
            "model_id": "MODEL_25.12",
            "model_name": "Brent - WTI Seaborne Risk Spread",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.12",
            "primary_value": spread,
            "unit": "USD",
            "status": status,
            "inputs": inputs_dict,
            "metrics": metrics_dict,
            "interpretation": interp
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


# --- Model 25.2: Sticky vs. Flexible CPI Spread ---
def calc_sticky_flexible_cpi_spread(sticky_val, flex_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (sticky_val, flex_val)):
        return None
    try:
        f_sticky = float(sticky_val)
        f_flex = float(flex_val)
        if not (math.isfinite(f_sticky) and math.isfinite(f_flex)):
            return None

        raw_impulse = f_sticky - f_flex
        if not math.isfinite(raw_impulse):
            return None
        impulse = round(raw_impulse, 2)

        if impulse > 2.0:
            status = "STRUCTURAL_INFLATION_TRAP"
        elif impulse < -2.0:
            status = "TRANSITORY_INFLATION_SURGE"
        else:
            status = "BALANCED_DISINFLATION_PATH"

        return {
            "model_id": "MODEL_25.2",
            "model_name": "Sticky vs. Flexible CPI Spread",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.2",
            "primary_value": impulse,
            "unit": "Percentage Points (ppt)",
            "status": status,
            "inputs": {
                "sticky_cpi_val": round(f_sticky, 2),
                "flexible_cpi_val": round(f_flex, 2)
            },
            "metrics": {
                "sticky_impulse_ppt": impulse,
                "sticky_cpi_rate": round(f_sticky, 2),
                "flexible_cpi_rate": round(f_flex, 2)
            },
            "interpretation": "Evaluates core inflation persistence versus transient price shocks by measuring the spread between sticky CPI (services, shelter) and flexible CPI (fuel, food). Spreads > 2.0 ppt reflect structural service-shelter inflation entrapment."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.3: NY Fed GSCPI Logistics Engine ---
def calc_supply_chain_pressure(gscpi_val):
    if gscpi_val is None or isinstance(gscpi_val, bool):
        return None
    try:
        f_gscpi = float(gscpi_val)
        if not math.isfinite(f_gscpi):
            return None
        z_score = round(f_gscpi, 2)
        if z_score > 1.5:
            status = "SUPPLY_CHAIN_SHOCK"
        elif z_score < -1.0:
            status = "LOGISTICS_DEFLATION_SLACK"
        else:
            status = "NORMALIZED_GLOBAL_TRADE"
        return {
            "model_id": "MODEL_25.3",
            "model_name": "Global Supply Chain Pressure Logistics Engine (NY Fed GSCPI)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.3",
            "primary_value": z_score,
            "unit": "Standard Deviations (Z-Score)",
            "status": status,
            "inputs": {
                "gscpi_zscore": z_score
            },
            "metrics": {
                "gscpi_zscore": z_score
            },
            "interpretation": "Tracks standard deviations of global freight rates, shipping costs, and delivery times from historical mean. Values > 1.5 indicate supply chain shocks."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.5: Repo Liquidity Friction Spread Engine (SOFR - EFFR) ---
def calc_repo_liquidity_friction_spread(sofr_val, effr_val):
    if any(v is None or isinstance(v, bool) for v in (sofr_val, effr_val)):
        return None
    try:
        f_sofr = float(sofr_val)
        f_effr = float(effr_val)
        if not (math.isfinite(f_sofr) and math.isfinite(f_effr)):
            return None
        if f_sofr < 0.0 or f_effr < 0.0:
            return None
        raw_spread = (f_sofr - f_effr) * 100.0
        if not math.isfinite(raw_spread):
            return None
        spread = round(raw_spread, 2)
        if spread > 10.0:
            status = "REPO_MARKET_LIQUIDITY_CRUNCH"
        elif spread >= 5.0:
            status = "SYSTEMIC_CASH_DRAIN_WARNING"
        elif spread < -5.0:
            status = "COLLATERAL_SCARCITY_GLUT"
        else:
            status = "HEALTHY_MONETARY_TRANSMISSION"

        return {
            "model_id": "MODEL_25.5",
            "model_name": "Repo Liquidity Friction Spread Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.5",
            "primary_value": spread,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {
                "sofr_rate": f_sofr,
                "effr_rate": f_effr
            },
            "metrics": {
                "spread_bps": spread
            },
            "interpretation": "Measures funding market friction tracking the spread between secured repo financing (SOFR) and unsecured Fed funds (EFFR). Spreads between -5.0 and +5.0 bps indicate healthy monetary transmission."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.6: Gold / Real Yield Debasement Gauge ---
def calc_gold_real_yield_debasement(real_yield_10y_val, gold_yoy_pct_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (real_yield_10y_val, gold_yoy_pct_val)):
        return None
    try:
        f_ry = float(real_yield_10y_val)
        f_gy = float(gold_yoy_pct_val)
        if not (math.isfinite(f_ry) and math.isfinite(f_gy)):
            return None

        ry_val = round(f_ry, 2)
        gy_val = round(f_gy, 2)

        if ry_val > 1.50 and gy_val > 15.0:
            status = "DEBALANCING_DEDOLLARIZATION_PANIC"
        elif ry_val <= 0.0 and gy_val > 0.0:
            status = "ACCOMMODATIVE_GOLD_BULL"
        else:
            status = "TRADITIONAL_REAL_RATE_DOMINANCE"

        return {
            "model_id": "MODEL_25.6",
            "model_name": "Gold / Real Yield Debasement Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.6",
            "primary_value": ry_val,
            "unit": "Percent (%)",
            "status": status,
            "inputs": {
                "tips_10y_real_yield_dfii10": ry_val,
                "gold_price_yoy_pct_ind_wb_gold": gy_val
            },
            "metrics": {
                "real_yield_10y_pct": ry_val,
                "gold_yoy_pct": gy_val
            },
            "interpretation": "Detects de-dollarization trends and fiat debasement by measuring breakdowns in the traditional inverse correlation between 10-year TIPS real yields and gold prices. Gold rallying above 15% alongside real yields > 1.5% signals systemic de-dollarization."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.7: OVX / VIX Geopolitical Energy Shock Engine ---
def calc_ovx_vix_risk_premium(ovx_val, vix_val):
    if any(v is None or isinstance(v, bool) for v in (ovx_val, vix_val)):
        return None
    try:
        f_ovx = float(ovx_val)
        f_vix = float(vix_val)
        if not (math.isfinite(f_ovx) and math.isfinite(f_vix)) or f_vix <= 0.0 or f_ovx < 0.0:
            return None
        raw_ratio = f_ovx / f_vix
        if not math.isfinite(raw_ratio):
            return None
        ratio = round(raw_ratio, 2)
        if ratio > 2.2:
            status = "ENERGY_SUPPLY_SHOCK_ALARM"
        elif ratio < 1.0:
            status = "EQUITY_PANIC_OVER_ENERGY"
        else:
            status = "BALANCED_ENERGY_VOLATILITY"

        return {
            "model_id": "MODEL_25.7",
            "model_name": "OVX / VIX Geopolitical Energy Shock Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.7",
            "primary_value": ratio,
            "unit": "Ratio",
            "status": status,
            "inputs": {
                "ovx_close": f_ovx,
                "vix_close": f_vix
            },
            "metrics": {
                "ovx_vix_ratio": ratio
            },
            "interpretation": "Evaluates the ratio between crude oil volatility (OVX) and equity volatility (VIX). Ratios > 2.2 signal severe geopolitical oil supply shocks and stagflationary headwinds."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 25.8: Natgas / Crude Oil BTU Disconnect Engine ---
def calc_natgas_crude_btu_disconnect(
    wti_price_val,
    natgas_price_val,
    natgas_storage_bcf_val=None,
    natgas_storage_yoy_val=None
) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (wti_price_val, natgas_price_val)):
        return None
    try:
        f_wti = float(wti_price_val)
        f_gas = float(natgas_price_val)
        if not (math.isfinite(f_wti) and math.isfinite(f_gas)) or f_gas <= 0.0 or f_wti < 0.0:
            return None

        raw_ratio = f_wti / f_gas
        if not math.isfinite(raw_ratio):
            return None
        ratio = round(raw_ratio, 2)

        if ratio < 6.0:
            status = "NATGAS_CRISIS_BLACKOUT_RISK"
        elif ratio > 35.0:
            status = "NATGAS_GLUT_ENERGY_CHEAP"
        else:
            status = "ENERGY_PARITY_EQUILIBRIUM"

        inputs_dict: Dict[str, Any] = {
            "wti_crude_usd_bbl": round(f_wti, 2),
            "henry_hub_natgas_usd_mmbtu": round(f_gas, 2)
        }
        metrics_dict: Dict[str, Any] = {
            "btu_disconnect_ratio": ratio,
            "wti_price": round(f_wti, 2),
            "natgas_price": round(f_gas, 2)
        }

        interp = "Measures physical energy parity between WTI crude oil and Henry Hub natural gas."

        if natgas_storage_bcf_val is not None and not isinstance(natgas_storage_bcf_val, bool):
            try:
                f_storage = float(natgas_storage_bcf_val)
                if math.isfinite(f_storage):
                    inputs_dict["lower48_natgas_storage_bcf"] = round(f_storage, 1)
                    metrics_dict["lower48_natgas_storage_bcf"] = round(f_storage, 1)
                    if natgas_storage_yoy_val is not None and not isinstance(natgas_storage_yoy_val, bool):
                        f_syoy = float(natgas_storage_yoy_val)
                        if math.isfinite(f_syoy):
                            inputs_dict["natgas_storage_yoy_pct"] = round(f_syoy, 2)
                            metrics_dict["natgas_storage_yoy_pct"] = round(f_syoy, 2)
                    interp += f" Live EIA underground gas storage: {round(f_storage, 1)} Bcf."
            except (ValueError, TypeError):
                pass

        interp += " Ratios > 35 indicate natural gas supply glut and cheap domestic fuel; < 6 signal acute gas deficit and power shock."

        return {
            "model_id": "MODEL_25.8",
            "model_name": "Natgas / Crude Oil BTU Disconnect Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.8",
            "primary_value": ratio,
            "unit": "WTI/NatGas Ratio",
            "status": status,
            "inputs": inputs_dict,
            "metrics": metrics_dict,
            "interpretation": interp
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 25.9: Gasoline / Crude Crack Spread Impulse Engine ---
def calc_gasoline_crude_crack_spread(
    gas_gal_price_val,
    wti_barrel_price_val,
    gasoline_stocks_kbbl_val=None,
    gasoline_stocks_yoy_val=None
) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (gas_gal_price_val, wti_barrel_price_val)):
        return None
    try:
        f_gas = float(gas_gal_price_val)
        f_wti = float(wti_barrel_price_val)
        if not (math.isfinite(f_gas) and math.isfinite(f_wti)) or f_wti <= 0.0 or f_gas <= 0.0:
            return None

        gas_barrel_equiv = f_gas * 42.0
        raw_spread = gas_barrel_equiv - f_wti
        if not math.isfinite(raw_spread):
            return None
        spread = round(raw_spread, 2)

        if spread > 40.0:
            status = "REFINERY_BOTTLENECK_CRUNCH"
        elif spread < 5.0:
            status = "REFINING_MARGIN_COLLAPSE"
        else:
            status = "NORMAL_REFINING_MARGIN"

        inputs_dict: Dict[str, Any] = {
            "gasoline_retail_usd_gal": round(f_gas, 3),
            "wti_crude_usd_bbl": round(f_wti, 2)
        }
        metrics_dict: Dict[str, Any] = {
            "crack_spread_usd": spread,
            "gasoline_barrel_equiv_usd": round(gas_barrel_equiv, 2),
            "wti_crude_usd": round(f_wti, 2)
        }

        interp = "Measures refinery processing margins between retail gasoline and crude oil."

        if gasoline_stocks_kbbl_val is not None and not isinstance(gasoline_stocks_kbbl_val, bool):
            try:
                f_stocks = float(gasoline_stocks_kbbl_val)
                if math.isfinite(f_stocks) and f_stocks > 0:
                    # Standard EIA US motor gasoline supplied consumption baseline: 9,000 kbpd (~8.9-9.0 mbpd)
                    days_of_supply = round(f_stocks / 9000.0, 1)
                    inputs_dict["gasoline_stocks_kbbl"] = round(f_stocks, 0)
                    metrics_dict["gasoline_stocks_kbbl"] = round(f_stocks, 0)
                    metrics_dict["gasoline_days_of_supply"] = days_of_supply

                    if days_of_supply < 22.0:
                        inv_status = "CRITICAL_INVENTORY_DEPLETION"
                    elif days_of_supply > 26.0:
                        inv_status = "INVENTORY_GLUT"
                    else:
                        inv_status = "BALANCED_INVENTORY_COVER"
                    metrics_dict["inventory_cover_status"] = inv_status

                    if gasoline_stocks_yoy_val is not None and not isinstance(gasoline_stocks_yoy_val, bool):
                        f_yoy = float(gasoline_stocks_yoy_val)
                        if math.isfinite(f_yoy):
                            inputs_dict["gasoline_stocks_yoy_pct"] = round(f_yoy, 2)
                            metrics_dict["gasoline_stocks_yoy_pct"] = round(f_yoy, 2)

                    interp += f" Live EIA gasoline inventories ({int(f_stocks):,} kbbl) provide {days_of_supply} days of supply ({inv_status})."
            except (ValueError, TypeError):
                pass

        interp += " Spreads > $40/bbl signal refinery capacity bottlenecks and consumer fuel cost shocks; < $5 indicate refining margin collapse."

        return {
            "model_id": "MODEL_25.9",
            "model_name": "Gasoline / Crude Crack Spread Impulse Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.9",
            "primary_value": spread,
            "unit": "USD per Barrel",
            "status": status,
            "inputs": inputs_dict,
            "metrics": metrics_dict,
            "interpretation": interp
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 25.10: SLOOS Lending Standards Recession Gauge ---
def calc_sloos_lending_tightness_gauge(drtscis_val) -> Optional[Dict[str, Any]]:
    if drtscis_val is None or isinstance(drtscis_val, bool):
        return None
    try:
        val = float(drtscis_val)
        if not math.isfinite(val):
            return None
        tightness = round(val, 2)

        if tightness > 40.0:
            status = "ACUTE_CREDIT_CRUNCH_RECESSION_SIGNAL"
        elif tightness >= 20.0:
            status = "RESTRICTIVE_CREDIT_CONTRACTION"
        elif tightness <= -10.0:
            status = "AGGRESSIVE_CREDIT_EXPANSION"
        else:
            status = "NEUTRAL_CREDIT_CONDITIONS"

        return {
            "model_id": "MODEL_25.10",
            "model_name": "SLOOS Lending Standards Recession Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.10",
            "primary_value": tightness,
            "unit": "Net Percent (%)",
            "status": status,
            "inputs": {
                "drtscis_net_pct": tightness
            },
            "metrics": {
                "credit_tightening_net_pct": tightness
            },
            "interpretation": "Tracks the net percentage of domestic US banks tightening lending standards on commercial and industrial (C&I) loans. Values > 40% signal an acute credit channel freeze and recession."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.11: Full-Time vs. Involuntary Part-Time Crack Gauge ---
def calc_hidden_employment_crack_gauge(part_time_econ_level_current, part_time_econ_level_yr_ago, full_time_level_current, full_time_level_yr_ago) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (part_time_econ_level_current, part_time_econ_level_yr_ago, full_time_level_current, full_time_level_yr_ago)):
        return None
    try:
        pt_curr = float(part_time_econ_level_current)
        pt_yr = float(part_time_econ_level_yr_ago)
        ft_curr = float(full_time_level_current)
        ft_yr = float(full_time_level_yr_ago)

        if not all(math.isfinite(x) for x in (pt_curr, pt_yr, ft_curr, ft_yr)):
            return None
        if pt_yr <= 0 or ft_yr <= 0 or pt_curr < 0 or ft_curr < 0:
            return None

        pt_yoy = ((pt_curr / pt_yr) - 1.0) * 100.0
        ft_yoy = ((ft_curr / ft_yr) - 1.0) * 100.0
        raw_spread = pt_yoy - ft_yoy

        if not math.isfinite(raw_spread):
            return None

        spread = round(raw_spread, 2)
        pt_yoy_rounded = round(pt_yoy, 2)
        ft_yoy_rounded = round(ft_yoy, 2)

        if spread > 30.0 and pt_yoy_rounded > 15.0:
            status = "ACUTE_LABOR_MARKET_FRACTURE_RECESSION"
        elif spread > 18.0:
            status = "STRUCTURAL_EMPLOYMENT_WEAKENING_SIGNAL"
        elif spread < -10.0:
            status = "ROBUST_FULL_TIME_EXPANSION"
        else:
            status = "STABLE_EMPLOYMENT_COMPOSITION"

        return {
            "model_id": "MODEL_25.11",
            "model_name": "Full-Time vs. Involuntary Part-Time Crack Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.11",
            "primary_value": spread,
            "unit": "Percentage Points (ppt)",
            "status": status,
            "inputs": {
                "involuntary_part_time_lns12032194_k": round(pt_curr, 1),
                "full_time_employed_lns12500000_k": round(ft_curr, 1)
            },
            "metrics": {
                "crack_spread_pct": spread,
                "part_time_econ_yoy_pct": pt_yoy_rounded,
                "full_time_yoy_pct": ft_yoy_rounded
            },
            "interpretation": "Detects hidden labor market fragility by comparing the annual surge in involuntary part-time workers against changes in full-time employment. Spreads > 18.0 ppt signal structural weakening obscured by headline data."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.17: Liquidity & Commodity Macro Regime Matrix ---
def calc_liquidity_commodity_matrix(dgs3mo, dgs1mo, brent_yoy_pct):
    if any(v is None or isinstance(v, bool) for v in (dgs3mo, dgs1mo, brent_yoy_pct)):
        return None
    try:
        f_3m = float(dgs3mo)
        f_1m = float(dgs1mo)
        f_brent_yoy = float(brent_yoy_pct)
        if not (math.isfinite(f_3m) and math.isfinite(f_1m) and math.isfinite(f_brent_yoy)):
            return None
        if f_3m < 0.0 or f_1m < 0.0:
            return None

        slope_bps = round((f_3m - f_1m) * 100.0, 2)
        brent_yoy = round(f_brent_yoy, 2)

        # 2x2 Macro Regime Decision Matrix
        if brent_yoy > 15.0:
            if slope_bps < 0.0:
                if slope_bps <= -25.0:
                    status = "ACUTE_STAGFLATION_CRUNCH"
                else:
                    status = "STAGFLATION_SHOCK"
            else:
                status = "REFLATIONARY_EXPANSION"
        elif brent_yoy < 0.0:
            if slope_bps < 0.0:
                status = "DEFLATIONARY_RECESSION"
            else:
                status = "GOLDILOCKS_EXPANSION"
        else:
            # Moderate / Neutral Cost Zone (0.0% <= brent_yoy <= 15.0%)
            if slope_bps < 0.0:
                status = "RESTRICTIVE_SLOWDOWN"
            else:
                status = "GOLDILOCKS_EXPANSION"

        return {
            "model_id": "MODEL_25.17",
            "model_name": "Liquidity & Commodity Macro Regime Matrix",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.17",
            "primary_value": slope_bps,
            "unit": "Basis Points (bps)",
            "status": status,
            "inputs": {
                "treasury_3m_yield_dgs3mo": f_3m,
                "treasury_1m_yield_dgs1mo": f_1m,
                "brent_crude_yoy_pct": brent_yoy
            },
            "metrics": {
                "slope_bps": slope_bps,
                "brent_yoy_pct": brent_yoy
            },
            "interpretation": "Evaluates front-end money market liquidity (3M-1M T-Bill spread) against crude oil cost inflation (Brent YoY %) in a 2x2 macro matrix to identify systemic liquidity and cost shock regimes."
        }
    except (TypeError, ValueError, OverflowError):
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
            "metrics": {
                "hardware_stress_score": stress_score,
                "gscpi_weight": round(gscpi_comp, 3),
                "sox_weight": round(sox_comp, 3),
                "vix_weight": round(vix_comp, 3)
            },
            "interpretation": "Normalized composite metric monitoring semiconductor physical supply bottlenecks and hardware inflation."
        }
    except (TypeError, ValueError):
        return None



def calc_jpy_carry_crack(dff_val, boj_rate_val, jpy_fx_mom) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dff_val, boj_rate_val, jpy_fx_mom)):
        return None
    try:
        r_us = float(dff_val)
        r_jp = float(boj_rate_val)
        fx_mom = float(jpy_fx_mom)
        if not (math.isfinite(r_us) and math.isfinite(r_jp) and math.isfinite(fx_mom)):
            return None
        rate_spread = round(r_us - r_jp, 4)
        net_buffer = round(rate_spread + fx_mom, 4)
        if net_buffer <= -1.0 or (fx_mom <= -5.0 and rate_spread <= 3.0):
            status = 'UNWIND_LIQUIDATION_CRASH'
        elif net_buffer < 1.5 or fx_mom <= -3.0:
            status = 'COMPRESSION_WARNING'
        elif net_buffer >= 3.5 and fx_mom >= -1.0:
            status = 'CALM_ACCUMULATION'
        else:
            status = 'MANAGED_TIGHTENING'
        return {
            'model_id': 'MODEL_25.16',
            'model_name': 'Yen Carry Trade Dissolution and Stress Gauge',
            'formula_ref': 'https://analysisreports.github.io/llms-formulas.txt#25.16',
            'primary_value': net_buffer,
            'unit': '% (Net Carry Buffer)',
            'status': status,
            'inputs': {
                'rate_us_dff': round(r_us, 2),
                'rate_jp_boj': round(r_jp, 2),
                'jpy_30d_momentum_pct': round(fx_mom, 2)
            },
            'components': {
                'rate_spread': rate_spread,
                'net_buffer': net_buffer
            },
            'metrics': {
                'rate_spread': rate_spread,
                'net_buffer': net_buffer
            },
            'interpretation': 'Monitors cross-currency Yen Carry Trade buffer, unwinding risk, and global leverage liquidation shocks.'
        }
    except (TypeError, ValueError, OverflowError):
        return None


# --- Model 18: Okun Sefalet Endeksi (Okun Misery Index) ---
def calc_misery_index(unrate_val, cpi_yoy_val):
    if any(v is None or isinstance(v, bool) for v in (unrate_val, cpi_yoy_val)):
        return None
    try:
        u = float(unrate_val)
        c = float(cpi_yoy_val)
        if not (math.isfinite(u) and math.isfinite(c)):
            return None
        if u < 0.0:
            return None

        score = round(u + c, 2)
        if not math.isfinite(score):
            return None

        if score > 12.0:
            status = "ACUTE_CRISIS"
        elif score >= 10.0:
            status = "ELEVATED_STRESS"
        elif score >= 6.0:
            status = "MODERATE"
        else:
            status = "GOLDILOCKS"

        return {
            "model_id": "MODEL_18",
            "model_name": "Okun Misery Index",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#18",
            "primary_value": score,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "civilian_unemployment_unrate": round(u, 2),
                "headline_cpi_yoy_pct": round(c, 2)
            },
            "metrics": {
                "misery_score": score,
                "unemployment_component": round(u, 2),
                "inflation_component": round(c, 2)
            },
            "interpretation": "Measures household welfare loss and stagflationary stress by summing civilian unemployment and annual inflation. Values > 12 indicate acute crisis."
        }
    except (TypeError, ValueError, OverflowError):
        return None


# --- Model 19: Buffett Indicator (Corporate Equities to GDP) ---
def calc_buffett_indicator(market_val_mil, gdp_val_bil) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (market_val_mil, gdp_val_bil)):
        return None
    try:
        m_val = float(market_val_mil)
        gdp_val = float(gdp_val_bil)
        if not (math.isfinite(m_val) and math.isfinite(gdp_val)):
            return None
        if m_val <= 0.0 or gdp_val <= 0.0:
            return None

        # Convert nominal GDP from billions to millions for unit consistency
        gdp_mil = gdp_val * 1000.0
        raw_ratio = (m_val / gdp_mil) * 100.0
        if not math.isfinite(raw_ratio):
            return None
        ratio = round(raw_ratio, 2)

        if ratio >= 180.0:
            status = "SEVERELY_OVERVALUED"
        elif ratio >= 140.0:
            status = "OVERVALUED"
        elif ratio >= 100.0:
            status = "FAIR_VALUED"
        else:
            status = "UNDERVALUED"

        return {
            "model_id": "MODEL_19",
            "model_name": "Buffett Indicator (Corporate Equities to GDP)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#19",
            "primary_value": ratio,
            "unit": "Percent (%)",
            "status": status,
            "inputs": {
                "corporate_equities_liability_ncbeilq027s_mil": round(m_val, 2),
                "nominal_gdp_bil": round(gdp_val, 2)
            },
            "metrics": {
                "buffett_ratio_pct": ratio,
                "total_equities_market_val_bil": round(m_val / 1000.0, 2),
                "nominal_gdp_bil": round(gdp_val, 2)
            },
            "interpretation": "Measures total equity valuation froth against national economic output using official Fed Z.1 accounts. Ratios >= 180% signal speculative bubble territory; < 100% reflect attractive valuation."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 20: Copper to Gold Macro Sentiment Ratio ---
def calc_copper_gold_ratio(copper_price_val, gold_price_val, copper_prev_val=None, gold_prev_val=None) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (copper_price_val, gold_price_val)):
        return None
    try:
        c_price = float(copper_price_val)
        g_price = float(gold_price_val)
        if not (math.isfinite(c_price) and math.isfinite(g_price)):
            return None
        if c_price <= 0.0 or g_price <= 0.0:
            return None

        ratio = round(c_price / g_price, 4)
        if not math.isfinite(ratio):
            return None

        # Determine trend if previous observations available, else historical benchmark
        if copper_prev_val is not None and gold_prev_val is not None:
            c_prev = float(copper_prev_val)
            g_prev = float(gold_prev_val)
            ratio_prev = round(c_prev / g_prev, 4) if (c_prev > 0 and g_prev > 0) else None
        else:
            ratio_prev = None

        if ratio_prev is not None:
            status = "CYCLICAL_EXPANSION" if ratio >= ratio_prev else "FLIGHT_TO_SAFETY"
        else:
            status = "CYCLICAL_EXPANSION" if ratio >= 3.00 else "FLIGHT_TO_SAFETY"

        return {
            "model_id": "MODEL_20",
            "model_name": "Copper to Gold Macro Sentiment Ratio",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#20",
            "primary_value": ratio,
            "unit": "Ratio (USD/MT to USD/oz)",
            "status": status,
            "inputs": {
                "copper_price_pcoppusdm_usd_mt": round(c_price, 2),
                "gold_price_ind_wb_gold_usd_oz": round(g_price, 2)
            },
            "metrics": {
                "copper_gold_ratio": ratio,
                "copper_price_usd_mt": round(c_price, 2),
                "gold_price_usd_oz": round(g_price, 2)
            },
            "interpretation": "Pits industrial cyclical momentum (Doctor Copper) against safe-haven store of value (Gold). A rising ratio signals robust global industrial demand and cyclical growth acceleration."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def calc_gold_oil_ratio(gold_price, oil_price) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (gold_price, oil_price)):
        return None
    try:
        g = float(gold_price)
        o = float(oil_price)
        if not (math.isfinite(g) and math.isfinite(o)):
            return None
        if g <= 0 or o <= 0:
            return None
        ratio = round(g / o, 2)
        if ratio >= 25.0:
            status = "MACRO_CRISIS_RECESSION"
        elif ratio <= 12.0:
            status = "SUPPLY_SHOCK_INFLATION"
        else:
            status = "HISTORICAL_EQUILIBRIUM"

        return {
            "model_id": "MODEL_21",
            "model_name": "Gold to Oil Crisis & Recession Ratio",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#21",
            "primary_value": ratio,
            "unit": "Barrels per Ounce",
            "status": status,
            "inputs": {
                "gold_price_usd_oz": round(g, 2),
                "oil_price_usd_bbl": round(o, 2)
            },
            "components": {
                "ratio": ratio,
                "historical_equilibrium_band": "12.0 - 25.0"
            },
            "metrics": {
                "gold_oil_ratio": ratio,
                "historical_equilibrium_band": "12.0 - 25.0"
            },
            "interpretation": "Calculates ounces of gold per barrel of crude oil to classify recessionary safe-haven demand or supply-side energy shocks."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 22: Household Credit Stress Gauge ---
def calc_household_credit_stress(delinquency_rate_val, saving_rate_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (delinquency_rate_val, saving_rate_val)):
        return None
    try:
        delinq = float(delinquency_rate_val)
        saving = float(saving_rate_val)
        if not (math.isfinite(delinq) and math.isfinite(saving)):
            return None
        # Delinquency rate cannot be negative
        if delinq < 0.0:
            return None

        # If saving rate is zero or negative, buffer is exhausted
        if saving <= 0.0:
            ratio = 999.0
            status = "SEVERE_CONSUMER_STRESS"
        else:
            ratio = round(delinq / saving, 3)
            if ratio > 1.00:
                status = "SEVERE_CONSUMER_STRESS"
            elif ratio >= 0.50:
                status = "ELEVATED_PRESSURE"
            else:
                status = "HEALTHY_BALANCE_SHEET"

        return {
            "model_id": "MODEL_22",
            "model_name": "Household Credit Stress Gauge",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#22",
            "primary_value": ratio,
            "unit": "Stress Ratio",
            "status": status,
            "inputs": {
                "credit_card_delinquency_rate_drcclacbs_pct": round(delinq, 2),
                "personal_saving_rate_psavert_pct": round(saving, 2)
            },
            "metrics": {
                "household_stress_ratio": ratio,
                "delinquency_rate_pct": round(delinq, 2),
                "saving_rate_pct": round(saving, 2)
            },
            "interpretation": "Measures consumer debt service vulnerability by evaluating credit card delinquency rates against the personal saving rate cushion. Ratios > 1.00 reflect severe consumer distress and spending contraction risk."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 23: Okun Gap (Growth-Employment Divergence) ---
def calc_okun_labor_gap(actual_unrate_delta, real_gdp_yoy) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (actual_unrate_delta, real_gdp_yoy)):
        return None
    try:
        actual_delta = float(actual_unrate_delta)
        gdp_yoy = float(real_gdp_yoy)
        if not (math.isfinite(actual_delta) and math.isfinite(gdp_yoy)):
            return None

        expected_delta = -0.5 * (gdp_yoy - 2.0)
        gap = round(actual_delta - expected_delta, 2)

        if gap > 0.50:
            status = "JOBLESS_GROWTH_WARNING"
        elif gap < -0.50:
            status = "LABOR_HOARDING"
        else:
            status = "BALANCED_OKUN_EQUILIBRIUM"

        return {
            "model_id": "MODEL_23",
            "model_name": "Okun Gap (Growth-Employment Divergence)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23",
            "primary_value": gap,
            "unit": "Percentage Points (ppt)",
            "status": status,
            "inputs": {
                "actual_unrate_delta_yoy": round(actual_delta, 2),
                "real_gdp_yoy_pct": round(gdp_yoy, 2)
            },
            "metrics": {
                "okun_gap_ppt": gap,
                "expected_unrate_delta": round(expected_delta, 2),
                "actual_unrate_delta": round(actual_delta, 2),
                "real_gdp_growth_yoy": round(gdp_yoy, 2)
            },
            "interpretation": "Evaluates the historical elasticity between real GDP growth and changes in unemployment to detect jobless growth or labor hoarding."
        }
    except (TypeError, ValueError):
        return None


# --- Model 23.1: Labor Market Dual-Track Dynamics ---
def calc_labor_dual_track_matrix(payems_mom, unrate_delta, civpart_delta) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (payems_mom, unrate_delta, civpart_delta)):
        return None
    try:
        p_mom = float(payems_mom)
        u_diff = round(float(unrate_delta), 2)
        c_diff = round(float(civpart_delta), 2)

        if not (math.isfinite(p_mom) and math.isfinite(u_diff) and math.isfinite(c_diff)):
            return None

        if p_mom > 150.0 and u_diff >= 0.0 and c_diff > 0.0:
            status = "BENIGN_SUPPLY_EXPANSION"
        elif p_mom < 100.0 and u_diff > 0.10:
            status = "RECESSION_EARLY_WARNING"
        else:
            status = "BALANCED_LABOR_MARKET"

        return {
            "model_id": "MODEL_23.1",
            "model_name": "Labor Market Dual-Track Dynamics",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23.1",
            "primary_value": round(p_mom, 2),
            "unit": "Thousands (k)",
            "status": status,
            "inputs": {
                "payems_change_mom_k": round(p_mom, 2),
                "unrate_change_mom_ppt": u_diff,
                "civpart_change_mom_ppt": c_diff
            },
            "metrics": {
                "payems_change_k": round(p_mom, 2),
                "unrate_change_ppt": u_diff,
                "civpart_change_ppt": c_diff
            },
            "interpretation": "Cross-evaluates payroll gains against unemployment rate and participation rate shifts to determine whether employment growth is organically absorbing new entrants or masking structural deterioration."
        }
    except (TypeError, ValueError):
        return None


# --- Model 23.4: Early Layoff and Recession Signal ---
def calc_early_layoff_signal(indpro_yoy_pct, awhaetp_yoy_pct) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (indpro_yoy_pct, awhaetp_yoy_pct)):
        return None
    try:
        ip = float(indpro_yoy_pct)
        hrs = float(awhaetp_yoy_pct)
        if not (math.isfinite(ip) and math.isfinite(hrs)):
            return None

        raw_index = ip + (hrs * 2.0)
        if not math.isfinite(raw_index):
            return None
        index = round(raw_index, 2)

        if index < -2.50:
            status = "ACUTE_LAYOFF_CONTRACTION"
        elif index < 0.0:
            status = "EARLY_RECESSION_SIGNAL"
        else:
            status = "EXPANSION_EMPLOYMENT_MOMENTUM"

        return {
            "model_id": "MODEL_23.4",
            "model_name": "Early Layoff and Recession Signal",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23.4",
            "primary_value": index,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "industrial_production_yoy_pct": round(ip, 2),
                "weekly_hours_yoy_pct": round(hrs, 2)
            },
            "metrics": {
                "early_layoff_index": index,
                "indpro_yoy_pct": round(ip, 2),
                "awhaetp_yoy_pct": round(hrs, 2)
            },
            "interpretation": "Detects latent employment losses and early recessionary inflection before headline unemployment rises by synthesizing weekly hours worked against industrial production momentum."
        }
    except (TypeError, ValueError):
        return None


def calc_early_employment_crack(ic4wsa_yoy, unrate_delta) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (ic4wsa_yoy, unrate_delta)):
        return None
    try:
        claims_yoy = float(ic4wsa_yoy)
        u_delta = float(unrate_delta)
        if not (math.isfinite(claims_yoy) and math.isfinite(u_delta)):
            return None

        # Prevent falling unemployment from generating false crisis signals
        effective_u_delta = max(0.0, u_delta)
        raw_index = claims_yoy - (effective_u_delta * 10.0)
        if not math.isfinite(raw_index):
            return None
        index = round(raw_index, 2)

        if claims_yoy >= 15.0 and index >= 15.0:
            status = "HIDDEN_CRISIS_UNFOLDING"
        elif claims_yoy >= 8.0 and index >= 5.0:
            status = "EARLY_WARNING_CRACK"
        else:
            status = "LABOR_MARKET_ALIGNED"

        return {
            "model_id": "MODEL_23.6",
            "model_name": "Early Employment Crack Signal",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23.6",
            "primary_value": index,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "ic4wsa_yoy_pct": round(claims_yoy, 2),
                "unrate_delta_ppt": round(u_delta, 2)
            },
            "components": {
                "effective_unrate_delta": round(effective_u_delta, 2),
                "crack_threshold": 15.0
            },
            "metrics": {
                "early_employment_crack_index": index,
                "effective_unrate_delta": round(effective_u_delta, 2),
                "crack_threshold": 15.0
            },
            "interpretation": "Identifies early labor cracks by comparing weekly jobless claims spikes against delayed headline unemployment shifts."
        }
    except (TypeError, ValueError):
        return None


# --- Model 23.7: Stok/Satış Tıkanıklık Oranı (Inventory to Sales Glut Ratio) ---
def calc_inventory_to_sales_glut(isratio_val):
    if isratio_val is None or isinstance(isratio_val, bool):
        return None
    try:
        r = float(isratio_val)
        if not math.isfinite(r) or r <= 0.0:
            return None

        ratio = round(r, 2)
        if ratio > 1.45:
            status = "SYSTEMIC_INVENTORY_GLUT"
        elif ratio < 1.28:
            status = "SUPPLY_SHOCK_SHORTAGE"
        else:
            status = "BALANCED_SUPPLY_CHAIN"

        return {
            "model_id": "MODEL_23.7",
            "model_name": "Inventory to Sales Glut Ratio",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23.7",
            "primary_value": ratio,
            "unit": "Ratio",
            "status": status,
            "inputs": {
                "total_business_isratio": ratio
            },
            "metrics": {
                "inventory_to_sales_ratio": ratio
            },
            "interpretation": "Measures total business inventories relative to monthly sales. Values > 1.45 indicate severe inventory glut and recessionary production cuts."
        }
    except (TypeError, ValueError, OverflowError):
        return None


# --- Model 23.8: Mortgage and Permit Divergence (Housing Freeze Index) ---
def calc_housing_freeze_index(mortgage_rate, permit_yoy) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (mortgage_rate, permit_yoy)):
        return None
    try:
        m_rate = float(mortgage_rate)
        p_yoy = float(permit_yoy)
        if not (math.isfinite(m_rate) and math.isfinite(p_yoy)):
            return None
        if m_rate <= 0.0:
            return None

        raw_index = m_rate - (p_yoy / 10.0)
        if not math.isfinite(raw_index):
            return None
        index = round(raw_index, 2)

        if index > 8.0:
            status = "SEVERE_HOUSING_FREEZE"
        elif index > 5.0:
            status = "SUPPLY_CONTRACTION"
        else:
            status = "HEALTHY_EXPANSION"

        return {
            "model_id": "MODEL_23.8",
            "model_name": "Mortgage and Permit Divergence (Housing Freeze Index)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#23.8",
            "primary_value": index,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "mortgage_30y_rate_pct": round(m_rate, 2),
                "building_permits_yoy_pct": round(p_yoy, 2)
            },
            "metrics": {
                "housing_freeze_index": index,
                "mortgage_rate": round(m_rate, 2),
                "permits_yoy_pct": round(p_yoy, 2)
            },
            "interpretation": "Measures divergence between surging mortgage borrowing costs and residential building permit momentum to model lock-in supply bottlenecks and housing transaction freezes."
        }
    except (TypeError, ValueError):
        return None


# --- Model 24: Safe Haven Flight Index ---
def calc_safe_haven_flight_index(dxy_val, hy_spread_val, dgs10_val) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (dxy_val, hy_spread_val, dgs10_val)):
        return None
    try:
        dxy = float(dxy_val)
        hy = float(hy_spread_val)
        y10 = float(dgs10_val)
        if not (math.isfinite(dxy) and math.isfinite(hy) and math.isfinite(y10)):
            return None
        if dxy <= 0.0 or hy <= 0.0 or y10 <= 0.0:
            return None

        raw_dollar_bond_ratio = dxy / y10
        raw_score = raw_dollar_bond_ratio * hy
        raw_ratio = raw_score / 100.0

        if not (math.isfinite(raw_dollar_bond_ratio) and math.isfinite(raw_score) and math.isfinite(raw_ratio)):
            return None

        dollar_bond_ratio = round(raw_dollar_bond_ratio, 2)
        score = round(raw_score, 2)
        ratio = round(raw_ratio, 3)

        if ratio > 2.50:
            status = "EXTREME_LIQUIDITY_PANIC"
        elif ratio > 1.80:
            status = "HIGH_FLIGHT_TO_SAFETY"
        elif ratio > 1.00:
            status = "MODERATE_HEDGING"
        else:
            status = "NORMAL_MARKET_REGIME"

        return {
            "model_id": "MODEL_24",
            "model_name": "Safe Haven Flight Index",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#24",
            "primary_value": ratio,
            "unit": "Flight Ratio",
            "status": status,
            "inputs": {
                "nominal_broad_dollar_index_dtwexbgs": round(dxy, 4),
                "high_yield_oas_bamlh0a0hym2": round(hy, 2),
                "nominal_10y_treasury_dgs10": round(y10, 2)
            },
            "metrics": {
                "flight_ratio": ratio,
                "safe_haven_score": score,
                "dollar_bond_ratio": dollar_bond_ratio
            },
            "interpretation": "Measures capital flight into safe-haven USD and flight-to-safety dynamics by evaluating dollar strength and credit spreads against Treasury yields. Values > 1.80 indicate acute flight to safety."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 25: Terms of Trade (TOT) ---
def calc_terms_of_trade(export_idx, import_idx) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (export_idx, import_idx)):
        return None
    try:
        iq = float(export_idx)
        ir = float(import_idx)
        if not (math.isfinite(iq) and math.isfinite(ir)):
            return None
        if iq <= 0.0 or ir <= 0.0:
            return None

        raw_tot = (iq / ir) * 100.0
        if not math.isfinite(raw_tot):
            return None
        tot = round(raw_tot, 2)

        if tot > 100.0:
            status = "FAVORABLE_TRADE"
        elif tot == 100.0:
            status = "BASELINE_EQUILIBRIUM"
        else:
            status = "DETERIORATING_TERMS"

        return {
            "model_id": "MODEL_25",
            "model_name": "Terms of Trade (TOT)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25",
            "primary_value": tot,
            "unit": "Index Points",
            "status": status,
            "inputs": {
                "export_price_index_iq": round(iq, 2),
                "import_price_index_ir": round(ir, 2)
            },
            "metrics": {
                "terms_of_trade_ratio": tot,
                "export_index": round(iq, 2),
                "import_index": round(ir, 2)
            },
            "interpretation": "Evaluates sovereign purchasing power and current account terms-of-trade transfers by measuring the relative price of exported commodities against imported goods."
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# --- Model 25.18: Mecca Pact Dynamic Transmission Engine ---
def calc_mecca_pact_transmission(brent_val, sofr_val, breakeven_oil=None):
    if any(v is None or isinstance(v, bool) for v in (brent_val, sofr_val, breakeven_oil)):
        return None
    try:
        brent = float(brent_val)
        sofr = float(sofr_val)
        be = float(breakeven_oil)
        if not all(math.isfinite(x) for x in (brent, sofr, be)) or brent <= 0.0 or be <= 0.0:
            return None
        if not all(math.isfinite(x) for x in (brent, sofr, be)) or brent <= 0.0 or be <= 0.0:
            return None

        delta_treaty = 0.10
        r_oil = round(brent / be, 4)

        if r_oil >= 1.05:
            s_energy = 0.05
            status = "TREATY_ACTIVE_SURPLUS_EXPANSION"
        elif r_oil < 0.90:
            s_energy = -0.05
            status = "TREATY_ACTIVE_FISCAL_RESTRAINT"
        else:
            s_energy = 0.00
            status = "TREATY_ACTIVE_EQUILIBRIUM"

        delta_dollar = -0.03 if sofr >= 5.25 else 0.00

        delta_tr_sa = round(min(0.30, max(-0.30, delta_treaty + s_energy + delta_dollar)), 2)
        delta_sa_pk = round(min(0.30, max(-0.30, delta_treaty + s_energy + delta_dollar)), 2)
        delta_tr_pk = round(min(0.30, max(-0.30, delta_treaty + min(0.0, delta_dollar))), 2)

        avg_uplift = round((delta_tr_sa + delta_sa_pk + delta_tr_pk) / 3.0, 3)

        return {
            "model_id": "MODEL_25.18",
            "model_name": "Non-Contiguous Alliance Dynamic Transmission Engine (Mecca Pact)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.18",
            "primary_value": avg_uplift,
            "unit": "Dynamic Delta Index (Avg)",
            "status": status,
            "inputs": {
                "brent_usd_bbl": round(brent, 2),
                "sofr_percent": round(sofr, 2),
                "imf_breakeven_usd_bbl": round(be, 2)
            },
            "metrics": {
                "oil_breakeven_ratio": r_oil,
                "delta_treaty_baseline": delta_treaty,
                "energy_fiscal_component": s_energy,
                "dollar_liquidity_friction": delta_dollar,
                "bilateral_deltas": {
                    "TR_SA": delta_tr_sa,
                    "SA_PK": delta_sa_pk,
                    "TR_PK": delta_tr_pk
                }
            },
            "interpretation": "Non-contiguous trilateral defense integration linking Turkish aerospace/defense co-production, Saudi sovereign liquidity, and Pakistani strategic deterrence under dynamic oil and dollar regimes."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.19: Sovereign Synthetic CDS & Actuarial Default Probability Engine ---
def calc_sovereign_synthetic_cds_pd(spread_input_pct, recovery_rate=0.40):
    if spread_input_pct is None or isinstance(spread_input_pct, bool):
        return None
    try:
        spread_pct = float(spread_input_pct)
        if not math.isfinite(spread_pct) or spread_pct <= 0.0 or spread_pct > 100.0:
            return None

        rec = float(recovery_rate)
        if not math.isfinite(rec) or rec < 0.0 or rec >= 1.0:
            return None

        spread_bps = round(spread_pct * 100.0, 1)
        lgd = 1.0 - rec
        if lgd <= 0.0:
            return None

        raw_pd = spread_pct / lgd
        if not math.isfinite(raw_pd):
            return None
        pd_pct = round(min(100.0, max(0.0, raw_pd)), 2)

        if spread_bps < 250.0:
            status = "STABLE_INVESTMENT_GRADE"
        elif spread_bps < 450.0:
            status = "MODERATE_SOVEREIGN_STRESS"
        elif spread_bps < 700.0:
            status = "HIGH_GEOPOLITICAL_RISK"
        else:
            status = "ACUTE_DEFAULT_DISTRESS"

        delta_macro = - round(min(0.60, max(0.0, (pd_pct - 4.0) / 10.0 * 0.50)), 2)

        return {
            "model_id": "MODEL_25.19",
            "model_name": "Sovereign Synthetic CDS & Actuarial Default Probability Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.19",
            "primary_value": pd_pct,
            "unit": "Annual Default Probability Percent (% PD)",
            "status": status,
            "inputs": {
                "credit_spread_benchmark_bamlh0a0hym2": round(spread_pct, 2),
                "isda_standard_recovery_rate": rec
            },
            "metrics": {
                "synthetic_cds_bps": spread_bps,
                "loss_given_default_pct": round(lgd * 100.0, 1),
                "annual_default_probability_pct": pd_pct,
                "dynamic_transmission_delta": delta_macro
            },
            "interpretation": f"Actuarial credit risk model computing synthetic sovereign CDS and default probability using ISDA emerging market {int(rec*100)}% recovery rate assumptions."
        }
    except (TypeError, ValueError):
        return None


# --- Model 25.15: Domestic Governance Gridlock & External Tariff Friction Engine ---
def calc_governance_gridlock_friction(country_code, majority_seat_margin, executive_decree_power):
    if not isinstance(country_code, str):
        return None

    country = country_code.upper().strip()
    valid_countries = {"GEO_US", "GEO_CN", "GEO_RU", "GEO_DE", "GEO_IL", "GEO_JP"}
    if country not in valid_countries:
        return None

    if executive_decree_power is None or isinstance(executive_decree_power, bool):
        return None

    try:
        decree = float(executive_decree_power)
    except (ValueError, TypeError):
        return None

    if not math.isfinite(decree) or decree < 0.0 or decree > 1.0:
        return None

    if country in {"GEO_CN", "GEO_RU"}:
        gridlock = 0.0
        ext_friction = round(decree * 0.75, 3)
        status = "CENTRALIZED_STRATEGIC_COMMAND"
        return {
            "model_id": "MODEL_25.15",
            "model_name": "Domestic Governance Gridlock & External Tariff Friction Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.15",
            "primary_value": ext_friction,
            "unit": "Friction Bias",
            "status": status,
            "inputs": {
                "country_code": country,
                "executive_decree_power": decree
            },
            "metrics": {
                "gridlock_index": gridlock,
                "external_friction_bias": ext_friction
            },
            "interpretation": "Centralized vertical strategic command deploying external trade and economic leverage without domestic legislative gridlock."
        }

    if majority_seat_margin is None or isinstance(majority_seat_margin, bool):
        return None

    try:
        margin = float(majority_seat_margin)
        if not math.isfinite(margin):
            return None

        if margin < 0:
            gridlock = round(min(1.0, 0.60 + abs(margin) * 0.02), 3)
        else:
            gridlock = round(max(0.0, 0.40 - (margin * 0.015)), 3)

        ext_friction = round(gridlock * decree, 3)

        if gridlock >= 0.60 and ext_friction >= 0.45:
            status = "DIVIDED_GRIDLOCK_TARIFF_SURGE"
        elif gridlock >= 0.35 and ext_friction < 0.45:
            status = "FRAGILE_COALITION_PARALYSIS"
        elif gridlock < 0.25 and margin >= 15:
            status = "UNIFIED_DOMESTIC_EXPANSION"
        else:
            status = "BALANCED_INSTITUTIONAL_EQUILIBRIUM"

        return {
            "model_id": "MODEL_25.15",
            "model_name": "Domestic Governance Gridlock & External Tariff Friction Engine",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#25.15",
            "primary_value": ext_friction,
            "unit": "Friction Bias",
            "status": status,
            "inputs": {
                "country_code": country,
                "majority_seat_margin": margin,
                "executive_decree_power": decree
            },
            "metrics": {
                "gridlock_index": gridlock,
                "external_friction_bias": ext_friction
            },
            "interpretation": "Quantifies domestic legislative gridlock driving unilateral executive trade tariffs, foreign sanctions, and cross-border economic friction."
        }
    except (TypeError, ValueError, OverflowError):
        return None


# --- Model 26: Central Bank Committee Dispersion & Hawkishness Index ---
def calc_committee_dispersion(n_hawkish, n_dovish, n_neutral, n_total=None):
    if any(v is None or isinstance(v, bool) for v in (n_hawkish, n_dovish, n_neutral)):
        return None
    try:
        # Enforce discrete integer counts for voting committee members
        for val in (n_hawkish, n_dovish, n_neutral):
            if isinstance(val, float) and not val.is_integer():
                return None
            if not isinstance(val, (int, float)):
                return None
            if not math.isfinite(val) or val < 0:
                return None

        h = int(n_hawkish)
        d = int(n_dovish)
        neu = int(n_neutral)

        tot = h + d + neu
        if n_total is not None and not isinstance(n_total, bool):
            if isinstance(n_total, float) and not n_total.is_integer():
                return None
            if not isinstance(n_total, (int, float)) or not math.isfinite(n_total):
                return None
            f_tot = int(n_total)
            if f_tot >= tot and f_tot > 0:
                tot = f_tot
            elif f_tot < tot:
                return None

        if tot <= 0:
            return None

        p_h = h / tot
        p_d = d / tot
        p_neu = neu / tot

        h_index = round((h - d) / tot, 4)
        sum_sq = (p_h ** 2) + (p_d ** 2) + (p_neu ** 2)
        dispersion = round(1.0 - sum_sq, 4)

        # Directional Stance (H-Index Regime)
        if h_index >= 0.50:
            directional_stance = "STRONG_HAWKISH_TILT"
        elif h_index >= 0.15:
            directional_stance = "MODERATE_HAWKISH_BIAS"
        elif h_index <= -0.50:
            directional_stance = "STRONG_DOVISH_TILT"
        elif h_index <= -0.15:
            directional_stance = "MODERATE_DOVISH_BIAS"
        else:
            directional_stance = "BALANCED_NEUTRAL_STANCE"

        # Consensus / Dispersion Regime
        if dispersion <= 0.30:
            consensus_regime = "STRONG_CONSENSUS"
        elif dispersion <= 0.48:
            consensus_regime = "MODERATE_DISSENT"
        else:
            consensus_regime = "HIGH_DISPERSION"

        return {
            "model_id": "MODEL_26",
            "model_name": "Central Bank Committee Dispersion & Hawkishness Index",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#26",
            "primary_value": h_index,
            "unit": "H-Index",
            "status": directional_stance,
            "inputs": {
                "n_total": int(tot),
                "n_hawkish": int(h),
                "n_dovish": int(d),
                "n_neutral": int(neu)
            },
            "metrics": {
                "share_hawkish_pct": round(p_h * 100.0, 2),
                "share_dovish_pct": round(p_d * 100.0, 2),
                "share_neutral_pct": round(p_neu * 100.0, 2),
                "h_index": h_index,
                "dispersion": dispersion,
                "consensus_regime": consensus_regime
            },
            "interpretation": "Quantifies FOMC monetary policy committee voting distribution across hawkish, dovish, and neutral members to compute directional policy stance and internal voting fracture."
        }
    except (TypeError, ValueError, OverflowError):
        return None


# --- Model 28.4: Chokepoint Macro Spillover Bridge ---
def calc_chokepoint_transmission_bridge(
    severity_enum: str,
    p_net: float,
    duration_days: int = 14,
    bypass_capacity_mbpd: float = 4.0,
    spr_stocks_kbbl: Optional[float] = None,
    spr_release_mbpd: Optional[float] = None,
    gross_flow_mbpd: float = 20.5,
    us_crude_prod_kbpd: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    if any(v is None or isinstance(v, bool) for v in (severity_enum, p_net)):
        return None
    try:
        sev_weights = {
            "CATASTROPHIC": 1.00,
            "HIGH": 0.70,
            "MODERATE-HIGH": 0.45,
            "MODERATE": 0.20
        }
        w_sev = sev_weights.get(severity_enum)
        if w_sev is None:
            return None

        p_val = float(p_net)
        if not math.isfinite(p_val):
            return None

        pol_clamped = min(1.0, max(-1.0, p_val))
        friction = max(0.0, -pol_clamped)

        t = max(1, int(duration_days)) if duration_days is not None else 14
        f_gross = max(0.1, float(gross_flow_mbpd)) if gross_flow_mbpd is not None else 20.5
        f_bypass = max(0.0, float(bypass_capacity_mbpd)) if bypass_capacity_mbpd is not None else 4.0

        # Dynamic SPR drawdown calculation from live EIA inventory (PET.WCSSTUS1.W)
        if spr_stocks_kbbl is not None and not isinstance(spr_stocks_kbbl, bool):
            f_spr_kbbl = float(spr_stocks_kbbl)
            spr_mbbl = f_spr_kbbl / 1000.0
            # 4.4 mbpd max mechanical drawdown capacity, 90-day crisis sustainable drawdown rate
            raw_spr = round(min(4.4, max(0.0, spr_mbbl / 90.0)), 2)
        elif spr_release_mbpd is not None and not isinstance(spr_release_mbpd, bool):
            raw_spr = max(0.0, float(spr_release_mbpd))
        else:
            return None  # Zero-synthetic-fallback: requires live data or explicit rate

        # SPR Depletion Decay Rule:
        # <= 60d: 100% capacity | 61-90d: 50% capacity | >90d: 25% emergency reserve
        if t <= 60:
            spr_decay = 1.0
        elif t <= 90:
            spr_decay = 0.50
        else:
            spr_decay = 0.25
        effective_spr = round(raw_spr * spr_decay, 2)

        # Net Unmet Deficit with Clamping Guard
        total_buffer = round(min(f_gross, f_bypass + effective_spr), 2)
        net_deficit_ratio = round(max(0.0, (f_gross - total_buffer) / f_gross), 4)

        # Sigmoid Crisis Duration Scaling (Centered at t0=14 with k=0.15)
        sigmoid_val = 1.0 / (1.0 + math.exp(-0.15 * (t - 14.0)))
        duration_scale = round(0.40 + 0.60 * sigmoid_val, 4)

        # Weighted Transmission: 70% physical disruption + 30% geopolitical polarity friction
        base_shock = (w_sev * net_deficit_ratio * 70.0) + (friction * 30.0)
        score = int(round(min(100.0, max(0.0, base_shock * duration_scale))))

        if score >= 85:
            transmission_regime = "CRITICAL_SYSTEMIC_SHOCK"
        elif score >= 60:
            transmission_regime = "HIGH_SPILLOVER"
        elif score >= 30:
            transmission_regime = "MODERATE_FRICTION"
        else:
            transmission_regime = "LOCALIZED_IMPACT"

        metrics: Dict[str, Any] = {
            "severity_weight": w_sev,
            "polarity_friction_factor": round(friction, 2),
            "spr_sustainable_drawdown_mbpd": raw_spr,
            "effective_spr_release_mbpd": effective_spr,
            "total_buffer_capacity_mbpd": total_buffer,
            "net_unmet_deficit_mbpd": round(f_gross - total_buffer, 2),
            "net_deficit_ratio": net_deficit_ratio,
            "duration_scale_factor": duration_scale,
            "unscaled_base_shock": round(base_shock, 2)
        }

        inputs: Dict[str, Any] = {
            "chokepoint_id": "CHOKE_HORMUZ",
            "severity_enum": severity_enum,
            "p_net": round(p_val, 2),
            "crisis_duration_days": t,
            "gross_flow_mbpd": round(f_gross, 2),
            "regional_bypass_capacity_mbpd": round(f_bypass, 2)
        }

        if spr_stocks_kbbl is not None:
            inputs["eia_spr_stocks_mbbl"] = round(float(spr_stocks_kbbl) / 1000.0, 2)
        if us_crude_prod_kbpd is not None:
            f_prod_mbpd = round(float(us_crude_prod_kbpd) / 1000.0, 2)
            inputs["eia_us_crude_prod_mbpd"] = f_prod_mbpd
            metrics["us_crude_field_production_mbpd"] = f_prod_mbpd

        return {
            "model_id": "MODEL_28.4",
            "model_name": "Chokepoint Macro Spillover Bridge (Hormuz - Live EIA SPR)",
            "formula_ref": "https://analysisreports.github.io/llms-formulas.txt#28.4",
            "primary_value": score,
            "unit": "Index (0-100)",
            "status": transmission_regime,
            "inputs": inputs,
            "metrics": metrics,
            "interpretation": f"Couples maritime chokepoint severity ({severity_enum}) with live EIA SPR inventory ({metrics.get('spr_sustainable_drawdown_mbpd')} mbpd sustainable release) and regional pipeline bypass to evaluate macroeconomic spillover under acute crisis."
        }
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None

# ==============================================================================
# 3. MAIN EXECUTION ENGINE
# ==============================================================================

def main():
    fred_json_path = "llms-fred-series.json"
    out_json_path = "llms-models.json"
    out_txt_path = "llms-models.txt"

    ingestion_warnings = []

    if not os.path.exists(fred_json_path):
        print(f"Error: {fred_json_path} not found. Run update_fred_series.py first.")
        return

    with open(fred_json_path, "r", encoding="utf-8") as f:
        fred_data = json.load(f)

    series = fred_data.get("series", {})
    if not series:
        ingestion_warnings.append("FRED series dictionary is empty.")

    # Extract Series Inputs
    dgs1mo = series.get("DGS1MO", {}).get("current_value")
    dgs3mo = series.get("DGS3MO", {}).get("current_value")
    dff_curr = series.get("DFF", {}).get("current_value")
    cpi_yoy = series.get("CPIAUCSL", {}).get("transformations", {}).get("percent_change_from_year_ago")

    dfedtaru_curr = series.get("DFEDTARU", {}).get("current_value")
    fed_rate = dfedtaru_curr if dfedtaru_curr is not None else dff_curr

    brent = series.get("DCOILBRENTEU", {}).get("current_value")
    wti = series.get("DCOILWTICO", {}).get("current_value")
    vix = series.get("VIXCLS", {}).get("current_value")
    ovx = series.get("OVXCLS", {}).get("current_value")
    sox_yoy = series.get("NASDAQSOX", {}).get("transformations", {}).get("percent_change_from_year_ago")
    sofr = series.get("SOFR", {}).get("current_value")

    # Dynamic New York Fed GSCPI Series (AMEC) - Zero Fallbacks
    nyfed_json_path = "llms-nyfed-series.json"
    gscpi = None
    if os.path.exists(nyfed_json_path):
        try:
            with open(nyfed_json_path, "r", encoding="utf-8") as f:
                nyfed_json = json.load(f)
                gscpi = nyfed_json.get("series", {}).get("GSCPI", {}).get("current_value")
        except Exception as e:
            gscpi = None
            ingestion_warnings.append(f"NY Fed GSCPI read error: {e}")
    else:
        ingestion_warnings.append("NY Fed series file missing: llms-nyfed-series.json")

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

    # Evaluate Models in Canonical Order
    models_calculated = []

    # Model 1: Fed Policy Stance & Market Pressure Gauge
    m_fed_stance = calc_fed_policy_stance(dgs1mo, fed_rate)
    if m_fed_stance:
        models_calculated.append(m_fed_stance)

    # Model 2: Real Policy Rate & Restrictiveness
    m_real_rate = calc_real_policy_rate(dff_curr, cpi_yoy)
    if m_real_rate:
        models_calculated.append(m_real_rate)

    # Model 3: Sahm Rule
    m_sahm = calc_sahm_rule(sahm_val)
    if m_sahm:
        models_calculated.append(m_sahm)

    # Model 4: Front-End T-Bill Slope & Liquidity Spread
    m_t_bill = calc_front_end_t_bill_slope(dgs3mo, dgs1mo)
    if m_t_bill:
        models_calculated.append(m_t_bill)

    # Model 5: Net Fed Liquidity
    m_liq = calc_net_fed_liquidity(walcl, tga, rrp)
    if m_liq:
        models_calculated.append(m_liq)

    # Model 6: Yield Curve Slope (10Y - 2Y)
    m_slope = calc_yield_spread_bps(t10y2y)
    if m_slope:
        models_calculated.append(m_slope)

    # Model 7: 10-Year Breakeven Inflation Rate
    dgs10_val = series.get("DGS10", {}).get("current_value")
    dfii10_val = series.get("DFII10", {}).get("current_value")
    m_breakeven = calc_breakeven_inflation(dgs10_val, dfii10_val)
    if m_breakeven:
        models_calculated.append(m_breakeven)

    # Model 8: Beveridge Curve Labor Tightness
    jtsjol_val = series.get("JTSJOL", {}).get("current_value")
    unemploy_val = series.get("UNEMPLOY", {}).get("current_value")
    m_bev = calc_beveridge_labor_tightness(jtsjol_val, unemploy_val)
    if m_bev:
        models_calculated.append(m_bev)

    # Model 9: Financial Repression Index
    debt_gdp_val = series.get("GFDEGDQ188S", {}).get("current_value")
    m_repression = calc_financial_repression_index(dgs10_val, cpi_yoy, debt_gdp_val)
    if m_repression:
        models_calculated.append(m_repression)

    # Model 10: Triffin External Balance
    dtwexbgs_val = series.get("DTWEXBGS", {}).get("current_value")
    bopgstb_val = series.get("BOPGSTB", {}).get("current_value")
    m_triffin = calc_triffin_external_balance(dtwexbgs_val, bopgstb_val)
    if m_triffin:
        models_calculated.append(m_triffin)

    # Model 11: Taylor Rule Policy Gap
    gdpc1_series = series.get("GDPC1", {})
    gdppot_series = series.get("GDPPOT", {})
    m_taylor = calc_taylor_policy_gap(
        dff_curr,
        cpi_yoy,
        gdpc1_series.get("current_value"),
        gdppot_series.get("current_value"),
        gdpc1_series.get("units"),
        gdppot_series.get("units")
    )
    if m_taylor:
        models_calculated.append(m_taylor)

    # Model 12: Financial Conditions Tightness (Chicago Fed NFCI)
    nfci_val = series.get("NFCI", {}).get("current_value")
    anfci_val = series.get("ANFCI", {}).get("current_value")
    m_nfci = calc_financial_conditions_tightness(nfci_val, anfci_val)
    if m_nfci:
        models_calculated.append(m_nfci)

    # Model 13: High Yield Credit Spread / OAS
    hy_spread = series.get("BAMLH0A0HYM2", {}).get("current_value")
    m_hy = calc_high_yield_credit_stress(hy_spread)
    if m_hy:
        models_calculated.append(m_hy)

    # Model 14: Real M2 Money Momentum
    m2_yoy = series.get("M2SL", {}).get("transformations", {}).get("percent_change_from_year_ago")
    m_m2 = calc_real_m2_momentum(m2_yoy, cpi_yoy)
    if m_m2:
        models_calculated.append(m_m2)

    # Model 15: NY Fed ACM 10-Year Term Premium
    threefytp10_val = series.get("THREEFYTP10", {}).get("current_value")
    m_acm = calc_acm_term_premium(dgs10_val, threefytp10_val)
    if m_acm:
        models_calculated.append(m_acm)

    # Model 16: VIX Regime
    m_vix = calc_vix_market_regime(vix)
    if m_vix:
        models_calculated.append(m_vix)

    # Model 18: Okun Misery Index (UNRATE x CPI YoY)
    m_misery = calc_misery_index(unrate_curr, cpi_yoy)
    if m_misery:
        models_calculated.append(m_misery)

    # Model 19: Buffett Indicator (Corporate Equities to GDP)
    ncbeilq_val = series.get("NCBEILQ027S", {}).get("current_value")
    gdp_nom_val = series.get("GDP", {}).get("current_value")
    m_buffett = calc_buffett_indicator(ncbeilq_val, gdp_nom_val)
    if m_buffett:
        models_calculated.append(m_buffett)

    # Load World Bank Pink Sheet series for commodity models
    wb_json_path = "llms-worldbank-series.json"
    gold_price = None
    gold_prev = None
    if os.path.exists(wb_json_path):
        try:
            with open(wb_json_path, "r", encoding="utf-8") as f:
                wb_json = json.load(f)
                gold_price = wb_json.get("series", {}).get("IND_WB_GOLD", {}).get("current_value")
                gold_prev = wb_json.get("series", {}).get("IND_WB_GOLD", {}).get("previous_value")
                if gold_price is None:
                    ingestion_warnings.append("World Bank Pink Sheet IND_WB_GOLD is missing/null.")
        except Exception as e:
            gold_price = None
            gold_prev = None
            ingestion_warnings.append(f"World Bank Pink Sheet read error: {e}")
    else:
        ingestion_warnings.append("World Bank Pink Sheet file missing: llms-worldbank-series.json")

    # Model 20: Copper to Gold Macro Sentiment Ratio
    copper_val = series.get("PCOPPUSDM", {}).get("current_value")
    copper_prev = series.get("PCOPPUSDM", {}).get("previous_value")
    m_copper_gold = calc_copper_gold_ratio(copper_val, gold_price, copper_prev, gold_prev)
    if m_copper_gold:
        models_calculated.append(m_copper_gold)

    # Model 21: Gold to Oil Ratio (World Bank Pink Sheet x FRED WTI)
    m_gold_oil = calc_gold_oil_ratio(gold_price, wti)
    if m_gold_oil:
        models_calculated.append(m_gold_oil)

    # Model 22: Household Credit Stress Gauge
    drcclacbs_val = series.get("DRCCLACBS", {}).get("current_value")
    psavert_val = series.get("PSAVERT", {}).get("current_value")
    m_household = calc_household_credit_stress(drcclacbs_val, psavert_val)
    if m_household:
        models_calculated.append(m_household)

    # Model 23: Okun Gap (Growth-Employment Divergence)
    gdp_yoy = series.get("GDPC1", {}).get("transformations", {}).get("percent_change_from_year_ago")
    unrate_delta_yoy = round(unrate_curr - unrate_yr, 2) if (unrate_curr is not None and unrate_yr is not None) else None
    m_okun = calc_okun_labor_gap(unrate_delta_yoy, gdp_yoy)
    if m_okun:
        models_calculated.append(m_okun)

    # Model 23.1: Labor Market Dual-Track Dynamics
    payems_mom = series.get("PAYEMS", {}).get("transformations", {}).get("change")
    unrate_mom = series.get("UNRATE", {}).get("transformations", {}).get("change")
    civpart_mom = series.get("CIVPART", {}).get("transformations", {}).get("change")
    m_dual_track = calc_labor_dual_track_matrix(payems_mom, unrate_mom, civpart_mom)
    if m_dual_track:
        models_calculated.append(m_dual_track)

    # Model 23.4: Early Layoff and Recession Signal
    indpro_yoy = series.get("INDPRO", {}).get("transformations", {}).get("percent_change_from_year_ago")
    awhaetp_yoy = series.get("AWHAETP", {}).get("transformations", {}).get("percent_change_from_year_ago")
    m_layoff = calc_early_layoff_signal(indpro_yoy, awhaetp_yoy)
    if m_layoff:
        models_calculated.append(m_layoff)

    # Model 23.6: Early Employment Crack Signal (FRED IC4WSA x UNRATE)
    ic4wsa_yoy = series.get("IC4WSA", {}).get("transformations", {}).get("percent_change_from_year_ago")
    unrate_delta = round(unrate_curr - unrate_yr, 2) if (unrate_curr is not None and unrate_yr is not None) else None
    m_crack = calc_early_employment_crack(ic4wsa_yoy, unrate_delta)
    if m_crack:
        models_calculated.append(m_crack)

    # Model 23.7: Inventory to Sales Glut Ratio (ISRATIO)
    isratio_val = series.get("ISRATIO", {}).get("current_value")
    m_glut = calc_inventory_to_sales_glut(isratio_val)
    if m_glut:
        models_calculated.append(m_glut)

    # Model 23.8: Mortgage and Permit Divergence (Housing Freeze Index)
    mortgage_rate = series.get("MORTGAGE30US", {}).get("current_value")
    permit_yoy = series.get("PERMIT", {}).get("transformations", {}).get("percent_change_from_year_ago")
    m_housing = calc_housing_freeze_index(mortgage_rate, permit_yoy)
    if m_housing:
        models_calculated.append(m_housing)

    # Model 24: Safe Haven Flight Index
    dtwexbgs_val = series.get("DTWEXBGS", {}).get("current_value")
    m_flight = calc_safe_haven_flight_index(dtwexbgs_val, hy_spread, dgs10_val)
    if m_flight:
        models_calculated.append(m_flight)

    # Model 25: Terms of Trade (TOT)
    export_idx = series.get("IQ", {}).get("current_value")
    import_idx = series.get("IR", {}).get("current_value")
    m_tot = calc_terms_of_trade(export_idx, import_idx)
    if m_tot:
        models_calculated.append(m_tot)

    # Load dynamic EIA series (SPR Stocks, Commercial Crude, US Crude Production, Gasoline Stocks, NatGas Storage)
    eia_json_path = "llms-eia-series.json"
    spr_stocks = None
    commercial_crude_stocks = None
    us_crude_prod = None
    gasoline_stocks = None
    gasoline_stocks_yoy = None
    natgas_storage = None
    natgas_storage_yoy = None
    if os.path.exists(eia_json_path):
        try:
            with open(eia_json_path, "r", encoding="utf-8") as f:
                eia_json = json.load(f)
                eia_series_data = eia_json.get("series", {})
                spr_stocks = eia_series_data.get("PET.WCSSTUS1.W", {}).get("current_value")
                commercial_crude_stocks = eia_series_data.get("PET.WCESTUS1.W", {}).get("current_value")
                us_crude_prod = eia_series_data.get("PET.WCRFPUS2.W", {}).get("current_value")

                gas_entry = eia_series_data.get("PET.WGTSTUS1.W", {})
                gasoline_stocks = gas_entry.get("current_value")
                gasoline_stocks_yoy = gas_entry.get("transformations", {}).get("percent_change_from_year_ago")

                ng_entry = eia_series_data.get("NG.NW2_EPG0_SWO_R48_BCF.W", {})
                natgas_storage = ng_entry.get("current_value")
                natgas_storage_yoy = ng_entry.get("transformations", {}).get("percent_change_from_year_ago")

                if spr_stocks is None:
                    ingestion_warnings.append("EIA PET.WCSSTUS1.W (SPR Stocks) is missing/null.")
                if us_crude_prod is None:
                    ingestion_warnings.append("EIA PET.WCRFPUS2.W (US Crude Production) is missing/null.")
                if gasoline_stocks is None:
                    ingestion_warnings.append("EIA PET.WGTSTUS1.W (Gasoline Stocks) is missing/null.")
        except Exception as e:
            ingestion_warnings.append(f"EIA series read error: {e}")
    else:
        ingestion_warnings.append("EIA series file missing: llms-eia-series.json")

    # Model 25.12: Brent - WTI Spread
    m_spread = calc_brent_wti_spread(brent, wti, commercial_crude_stocks, us_crude_prod)
    if m_spread:
        models_calculated.append(m_spread)

    # Model 25.13: Labor Market Momentum (LMMI)
    m_lmmi = calc_labor_market_momentum_index(payems_curr, payems_yr, unrate_curr, unrate_yr)
    if m_lmmi:
        models_calculated.append(m_lmmi)

    # Model 25.2: Sticky vs. Flexible CPI Spread
    sticky_cpi = series.get("STICKCPIM157SFRBATL", {}).get("current_value")
    flex_cpi = series.get("FLEXCPIM157SFRBATL", {}).get("current_value")
    m_sticky = calc_sticky_flexible_cpi_spread(sticky_cpi, flex_cpi)
    if m_sticky:
        models_calculated.append(m_sticky)

    # Model 25.3: Global Supply Chain Pressure Logistics Engine (NY Fed GSCPI)
    m_gscpi = calc_supply_chain_pressure(gscpi)
    if m_gscpi:
        models_calculated.append(m_gscpi)

    # Model 25.5: Repo Liquidity Friction Spread Engine (SOFR - EFFR)
    m_repo = calc_repo_liquidity_friction_spread(sofr, dff_curr)
    if m_repo:
        models_calculated.append(m_repo)

    # Model 25.6: Gold / Real Yield Debasement Gauge
    dfii10_val = series.get("DFII10", {}).get("current_value")
    gold_yoy = None
    if os.path.exists(wb_json_path):
        try:
            with open(wb_json_path, "r", encoding="utf-8") as f:
                wb_json = json.load(f)
                gold_yoy = wb_json.get("series", {}).get("IND_WB_GOLD", {}).get("transformations", {}).get("percent_change_from_year_ago")
        except Exception:
            gold_yoy = None

    m_debasement = calc_gold_real_yield_debasement(dfii10_val, gold_yoy)
    if m_debasement:
        models_calculated.append(m_debasement)

    # Model 25.7: OVX / VIX Geopolitical Energy Shock Engine
    m_ovx_vix = calc_ovx_vix_risk_premium(ovx, vix)
    if m_ovx_vix:
        models_calculated.append(m_ovx_vix)

    # Model 25.8: Natgas / Crude Oil BTU Disconnect Engine
    natgas_price = series.get("DHHNGSP", {}).get("current_value")
    m_btu = calc_natgas_crude_btu_disconnect(wti, natgas_price, natgas_storage, natgas_storage_yoy)
    if m_btu:
        models_calculated.append(m_btu)

    # Model 25.9: Gasoline / Crude Crack Spread Impulse Engine
    gas_price = series.get("GASREGW", {}).get("current_value")
    m_crack_spread = calc_gasoline_crude_crack_spread(gas_price, wti, gasoline_stocks, gasoline_stocks_yoy)
    if m_crack_spread:
        models_calculated.append(m_crack_spread)

    # Model 25.10: SLOOS Lending Standards Recession Gauge
    drtscis_val = series.get("DRTSCIS", {}).get("current_value")
    m_sloos = calc_sloos_lending_tightness_gauge(drtscis_val)
    if m_sloos:
        models_calculated.append(m_sloos)

    # Model 25.11: Full-Time vs. Involuntary Part-Time Crack Gauge
    pt_curr = series.get("LNS12032194", {}).get("current_value")
    pt_yr = series.get("LNS12032194", {}).get("year_ago_value")
    ft_curr = series.get("LNS12500000", {}).get("current_value")
    ft_yr = series.get("LNS12500000", {}).get("year_ago_value")
    m_pt_crack = calc_hidden_employment_crack_gauge(pt_curr, pt_yr, ft_curr, ft_yr)
    if m_pt_crack:
        models_calculated.append(m_pt_crack)

    # Model 25.17: Liquidity & Commodity Macro Regime Matrix
    brent_yoy = series.get("DCOILBRENTEU", {}).get("transformations", {}).get("percent_change_from_year_ago")
    m_matrix = calc_liquidity_commodity_matrix(dgs3mo, dgs1mo, brent_yoy)
    if m_matrix:
        models_calculated.append(m_matrix)

    # Model 25.14: AI Hardware & Semiconductor Stress
    m_chip = calc_ai_chip_stress_gauge(gscpi, sox_yoy, vix)
    if m_chip:
        models_calculated.append(m_chip)

    # Load dynamic IMF series (BoJ Policy Rate & Saudi Fiscal Breakeven Oil Price)
    imf_json_path = "llms-imf-series.json"
    breakeven_oil = None
    boj_rate = None
    if os.path.exists(imf_json_path):
        try:
            with open(imf_json_path, "r", encoding="utf-8") as f:
                imf_json = json.load(f)
                imf_series_data = imf_json.get("series", {})
                breakeven_oil = imf_series_data.get("SAUPZPIOILBEGUSD", {}).get("current_value")
                boj_rate = imf_series_data.get("JP_FPOLM_PA", {}).get("current_value")
                if breakeven_oil is None:
                    ingestion_warnings.append("IMF SAUPZPIOILBEGUSD is missing/null.")
        except Exception as e:
            breakeven_oil = None
            boj_rate = None
            ingestion_warnings.append(f"IMF IFS read error: {e}")
    else:
        ingestion_warnings.append("IMF series file missing: llms-imf-series.json")

    # Model 25.16: Yen Carry Trade Dissolution (BoJ Policy Rate via IMF / FED DFF)
    dff_val = series.get('DFF', {}).get('current_value')
    jpy_mom = series.get('DEXJPUS', {}).get('transformations', {}).get('percent_change_from_year_ago')

    m_carry = calc_jpy_carry_crack(dff_val, boj_rate, jpy_mom)
    if m_carry:
        models_calculated.append(m_carry)

    sofr = series.get("SOFR", {}).get("current_value")

    # Model 25.18: Mecca Pact Dynamic Transmission Engine
    m_mecca = calc_mecca_pact_transmission(brent, sofr, breakeven_oil)
    if m_mecca:
        models_calculated.append(m_mecca)

    # Model 25.19: Sovereign Synthetic CDS & Actuarial Default Probability Engine
    hy_spread = series.get("BAMLH0A0HYM2", {}).get("current_value")
    m_cds_pd = calc_sovereign_synthetic_cds_pd(hy_spread)
    if m_cds_pd:
        models_calculated.append(m_cds_pd)

    # Model 28.4: Chokepoint Macro Spillover Bridge (Hormuz - Live EIA SPR & US Field Production)
    hormuz_p_net = -0.95  # IL-IR standoff polarity (llms-relationships.txt #2.2.1)
    m_hormuz_bridge = calc_chokepoint_transmission_bridge(
        severity_enum="CATASTROPHIC",
        p_net=hormuz_p_net,
        duration_days=14,
        bypass_capacity_mbpd=4.0,
        spr_stocks_kbbl=spr_stocks,
        gross_flow_mbpd=20.5,
        us_crude_prod_kbpd=us_crude_prod
    )
    if m_hormuz_bridge:
        models_calculated.append(m_hormuz_bridge)

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_dt.isoformat()
    now_utc_str = now_dt.strftime("%Y-%m-%d %H:%M UTC")

    # A) BUILD llms-models.json
    is_success = (len(ingestion_warnings) == 0 and len(models_calculated) >= 42)
    sync_status = "SUCCESS" if is_success else "DEGRADED"

    if not is_success:
        print(
            f"[ERROR] Model refresh is degraded: generated {len(models_calculated)} models (expected >= 42) "
            f"with {len(ingestion_warnings)} ingestion warning(s). Existing snapshots were preserved."
        )
        raise SystemExit(1)

    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "engine": "Autonomous Quantitative Macroeconomic Model Engine",
            "author": "Ersoy Toptaş",
            "license": "CC BY 4.0",
            "sync_status": sync_status,
            "ingestion_health": "OPTIMAL" if not ingestion_warnings else "WARNING",
            "ingestion_warnings": ingestion_warnings,
            "last_successful_sync": now_iso,
            "master_formulas_reference": "https://analysisreports.github.io/llms-formulas.txt",
            "monitored_data_sources": [
                "Federal Reserve Bank of St. Louis (FRED)",
                "European Central Bank (ECB)",
                "World Bank (The Pink Sheet)",
                "International Monetary Fund (IMF)",
                "U.S. Energy Information Administration (EIA)"
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
        "> Ingested Live Time-Series: FRED, ECB, World Bank, IMF & EIA Canonical APIs",
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
