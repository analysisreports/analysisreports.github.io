#!/usr/bin/env python3
"""Focused regressions for the strict canonical TXT source guard."""

import os
import tempfile
import unittest
from unittest.mock import patch

import verify_special_sources as guard


class SpecialSourceGuardTests(unittest.TestCase):
    def test_duplicate_entity_is_rejected_with_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "llms-entities-id.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("GEO_US | Aliases: United States\nGEO_US | Aliases: USA\n")
            with patch.object(guard, "ROOT_DIR", tmp):
                issues = guard.verify_entities()
        self.assertEqual(1, len(issues))
        self.assertEqual(2, issues[0].line)
        self.assertIn("duplicate", issues[0].message)

    def test_formula_without_purpose_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "formula.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("### 1. Broken\n- Formula: x\n- Interpretation: x\n")
            models, issues = guard.parse_formula_models(path)
        self.assertIn("1", models)
        self.assertTrue(any(issue.field == "purpose" for issue in issues))

    def test_current_special_sources_pass(self):
        issues = [
            *guard.verify_entities(),
            *guard.verify_indicators(),
            *guard.verify_formulas(),
            *guard.verify_news(),
            *guard.verify_sitrep(),
        ]
        self.assertEqual([], [(issue.file, issue.line, issue.field, issue.message) for issue in issues])


if __name__ == "__main__":
    unittest.main()
