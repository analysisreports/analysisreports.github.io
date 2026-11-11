#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_country_relationships.py
--------------------------------
Parses canonical bilateral country relationships from llms-country-relationships.txt
and deterministically generates its official machine-readable twin llms-country-relationships.json.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-country-relationships.txt
JSON Twin: https://analysisreports.github.io/llms-country-relationships.json
"""

import os
import re
import json
import datetime
from typing import Dict, Any, List

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TXT_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.txt")
JSON_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.json")

def parse_country_relationships(txt_content: str) -> Dict[str, Any]:
    lines = txt_content.splitlines()
    hubs = {}
    current_hub = None
    current_block_lines = []

    def process_block(blk_lines: List[str]):
        if not blk_lines:
            return None
        text = "\n".join(blk_lines)
        
        dyad_m = re.search(r"Bilateral Dyad:\s*(\S+)\s*↔\s*(\S+)", text)
        ref_m = re.search(r"Common Reference:\s*(.+)", text)
        id_m = re.search(r"Dyad ID:\s*(\S+)", text)
        stance_m = re.search(r"Bilateral Stance:\s*([+\-0-9\.]+)\s*\((.+)\)", text)
        cat_m = re.search(r"Strategic Category:\s*(.+)", text)
        
        if not (dyad_m and id_m and stance_m):
            return None

        actor_1 = dyad_m.group(1).strip()
        actor_2 = dyad_m.group(2).strip()
        dyad_id = id_m.group(1).strip()
        stance_val = float(stance_m.group(1))
        stance_class = stance_m.group(2).strip()
        common_ref = ref_m.group(1).strip() if ref_m else f"{actor_1} ↔ {actor_2}"
        strat_cat = cat_m.group(1).strip() if cat_m else "Geopolitical Alignment"

        # Asymmetric power vectors
        vectors = []
        in_vectors = False
        in_flashpoints = False
        flashpoints = []
        cross_refs = []

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

    for line in lines:
        line_clean = line.strip()
        hub_match = re.search(r"# \d+\.\s*SOVEREIGN HUB:\s*(.+?)\s*\((GEO_[A-Z0-9_]+)\)", line)
        if hub_match:
            current_hub = hub_match.group(2).strip()
            hub_name = hub_match.group(1).strip()
            if current_hub not in hubs:
                hubs[current_hub] = {
                    "hub_id": current_hub,
                    "hub_name": hub_name,
                    "dyads": {}
                }
            continue

        if line_clean.startswith("--------------------------------------------------------------------------------"):
            if current_block_lines and current_hub:
                parsed = process_block(current_block_lines)
                if parsed:
                    hubs[current_hub]["dyads"][parsed["dyad_id"]] = parsed
            current_block_lines = []
        else:
            if current_hub:
                current_block_lines.append(line)

    if current_block_lines and current_hub:
        parsed = process_block(current_block_lines)
        if parsed:
            hubs[current_hub]["dyads"][parsed["dyad_id"]] = parsed

    return hubs

def main():
    if not os.path.exists(TXT_PATH):
        print(f"Error: {TXT_PATH} not found.")
        return

    with open(TXT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    hubs_data = parse_country_relationships(content)
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

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Wrote {total_dyads} bilateral dyads across {len(hubs_data)} hubs to {JSON_PATH}")

if __name__ == "__main__":
    main()
