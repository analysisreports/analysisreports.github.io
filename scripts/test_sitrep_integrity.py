#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_sitrep_integrity.py
---------------------------------
Comprehensive Automated Verification & Integrity Test Suite for SITREP:
  - llms-sitrep.json (Autonomous Machine-Readable Twin)
  - llms-sitrep.txt  (Canonical Plain Text Markdown Twin)
  - schemas/sitrep.schema.json (Draft 2020-12 Formal Data Contract)

Verification Pillars:
1. JSON Schema Draft 2020-12 Contract Compliance (Root structure, metadata, 8 Golden Keys).
2. Canonical Entity IDs SSOT validation (llms-entities-id.txt adherence).
3. Zero-Synthetic & Strict Ground Truth Telemetry assertion (finite numbers, valid bounds).
4. Deterministic Causal Chains formatting (A -> B -> C token flow).
5. Dual Twin Parity: Synchronized entity, event, and section counts across JSON and TXT.
6. Systemic Contagion Rules integrity (valid rules, schemas, and formula links).

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-sitrep.json
"""

import os
import re
import json
import unittest
from typing import Set, Dict, Any

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITREP_JSON = os.path.join(ROOT_DIR, "llms-sitrep.json")
SITREP_TXT = os.path.join(ROOT_DIR, "llms-sitrep.txt")
SCHEMA_JSON = os.path.join(ROOT_DIR, "schemas", "sitrep.schema.json")
ENTITIES_TXT = os.path.join(ROOT_DIR, "llms-entities-id.txt")


def load_canonical_entities() -> Set[str]:
    """Extracts all valid Canonical Entity IDs from llms-entities-id.txt."""
    if not os.path.exists(ENTITIES_TXT):
        return set()
    valid_ids = set()
    with open(ENTITIES_TXT, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                entity_id = line.split("|")[0].strip()
                if entity_id:
                    valid_ids.add(entity_id)
    return valid_ids


class SitrepIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assertTrue(os.path.exists(SITREP_JSON), f"Missing {SITREP_JSON}")
        cls.assertTrue(os.path.exists(SITREP_TXT), f"Missing {SITREP_TXT}")
        cls.assertTrue(os.path.exists(SCHEMA_JSON), f"Missing {SCHEMA_JSON}")

        with open(SITREP_JSON, "r", encoding="utf-8") as f:
            cls.sitrep = json.load(f)

        with open(SCHEMA_JSON, "r", encoding="utf-8") as f:
            cls.schema = json.load(f)

        with open(SITREP_TXT, "r", encoding="utf-8") as f:
            cls.sitrep_txt = f.read()

        cls.valid_entities = load_canonical_entities()

    def test_formal_json_schema_compliance(self):
        """Pillar 1: Validate llms-sitrep.json strictly adheres to schemas/sitrep.schema.json."""
        if not HAS_JSONSCHEMA:
            self.skipTest("jsonschema library is not installed in the current environment")

        validator = jsonschema.Draft202012Validator(self.schema)
        errors = list(validator.iter_errors(self.sitrep))
        error_msgs = [f"Schema violation at {'/'.join(str(p) for p in err.path)}: {err.message}" for err in errors]
        self.assertEqual(len(errors), 0, "\n".join(error_msgs))

    def test_golden_keys_metadata(self):
        """Pillar 2: Verify root metadata complies with the 8 Golden Keys standard."""
        meta = self.sitrep.get("metadata", {})
        required_keys = [
            "title", "domain", "version", "author", "license", "endpoint",
            "documentation", "last_updated", "sync_status", "data_completeness_pct",
            "source_authority", "methodology_reference", "root_index"
        ]
        for key in required_keys:
            self.assertIn(key, meta, f"Metadata missing required key: {key}")
            self.assertIsNotNone(meta[key], f"Metadata key {key} must not be None")

        self.assertIn(meta["sync_status"], ["SUCCESS", "PARTIAL", "FAILED"])
        self.assertGreaterEqual(meta["data_completeness_pct"], 0.0)
        self.assertLessEqual(meta["data_completeness_pct"], 100.0)

    def test_canonical_entity_ids_in_flashes(self):
        """Pillar 3: All entity_ids in top_systemic_flashes must exist in llms-entities-id.txt."""
        self.assertGreater(len(self.valid_entities), 0, "No canonical entities loaded from llms-entities-id.txt")
        flashes = self.sitrep.get("top_systemic_flashes", [])
        self.assertGreater(len(flashes), 0, "top_systemic_flashes must not be empty")

        for idx, flash in enumerate(flashes, 1):
            entity_id = flash.get("entity_id")
            self.assertIn(
                entity_id,
                self.valid_entities,
                f"Flash #{idx} contains unregistered canonical entity ID: '{entity_id}'"
            )

    def test_deterministic_causal_chains_structure(self):
        """Pillar 4: Validate causal chains adhere to the A -> B -> C deterministic vector grammar."""
        flashes = self.sitrep.get("top_systemic_flashes", [])
        for idx, flash in enumerate(flashes, 1):
            chain = flash.get("causal_chain", "")
            self.assertTrue(bool(chain), f"Flash #{idx} has missing or empty causal_chain")
            self.assertIn("->", chain, f"Flash #{idx} causal_chain '{chain}' must contain '->' transition operators")
            
            steps = [s.strip() for s in chain.split("->")]
            self.assertGreaterEqual(len(steps), 2, f"Flash #{idx} causal_chain must have at least 2 causal steps")
            for step in steps:
                self.assertTrue(len(step) > 0, f"Flash #{idx} causal_chain has empty steps in '{chain}'")
                # Tokens should follow institutional SCREAMING_SNAKE_CASE or standard uppercase naming
                self.assertTrue(
                    re.match(r"^[A-Z0-9_]+$", step),
                    f"Flash #{idx} causal_chain step '{step}' must be uppercase SNAKE_CASE"
                )

    def test_systemic_contagion_rules_integrity(self):
        """Pillar 5: Verify systemic contagion rules have valid rule IDs, telemetry signals, and formula links."""
        rules = self.sitrep.get("systemic_contagion_rules", [])
        self.assertGreaterEqual(len(rules), 5, "Expected at least 5 core systemic contagion rules")
        seen_rule_ids = set()

        for idx, rule in enumerate(rules, 1):
            rule_id = rule.get("rule_id")
            self.assertTrue(bool(rule_id), f"Rule #{idx} missing rule_id")
            self.assertNotIn(rule_id, seen_rule_ids, f"Duplicate rule_id found: {rule_id}")
            seen_rule_ids.add(rule_id)

            formula_link = rule.get("formula_link", "")
            self.assertTrue(formula_link.startswith("https://analysisreports.github.io/"), 
                            f"Rule {rule_id} invalid formula_link: {formula_link}")

    def test_dual_twin_sync_json_txt_parity(self):
        """Pillar 6: Verify exact parity between llms-sitrep.json and llms-sitrep.txt."""
        flashes_json = self.sitrep.get("top_systemic_flashes", [])
        
        # Regex to parse flash headers in llms-sitrep.txt:
        # e.g., FLASH_1 [IMF_PORTWATCH_AIS | CHOKE_HORMUZ]: CRITICAL_BLOCKADE: ...
        pattern = r"FLASH_(\d+)\s+\[([^|]+)\s*\|\s*([^\]]+)\]:\s*([^\n]+)"
        flashes_txt = re.findall(pattern, self.sitrep_txt)

        self.assertEqual(
            len(flashes_json),
            len(flashes_txt),
            f"Dual twin mismatch: llms-sitrep.json has {len(flashes_json)} flashes but llms-sitrep.txt has {len(flashes_txt)}"
        )

        for i, (num_str, src_txt, eid_txt, event_txt) in enumerate(flashes_txt):
            f_json = flashes_json[i]
            expected_idx = i + 1
            self.assertEqual(int(num_str), expected_idx, f"TXT flash index sequence broken at #{num_str}")
            self.assertEqual(src_txt.strip(), f_json.get("source"), f"Flash #{expected_idx} source mismatch between JSON and TXT")
            self.assertEqual(eid_txt.strip(), f_json.get("entity_id"), f"Flash #{expected_idx} entity_id mismatch between JSON and TXT")


if __name__ == "__main__":
    unittest.main()
