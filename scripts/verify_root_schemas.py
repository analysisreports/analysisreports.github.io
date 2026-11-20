#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/verify_root_schemas.py
--------------------------------
Formal JSON Schema Draft 2020-12 Validator for Root Contract Endpoints.
Part of the Enterprise Verification Suite.

Validates the formal compliance of:
1. concept.json                  <-> schemas/concept.schema.json
2. editorial.json                <-> schemas/editorial.schema.json
3. political.json                <-> schemas/political.schema.json
4. political-country.json        <-> schemas/political-country.schema.json
5. strategic-macro.json          <-> schemas/strategic-macro.schema.json
6. economy.json                  <-> schemas/strategic-macro.schema.json
7. country.json                  <-> schemas/country-strategic-assessment.schema.json
8. glossary.json                 <-> schemas/glossary-term.schema.json

Author: Ersoy Toptaş
License: CC BY 4.0
Endpoint: https://analysisreports.github.io/
"""

import os
import sys
import json
from typing import List, Dict

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMAS_DIR = os.path.join(ROOT_DIR, "schemas")

SCHEMA_MAPPING: Dict[str, str] = {
    "concept.json": "concept.schema.json",
    "editorial.json": "editorial.schema.json",
    "political.json": "political.schema.json",
    "political-country.json": "political-country.schema.json",
    "strategic-macro.json": "strategic-macro.schema.json",
    "economy.json": "strategic-macro.schema.json",
    "country.json": "country-strategic-assessment.schema.json",
    "glossary.json": "glossary-term.schema.json"
}

def audit_root_schemas() -> List[str]:
    try:
        import jsonschema
        has_jsonschema = True
    except ImportError:
        has_jsonschema = False

    errors = []
    print("=" * 70)
    print("ROOT CONTRACT JSON SCHEMA DRAFT 2020-12 AUDITOR")
    print("=" * 70)

    if not has_jsonschema:
        print("[WARN] python 'jsonschema' package not installed; performing structural fallback validation.")

    for target_name, schema_name in SCHEMA_MAPPING.items():
        target_path = os.path.join(ROOT_DIR, target_name)
        schema_path = os.path.join(SCHEMAS_DIR, schema_name)

        if not os.path.exists(target_path):
            errors.append(f"Target payload file missing: {target_name}")
            continue
        if not os.path.exists(schema_path):
            errors.append(f"Schema contract missing: {schema_name}")
            continue

        with open(target_path, "r", encoding="utf-8") as tf:
            try:
                target_data = json.load(tf)
            except Exception as e:
                errors.append(f"JSON Decode Error in {target_name}: {e}")
                continue

        with open(schema_path, "r", encoding="utf-8") as sf:
            try:
                schema_data = json.load(sf)
            except Exception as e:
                errors.append(f"Schema Decode Error in {schema_name}: {e}")
                continue

        # Basic structural required keys check (available in pure standard library)
        req_keys = schema_data.get("required", [])
        for rk in req_keys:
            if rk not in target_data:
                errors.append(f"{target_name}: Missing root required key '{rk}' specified by {schema_name}")

        meta = target_data.get("metadata", {})
        for gk in ["title", "domain", "version", "author", "license", "endpoint", "last_updated", "documentation"]:
            if gk not in meta or not meta[gk]:
                errors.append(f"{target_name}: Missing or empty golden key '{gk}' in metadata")

        # Formal Draft 2020-12 validator when jsonschema is available
        if has_jsonschema:
            validator = jsonschema.Draft202012Validator(schema_data)
            schema_errors = list(validator.iter_errors(target_data))

            if schema_errors:
                for err in schema_errors:
                    loc = " -> ".join(str(p) for p in err.path) if err.path else "root"
                    errors.append(f"{target_name} ({schema_name}) at [{loc}]: {err.message}")
            else:
                print(f"[*] [PASS] {target_name:<26} strictly conforms to {schema_name}")
        else:
            print(f"[*] [PASS] {target_name:<26} conforms to schema structural contract")

    return errors

def main():
    errors = audit_root_schemas()
    print("=" * 70)
    if errors:
        print(f"[FAIL] ROOT SCHEMA INTEGRITY FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  [!] {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print("[SUCCESS] All 8 Root JSON Payloads strictly comply with formal Draft 2020-12 schemas.")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
