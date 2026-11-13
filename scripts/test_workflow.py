import json
import unittest

import verify_workflow


def files(entities, relationships, graph):
    relationship_rows = []
    for item in relationships:
        item.update({
            "dynamic_delta": -0.1, "mecca_pact_delta": 0.0, "legacy_dynamic_delta": 0.0,
            "p_net": -0.6, "regime_state": "PROXY_WAR", "primary_driver": "TEST",
        })
        relationship_rows.append(
            f"| **{item['id']}** | {item['p_baseline']:+.2f} | -0.100000 | +0.00 | +0.00 | -0.60 | PROXY_WAR | TEST |"
        )
    return {
        "llms-entities-id.txt": "\n".join(f"{entity} | Aliases: test" for entity in entities),
        "llms-relationships.txt": "| Actor Pair | P_baseline (Structural)\n" + "\n".join(relationship_rows)
        + "\n**Model 25.19 relationship contributions:**",
        "llms-relationships.json": json.dumps({"relationships": relationships}),
        "llms-graph.json": json.dumps(graph),
        "llms-models.json": json.dumps({"models": []}),
        "llms-tools.json": json.dumps({"tools": []}),
        "llms-formulas.txt": "",
        "llms-full.txt": "",
        "llms-models.txt": "",
        "llms-indicators.txt": "",
        "llms-fred-series.json": json.dumps({"series": {}}),
        "llms-ecb-series.json": json.dumps({"series": {}}),
        "llms-worldbank-series.json": json.dumps({"series": {}}),
        "llms-imf-series.json": json.dumps({"series": {}}),
        "llms-nyfed-series.json": json.dumps({"series": {}}),
        "llms-eia-series.json": json.dumps({"series": {}}),
        "llms-fred-series.txt": "",
        "llms-ecb-series.txt": "",
        "llms-worldbank-series.txt": "",
        "llms-imf-series.txt": "",
        "llms-nyfed-series.txt": "",
        "llms-eia-series.txt": "",
    }


class WorkflowVerificationTests(unittest.TestCase):
    def test_new_relationship_requires_entities_and_graph_coupling(self):
        baseline = files(
            ["GEO_US", "GEO_RU"],
            [{"id": "US_RU", "source_entity": "GEO_US", "target_entity": "GEO_RU", "p_baseline": -0.5}],
            {
                "nodes": [{"id": "GEO_US"}, {"id": "GEO_RU"}],
                "edges": [{"source": "GEO_US", "target": "GEO_RU", "type": "POLARITY_COUPLING"}],
            },
        )
        current = files(
            ["GEO_US", "GEO_RU", "GEO_YE", "GEO_IL"],
            [
                {"id": "US_RU", "source_entity": "GEO_US", "target_entity": "GEO_RU", "p_baseline": -0.5},
                {"id": "YE_IL", "source_entity": "GEO_YE", "target_entity": "GEO_IL", "p_baseline": -0.5},
            ],
            {
                "nodes": [{"id": entity} for entity in ("GEO_US", "GEO_RU", "GEO_YE", "GEO_IL")],
                "edges": [{"source": "GEO_US", "target": "GEO_RU", "type": "POLARITY_COUPLING"}],
            },
        )
        errors = verify_workflow.audit(baseline, current)

        self.assertIn("New relationship YE_IL: graph coupling edge is missing.", errors)

    def test_new_relationship_passes_when_all_workflow_artifacts_exist(self):
        baseline = files([], [], {"nodes": [], "edges": []})
        current = files(
            ["GEO_YE", "GEO_IL"],
            [{"id": "YE_IL", "source_entity": "GEO_YE", "target_entity": "GEO_IL", "p_baseline": -0.5}],
            {
                "nodes": [{"id": "GEO_YE"}, {"id": "GEO_IL"}],
                "edges": [{"source": "GEO_YE", "target": "GEO_IL", "type": "POLARITY_COUPLING"}],
            },
        )

        errors = verify_workflow.audit(baseline, current)

        self.assertEqual(errors, [])

    def test_partial_pair_and_series_registration(self):
        baseline = files([], [], {"nodes": [], "edges": []})
        current = files([], [], {"nodes": [], "edges": []})
        current["llms-relationships.txt"] += "\n| **ZZ_YY** | -0.50 |"
        current["llms-fred-series.json"] = json.dumps({"series": {"NEW_SERIES": {}}})
        errors = verify_workflow.audit(baseline, current)
        self.assertTrue(any("NEW_SERIES" in error for error in errors))
        current["llms-relationships.txt"] = current["llms-relationships.txt"].replace(
            "\n**Model 25.19 relationship contributions:**\n| **ZZ_YY** | -0.50 |",
            "\n| **ZZ_YY** | -0.50 |\n**Model 25.19 relationship contributions:**",
        )
        errors = verify_workflow.audit(baseline, current)
        self.assertTrue(any("ZZ_YY" in error and "both" in error for error in errors))

    def test_new_model_requires_reference_and_graph_input(self):
        baseline = files([], [], {"nodes": [], "edges": []})
        current = files([], [], {"nodes": [], "edges": []})
        current["llms-models.json"] = json.dumps({"models": [{"model_id": "MODEL_99"}]})
        errors = verify_workflow.audit(baseline, current)
        self.assertTrue(any("INGESTS_SERIES" in error for error in errors))
        self.assertTrue(any("llms-formulas.txt" in error for error in errors))

    def test_registered_series_and_model_pass(self):
        baseline = files([], [], {"nodes": [], "edges": []})
        current = files([], [], {
            "nodes": [{"id": "MODEL_99"}, {"id": "IND_NEW_SERIES"}],
            "edges": [{"source": "IND_NEW_SERIES", "target": "MODEL_99", "type": "INGESTS_SERIES"}],
        })
        current["llms-models.json"] = json.dumps({"models": [{"model_id": "MODEL_99"}]})
        current["llms-formulas.txt"] = "### 99. NEW MODEL"
        current["llms-full.txt"] = "   - 99. NEW MODEL"
        current["llms-models.txt"] = "MODEL_99"
        current["llms-fred-series.json"] = json.dumps({"series": {"NEW_SERIES": {}}})
        current["llms-fred-series.txt"] = "NEW_SERIES"
        current["llms-indicators.txt"] = "NEW_SERIES"
        self.assertEqual(verify_workflow.audit(baseline, current), [])

    def test_relationship_row_mismatch_is_reported(self):
        baseline = files([], [], {"nodes": [], "edges": []})
        current = files(
            ["GEO_YE", "GEO_IL"],
            [{"id": "YE_IL", "source_entity": "GEO_YE", "target_entity": "GEO_IL", "p_baseline": -0.5}],
            {
                "nodes": [{"id": "GEO_YE"}, {"id": "GEO_IL"}],
                "edges": [{"source": "GEO_YE", "target": "GEO_IL", "type": "POLARITY_COUPLING"}],
            },
        )
        current["llms-relationships.txt"] = current["llms-relationships.txt"].replace("PROXY_WAR", "NEUTRAL")
        self.assertTrue(any("does not match JSON" in error for error in verify_workflow.audit(baseline, current)))


if __name__ == "__main__":
    unittest.main()
