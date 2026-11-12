#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_dyad_integrity.py
-------------------------
Institutional Geopolitical Dyad Symmetry, Hub Isolation & Schema Integrity Auditor.

Validates across both 'llms-country-relationships.txt' and 'llms-country-relationships.json':
1. Mirror Invariance: Ensures P(A, B) == P(B, A) across all sovereign hubs.
2. Hub Isolation / Boundary Leak Guard: Dyads inside Hub GEO_X must have actor_1 == GEO_X.
3. Clamping & Precision: All baseline scores must be within [-1.00, +1.00].
4. Structural Schema Compliance:
   - Presence of Common Reference & Strategic Category.
   - Minimum 2 Asymmetric Power Vectors per dyad.
   - Minimum 1 Core Strategic Flashpoint per dyad.
   - Valid Multilateral Cross-Reference nodes.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-country-relationships.txt
"""

import os
import re
import sys
import json
from typing import Dict, Any, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TXT_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.txt")
JSON_PATH = os.path.join(ROOT_DIR, "llms-country-relationships.json")

def audit_txt_integrity(content: str) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    errors = []
    dyads = {}
    
    # Check hubs
    hubs = re.split(r"# =+\n# \d+\.\s*SOVEREIGN HUB:\s*", content)
    if len(hubs) < 2:
        errors.append("CRITICAL: No Sovereign Hubs detected in TXT.")
        return errors, dyads

    total_txt_dyads = 0

    for idx, hub_txt in enumerate(hubs[1:], 1):
        lines = hub_txt.splitlines()
        header = lines[0].strip()
        hub_match = re.search(r"\(GEO_([A-Z0-9_]+)\)", header)
        if not hub_match:
            errors.append(f"Hub {idx} header format invalid: {header}")
            continue
        hub_geo = f"GEO_{hub_match.group(1)}"

        blocks = hub_txt.split("--------------------------------------------------------------------------------")
        for b_idx, block in enumerate(blocks):
            if "Bilateral Dyad:" not in block:
                continue

            total_txt_dyads += 1
            dyad_m = re.search(r"Bilateral Dyad:\s*(GEO_[A-Z0-9_]+)\s*↔\s*(GEO_[A-Z0-9_]+)", block)
            id_m = re.search(r"Dyad ID:\s*(REL_GEO_[A-Z0-9_]+_GEO_[A-Z0-9_]+)", block)
            stance_m = re.search(r"Bilateral Stance:\s*([+\-0-9\.]+)\s*\((.+?)\)", block)
            ref_m = re.search(r"Common Reference:\s*(.+)", block)
            cat_m = re.search(r"Strategic Category:\s*(.+)", block)
            cross_m = re.search(r"Cross-Reference Multilateral Nodes:\s*(.+)", block)

            # Check ID & actor extraction
            if not (dyad_m and id_m and stance_m):
                errors.append(f"Hub {hub_geo}: Malformed dyad block #{b_idx} (missing ID, Dyad or Stance).")
                continue

            a1, a2 = dyad_m.group(1), dyad_m.group(2)
            d_id = id_m.group(1)
            stance = float(stance_m.group(1))
            stance_desc = stance_m.group(2).strip()

            # Boundary Leak Check
            if a1 != hub_geo:
                errors.append(f"BOUNDARY LEAK in TXT: Dyad {d_id} with Actor 1 '{a1}' is placed under Hub '{hub_geo}'.")

            if d_id != f"REL_{a1}_{a2}":
                errors.append(f"ID MISMATCH in TXT: Dyad ID '{d_id}' does not match Actor pair 'REL_{a1}_{a2}'.")

            # Clamping check
            if not (-1.0 <= stance <= 1.0):
                errors.append(f"OUT-OF-BOUNDS POLARITY in TXT: {d_id} has stance {stance} outside [-1.0, 1.0].")

            # Schema presence
            if not ref_m:
                errors.append(f"MISSING FIELD: {d_id} lacks 'Common Reference'.")
            if not cat_m:
                errors.append(f"MISSING FIELD: {d_id} lacks 'Strategic Category'.")
            if not cross_m:
                errors.append(f"MISSING FIELD: {d_id} lacks 'Cross-Reference Multilateral Nodes'.")

            # Asymmetric vectors count
            vectors = re.findall(r"-\s*\[([^\]]+)\]\s*([^:]+):\s*(.*)", block)
            if len(vectors) < 2:
                errors.append(f"INSUFFICIENT VECTORS: {d_id} has {len(vectors)} asymmetric vectors (minimum 2 required).")

            # Flashpoints count
            flashpoints = re.findall(r"^\s*\d+\.\s*(.+)", block, re.M)
            if len(flashpoints) < 1:
                errors.append(f"MISSING FLASHPOINTS: {d_id} has 0 strategic flashpoints (minimum 1 required).")

            dyads[d_id] = {
                "hub": hub_geo,
                "actor_1": a1,
                "actor_2": a2,
                "stance": stance,
                "stance_desc": stance_desc
            }

    return errors, dyads

def audit_json_integrity(json_path: str, txt_dyads: Dict[str, Dict[str, Any]]) -> List[str]:
    errors = []
    if not os.path.exists(json_path):
        return ["CRITICAL: JSON Twin not found."]

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hubs = data.get("sovereign_hubs", {})
    json_dyads = {}

    for hub_id, hub in hubs.items():
        dyads = hub.get("dyads", {})
        for dyad_id, dyad in dyads.items():
            json_dyads[dyad_id] = dyad

            # Boundary Leak Check
            if dyad.get("actor_1") != hub_id:
                errors.append(f"BOUNDARY LEAK in JSON: Dyad {dyad_id} actor_1 '{dyad.get('actor_1')}' != hub '{hub_id}'.")

            if not dyad_id.startswith(f"REL_{hub_id}_"):
                errors.append(f"KEY MISMATCH in JSON: Dyad ID '{dyad_id}' does not match hub prefix 'REL_{hub_id}_'.")

            # Polarity Check
            st = dyad.get("bilateral_stance")
            if st is None or not (-1.0 <= st <= 1.0):
                errors.append(f"OUT-OF-BOUNDS POLARITY in JSON: {dyad_id} has stance {st}.")

            # Power Vectors
            vecs = dyad.get("asymmetric_power_vectors", [])
            if len(vecs) < 2:
                errors.append(f"INSUFFICIENT VECTORS in JSON: {dyad_id} has {len(vecs)} vectors.")

            # Flashpoints
            fps = dyad.get("core_strategic_flashpoints", [])
            if len(fps) < 1:
                errors.append(f"INSUFFICIENT FLASHPOINTS in JSON: {dyad_id} has {len(fps)} flashpoints.")

    # Compare TXT and JSON dyad sets
    txt_keys = set(txt_dyads.keys())
    json_keys = set(json_dyads.keys())

    diff_in_txt = txt_keys - json_keys
    diff_in_json = json_keys - txt_keys

    if diff_in_txt:
        errors.append(f"DESYNC: Dyads in TXT but missing in JSON: {list(diff_in_txt)}")
    if diff_in_json:
        errors.append(f"DESYNC: Dyads in JSON but missing in TXT: {list(diff_in_json)}")

    # Score comparison between TXT and JSON
    for k in txt_keys.intersection(json_keys):
        txt_s = txt_dyads[k]["stance"]
        json_s = json_dyads[k]["bilateral_stance"]
        if abs(txt_s - json_s) > 0.0001:
            errors.append(f"SCORE DESYNC for {k}: TXT={txt_s} vs JSON={json_s}")

    return errors

def audit_mirror_symmetry(dyads: Dict[str, Dict[str, Any]]) -> Tuple[List[str], int]:
    errors = []
    checked_pairs = set()
    mirrors_verified = 0

    for dyad_id, data in dyads.items():
        a1 = data["actor_1"]
        a2 = data["actor_2"]
        mirror_id = f"REL_{a2}_{a1}"

        pair_key = tuple(sorted([dyad_id, mirror_id]))
        if pair_key in checked_pairs:
            continue
        checked_pairs.add(pair_key)

        if mirror_id in dyads:
            m_data = dyads[mirror_id]
            s1 = data["stance"]
            s2 = m_data["stance"]
            if abs(s1 - s2) > 0.0001:
                errors.append(
                    f"MIRROR SYMMETRY VIOLATION: {dyad_id} (Stance: {s1:+.2f}) != {mirror_id} (Stance: {s2:+.2f})"
                )
            else:
                mirrors_verified += 1

    return errors, mirrors_verified

def main():
    print("=" * 70)
    print("GEOPOLITICAL DYAD SYMMETRY, HUB ISOLATION & SCHEMA AUDITOR")
    print("Master Single Source of Truth (SSOT): llms-country-relationships.txt")
    print("Machine-Readable Twin: llms-country-relationships.json")
    print("=" * 70)

    if not os.path.exists(TXT_PATH):
        print(f"[FAIL] TXT file not found at {TXT_PATH}")
        sys.exit(1)

    with open(TXT_PATH, "r", encoding="utf-8") as f:
        txt_content = f.read()

    # 1. Audit TXT
    txt_errors, dyads = audit_txt_integrity(txt_content)
    print(f"[*] Parsed {len(dyads)} sovereign bilateral dyads from TXT.")

    # 2. Audit JSON
    json_errors = audit_json_integrity(JSON_PATH, dyads)
    print(f"[*] Verified machine-readable JSON twin synchronicity.")

    # 3. Audit Mirror Symmetry
    sym_errors, mirrors_count = audit_mirror_symmetry(dyads)
    print(f"[*] Verified {mirrors_count} cross-hub canonical mirror pairs.")

    all_errors = txt_errors + json_errors + sym_errors

    print("\n" + "=" * 70)
    if all_errors:
        print(f"[FAIL] DETECTED {len(all_errors)} INTEGRITY ISSUES:")
        for err in all_errors:
            print(f"  [!] {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print("[SUCCESS] 100% COMPLIANT & INVARIANT:")
        print(f"  - Total Dyads Audited: {len(dyads)} dyads")
        print(f"  - Hub Boundary Isolation: 100% Clean (0 leaks)")
        print(f"  - Canonical Mirror Symmetry: {mirrors_count} pairs 100% matched")
        print(f"  - Schema Compliance: 100% (Vectors, Flashpoints, Multilateral Nodes)")
        print(f"  - TXT <-> JSON Parity: 100% Synchronized")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
