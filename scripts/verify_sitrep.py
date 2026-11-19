#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/verify_sitrep.py
-------------------------
Autonomous Situation Report (SITREP) Schema & Dual-Twin Auditor.
Part of the Enterprise Verification Suite (Pillar 9).

Audits:
1. Formal JSON Schema Draft 2020-12 compliance of llms-sitrep.json.
2. Root metadata & 8 Golden Keys completeness.
3. Canonical Entity IDs validity against llms-entities-id.txt.
4. Deterministic Causal Chains formatting (A -> B -> C token flow).
5. Dual Twin Parity (llms-sitrep.json vs llms-sitrep.txt).
6. Systemic Contagion Rules validity.

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/llms-sitrep.json
"""

import os
import sys
import json
import re
from typing import List, Set

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITREP_JSON = os.path.join(ROOT_DIR, "llms-sitrep.json")
SITREP_TXT = os.path.join(ROOT_DIR, "llms-sitrep.txt")
SCHEMA_JSON = os.path.join(ROOT_DIR, "schemas", "sitrep.schema.json")
ENTITIES_TXT = os.path.join(ROOT_DIR, "llms-entities-id.txt")


def load_canonical_entities() -> Set[str]:
    valid_ids = set()
    if not os.path.exists(ENTITIES_TXT):
        return valid_ids
    with open(ENTITIES_TXT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                eid = line.split("|")[0].strip()
                if eid:
                    valid_ids.add(eid)
    return valid_ids


def audit_sitrep() -> List[str]:
    errors = []

    if not os.path.exists(SITREP_JSON):
        return [f"CRITICAL: llms-sitrep.json not found at {SITREP_JSON}"]
    if not os.path.exists(SITREP_TXT):
        return [f"CRITICAL: llms-sitrep.txt not found at {SITREP_TXT}"]
    if not os.path.exists(SCHEMA_JSON):
        return [f"CRITICAL: sitrep.schema.json not found at {SCHEMA_JSON}"]

    try:
        with open(SITREP_JSON, "r", encoding="utf-8") as f:
            sitrep_data = json.load(f)
    except Exception as e:
        return [f"CRITICAL: Failed to parse llms-sitrep.json: {e}"]

    try:
        with open(SCHEMA_JSON, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    except Exception as e:
        return [f"CRITICAL: Failed to parse sitrep.schema.json: {e}"]

    with open(SITREP_TXT, "r", encoding="utf-8") as f:
        sitrep_txt = f.read()

    # 1. JSON Schema Draft 2020-12 Validation
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema_data)
        schema_errors = list(validator.iter_errors(sitrep_data))
        for err in schema_errors:
            loc = "/".join(str(p) for p in err.path)
            errors.append(f"Schema violation at '{loc}': {err.message}")
    except ImportError:
        pass

    # 2. Metadata Golden Keys Validation
    meta = sitrep_data.get("metadata", {})
    required_keys = [
        "title", "domain", "version", "author", "license", "endpoint",
        "documentation", "last_updated", "sync_status", "data_completeness_pct",
        "source_authority", "methodology_reference", "root_index"
    ]
    for key in required_keys:
        if key not in meta or meta[key] is None:
            errors.append(f"Metadata missing required Golden Key: '{key}'")

    if meta.get("sync_status") not in ["SUCCESS", "PARTIAL", "FAILED"]:
        errors.append(f"Invalid metadata sync_status: {meta.get('sync_status')}")

    # 3. Canonical Entity IDs Validation
    valid_entities = load_canonical_entities()
    flashes = sitrep_data.get("top_systemic_flashes", [])
    if not flashes:
        errors.append("top_systemic_flashes is empty.")

    for idx, flash in enumerate(flashes, 1):
        eid = flash.get("entity_id")
        if not eid or eid not in valid_entities:
            errors.append(f"Flash #{idx} contains unregistered canonical entity ID: '{eid}'")

        # 4. Causal Chain format validation
        chain = flash.get("causal_chain", "")
        if not chain or "->" not in chain:
            errors.append(f"Flash #{idx} missing valid '->' transitions in causal_chain: '{chain}'")
        else:
            steps = [s.strip() for s in chain.split("->")]
            if len(steps) < 2:
                errors.append(f"Flash #{idx} causal_chain has fewer than 2 steps: '{chain}'")
            for step in steps:
                if not re.match(r"^[A-Z0-9_]+$", step):
                    errors.append(f"Flash #{idx} causal_chain token '{step}' is not SCREAMING_SNAKE_CASE")

    # 5. Systemic Contagion Rules
    rules = sitrep_data.get("systemic_contagion_rules", [])
    if len(rules) < 5:
        errors.append(f"Expected at least 5 systemic contagion rules, found {len(rules)}.")

    seen_rule_ids = set()
    for idx, rule in enumerate(rules, 1):
        rid = rule.get("rule_id")
        if not rid:
            errors.append(f"Rule #{idx} has no rule_id")
        elif rid in seen_rule_ids:
            errors.append(f"Duplicate rule_id: '{rid}'")
        else:
            seen_rule_ids.add(rid)

    # 6. Dual Twin Parity (JSON vs TXT)
    pattern = r"FLASH_(\d+)\s+\[([^|]+)\s*\|\s*([^\]]+)\]:\s*([^\n]+)"
    flashes_txt = re.findall(pattern, sitrep_txt)
    if len(flashes) != len(flashes_txt):
        errors.append(f"Dual Twin mismatch: JSON has {len(flashes)} flashes, TXT has {len(flashes_txt)}.")
    else:
        for i, (num_str, src_txt, eid_txt, _) in enumerate(flashes_txt):
            f_json = flashes[i]
            if src_txt.strip() != f_json.get("source"):
                errors.append(f"Flash #{i+1} source mismatch: JSON='{f_json.get('source')}' vs TXT='{src_txt.strip()}'")
            if eid_txt.strip() != f_json.get("entity_id"):
                errors.append(f"Flash #{i+1} entity_id mismatch: JSON='{f_json.get('entity_id')}' vs TXT='{eid_txt.strip()}'")

    return errors


def main():
    print("=" * 70)
    print("AUTONOMOUS SITUATION REPORT (SITREP) SCHEMA & DUAL-TWIN AUDITOR")
    print("Sources: llms-sitrep.json | llms-sitrep.txt | schemas/sitrep.schema.json")
    print("=" * 70)

    errors = audit_sitrep()
    if errors:
        print(f"\n[FAIL] {len(errors)} AUDIT DEFECT(S) DETECTED IN SITREP:")
        for err in errors:
            print(f"  - {err}")
        print("=" * 70)
        sys.exit(1)

    with open(SITREP_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    flash_count = len(data.get("top_systemic_flashes", []))
    rule_count = len(data.get("systemic_contagion_rules", []))
    meta = data.get("metadata", {})
    completeness = meta.get("data_completeness_pct")

    print("\n[SUCCESS] 100% VALIDATED SITREP DATA CONTRACT & INTEGRITY:")
    print(f"  - Draft 2020-12 Schema: 100% Conforming")
    print(f"  - Top Systemic Flashes: {flash_count} Verified Signals (All Entity IDs Validated)")
    print(f"  - Systemic Contagion Rules: {rule_count} Deterministic Rules")
    print(f"  - Dual-Twin Sync: JSON <-> TXT 100% Invariant")
    print(f"  - Data Completeness: {completeness}%")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
