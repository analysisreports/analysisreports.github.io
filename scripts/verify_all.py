#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_all.py
--------------
Master Enterprise Orchestrator & Unified CI/CD Continuous Quality Suite.

Runs the complete 8-pillar institutional verification pipeline:
1. Entity Dictionary Compliance (verify_entities.py)
2. Zero-Synthetic-Data & Fallback Validator (verify_zero_fallbacks.py)
3. Cross-File Polarity Auto-Sync & SSOT Equalizer (verify_cross_consistency.py)
4. Geopolitical Dyad Symmetry & Hub Isolation Auditor (verify_dyad_integrity.py)
5. Chronological & Treaty Sequence Sanity Auditor (verify_temporal_sanity.py)
6. Knowledge Graph Topology & Edge Integrity Auditor (verify_graph_topology.py)
7. Quantitative Models Stress & Numerical Stability Auditor (verify_model_stress.py)
8. LLM Tool Specification & Function Calling Schema Auditor (verify_tools_schema.py)

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/
"""

import os
import sys
import time
import subprocess
from typing import List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

TEST_SUITE: List[Tuple[str, str, str, Tuple[str, ...]]] = [
    ("Entity Dictionary Compliance", "verify_entities.py", "388 Valid Entities across 40 Dynamic Files", ()),
    ("Zero-Synthetic-Data & Fallback Guard", "verify_zero_fallbacks.py", "100% Real API Ingestion, Zero Mocks", ()),
    ("Cross-File Polarity Consistency (SSOT)", "verify_cross_consistency.py", "Read-only Single Source of Truth check", ("--check",)),
    ("Dyad Symmetry & Hub Isolation Guard", "verify_dyad_integrity.py", "165 Dyads, 0 Leaks, 100% Symmetric Mirrors", ()),
    ("Chronological & Treaty Temporal Sanity", "verify_temporal_sanity.py", "Sequence (Sign<=Enact), Watersheds, 2026 Horizon", ()),
    ("Knowledge Graph Topology & Edge Integrity", "verify_graph_topology.py", "Topological Health, Zero Broken Edges, SSOT Polarity Invariance", ()),
    ("Quantitative Models Stress & Stability", "verify_model_stress.py", "42 Active Models, Zero NaN/Inf under Crisis Shocks", ()),
    ("LLM Tool Specification & Schema Integrity", "verify_tools_schema.py", "63 Active Tools, Zero Schema Defects, 100% Parameter Coverage", ())
]

def run_step(title: str, script_name: str, desc: str, args: Tuple[str, ...]) -> Tuple[bool, float, str]:
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        return False, 0.0, f"Script not found: {script_path}"

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, script_path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=ROOT_DIR
        )
        duration = time.perf_counter() - start
        success = (proc.returncode == 0)
        output = proc.stdout if success else (proc.stdout + "\n" + proc.stderr)
        return success, duration, output
    except Exception as e:
        duration = time.perf_counter() - start
        return False, duration, str(e)

def main():
    print("=" * 78)
    print("      ANALYSIS REPORTS - ENTERPRISE AUTOMATED VERIFICATION SUITE")
    print(f"      Horizon: November 2026 | Environment: Production CI/CD")
    print("=" * 78)

    results = []
    total_start = time.perf_counter()

    for idx, (title, script_name, desc, args) in enumerate(TEST_SUITE, 1):
        print(f"[*] Step {idx}/{len(TEST_SUITE)}: Running {title} ...", end="", flush=True)
        success, duration, out = run_step(title, script_name, desc, args)
        status_str = "[ PASS ]" if success else "[ FAIL ]"
        print(f"\r  {status_str} Step {idx}/{len(TEST_SUITE)}: {title:<40} ({duration:.2f}s)")
        results.append((title, script_name, desc, success, duration, out))

    total_duration = time.perf_counter() - total_start

    print("\n" + "=" * 78)
    print(f"                     PIPELINE EXECUTION SUMMARY")
    print("=" * 78)

    all_passed = True
    for title, script_name, desc, success, duration, _ in results:
        status_tag = "✔ PASSED" if success else "✖ FAILED"
        if not success:
            all_passed = False
        print(f"  {status_tag:<10} | {title:<42} | {desc}")

    print("-" * 78)
    print(f"  Total Duration: {total_duration:.2f} seconds | Test Pillars: {len(TEST_SUITE)} Automated Engines")

    if all_passed:
        print("=" * 78)
        print("  >>> SYSTEM HEALTH: 100% OPERATIONAL | ZERO DEFECTS DETECTED <<<")
        print("=" * 78)
        sys.exit(0)
    else:
        print("=" * 78)
        print("  >>> SYSTEM ALERT: DEFECTS DETECTED IN PIPELINE! INSPECT LOGS. <<<")
        print("=" * 78)
        for title, script_name, desc, success, duration, out in results:
            if not success:
                print(f"\n--- FAILED: {title} ({script_name}) ---")
                print(out.strip())
        sys.exit(1)

if __name__ == "__main__":
    main()
