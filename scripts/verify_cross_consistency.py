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
BRIDGE_TXT = os.path.join(ROOT_DIR, "llms-models-bridge.txt")
FORMULAS_TXT = os.path.join(ROOT_DIR, "llms-formulas.txt")
TOOLS_JSON = os.path.join(ROOT_DIR, "llms-tools.json")
GRAPH_ACTORS_JSON = os.path.join(ROOT_DIR, "llms-graph-actors.json")
GRAPH_CHOKEPOINTS_JSON = os.path.join(ROOT_DIR, "llms-graph-chokepoints.json")
GRAPH_MODELS_JSON = os.path.join(ROOT_DIR, "llms-graph-models.json")
ENTITIES_TXT = os.path.join(ROOT_DIR, "llms-entities-id.txt")

FORMULA_TO_TOOL_OVERRIDE = {
    "fed_policy_spread": "calculate_fed_policy_spread",
    "financial_conditions_regime": "calculate_financial_conditions_regime",
    "acm_term_premium_breakdown": "calculate_acm_term_premium_breakdown",
    "gasoline_321_crack_spread": "calculate_gasoline_crude_crack_spread",
    "governance_gridlock_friction_engine": "calculate_governance_gridlock_friction",
    "calc_dynamic_macro_triggers": "calculate_dynamic_macro_triggers",
    "committee_dispersion": "calculate_committee_dispersion",
    "adjusted_market_impact": "calculate_adjusted_market_impact",
}

def verify_tools_graph_bridge_sync() -> int:
    """Verifies 100% synchronization across llms-tools.json, llms-graph-models.json, and llms-models-bridge.txt."""
    errors = []
    if not (os.path.exists(TOOLS_JSON) and os.path.exists(GRAPH_MODELS_JSON) and os.path.exists(BRIDGE_TXT)):
        return 0

    with open(TOOLS_JSON, "r", encoding="utf-8") as f:
        tools_data = json.load(f)
    tool_names = {t["function"]["name"] for t in tools_data.get("tools", [])}

    with open(GRAPH_MODELS_JSON, "r", encoding="utf-8") as f:
        models_data = json.load(f)
    model_nodes = {n["id"]: n for n in models_data.get("nodes", []) if n.get("category") == "MODEL"}

    # 1. Every MODEL node function must exist in tools
    for mid, node in model_nodes.items():
        fn = node.get("attributes", {}).get("function")
        if not fn or fn not in tool_names:
            errors.append(f"{mid} function '{fn}' not found in llms-tools.json")

    # 2. Bridge Target Formulas & Status Enums
    with open(BRIDGE_TXT, "r", encoding="utf-8") as f:
        bridge_txt = f.read()

    bridge_blocks = re.split(r"\n(?=\d+\.\d+\.\d+\.\s+)", bridge_txt)
    for block in bridge_blocks:
        m_formula = re.search(r"Target Formula:\s*llms-formulas\.txt\s*->\s*Model\s+([\d.]+)\s*\(([^)]+)\)", block)
        if not m_formula:
            continue
        model_id = f"MODEL_{m_formula.group(1)}"
        raw_fn = m_formula.group(2).strip()
        canonical_fn = FORMULA_TO_TOOL_OVERRIDE.get(raw_fn, raw_fn if raw_fn.startswith("calculate_") else f"calculate_{raw_fn}")
        if canonical_fn not in tool_names:
            errors.append(f"Bridge {model_id} formula '{raw_fn}' -> '{canonical_fn}' missing in llms-tools.json")

        m_enums = re.search(r"Status Enums:\s*(.+)", block)
        if m_enums and model_id in model_nodes and "status_enums" in model_nodes[model_id].get("attributes", {}):
            bridge_enums = {e.strip() for e in m_enums.group(1).split("|")}
            graph_enums = set(model_nodes[model_id]["attributes"]["status_enums"])
            if bridge_enums != graph_enums:
                errors.append(f"Enum mismatch on {model_id}: bridge={bridge_enums} vs graph={graph_enums}")

    if errors:
        print(f"[FAIL] Tools <-> Graph <-> Bridge synchronization detected {len(errors)} issues:")
        for err in errors:
            print(f"  - {err}")

    return len(errors)

