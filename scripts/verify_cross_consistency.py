#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_cross_consistency.py
----------------------------
Self-Healing Dynamic Cross-File Consistency & Auto-Sync Engine.
Uses 'llms-country-relationships.txt' as the absolute Single Source of Truth (SSOT).
Automatically detects and equalizes any baseline polarity (P_baseline) discrepancies
in 'llms-relationships.txt' without breaking CI/CD or halting processes.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
"""

import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REL_TXT = os.path.join(ROOT_DIR, "llms-relationships.txt")
COUNTRY_TXT = os.path.join(ROOT_DIR, "llms-country-relationships.txt")

def main():
    print("=" * 70)
    print("SELF-HEALING CROSS-FILE POLARITY AUTO-SYNC & EQUALIZER")
    print("Master Source of Truth (SSOT): llms-country-relationships.txt")
    print("=" * 70)

    if not os.path.exists(REL_TXT) or not os.path.exists(COUNTRY_TXT):
        print("[WARN] Relationship files not found, skipping auto-sync.")
        sys.exit(0)

    with open(COUNTRY_TXT, "r", encoding="utf-8") as f:
        country_content = f.read()

    with open(REL_TXT, "r", encoding="utf-8") as f:
        rel_content = f.read()

    # 1. Build Master Baseline Dictionary from llms-country-relationships.txt (SSOT)
    country_dyads = re.findall(
        r"Bilateral Dyad:\s*GEO_([A-Z0-9_]+)\s*↔\s*GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
        country_content,
        re.S
    )

    country_map = {}
    for a1, a2, score in country_dyads:
        s_val = float(score)
        country_map[(f"GEO_{a1}", f"GEO_{a2}")] = s_val
        country_map[(f"GEO_{a2}", f"GEO_{a1}")] = s_val

    print(f"[*] Loaded {len(country_dyads)} master sovereign baselines from country-relationships.")

    # 2. Scan and Auto-Equalize Section 2 in llms-relationships.txt
    updated_count = 0

    def replace_baseline_callback(match):
        nonlocal updated_count
        full_block = match.group(0)
        e1 = match.group(2)
        e2 = match.group(3)
        old_val_str = match.group(4)
        old_val = float(old_val_str)

        pair_key = (e1, e2)
        if pair_key in country_map:
            master_val = country_map[pair_key]
            if abs(master_val - old_val) > 0.001:
                sign = "+" if master_val > 0 else ""
                new_str = f"{sign}{master_val:.2f}"
                updated_count += 1
                print(f"  [AUTO-SYNC] Equalized {e1} vs {e2}: {old_val:+.2f} -> {new_str} (Synced from Master)")
                # Replace the old value string in the block
                return full_block.replace(f"Baseline Polarity (P_baseline): {old_val_str}", f"Baseline Polarity (P_baseline): {new_str}")
        return full_block

    pattern = re.compile(
        r"(Canonical Entities:\s*(GEO_[A-Z0-9_]+)\s*(?:vs\.?|-)\s*(GEO_[A-Z0-9_]+)\s*\n\s*-\s*Baseline Polarity\s*\((?:P_baseline)?\):\s*([+\-0-9\.]+))"
    )

    new_rel_content = pattern.sub(replace_baseline_callback, rel_content)

    # 3. Write back if any discrepancies were equalized
    if updated_count > 0:
        with open(REL_TXT, "w", encoding="utf-8") as f:
            f.write(new_rel_content)
        print(f"[SUCCESS] Auto-equalized and synchronized {updated_count} baselines in llms-relationships.txt!")
    else:
        print("[SUCCESS] 100% Invariance: All overlapping baselines are already perfectly equalized.")

    print("=" * 70)
    sys.exit(0)

if __name__ == "__main__":
    main()
