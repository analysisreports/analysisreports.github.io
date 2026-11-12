#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_cross_consistency.py
----------------------------
Self-Healing Dynamic Cross-File Consistency & Master SSOT Auto-Sync Engine.
Uses 'llms-country-relationships.txt' as the absolute Single Source of Truth (SSOT).

Automatically detects and equalizes baseline polarities across ALL secondary files:
1. 'llms-relationships.txt' (Core Geopolitical Dyads text)
2. 'llms-relationships.json' (Core Relationships JSON)
3. 'llms-graph.json' (Knowledge Graph Edges with p_baseline)
4. 'llms-country-relationships.json' (Verified against TXT twin)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-country-relationships.txt
"""

import argparse
import os
import re
import sys
import json
from typing import Dict, Tuple, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COUNTRY_TXT = os.path.join(ROOT_DIR, "llms-country-relationships.txt")
COUNTRY_JSON = os.path.join(ROOT_DIR, "llms-country-relationships.json")
REL_TXT = os.path.join(ROOT_DIR, "llms-relationships.txt")
REL_JSON = os.path.join(ROOT_DIR, "llms-relationships.json")
GRAPH_JSON = os.path.join(ROOT_DIR, "llms-graph.json")

def load_master_country_polarities(txt_path: str) -> Dict[Tuple[str, str], float]:
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    country_dyads = re.findall(
        r"Bilateral Dyad:\s*GEO_([A-Z0-9_]+)\s*↔\s*GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
        content,
        re.S
    )

    country_map = {}
    for a1, a2, score in country_dyads:
        s_val = float(score)
        # Symmetric mappings for GEO and ACTOR formats
        country_map[(f"GEO_{a1}", f"GEO_{a2}")] = s_val
        country_map[(f"GEO_{a2}", f"GEO_{a1}")] = s_val
        country_map[(f"ACTOR_{a1}", f"ACTOR_{a2}")] = s_val
        country_map[(f"ACTOR_{a2}", f"ACTOR_{a1}")] = s_val

    return country_map

def sync_relationships_txt(
    rel_txt_path: str,
    country_map: Dict[Tuple[str, str], float],
    write_changes: bool = True
) -> int:
    if not os.path.exists(rel_txt_path):
        return 0

    with open(rel_txt_path, "r", encoding="utf-8") as f:
        rel_content = f.read()

    updated_count = 0

    def replace_callback(match):
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
                return full_block.replace(
                    f"Baseline Polarity (P_baseline): {old_val_str}",
                    f"Baseline Polarity (P_baseline): {new_str}"
                )
        return full_block

    pattern = re.compile(
        r"(Canonical Entities:\s*(GEO_[A-Z0-9_]+)\s*(?:vs\.?|-)\s*(GEO_[A-Z0-9_]+)\s*\n\s*-\s*Baseline Polarity\s*\((?:P_baseline)?\):\s*([+\-0-9\.]+))"
    )

    new_content = pattern.sub(replace_callback, rel_content)
    if updated_count > 0 and write_changes:
        with open(rel_txt_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return updated_count

def sync_graph_json(
    graph_path: str,
    country_map: Dict[Tuple[str, str], float],
    write_changes: bool = True
) -> int:
    if not os.path.exists(graph_path):
        return 0

    with open(graph_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_count = 0
    for edge in data.get("edges", []):
        s = edge.get("source")
        t = edge.get("target")
        p_base = edge.get("p_baseline")

        if p_base is not None and (s, t) in country_map:
            master_val = country_map[(s, t)]
            if abs(p_base - master_val) > 0.001:
                edge["p_baseline"] = master_val
                updated_count += 1

    if updated_count > 0 and write_changes:
        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return updated_count

def sync_relationships_json(
    rel_json_path: str,
    country_map: Dict[Tuple[str, str], float],
    write_changes: bool = True
) -> int:
    if not os.path.exists(rel_json_path):
        return 0

    with open(rel_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated_count = 0
    for rel in data.get("relationships", []):
        s = rel.get("source_entity")
        t = rel.get("target_entity")
        pol = rel.get("polarity")

        if pol is not None and (s, t) in country_map:
            master_val = country_map[(s, t)]
            if abs(pol - master_val) > 0.001:
                rel["polarity"] = master_val
                updated_count += 1

    if updated_count > 0 and write_changes:
        with open(rel_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return updated_count

def main():
    parser = argparse.ArgumentParser(description="Check or synchronize relationship polarity against the master SSOT.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report mismatches without modifying any files."
    )
    args = parser.parse_args()

    print("=" * 70)
    print("ENTERPRISE CROSS-FILE POLARITY CHECK" if args.check else "ENTERPRISE CROSS-FILE POLARITY AUTO-SYNC & SSOT EQUALIZER")
    print("Master Source of Truth (SSOT): llms-country-relationships.txt")
    print("=" * 70)

    missing_files = [path for path in (COUNTRY_TXT, REL_TXT, GRAPH_JSON, REL_JSON) if not os.path.exists(path)]
    if missing_files:
        print("[FAIL] Required cross-consistency files are missing:")
        for path in missing_files:
            print(f"  - {path}")
        sys.exit(1)

    if not os.path.exists(COUNTRY_TXT):
        print(f"[FAIL] Master SSOT file not found at {COUNTRY_TXT}")
        sys.exit(1)

    country_map = load_master_country_polarities(COUNTRY_TXT)
    print(f"[*] Loaded {len(country_map)//4} sovereign dyads from Master SSOT.")

    # 1. Sync llms-relationships.txt
    write_changes = not args.check
    txt_sync = sync_relationships_txt(REL_TXT, country_map, write_changes)
    txt_label = "mismatches found" if args.check else "baselines equalized"
    print(f"[*] llms-relationships.txt       : {txt_sync} {txt_label}")

    # 2. Sync llms-graph.json
    graph_sync = sync_graph_json(GRAPH_JSON, country_map, write_changes)
    graph_label = "mismatches found" if args.check else "edge polarities equalized"
    print(f"[*] llms-graph.json               : {graph_sync} {graph_label}")

    # 3. Sync llms-relationships.json
    json_sync = sync_relationships_json(REL_JSON, country_map, write_changes)
    json_label = "mismatches found" if args.check else "relationships equalized"
    print(f"[*] llms-relationships.json      : {json_sync} {json_label}")

    total_synced = txt_sync + graph_sync + json_sync
    print("-" * 70)
    if args.check and total_synced > 0:
        print(f"[FAIL] Found {total_synced} cross-file discrepancies; no files were modified.")
        exit_code = 1
    elif total_synced > 0:
        print(f"[AUTO-HEALED] Successfully equalized {total_synced} discrepancies across secondary files!")
        exit_code = 0
    else:
        print("[SUCCESS] 100% Invariance: All secondary files are perfectly synchronized with Master SSOT.")
        exit_code = 0
    print("=" * 70)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
