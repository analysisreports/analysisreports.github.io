import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import calculate_models as cm


ROOT = Path(__file__).resolve().parent.parent


class NetFedLiquidityTests(unittest.TestCase):
    def test_function_accepts_all_inputs_in_millions(self):
        result = cm.calc_net_fed_liquidity(6_748_145, 957_175, 152)
        self.assertEqual(result["metrics"]["net_liquidity_millions_usd"], 5_790_818)
        self.assertEqual(result["inputs"]["overnight_reverse_repo_rrp_mil"], 152)

    def test_function_rejects_invalid_rrp(self):
        for value in (None, True, float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                self.assertIsNone(cm.calc_net_fed_liquidity(6_748_145, 957_175, value))

    def run_engine(self, rrp_value, rrp_units):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            for source in ROOT.glob("llms-*.json"):
                shutil.copyfile(source, temp / source.name)
            fred_path = temp / "llms-fred-series.json"
            fred_data = json.loads(fred_path.read_text(encoding="utf-8"))
            fred_data["series"]["WALCL"]["current_value"] = 6_748_145
            fred_data["series"]["WTREGEN"]["current_value"] = 957_175
            fred_data["series"]["RRPONTSYD"]["current_value"] = rrp_value
            fred_data["series"]["RRPONTSYD"]["units"] = rrp_units
            fred_path.write_text(json.dumps(fred_data), encoding="utf-8")
            for name in ("llms-models.json", "llms-models.txt"):
                (temp / name).write_text("existing snapshot", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "calculate_models.py")],
                cwd=temp, capture_output=True, text=True, env=dict(os.environ, PYTHONUTF8="1"),
            )
            json_text = (temp / "llms-models.json").read_text(encoding="utf-8")
            txt_text = (temp / "llms-models.txt").read_text(encoding="utf-8")
            return result, json_text, txt_text

    def test_engine_converts_fred_billions_once(self):
        result, json_text, _ = self.run_engine(0.152, "Billions of US Dollars")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        models = json.loads(json_text)["models"]
        model = next(model for model in models if model["model_id"] == "MODEL_5")
        self.assertEqual(model["inputs"]["overnight_reverse_repo_rrp_mil"], 152)
        self.assertEqual(model["metrics"]["net_liquidity_millions_usd"], 5_790_818)

    def test_invalid_fred_units_or_value_preserve_snapshots(self):
        for value, units in ((152, "Millions of US Dollars"), (None, "Billions of US Dollars")):
            with self.subTest(value=value, units=units):
                result, json_text, txt_text = self.run_engine(value, units)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Model 5", result.stdout)
                self.assertEqual(json_text, "existing snapshot")
                self.assertEqual(txt_text, "existing snapshot")


if __name__ == "__main__":
    unittest.main()
