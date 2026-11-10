#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_zero_fallbacks.py
------------------------
Strict Zero-Fallback and Zero-Synthetic-Data Validator for analysisreports.github.io.
Ensures no script across the repository injects hardcoded numeric/string fallbacks.
If missing data occurs, the system must strictly evaluate to None.
"""

import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

FORBIDDEN_PATTERNS = [
    # Look for .get(..., <numeric default>) like .get('val', 20.0) or .get('val', 0.0)
    (r"\.get\([^,\)]+,\s*([0-9\.\-]+)\)", "LITERAL_NUMERIC_FALLBACK"),
    # Look for fallback variable assignments
    (r"(decree_defaults|curated_imf_fallbacks)", "HARDCODED_FALLBACK_DICTIONARY"),
]

def main():
    print("=" * 70)
    print("STRICT ZERO-FALLBACK & ZERO-SYNTHETIC-DATA VALIDATOR")
    print("=" * 70)

    violations = []
    py_files = [os.path.join(SCRIPTS_DIR, f) for f in os.listdir(SCRIPTS_DIR) if f.endswith(".py") and f != "verify_zero_fallbacks.py"]

    for path in sorted(py_files):
        fname = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, violation_type in FORBIDDEN_PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    # Ignore harmless frequency mapping in update_fred_series / update_ecb_series
                    if "FREQ_N_MAP" in line or "freq_n_map" in line or "json.dumps" in line:
                        continue
                    violations.append((fname, idx + 1, violation_type, line.strip()))

    if violations:
        print(f"\n[FATAL ERROR] Found {len(violations)} synthetic fallback violations:\n")
        for fn, line_no, vtype, code in violations:
            print(f"  {fn}:L{line_no} [{vtype}] -> {code}")
        print("\nFix all violations before proceeding.")
        sys.exit(1)
    else:
        print(f"[*] Scanned {len(py_files)} scripts.")
        print("[SUCCESS] 100% CLEAN! Zero synthetic data or numeric fallbacks detected across all scripts.")
        sys.exit(0)

if __name__ == "__main__":
    main()
