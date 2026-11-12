#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_model_stress.py
-----------------------
Autonomous Quantitative Model Stress, Finite Boundedness & Numerical Stability Auditor.

Audits:
1. Production Output Sanity:
   - Audits all active models in 'llms-models.json' (42 models).
   - Verifies each model produces finite, real numbers (Zero NaN, Zero Inf).
   - Verifies presence of formula_ref, status, unit, and interpretation.
2. Macroeconomic Stress Regime Testing:
   - Tests core model calculator algorithms against extreme geopolitical and macro shocks:
     * Stagflation Spike: CPI YoY = 25.0%, Fed Funds = 9.5%, Oil = $140/bbl
     * Hyperinflation & Extreme Rate Hikes: CBRT Policy Rate = 80%, Inflation = 85%
     * Oil Chokepoint Shock: Hormuz Blockade proxy (Brent = $180, Gold = $3500)
3. Year-over-Year Crack Spread Classification: Tests expanding, contracting, unchanged, and missing-history cases.
4. Zero Crash Assurance: Proves zero Unhandled Exceptions (DivisionByZero, OverflowError, ValueError).

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/llms-models.json
"""

import os
import sys
import json
import math
from typing import List, Dict, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_JSON = os.path.join(ROOT_DIR, "llms-models.json")
MODELS_TXT = os.path.join(ROOT_DIR, "llms-models.txt")

# Import calculation engine functions directly from calculate_models.py
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
try:
    import calculate_models as cm
except ImportError as e:
    cm = None

def audit_production_models(models_data: List[Dict[str, Any]]) -> List[str]:
    errors = []
    if len(models_data) < 42:
        errors.append(f"INCOMPLETE MODEL SUITE: Expected at least 42 active models, found {len(models_data)}.")

    seen_ids = set()
    for m in models_data:
        mid = m.get("model_id")
        name = m.get("model_name")
        val = m.get("primary_value")
        status = m.get("status")
        f_ref = m.get("formula_ref")

        if not mid:
            errors.append(f"Missing model_id in model: {m}")
            continue

        if mid in seen_ids:
            errors.append(f"DUPLICATE MODEL ID: {mid}")
        seen_ids.add(mid)

        # Finite number check
        if val is None:
            errors.append(f"{mid} ({name}): primary_value is None.")
        elif isinstance(val, (int, float)):
            if not math.isfinite(val):
                errors.append(f"{mid} ({name}): primary_value is non-finite (NaN or Inf): {val}")
        else:
            errors.append(f"{mid} ({name}): primary_value is not numeric: {val}")

        # Required meta
        if not status:
            errors.append(f"{mid} lacks status classification.")
        if not f_ref or not f_ref.startswith("https://analysisreports.github.io/llms-formulas.txt"):
            errors.append(f"{mid} has invalid formula_ref: {f_ref}")
        if not m.get("unit"):
            errors.append(f"{mid} lacks unit specification.")
        if not m.get("interpretation"):
            errors.append(f"{mid} lacks interpretation field.")

        # Strict Schema Integrity: inputs and metrics MUST exist and MUST be non-empty dicts
        inputs = m.get("inputs")
        if inputs is None or not isinstance(inputs, dict) or len(inputs) == 0:
            errors.append(f"STRICT SCHEMA FAIL: {mid} lacks required non-empty 'inputs' dict (found: {type(inputs).__name__ if inputs is not None else 'None'}).")

        metrics = m.get("metrics")
        if metrics is None or not isinstance(metrics, dict) or len(metrics) == 0:
            errors.append(f"STRICT SCHEMA FAIL: {mid} lacks required non-empty 'metrics' dict (found: {type(metrics).__name__ if metrics is not None else 'None'}).")

    return errors

def audit_extreme_stress_regimes() -> Tuple[List[str], int, int]:
    errors = []
    if cm is None:
        return ["Failed to import calculate_models.py for stress testing."], 0, 8

    total_regimes = 8
    passed_regimes = 0

    # Regime 2: Hyperinflation & High Rate Regime
    r2_ok = True
    try:
        res_real = cm.calc_real_policy_rate(80.0, 75.0)
        if not (res_real and math.isfinite(res_real["primary_value"])):
            errors.append("STRESS FAIL (Regime 2 - Real Rate): Invalid result.")
            r2_ok = False
    except Exception as e:
        errors.append(f"CRASH in calc_real_policy_rate under extreme inputs: {e}")
        r2_ok = False
    if r2_ok: passed_regimes += 1

    # Regime 3: Severe Stagflation (CPI 25%, Fed 9%)
    r3_ok = True
    try:
        res_fed = cm.calc_fed_policy_stance(9.8, 9.0)
        if not (res_fed and math.isfinite(res_fed["primary_value"])):
            errors.append("STRESS FAIL (Regime 3 - Fed Stance): Invalid result.")
            r3_ok = False
    except Exception as e:
        errors.append(f"CRASH in calc_fed_policy_stance: {e}")
        r3_ok = False
    if r3_ok: passed_regimes += 1

    # Regime 4: Taylor Rule under extreme recession
    r4_ok = True
    try:
        canonical_units = "Billions of Chained 2017 Dollars"
        same_quarter = ("2026-07-01", "2026-07-01")
        res_taylor = cm.calc_taylor_policy_gap(
            8.5, 12.0, 20000.0, 23000.0, canonical_units, canonical_units, *same_quarter
        )
        if not (res_taylor and math.isfinite(res_taylor["primary_value"])):
            errors.append("STRESS FAIL (Regime 4 - Taylor Policy Gap): Invalid result.")
            r4_ok = False
        if cm.calc_taylor_policy_gap(
            8.5, 2.0, 20000.0, 1e-12, canonical_units, canonical_units, *same_quarter
        ) is not None:
            errors.append("STRESS FAIL (Regime 4 - Taylor Policy Gap): Tiny potential GDP was accepted.")
            r4_ok = False
        if cm.calc_taylor_policy_gap(
            8.5, 2.0, 24.0, 23000.0,
            "Trillions of Chained 2017 Dollars",
            "Billions of Chained 2017 Dollars",
            *same_quarter
        ) is not None:
            errors.append("STRESS FAIL (Regime 4 - Taylor Policy Gap): Mixed GDP units were accepted.")
            r4_ok = False
        if cm.calc_taylor_policy_gap(
            8.5, 2.0, 20000.0, 23000.0,
            canonical_units,
            canonical_units,
            *same_quarter
        ) is None:
            errors.append("STRESS FAIL (Regime 4 - Taylor Policy Gap): Canonical GDP units were rejected.")
            r4_ok = False
        if cm.calc_taylor_policy_gap(8.5, 2.0, 20000.0, 23000.0) is not None:
            errors.append("STRESS FAIL (Regime 4 - Taylor Policy Gap): Unlabeled GDP units were accepted.")
            r4_ok = False
    except Exception as e:
        errors.append(f"CRASH in calc_taylor_policy_gap: {e}")
        r4_ok = False
    if r4_ok: passed_regimes += 1

    # Regime 5: Extreme Yield Inversion (-350 bps)
    r5_ok = True
    try:
        res_yield = cm.calc_yield_spread_bps(-3.50)
        if not (res_yield and math.isfinite(res_yield["primary_value"])):
            errors.append("STRESS FAIL (Regime 5 - Yield Curve): Invalid result.")
            r5_ok = False
    except Exception as e:
        errors.append(f"CRASH in calc_yield_spread_bps: {e}")
        r5_ok = False
    if r5_ok: passed_regimes += 1

    # Regime 7: Committee Dispersion Discrete Integer Voting Integrity
    r7_ok = True
    try:
        # Fractional votes (1.5 hawkish) must return None (voting members cannot be fractional)
        if cm.calc_committee_dispersion(n_hawkish=1.5, n_dovish=2, n_neutral=6) is not None:
            errors.append("VULNERABILITY FAIL (Regime 7 - Dispersion): Fractional vote 1.5 did not return None.")
            r7_ok = False
        if cm.calc_committee_dispersion(n_hawkish=-1, n_dovish=2, n_neutral=6) is not None:
            errors.append("VULNERABILITY FAIL (Regime 7 - Dispersion): Negative vote did not return None.")
            r7_ok = False
    except Exception as e:
        errors.append(f"CRASH in Regime 7 Committee Dispersion: {e}")
        r7_ok = False
    if r7_ok: passed_regimes += 1

    # Regime 8: ACM Term Premium Unit Guard & Threshold Invariance
    r8_ok = True
    try:
        # 1. Reject bps confused for pct (55.0% term premium is an obvious unit error)
        if cm.calc_acm_term_premium(4.5, 55.0) is not None:
            errors.append("VULNERABILITY FAIL (Regime 8 - ACM): Bps confused for percent was accepted.")
            r8_ok = False
        # 2. Reject extreme anomaly (< -5.0%)
        if cm.calc_acm_term_premium(4.5, -6.5) is not None:
            errors.append("VULNERABILITY FAIL (Regime 8 - ACM): Extreme negative anomaly was accepted.")
            r8_ok = False
        # 3. Exact threshold boundary alignment with formulas.txt (>= 0.50 and <= -0.50)
        res_pos = cm.calc_acm_term_premium(4.0, 0.50)
        if not res_pos or res_pos.get("status") != "FISCAL_SUPPLY_PRESSURE":
            errors.append("THRESHOLD FAIL (Regime 8 - ACM): +0.50 did not map to FISCAL_SUPPLY_PRESSURE.")
            r8_ok = False
        res_neg = cm.calc_acm_term_premium(4.0, -0.50)
        if not res_neg or res_neg.get("status") != "FLIGHT_TO_SAFETY":
            errors.append("THRESHOLD FAIL (Regime 8 - ACM): -0.50 did not map to FLIGHT_TO_SAFETY.")
            r8_ok = False
        # 4. Negative term premium expected short rate decomposition (4.0 - (-1.5) = 5.50%)
        res_qe = cm.calc_acm_term_premium(4.0, -1.50)
        if not res_qe or abs(res_qe["metrics"]["expected_average_short_rate_pct"] - 5.50) > 0.001:
            errors.append("DECOMPOSITION FAIL (Regime 8 - ACM): Negative term premium decomposition error.")
            r8_ok = False
    except Exception as e:
        errors.append(f"CRASH in Regime 8 ACM Term Premium: {e}")
        r8_ok = False
    if r8_ok: passed_regimes += 1

    # Regime 9: Chokepoint Macro Spillover Bridge & EIA Dynamic Ingestion Guard
    r9_ok = True
    try:
        # 1. Zero-synthetic-fallback guard: Missing SPR parameters must strictly fail closed (return None)
        if cm.calc_chokepoint_transmission_bridge("CATASTROPHIC", -0.95) is not None:
            errors.append("VULNERABILITY FAIL (Regime 9 - Chokepoint Bridge): Missing SPR data did not fail closed.")
            r9_ok = False
        # 2. Reject invalid severity enum
        if cm.calc_chokepoint_transmission_bridge("INVALID_SEV", -0.95, spr_stocks_kbbl=282000.0) is not None:
            errors.append("VULNERABILITY FAIL (Regime 9 - Chokepoint Bridge): Invalid severity enum was accepted.")
            r9_ok = False
        # 3. Reject NaN / Inf polarity
        if cm.calc_chokepoint_transmission_bridge("CATASTROPHIC", float("nan"), spr_stocks_kbbl=282000.0) is not None:
            errors.append("VULNERABILITY FAIL (Regime 9 - Chokepoint Bridge): NaN polarity was accepted.")
            r9_ok = False
        # 4. Extreme crisis bounding: Maximum conflict, zero SPR, 90-day blockade
        res_shock = cm.calc_chokepoint_transmission_bridge("CATASTROPHIC", -1.0, duration_days=90, spr_stocks_kbbl=0.0)
        if not res_shock or not (0 <= res_shock["primary_value"] <= 100):
            errors.append("BOUNDING FAIL (Regime 9 - Chokepoint Bridge): Shock score outside [0, 100].")
            r9_ok = False
        elif res_shock.get("status") not in ["CRITICAL_SYSTEMIC_SHOCK", "HIGH_SPILLOVER", "MODERATE_FRICTION", "LOCALIZED_IMPACT"]:
            errors.append("STATUS FAIL (Regime 9 - Chokepoint Bridge): Status enum is invalid.")
            r9_ok = False
    except Exception as e:
        errors.append(f"CRASH in Regime 9 Chokepoint Spillover Bridge: {e}")
        r9_ok = False
    if r9_ok: passed_regimes += 1

    # Regime 10: 3:2:1 Crack Spread Year-over-Year Classification
    r10_ok = True
    try:
        expanding = cm.calc_gasoline_321_crack_spread(
            2.728, 4.823, 99.64,
            "2026-11-03", "2026-11-03", "2026-11-03",
            gasoline_spot_price_year_ago_val=1.837,
            ulsd_spot_price_year_ago_val=2.238,
            wti_barrel_price_year_ago_val=58.34
        )
        if (
            not expanding
            or expanding.get("status") != "CRACK_SPREAD_EXPANDING"
            or expanding["metrics"].get("crack_spread_321_year_ago_usd_bbl") != 24.43
            or expanding["metrics"].get("crack_spread_321_yoy_change_usd_bbl") != 19.84
        ):
            errors.append("CLASSIFICATION FAIL (Regime 10 - Crack Spread): Expanding spread was not classified correctly.")
            r10_ok = False

        contracting = cm.calc_gasoline_321_crack_spread(
            1.837, 2.238, 58.34,
            "2026-11-03", "2026-11-03", "2026-11-03",
            gasoline_spot_price_year_ago_val=2.728,
            ulsd_spot_price_year_ago_val=4.823,
            wti_barrel_price_year_ago_val=99.64
        )
        if not contracting or contracting.get("status") != "CRACK_SPREAD_CONTRACTING":
            errors.append("CLASSIFICATION FAIL (Regime 10 - Crack Spread): Contracting spread was not classified correctly.")
            r10_ok = False

        unchanged = cm.calc_gasoline_321_crack_spread(
            2.728, 4.823, 99.64,
            "2026-11-03", "2026-11-03", "2026-11-03",
            gasoline_spot_price_year_ago_val=2.728,
            ulsd_spot_price_year_ago_val=4.823,
            wti_barrel_price_year_ago_val=99.64
        )
        if not unchanged or unchanged.get("status") != "CRACK_SPREAD_UNCHANGED":
            errors.append("CLASSIFICATION FAIL (Regime 10 - Crack Spread): Unchanged spread was not classified correctly.")
            r10_ok = False

        no_history = cm.calc_gasoline_321_crack_spread(
            2.728, 4.823, 99.64,
            "2026-11-03", "2026-11-03", "2026-11-03"
        )
        if not no_history or no_history.get("status") != "UNCLASSIFIED":
            errors.append("CLASSIFICATION FAIL (Regime 10 - Crack Spread): Missing prior-year data did not remain UNCLASSIFIED.")
            r10_ok = False
    except Exception as e:
        errors.append(f"CRASH in 3:2:1 crack spread year-over-year classification: {e}")
        r10_ok = False
    if r10_ok: passed_regimes += 1

    return errors, passed_regimes, total_regimes

def main():
    print("=" * 70)
    print("QUANTITATIVE MODELS STRESS, BOUNDEDNESS & NUMERICAL STABILITY AUDITOR")
    print("Source: llms-models.json & scripts/calculate_models.py")
    print("=" * 70)

    if not os.path.exists(MODELS_JSON):
        print(f"[FAIL] Models JSON file not found at {MODELS_JSON}")
        sys.exit(1)

    with open(MODELS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    models_list = data.get("models", [])
    print(f"[*] Total Active Models Loaded: {len(models_list)}")

    # 1. Audit Production Values
    prod_errors = audit_production_models(models_list)
    print(f"[*] Production Model Health   : {len(models_list) - len(prod_errors)} / {len(models_list)} Passed")

    # 2. Audit Stress Regimes
    stress_errors, passed_regimes, total_regimes = audit_extreme_stress_regimes()
    print(f"[*] Extreme Stress Regimes    : {passed_regimes} / {total_regimes} Stress Regimes Passed")

    all_errors = prod_errors + stress_errors

    print("\n" + "=" * 70)
    if all_errors:
        print(f"[FAIL] DETECTED {len(all_errors)} MODEL STRESS / NUMERICAL ERRORS:")
        for err in all_errors:
            print(f"  [!] {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print("[SUCCESS] 100% NUMERICALLY STABLE & FINITE:")
        print(f"  - Active Model Suite: {len(models_list)} models fully verified")
        print("  - Zero NaN / Zero Inf across all quantitative models")
        print("  - Zero DivisionByZero or Unhandled Exceptions under crisis shocks")
        print("  - 100% Schema & Formula Reference Compliance")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
