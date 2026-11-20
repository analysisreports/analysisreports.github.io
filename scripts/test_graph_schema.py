import copy
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://analysisreports.github.io/schemas/graph.schema.json"
GRAPH_FILES = (
    "llms-graph.json",
    "llms-graph-actors.json",
    "llms-graph-models.json",
    "llms-graph-chokepoints.json",
)


class GraphSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas" / "graph.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def load_graphs(self):
        return {
            name: json.loads((ROOT / name).read_text(encoding="utf-8"))
            for name in GRAPH_FILES
        }

    def test_all_graph_documents_validate_and_use_canonical_schema(self):
        for name, graph in self.load_graphs().items():
            with self.subTest(name=name):
                self.assertEqual(graph.get("$schema"), SCHEMA_URL)
                self.assertEqual(list(self.validator.iter_errors(graph)), [])

    def test_rejects_wrong_schema_reference(self):
        graph = self.load_graphs()["llms-graph.json"]
        graph["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        self.assertFalse(self.validator.is_valid(graph))

    def test_rejects_invalid_node_and_edge_fields(self):
        invalid_cases = (
            ("nodes", 0, "id", ""),
            ("nodes", 0, "category", "UNKNOWN_CATEGORY"),
            ("edges", 0, "type", "UNKNOWN_EDGE"),
            ("edges", 0, "source", None),
            ("edges", 0, "p_baseline", 1.01),
        )
        for field, index, key, value in invalid_cases:
            with self.subTest(field=field, key=key, value=value):
                graph = copy.deepcopy(self.load_graphs()["llms-graph-actors.json"])
                graph[field][index][key] = value
                self.assertFalse(self.validator.is_valid(graph))

    def test_rejects_missing_master_accounting_and_metadata(self):
        graph = self.load_graphs()["llms-graph.json"]
        for key in ("graph_accounting", "graph_metadata", "metadata"):
            with self.subTest(key=key):
                invalid = copy.deepcopy(graph)
                invalid.pop(key)
                self.assertFalse(self.validator.is_valid(invalid))

    def test_null_polarity_is_allowed(self):
        graph = self.load_graphs()["llms-graph-actors.json"]
        polarity_edge = next(edge for edge in graph["edges"] if "p_baseline" in edge)
        polarity_edge["p_baseline"] = None
        self.assertTrue(self.validator.is_valid(graph))


if __name__ == "__main__":
    unittest.main()
