import contextlib
import builtins
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jsonschema
import verify_root_schemas


ROOT = Path(__file__).resolve().parent.parent


class EconomySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas" / "economy.schema.json").read_text(encoding="utf-8"))
        cls.template = json.loads((ROOT / "economy.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_existing_template_and_articles(self):
        for path in [ROOT / "economy.json", *(ROOT / "economy").rglob("*.json")]:
            with self.subTest(path=path):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(list(self.validator.iter_errors(data)), [])

    def test_rejects_wrong_reference_type_and_score(self):
        cases = [
            (("$schema",), "https://json-schema.org/draft/2020-12/schema"),
            (("metadata", "domain"), "country"),
            (("structured_content_analysis", "quantitative_data_summary"), []),
            (("structured_content_analysis", "future_outlook", "probability_percent"), 101),
            (("structured_content_analysis", "quantitative_data_summary", "primary_indicator_tracking",
              "value_comparison", "current_numeric_value"), "4.0"),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys):
                data = copy.deepcopy(self.template)
                target = data
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.assertFalse(self.validator.is_valid(data))

    def test_missing_numeric_values_can_be_null(self):
        data = copy.deepcopy(self.template)
        analysis = data["structured_content_analysis"]
        analysis["quantitative_data_summary"]["primary_indicator_tracking"]["value_comparison"]["current_numeric_value"] = None
        analysis["future_outlook"]["probability_percent"] = None
        self.assertTrue(self.validator.is_valid(data))

    def test_auditor_discovers_invalid_english_article(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "economy" / "en" / "invalid.json"
            article.parent.mkdir(parents=True)
            data = copy.deepcopy(self.template)
            data["structured_content_analysis"]["future_outlook"]["impact_score"] = 101
            article.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.object(verify_root_schemas, "ROOT_DIR", str(root)), \
                 mock.patch.object(verify_root_schemas, "SCHEMAS_DIR", str(ROOT / "schemas")), \
                 mock.patch.object(verify_root_schemas, "SCHEMA_MAPPING", {}), \
                 contextlib.redirect_stdout(io.StringIO()):
                errors = verify_root_schemas.audit_root_schemas()
            self.assertTrue(any("invalid.json" in error and "impact_score" in error for error in errors), errors)

    def test_auditor_fails_without_jsonschema(self):
        original_import = builtins.__import__

        def import_without_jsonschema(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("jsonschema is unavailable")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_jsonschema), \
             mock.patch.object(verify_root_schemas, "SCHEMA_MAPPING", {"economy.json": "economy.schema.json"}), \
             contextlib.redirect_stdout(io.StringIO()):
            errors = verify_root_schemas.audit_root_schemas()
        self.assertTrue(any("jsonschema is required" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
