import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import update_relationships as relationships


def sample_series():
    return {
        "OVXCLS": {
            "current_value": 57.2,
            "year_ago_value": 38.96,
            "last_date": "2026-11-09",
            "year_ago_date": "2025-11-10",
        },
        "VIXCLS": {
            "current_value": 19.92,
            "year_ago_value": 18.01,
            "last_date": "2026-11-09",
            "year_ago_date": "2025-11-10",
        },
    }


class OvxEnergyTriggerTests(unittest.TestCase):
    def test_ratio_change_and_bounds(self):
        series = sample_series()
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertEqual(result["value"], 0.3274)
        self.assertEqual(result["status"], "OK")
        series["OVXCLS"]["current_value"] = 1000
        self.assertEqual(relationships.calc_ovx_energy_trigger(series)["value"], 1.0)
        series["OVXCLS"]["current_value"] = 1
        self.assertLess(relationships.calc_ovx_energy_trigger(series)["value"], 0)

    def test_missing_and_invalid_inputs_are_not_zero(self):
        result = relationships.calc_ovx_energy_trigger({})
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "NO_DATA")
        series = sample_series()
        series["OVXCLS"]["year_ago_date"] = None
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "MISSING_DATA")
        self.assertIn("OVXCLS.year_ago_date", result["warning"])
        series = sample_series()
        series["VIXCLS"]["current_value"] = 0
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "INVALID_DATA")

    def test_year_ago_dates_may_differ_but_current_dates_must_match(self):
        series = sample_series()
        series["VIXCLS"]["year_ago_date"] = "2025-11-07"
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertEqual(result["value"], 0.3274)
        self.assertEqual(result["status"], "OK")
        series["VIXCLS"]["last_date"] = "2026-11-06"
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "DATE_MISMATCH")

    def test_each_year_ago_date_must_precede_its_current_date(self):
        series = sample_series()
        series["VIXCLS"]["year_ago_date"] = "2027-01-01"
        result = relationships.calc_ovx_energy_trigger(series)
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "INVALID_DATA")

    def test_trigger_is_transmitted_to_relationships(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            for name in (
                "llms-fred-series.json",
                "llms-nyfed-series.json",
                "llms-imf-series.json",
                "llms-ecb-series.json",
                "llms-country-relationships.json",
                "llms-relationships.txt",
            ):
                shutil.copyfile(root / name, temp / name)
            fred_path = temp / "llms-fred-series.json"
            fred_data = json.loads(fred_path.read_text(encoding="utf-8"))
            for key, entry in sample_series().items():
                fred_data["series"][key].update(entry)
            fred_data["series"]["NASDAQSOX"]["last_date"] = sample_series()["VIXCLS"]["last_date"]
            fred_path.write_text(json.dumps(fred_data), encoding="utf-8")
            old_cwd = os.getcwd()
            try:
                os.chdir(temp)
                with contextlib.redirect_stdout(io.StringIO()):
                    relationships.main()
            finally:
                os.chdir(old_cwd)
            output = json.loads((temp / "llms-relationships.json").read_text(encoding="utf-8"))
            triggers = {item["entity_id"]: item for item in output["macro_triggers"]}
            self.assertEqual(len(triggers), 6)
            self.assertTrue(all(item["model"] == "MODEL_25.19" for item in triggers.values()))
            self.assertEqual(triggers["IND_TRIGGER_OVX_ENERGY_PANIC"]["value"], 0.3274)
            output_text = (temp / "llms-relationships.txt").read_text(encoding="utf-8")
            self.assertIn("Model 25.19 Macro Triggers:**", output_text)
            self.assertIn("IND_TRIGGER_OVX_ENERGY_PANIC:** 0.3274", output_text)
            self.assertIn("Model 25.19 relationship contributions:", output_text)
            pair = next(item for item in output["relationships"] if item["id"] == "SA_IR")
            self.assertEqual(pair["mecca_pact_delta"], 0.0)
            spread = output["metadata"]["macro_inputs"]["brent_wti_spread_usd"]
            expected_oil = -0.15 if spread > 12 else (-0.10 if spread > 8 else 0.0)
            self.assertEqual(pair["legacy_dynamic_delta"], round(expected_oil * 0.5, 2))
            hormuz = triggers["IND_TRIGGER_HORMUZ_SPREAD"]["value"]
            self.assertEqual(pair["dynamic_delta"], 0.074144)
            self.assertEqual(pair["p_net"], round(relationships.clamp(pair["p_baseline"] + pair["dynamic_delta"]), 2))
            self.assertEqual(pair["macro_trigger_contributions"][0]["contribution"], -hormuz)
            for pair_id in ("TR_SA", "SA_PK", "TR_PK"):
                mecca_pair = next(item for item in output["relationships"] if item["id"] == pair_id)
                self.assertEqual(mecca_pair["mecca_pact_delta"], 0.1)
                self.assertIsNone(mecca_pair["legacy_dynamic_delta"])
                self.assertEqual(mecca_pair["p_net"], round(relationships.clamp(
                    mecca_pair["p_baseline"] + mecca_pair["dynamic_delta"] + mecca_pair["mecca_pact_delta"]), 2))
            pairs = {item["id"]: item for item in output["relationships"]}
            for pair_id in ("LT_RU", "EE_RU", "LV_RU"):
                self.assertEqual(pairs[pair_id]["dynamic_delta"], -0.09)
                self.assertEqual(pairs[pair_id]["p_net"], -0.94)
                self.assertEqual(pairs[pair_id]["regime_state"], "PROXY_WAR")
            self.assertEqual(pairs["US_KP"]["regime_state"], "PROXY_WAR")
            self.assertFalse(pairs["US_KP"]["kinetic_contact_configured"])
            for pair_id in ("IL_IR", "YE_IL"):
                self.assertTrue(pairs[pair_id]["kinetic_contact_configured"])
                self.assertEqual(pairs[pair_id]["regime_state"],
                                 relationships.get_regime(pairs[pair_id]["p_net"], pair_id))
            self.assertEqual(pairs["YE_IL"]["regime_state"], "KINETIC_WAR")
            self.assertEqual(len(output["relationships"]), 23)
            for entry in ("OVXCLS", "VIXCLS"):
                fred_data["series"][entry]["year_ago_date"] = None
            fred_path.write_text(json.dumps(fred_data), encoding="utf-8")
            try:
                os.chdir(temp)
                with contextlib.redirect_stdout(io.StringIO()) as log:
                    relationships.main()
            finally:
                os.chdir(old_cwd)
            output = json.loads((temp / "llms-relationships.json").read_text(encoding="utf-8"))
            triggers = {item["entity_id"]: item for item in output["macro_triggers"]}
            self.assertIsNone(triggers["IND_TRIGGER_OVX_ENERGY_PANIC"]["value"])
            self.assertEqual(triggers["IND_TRIGGER_OVX_ENERGY_PANIC"]["status"], "MISSING_DATA")
            self.assertEqual(output["metadata"]["sync_status"], "PARTIAL_SUCCESS")
            self.assertIsNone(output["metadata"]["last_successful_sync"])
            self.assertIn("OVXCLS.year_ago_date", log.getvalue())
            self.assertIn("IND_TRIGGER_OVX_ENERGY_PANIC:** null", (temp / "llms-relationships.txt").read_text(encoding="utf-8"))
            pair = next(item for item in output["relationships"] if item["id"] == "SA_IR")
            self.assertIsNone(pair["dynamic_delta"])
            self.assertIsNone(pair["p_net"])
            self.assertEqual(pair["regime_state"], "UNAVAILABLE")
            self.assertIn("SA_IR: relationship delta unavailable", log.getvalue())


if __name__ == "__main__":
    unittest.main()