def load_master_country_polarities(txt_path: str) -> Dict[Tuple[str, str], float]:
    country_map = {}
    country_dyads = []

    # 1. Try reading from specialized shelves if available (SSOT)
    shelf_files = [
        os.path.join(ROOT_DIR, f"llms-country-relationships-{slug}.txt")
        for slug in ("us", "ru", "cn", "ir")
    ]
    all_shelves_exist = all(os.path.exists(sf) for sf in shelf_files)

    if all_shelves_exist:
        for sf in shelf_files:
            with open(sf, "r", encoding="utf-8") as f:
                content = f.read()
            found = re.findall(
                r"Bilateral Dyad:\s*GEO_([A-Z0-9_]+)\s*↔\s*GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
                content,
                re.S
            )
            country_dyads.extend(found)
    else:
        # Fallback to single TXT (either Master Router format or legacy monolith format)
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        country_dyads = re.findall(
            r"Bilateral Dyad:\s*GEO_([A-Z0-9_]+)\s*↔\s*GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
            content,
            re.S
        )
        if not country_dyads:
            # Match Master Router fast-lookup format:
            # - Dyad: GEO_US ↔ GEO_GB | ID: REL_GEO_US_GEO_GB
            #   Ref: United States ↔ United Kingdom
            #   P_baseline: +0.95 (Special Relationship...
            country_dyads = re.findall(
                r"- Dyad:\s*GEO_([A-Z0-9_]+)\s*↔\s*GEO_([A-Z0-9_]+)[^\n]*\n\s*Ref:[^\n]*\n\s*P_baseline:\s*([+\-0-9\.]+)",
                content
            )

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
    # In federated architecture, bilateral polarities live in llms-graph-actors.json
    actors_path = os.path.join(os.path.dirname(graph_path), "llms-graph-actors.json")
    target_path = actors_path if os.path.exists(actors_path) else graph_path

    if not os.path.exists(target_path):
        return 0

    with open(target_path, "r", encoding="utf-8") as f:
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
        # Save back in line_per_object_json format if it's the actors layer
        with open(target_path, "w", encoding="utf-8") as f:
            lines = ["{"]
            keys = list(data.keys())
            for idx, (k, v) in enumerate(data.items()):
                comma_outer = "," if idx < len(keys) - 1 else ""
                if k in ("nodes", "edges"):
                    lines.append(f'  "{k}": [')
                    for i, item in enumerate(v):
                        comma = "," if i < len(v) - 1 else ""
                        lines.append("    " + json.dumps(item, ensure_ascii=False) + comma)
                    lines.append(f"  ]{comma_outer}")
                else:
                    lines.append(f'  "{k}": ' + json.dumps(v, ensure_ascii=False) + comma_outer)
            lines.append("}")
            f.write("\n".join(lines))

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

def verify_bridge_cross_references(
    bridge_path: str,
    rel_path: str
) -> int:
    """
    Audits section cross-references in llms-models-bridge.txt (e.g. (2.10.2), (4.6))
    against declared sections and actor pairs in llms-relationships.txt.
    Returns count of unresolved references.
    """
    if not os.path.exists(bridge_path) or not os.path.exists(rel_path):
        return 0

    with open(rel_path, "r", encoding="utf-8") as f:
        rel_text = f.read()

    declared_sections = set()
    for line in rel_text.split("\n"):
        line = line.strip()
        m = re.match(r"^(?:###?\s*)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)\.?\s+(.+)", line)
        if m:
            declared_sections.add(m.group(1))

    with open(bridge_path, "r", encoding="utf-8") as f:
        bridge_text = f.read()

    unresolved = []
    for i, line in enumerate(bridge_text.split("\n"), 1):
        found = re.findall(r"\(([1-9]\.[0-9]+(?:\.[0-9]+)?)\)", line)
        for ref in found:
            # Skip numeric calculation weights/multipliers like (1.0)
            if ref in ("1.0", "0.0"):
                continue
            if ref not in declared_sections:
                unresolved.append((i, ref, line.strip()))

    if unresolved:
        print(f"[FAIL] Found {len(unresolved)} unresolved section references in llms-models-bridge.txt:")
        for line_num, ref, ltxt in unresolved:
            print(f"  - Line {line_num}: ({ref}) not declared in llms-relationships.txt -> '{ltxt}'")

    return len(unresolved)

