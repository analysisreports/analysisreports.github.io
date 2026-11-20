import builtins
import contextlib
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
SCHEMA_NAME = "country-strategic-assessment.schema.json"


class CountrySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas" / SCHEMA_NAME).read_text(encoding="utf-8"))
        cls.template = json.loads((ROOT / "country.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_existing_template_and_articles(self):
        for path in [ROOT / "country.json", *(ROOT / "country").rglob("*.json")]:
            with self.subTest(path=path):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(list(self.validator.iter_errors(data)), [])

    def test_invalid_reference_types_and_bounds(self):
        cases = [
            (("$schema",), "https://json-schema.org/draft/2020-12/schema"),
            (("metadata", "domain"), "economy"),
            (("structured_content_analysis", "country_strategic_assessment"), "not an object"),
            (("structured_content_analysis", "country_strategic_assessment",
              "internal_political_dynamics", "severity_score"), 999),
            (("structured_content_analysis", "country_strategic_assessment",
              "security_and_defense_posture", "severity_score"), -1),
            (("structured_content_analysis", "country_strategic_assessment",
              "geopolitical_alignment", "severity_score"), "75"),
            (("structured_content_analysis", "country_strategic_assessment",
              "strategic_vulnerabilities", "severity_score"), True),
            (("structured_content_analysis", "actors_and_dynamics", "relationship_map", 0, "polarity"), -1.01),
            (("structured_content_analysis", "geopolitical_state_vector", "dynamic_delta"), 2.01),
            (("structured_content_analysis", "future_outlook", "probability_percent"), 101),
            (("structured_content_analysis", "future_outlook", "potential_consequences", "long_term_days"), 180),
            (("structured_content_analysis", "future_outlook", "status"), "UNKNOWN"),
            (("structured_content_analysis", "editorial_frontend"), "not an object"),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys):
                data = copy.deepcopy(self.template)
                target = data
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.assertFalse(self.validator.is_valid(data))

    def test_null_and_boundary_values(self):
        data = copy.deepcopy(self.template)
        analysis = data["structured_content_analysis"]
        assessment = analysis["country_strategic_assessment"]
        self.assertIsNone(assessment["resilience_score"])
        self.assertIsNone(assessment["internal_political_dynamics"]["severity_score"])
        self.assertIsNone(analysis["geopolitical_state_vector"]["dynamic_delta"])
        self.assertIsNone(analysis["future_outlook"]["probability_percent"])
        self.assertTrue(self.validator.is_valid(data))

        assessment["resilience_score"] = 0
        assessment["internal_political_dynamics"]["severity_score"] = 100
        analysis["actors_and_dynamics"]["relationship_map"][0]["polarity"] = -1
        analysis["geopolitical_state_vector"]["dynamic_delta"] = 2
        analysis["future_outlook"]["probability_percent"] = 0
        self.assertTrue(self.validator.is_valid(data))

    def test_auditor_discovers_invalid_english_article(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "country" / "en" / "invalid.json"
            article.parent.mkdir(parents=True)
            data = copy.deepcopy(self.template)
            data["structured_content_analysis"]["country_strategic_assessment"]["resilience_score"] = 101
            article.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.object(verify_root_schemas, "ROOT_DIR", str(root)), \
                 mock.patch.object(verify_root_schemas, "SCHEMAS_DIR", str(ROOT / "schemas")), \
                 mock.patch.object(verify_root_schemas, "SCHEMA_MAPPING", {}), \
                 contextlib.redirect_stdout(io.StringIO()):
                errors = verify_root_schemas.audit_root_schemas()
            self.assertTrue(any("invalid.json" in error and "resilience_score" in error for error in errors), errors)

    def test_auditor_fails_without_jsonschema(self):
        original_import = builtins.__import__

        def import_without_jsonschema(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("jsonschema is unavailable")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_jsonschema), \
             mock.patch.object(verify_root_schemas, "SCHEMA_MAPPING", {"country.json": SCHEMA_NAME}), \
             contextlib.redirect_stdout(io.StringIO()):
            errors = verify_root_schemas.audit_root_schemas()
        self.assertTrue(any("jsonschema is required" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
