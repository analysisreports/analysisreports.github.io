#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_country_relationships.py
--------------------------------
Deterministic Sovereign Dyadic Relationship Parser & Atomic Machine-Readable Twin Generator.
Parses 'llms-country-relationships.txt' and safely produces 'llms-country-relationships.json'.

Key Architecture Upgrades:
1. Anchor-driven Block Splitting: Anchored strictly on 'Bilateral Dyad:' and 'SOVEREIGN HUB:' (horizontal lines are ignored).
2. Explicit Line Number Reporting: Any syntax or schema flaw raises a ValueError with exact line numbers.
3. Zero Silent Dropping: Required fields, vectors (>=2), and flashpoints (>=1) are strictly validated.
4. Global Uniqueness & Boundary Guard: Detects duplicate dyad IDs and boundary leakage.
5. Atomic File Replacement: Validates in-memory first; writes to temporary file before atomic rename.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-country-relationships.txt
JSON Twin: https://analysisreports.github.io/llms-country-relationships.json
"""

import os
import re
import sys
import json
import math
import datetime
from typing import Dict, Any, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TXT_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.txt")
JSON_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.json")

def process_block(blk_lines: List[str], start_line: int, current_hub: str, seen_dyad_ids: Dict[str, int]) -> Dict[str, Any]:
    if not blk_lines:
        raise ValueError(f"[Line {start_line}] Empty dyad block encountered under Hub '{current_hub}'.")

    text = "\n".join(blk_lines)

    # 1. Bilateral Dyad Header
    dyad_m = re.search(r"^Bilateral Dyad:\s*(GEO_[A-Z0-9_]+)\s*↔\s*(GEO_[A-Z0-9_]+)", text, re.M)
    if not dyad_m:
        raise ValueError(f"[Line {start_line}] Malformed or missing 'Bilateral Dyad' header.")
    actor_1 = dyad_m.group(1).strip()
    actor_2 = dyad_m.group(2).strip()

    # Boundary Leak Guard
    if actor_1 != current_hub:
        raise ValueError(
            f"[Line {start_line}] BOUNDARY LEAK: Actor 1 '{actor_1}' does not match current Sovereign Hub '{current_hub}'."
        )

    # 2. Common Reference
    ref_m = re.search(r"^Common Reference:\s*(.+)", text, re.M)
    if not ref_m:
        raise ValueError(f"[Line {start_line}] Missing 'Common Reference' in dyad {actor_1} ↔ {actor_2}.")
    common_ref = ref_m.group(1).strip()

    # 3. Dyad ID
    id_m = re.search(r"^Dyad ID:\s*(REL_GEO_[A-Z0-9_]+_GEO_[A-Z0-9_]+)", text, re.M)
    if not id_m:
        raise ValueError(f"[Line {start_line}] Missing or invalid 'Dyad ID' for {actor_1} ↔ {actor_2}.")
    dyad_id = id_m.group(1).strip()
    expected_id = f"REL_{actor_1}_{actor_2}"
    if dyad_id != expected_id:
        raise ValueError(f"[Line {start_line}] ID MISMATCH: Found '{dyad_id}', expected '{expected_id}'.")

    # Duplicate ID Check
    if dyad_id in seen_dyad_ids:
        prev_line = seen_dyad_ids[dyad_id]
        raise ValueError(f"[Line {start_line}] DUPLICATE DYAD ID '{dyad_id}': Previously defined at line {prev_line}.")
    seen_dyad_ids[dyad_id] = start_line

    # 4. Bilateral Stance & Classification
    stance_m = re.search(r"^Bilateral Stance:\s*([+\-0-9\.]+)\s*\((.+?)\)", text, re.M)
    if not stance_m:
        raise ValueError(f"[Line {start_line}] Missing or malformed 'Bilateral Stance' for {dyad_id}.")
    try:
        stance_val = float(stance_m.group(1))
    except ValueError:
        raise ValueError(f"[Line {start_line}] Non-numeric Bilateral Stance '{stance_m.group(1)}' in {dyad_id}.")

    if not math.isfinite(stance_val) or not (-1.0 <= stance_val <= 1.0):
        raise ValueError(f"[Line {start_line}] Out-of-bounds Bilateral Stance {stance_val} in {dyad_id} (Must be [-1.0, 1.0]).")
    stance_class = stance_m.group(2).strip()

    # 5. Strategic Category
    cat_m = re.search(r"^Strategic Category:\s*(.+)", text, re.M)
    if not cat_m:
        raise ValueError(f"[Line {start_line}] Missing 'Strategic Category' in {dyad_id}.")
    strat_cat = cat_m.group(1).strip()

    # 6. Asymmetric Power Vectors & Flashpoints parsing
    vectors = []
    flashpoints = []
    cross_refs = []

    in_vectors = False
    in_flashpoints = False

    for l in blk_lines:
        l_str = l.strip()
        if l_str.startswith("Asymmetric Power Vectors:"):
            in_vectors = True
            in_flashpoints = False
            continue
        elif l_str.startswith("Core Strategic Flashpoints:"):
            in_vectors = False
            in_flashpoints = True
            continue
        elif l_str.startswith("Cross-Reference Multilateral Nodes:"):
            in_vectors = False
            in_flashpoints = False
            raw_refs = l_str.split(":", 1)[1].strip()
            cross_refs = [r.strip() for r in raw_refs.split(",") if r.strip()]
            continue

        if in_vectors and l_str.startswith("-"):
            vec_m = re.match(r"^-\s*\[([^\]]+)\]\s*([^:]+):\s*(.*)$", l_str)
            if vec_m:
                raw_holder = vec_m.group(1).strip()
                holder = re.sub(r"\s+Leverage$", "", raw_holder).strip()
                domain = vec_m.group(2).strip()
                desc = vec_m.group(3).strip()
                vectors.append({
                    "leverage_holder": holder,
                    "domain": domain,
                    "description": desc
                })
            else:
                parts = l_str[1:].split(":", 1)
                if len(parts) == 2:
                    vectors.append({
                        "leverage_holder": "Unspecified",
                        "domain": parts[0].strip(),
                        "description": parts[1].strip()
                    })
        elif in_flashpoints and re.match(r"^\d+\.", l_str):
            flashpoints.append(re.sub(r"^\d+\.\s*", "", l_str))

    if len(vectors) < 2:
        raise ValueError(f"[Line {start_line}] {dyad_id} has {len(vectors)} asymmetric vectors (Minimum 2 required).")

    if len(flashpoints) < 1:
        raise ValueError(f"[Line {start_line}] {dyad_id} has 0 strategic flashpoints (Minimum 1 required).")

    if not cross_refs:
        raise ValueError(f"[Line {start_line}] {dyad_id} lacks 'Cross-Reference Multilateral Nodes'.")

    return {
        "dyad_id": dyad_id,
        "actor_1": actor_1,
        "actor_2": actor_2,
        "common_reference": common_ref,
        "bilateral_stance": stance_val,
        "stance_classification": stance_class,
        "strategic_category": strat_cat,
        "asymmetric_power_vectors": vectors,
        "core_strategic_flashpoints": flashpoints,
        "multilateral_cross_references": cross_refs
    }

def parse_country_relationships(txt_content: str) -> Dict[str, Any]:
    lines = txt_content.splitlines()
    hubs = {}
    current_hub = None
    current_block_lines = []
    current_block_start = 0
    seen_dyad_ids = {}

    def flush_block():
        nonlocal current_block_lines, current_block_start
        if current_block_lines and current_hub:
            parsed = process_block(current_block_lines, current_block_start, current_hub, seen_dyad_ids)
            hubs[current_hub]["dyads"][parsed["dyad_id"]] = parsed
        current_block_lines = []
        current_block_start = 0

    for line_num, line in enumerate(lines, 1):
        line_clean = line.strip()

        # Check for Sovereign Hub Header
        hub_match = re.search(r"^# \d+\.\s*SOVEREIGN HUB:\s*(.+?)\s*\((GEO_[A-Z0-9_]+)\)", line_clean)
        if hub_match:
            flush_block()
            current_hub = hub_match.group(2).strip()
            hub_name = hub_match.group(1).strip()
            if current_hub in hubs:
                raise ValueError(f"[Line {line_num}] DUPLICATE SOVEREIGN HUB '{current_hub}' defined.")
            hubs[current_hub] = {
                "hub_id": current_hub,
                "hub_name": hub_name,
                "dyads": {}
            }
            continue

        # Check for Bilateral Dyad Header (Structural Anchor)
        if line_clean.startswith("Bilateral Dyad:"):
            # Validate proper format
            if not re.match(r"^Bilateral Dyad:\s*GEO_[A-Z0-9_]+\s*↔\s*GEO_[A-Z0-9_]+", line_clean):
                raise ValueError(f"[Line {line_num}] Malformed 'Bilateral Dyad' header: '{line_clean}'")

            flush_block()
            if not current_hub:
                raise ValueError(f"[Line {line_num}] 'Bilateral Dyad' defined before any SOVEREIGN HUB declaration.")

            current_block_start = line_num
            current_block_lines.append(line)
            continue

        # Ignore formatting divider lines
        if re.match(r"^[-—=]{5,}$", line_clean):
            continue

        # Collect lines inside active dyad block
        if current_block_lines:
            current_block_lines.append(line)

    # Flush final block at end of file
    flush_block()

    return hubs

def main():
    if not os.path.exists(TXT_PATH):
        print(f"[FAIL] Error: {TXT_PATH} not found.")
        sys.exit(1)

    with open(TXT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        hubs_data = parse_country_relationships(content)
    except Exception as e:
        print(f"[PARSER ERROR] {e}")
        sys.exit(1)

    total_dyads = sum(len(h["dyads"]) for h in hubs_data.values())
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "Canonical Bilateral Country Relationships & Dyadic Matrix",
            "author": "Ersoy Toptaş",
            "version": "2026-Q4",
            "license": "CC BY-NC-ND 4.0",
            "last_successful_sync": now_iso,
            "total_hubs": len(hubs_data),
            "total_dyads": total_dyads,
            "entity_dictionary": "https://analysisreports.github.io/llms-entities-id.txt",
            "multilateral_relationships": "https://analysisreports.github.io/llms-relationships.txt",
            "canonical_endpoint": "https://analysisreports.github.io/llms-country-relationships.txt"
        },
        "sovereign_hubs": hubs_data
    }

    # Safe Atomic Write: write to .tmp first, then atomic replace
    tmp_path = JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    os.replace(tmp_path, JSON_PATH)
    print(f"[SUCCESS] Safely parsed and atomically wrote {total_dyads} bilateral dyads across {len(hubs_data)} hubs to {JSON_PATH}")

if __name__ == "__main__":
    main()