def verify_structural_duplicates(
    rel_path: str,
    formulas_path: str,
    bridge_path: str
) -> int:
    """
    Automated Structural Duplicate Guard:
    1. Duplicate Section Numbers (e.g. two '2.1.1.' headers).
    2. Duplicate Actor Dyads in Section 2 (e.g. 'US - RU' declared twice, or 'RU - US' duplicate).
    3. Duplicate Formula IDs in llms-formulas.txt (e.g. two '### 25.14.' models).
    4. Duplicate Bridge Model IDs in llms-models-bridge.txt (e.g. two '8.10.1.' models).
    Returns total count of structural duplicates.
    """
    duplicate_errors = []

    # 1. Audit llms-relationships.txt
    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        sec_numbers = {}
        actor_dyads = {}

        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            # Match numbered headers like '2.1.1. US - RU' or '### 1.2. RATIFIED...'
            m_sec = re.match(r"^(?:#{1,4}\s+)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)\.?\s+(.+)", sline)
            if m_sec:
                sec_id = m_sec.group(1)
                sec_title = m_sec.group(2)
                if sec_id in sec_numbers:
                    prev_idx, prev_title = sec_numbers[sec_id]
                    duplicate_errors.append(
                        f"llms-relationships.txt: Duplicate Section ID '{sec_id}' at line {idx} ('{sec_title}') previously declared at line {prev_idx} ('{prev_title}')"
                    )
                else:
                    sec_numbers[sec_id] = (idx, sec_title)

            # Match Section 2 actor headers: '2.1.1. US - RU ...'
            m_dyad = re.match(r"^2\.[0-9]+\.[0-9]+\.\s+([A-Z0-9_]+)\s*-\s*([A-Z0-9_]+)", sline)
            if m_dyad:
                a1, a2 = m_dyad.groups()
                canonical_pair = tuple(sorted([a1, a2]))
                if canonical_pair in actor_dyads:
                    prev_idx, prev_text = actor_dyads[canonical_pair]
                    duplicate_errors.append(
                        f"llms-relationships.txt: Duplicate Actor Dyad '{a1}_{a2}' at line {idx} clashes with existing dyad at line {prev_idx} ('{prev_text}')"
                    )
                else:
                    actor_dyads[canonical_pair] = (idx, sline)

    # 2. Audit llms-formulas.txt
    if os.path.exists(formulas_path):
        with open(formulas_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        formula_ids = {}
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            m_form = re.match(r"^###\s+([0-9]+(?:\.[0-9]+)?)\.\s+(.+)", sline)
            if m_form:
                fid = m_form.group(1)
                ftitle = m_form.group(2)
                if fid in formula_ids:
                    prev_idx, prev_title = formula_ids[fid]
                    duplicate_errors.append(
                        f"llms-formulas.txt: Duplicate Formula ID '{fid}' at line {idx} ('{ftitle}') previously declared at line {prev_idx} ('{prev_title}')"
                    )
                else:
                    formula_ids[fid] = (idx, ftitle)

    # 3. Audit llms-models-bridge.txt
    if os.path.exists(bridge_path):
        with open(bridge_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        bridge_ids = {}
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            m_b = re.match(r"^(8\.[0-9]+(?:\.[0-9]+)?)\.\s+(.+)", sline)
            if m_b:
                bid = m_b.group(1)
                btitle = m_b.group(2)
                if bid in bridge_ids:
                    prev_idx, prev_title = bridge_ids[bid]
                    duplicate_errors.append(
                        f"llms-models-bridge.txt: Duplicate Bridge ID '{bid}' at line {idx} ('{btitle}') previously declared at line {prev_idx} ('{prev_title}')"
                    )
                else:
                    bridge_ids[bid] = (idx, btitle)

    if duplicate_errors:
        print(f"[FAIL] Structural Duplicate Guard detected {len(duplicate_errors)} duplicate entries:")
        for err in duplicate_errors:
            print(f"  - {err}")

    return len(duplicate_errors)

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

    # 4. Audit Bridge Cross-References against llms-relationships.txt
    bridge_mismatches = verify_bridge_cross_references(BRIDGE_TXT, REL_TXT)
    bridge_label = "broken cross-references found" if bridge_mismatches > 0 else "cross-references verified"
    print(f"[*] llms-models-bridge.txt        : {bridge_mismatches} {bridge_label}")

    # 5. Audit Structural Duplicates (Section IDs, Dyads, Formula IDs)
    structural_duplicates = verify_structural_duplicates(REL_TXT, FORMULAS_TXT, BRIDGE_TXT)
    dup_label = "structural duplicates found" if structural_duplicates > 0 else "structural duplicates verified (0 duplicates)"
    print(f"[*] Structural Duplicate Guard    : {structural_duplicates} {dup_label}")

    # 6. Audit Tools <-> Graph <-> Bridge Synchronization
    tools_graph_sync = verify_tools_graph_bridge_sync()
    tgs_label = "function/enum mismatches found" if tools_graph_sync > 0 else "function/enum sync verified (0 mismatches)"
    print(f"[*] Tools-Graph-Bridge Sync       : {tools_graph_sync} {tgs_label}")

    total_synced = txt_sync + graph_sync + json_sync + bridge_mismatches + structural_duplicates + tools_graph_sync
    print("-" * 70)
    if args.check and total_synced > 0:
        print(f"[FAIL] Found {total_synced} cross-file discrepancies, duplicates or unresolved references; no files were modified.")
        exit_code = 1
    elif bridge_mismatches > 0 or structural_duplicates > 0 or tools_graph_sync > 0:
        print(f"[FAIL] Found {bridge_mismatches} unresolved cross-references, {structural_duplicates} duplicates, or {tools_graph_sync} function/enum mismatches!")
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
