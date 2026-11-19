#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/test_news_integrity.py
------------------------------
Unit Test & Integrity Guard for Autonomous News Telemetry:
  - llms-news.json (Machine Twin)
  - llms-news.txt  (Markdown Text Twin)
  - Canonical Entity IDs (llms-entities-id.txt)
  - Tier-1 Source Whitelist Compliance

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
"""

import os
import re
import json
import unittest
from typing import Set

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NEWS_JSON = os.path.join(ROOT_DIR, "llms-news.json")
NEWS_TXT = os.path.join(ROOT_DIR, "llms-news.txt")
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


class TestNewsTelemetryIntegrity(unittest.TestCase):

    def setUp(self):
        self.assertTrue(os.path.exists(NEWS_JSON), f"Missing {NEWS_JSON}")
        self.assertTrue(os.path.exists(NEWS_TXT), f"Missing {NEWS_TXT}")
        with open(NEWS_JSON, "r", encoding="utf-8") as f:
            self.data_json = json.load(f)
        with open(NEWS_TXT, "r", encoding="utf-8") as f:
            self.text_twin = f.read()
        self.canonical_entities = load_canonical_entities()

    def test_golden_keys_and_metadata(self):
        """Pillar 1: Root metadata contains 8 Golden Keys."""
        meta = self.data_json.get("metadata", {})
        expected_keys = ["title", "domain", "version", "author", "license", "endpoint", "last_updated", "documentation"]
        for k in expected_keys:
            self.assertIn(k, meta, f"Missing golden key '{k}' in metadata")
            self.assertTrue(bool(meta[k]), f"Empty golden key '{k}'")

    def test_dispatches_entity_compliance(self):
        """Pillar 2: Every dispatch has a valid canonical Entity ID from llms-entities-id.txt."""
        dispatches = self.data_json.get("dispatches", [])
        self.assertGreaterEqual(len(dispatches), 1, "Dispatches list is empty")
        for d in dispatches:
            pe = d.get("primary_entity")
            self.assertIn(pe, self.canonical_entities, f"Invalid primary_entity: {pe}")
            for re_id in d.get("related_entities", []):
                self.assertIn(re_id, self.canonical_entities, f"Invalid related_entity: {re_id}")

    def test_dual_twin_dispatch_count_parity(self):
        """Pillar 3: Exact count and ID parity between JSON dispatches and TXT headers."""
        dispatches_json = self.data_json.get("dispatches", [])
        # Find dispatch headers in TXT: e.g. [DISPATCH_20261119_01]
        txt_dispatch_ids = re.findall(r"\[(DISPATCH_\d+_\d+)\]", self.text_twin)
        
        self.assertEqual(
            len(dispatches_json), 
            len(txt_dispatch_ids), 
            f"Dual twin count mismatch: JSON has {len(dispatches_json)}, TXT has {len(txt_dispatch_ids)}"
        )
        
        for i, d in enumerate(dispatches_json):
            self.assertEqual(d["dispatch_id"], txt_dispatch_ids[i])


if __name__ == "__main__":
    unittest.main()
