#!/usr/bin/env python3
"""Regression tests for the strict llms-models TXT/JSON twin guard."""

import json
import os
import tempfile
import unittest

import verify_models_source as guard


class ModelsSourceGuardTests(unittest.TestCase):
    def test_current_models_twin_passes(self):
        self.assertEqual([], guard.verify_models())

    def test_value_mismatch_is_reported_on_model_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(guard.JSON_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            with open(guard.TXT_PATH, "r", encoding="utf-8") as handle:
                text = handle.read()
            payload["models"][0]["primary_value"] = 999
            json_path = os.path.join(tmp, "llms-models.json")
            txt_path = os.path.join(tmp, "llms-models.txt")
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            with open(txt_path, "w", encoding="utf-8") as handle:
                handle.write(text)
            issues = guard.verify_models(json_path, txt_path)
        self.assertTrue(any(issue.field == "primary_value" and issue.file == txt_path for issue in issues))

    def test_current_formula_links_resolve(self):
        with open(guard.JSON_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        unresolved = [
            model["model_id"]
            for model in payload["models"]
            if not guard.formula_model_exists(model.get("formula_ref", ""))
        ]
        self.assertEqual([], unresolved)


if __name__ == "__main__":
    unittest.main()
