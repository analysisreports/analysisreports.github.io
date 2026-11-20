import copy
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://analysisreports.github.io/schemas/country-relationships.schema.json"
FILES = (
    "llms-country-relationships.json",
    "llms-country-relationships-us.json",
    "llms-country-relationships-ru.json",
    "llms-country-relationships-cn.json",
    "llms-country-relationships-ir.json",
)


class CountryRelationshipsSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (ROOT / "schemas" / "country-relationships.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def load_documents(self):
        return {
            name: json.loads((ROOT / name).read_text(encoding="utf-8"))
            for name in FILES
        }

    def test_all_documents_validate_and_use_canonical_schema(self):
        for name, document in self.load_documents().items():
            with self.subTest(name=name):
                self.assertEqual(document.get("$schema"), SCHEMA_URL)
                self.assertEqual(list(self.validator.iter_errors(document)), [])

    def test_rejects_wrong_schema_reference(self):
        document = copy.deepcopy(self.load_documents()["llms-country-relationships-us.json"])
        document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        self.assertFalse(self.validator.is_valid(document))

    def test_rejects_out_of_bounds_stance(self):
        document = copy.deepcopy(self.load_documents()["llms-country-relationships-us.json"])
        dyad = next(iter(document["sovereign_hub"]["dyads"].values()))
        dyad["bilateral_stance"] = 1.01
        self.assertFalse(self.validator.is_valid(document))

    def test_rejects_missing_dyad_content(self):
        document = copy.deepcopy(self.load_documents()["llms-country-relationships-ru.json"])
        dyad = next(iter(document["sovereign_hub"]["dyads"].values()))
        for key in ("common_reference", "asymmetric_power_vectors", "core_strategic_flashpoints"):
            with self.subTest(key=key):
                invalid = copy.deepcopy(document)
                invalid_dyad = next(iter(invalid["sovereign_hub"]["dyads"].values()))
                invalid_dyad.pop(key)
                self.assertFalse(self.validator.is_valid(invalid))

    def test_rejects_wrong_master_accounting(self):
        document = copy.deepcopy(self.load_documents()["llms-country-relationships.json"])
        document["metadata"]["total_dyads"] = 164
        self.assertFalse(self.validator.is_valid(document))


if __name__ == "__main__":
    unittest.main()
