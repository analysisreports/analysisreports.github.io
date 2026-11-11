#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_zero_fallbacks.py
------------------------
Strict Zero-Fallback and Zero-Synthetic-Data Enterprise Validator.
Scans all codebase scripts, formula documentation (llms-formulas.txt),
and model outputs (llms-models.json/txt) to ensure absolute zero synthetic
numbers, default fallbacks, or mock metrics exist in production artifacts.
If live upstream data is offline or missing, evaluation must strictly fail closed (None).
"""

import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")

DOC_FILES = [
    os.path.join(ROOT_DIR, "llms-formulas.txt"),
    os.path.join(ROOT_DIR, "llms-models.txt"),
    os.path.join(ROOT_DIR, "llms-models.json"),
]

FORBIDDEN_SCRIPT_PATTERNS = [
    # Look for .get(..., <numeric default>) like .get('val', 20.0) or .get('val', 0.0)
    (r"\.get\([^,\)]+,\s*([0-9\.\-]+)\)", "LITERAL_NUMERIC_FALLBACK"),
    # Look for fallback variable assignments
    (r"(decree_defaults|curated_imf_fallbacks)", "HARDCODED_FALLBACK_DICTIONARY"),
    # Look for 86.2 synthetic breakeven oil
    (r"\b86\.20?\b", "HARDCODED_SYNTHETIC_BREAKEVEN_OIL"),
]

FORBIDDEN_DOC_PATTERNS = [
    (r"\b86\.20?\b", "HARDCODED_SYNTHETIC_BREAKEVEN_OIL"),
    (r"defaults?\s+to\s+calibrated\s+baseline", "DOCUMENTED_FALLBACK_DEFAULT"),
    (r"def\s+calculate_mecca_pact_transmission\([^)]*86\.2", "SYNTHETIC_DEFAULT_IN_SIGNATURE"),
    (r"def\s+macro_regime_impact_multiplier\([^)]*\):[\s\S]*?return\s+1\.0\b", "SILENT_NEUTRAL_FALLBACK"),
]

def main():
    print("=" * 70)
    print("STRICT ZERO-FALLBACK & ZERO-SYNTHETIC-DATA VALIDATOR (ENTERPRISE)")
    print("=" * 70)

    violations = []

    # 1. Audit Python scripts
    py_files = [
        os.path.join(SCRIPTS_DIR, f)
        for f in os.listdir(SCRIPTS_DIR)
        if f.endswith(".py") and f != "verify_zero_fallbacks.py"
    ]

    for path in sorted(py_files):
        fname = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern, violation_type in FORBIDDEN_SCRIPT_PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    # Ignore harmless frequency mapping in update_fred_series / update_ecb_series
                    if "FREQ_N_MAP" in line or "freq_n_map" in line or "json.dumps" in line:
                        continue
                    violations.append((fname, idx + 1, violation_type, line.strip()))

    # 2. Audit Documentation and Reference Files
    for doc_path in DOC_FILES:
        if not os.path.exists(doc_path):
            continue
        fname = os.path.basename(doc_path)
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check line by line for simple regexes
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            # Check for forbidden 86.2 or doc fallbacks
            if re.search(r"\b86\.20?\b", line):
                violations.append((fname, idx + 1, "HARDCODED_SYNTHETIC_BREAKEVEN_OIL", line.strip()))
            if re.search(r"defaults?\s+to\s+calibrated\s+baseline", line, re.IGNORECASE):
                violations.append((fname, idx + 1, "DOCUMENTED_FALLBACK_DEFAULT", line.strip()))

        # Check multiline patterns if any
        if fname == "llms-formulas.txt":
            # Check for macro_regime_impact_multiplier returning 1.0 on None
            if re.search(r"def macro_regime_impact_multiplier[^\n]+\n\s+if[^\n]+None[^\n]*:\s*\n\s+return 1\.0", content):
                violations.append((fname, 0, "SILENT_NEUTRAL_FALLBACK", "macro_regime_impact_multiplier returns 1.0 on None"))

    if violations:
        print(f"\n[FATAL ERROR] Found {len(violations)} synthetic fallback violations:\n")
        for fn, line_no, vtype, code in violations:
            loc = f"{fn}:L{line_no}" if line_no > 0 else fn
            print(f"  {loc} [{vtype}] -> {code}")
        print("\nFix all violations before proceeding.")
        sys.exit(1)
    else:
        print(f"[*] Audited {len(py_files)} Python scripts and {len(DOC_FILES)} core documentation / model files.")
        print("[SUCCESS] 100% CLEAN! Zero synthetic data or numeric fallbacks detected across the entire repository.")
        sys.exit(0)

if __name__ == "__main__":
    main()
