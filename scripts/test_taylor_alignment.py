import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import calculate_models as cm
import update_fred_series as fred


class TaylorAlignmentTests(unittest.TestCase):
    def test_exact_fred_quarter_and_latest_projection_remain_separate(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        units = "Billions of Chained 2017 Dollars"
        cached = {
            "GDPC1": {
                "series_id": "GDPC1", "last_date": "2026-07-01",
                "current_value": 24611.077, "units": units, "last_synced_utc": now,
            },
            "GDPPOT": {
                "series_id": "GDPPOT", "last_date": "2036-10-01",
                "current_value": 29443.0227307, "units": units, "last_synced_utc": now,
            },
        }
        # Cached series normally include these fields for text formatting.
        for entry in cached.values():
            entry["n_obs_per_yr"] = 4
        response = io.BytesIO(b"observation_date,GDPPOT\n2026-07-01,24200.4446936\n")
        with patch.object(fred.urllib.request, "urlopen", return_value=response) as urlopen:
            _, result = fred.build_outputs({"QUARTERLY": ["GDPC1", "GDPPOT"]}, "", cached)
        url = urlopen.call_args.args[0].full_url
        self.assertIn("cosd=2026-07-01", url)
        self.assertIn("coed=2026-07-01", url)
        potential = result["series"]["GDPPOT"]
        self.assertEqual(potential["current_value"], 29443.0227307)
        matched = potential["gdpc1_quarter_observation"]
        self.assertEqual(matched["date"], "2026-07-01")
        model = cm.calc_taylor_policy_gap(
            3.88, 4.08, 24611.077, matched["value"], units, units,
            "2026-07-01", matched["date"],
        )
        self.assertEqual(model["metrics"]["output_gap_pct"], 1.70)
        self.assertEqual(model["primary_value"], -4.09)
        self.assertEqual(model["status"], "BEHIND_THE_CURVE")

    def test_missing_or_different_quarter_is_rejected(self):
        units = "Billions of Chained 2017 Dollars"
        for actual, potential in [
            ("2026-07-01", "2036-10-01"),
            ("2026-07-01", None),
            ("2026-07-02", "2026-07-02"),
            (None, None),
        ]:
            with self.subTest(actual=actual, potential=potential):
                self.assertIsNone(cm.calc_taylor_policy_gap(
                    3.88, 4.08, 24611.077, 24200.4446936, units, units, actual, potential
                ))

    def test_fred_missing_wrong_date_and_failure_do_not_fabricate_values(self):
        for content in (
            b"observation_date,GDPPOT\n",
            b"observation_date,GDPPOT\n2036-10-01,29443.0\n",
            b"observation_date,GDPPOT\n2026-07-01,.\n",
        ):
            with self.subTest(content=content), patch.object(
                fred.urllib.request, "urlopen", return_value=io.BytesIO(content)
            ):
                self.assertIsNone(fred.fetch_gdppot_for_quarter("2026-07-01"))
        with patch.object(fred.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertIsNone(fred.fetch_gdppot_for_quarter("2026-07-01"))

    def test_missing_matching_quarter_fails_without_overwriting_snapshots(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            for source in root.glob("llms-*.json"):
                shutil.copyfile(source, temp / source.name)
            fred_path = temp / "llms-fred-series.json"
            fred_data = json.loads(fred_path.read_text(encoding="utf-8"))
            fred_data["series"]["GDPPOT"]["gdpc1_quarter_observation"] = None
            fred_path.write_text(json.dumps(fred_data), encoding="utf-8")
            for name in ("llms-models.json", "llms-models.txt"):
                (temp / name).write_text("existing snapshot", encoding="utf-8")
            env = dict(os.environ, PYTHONUTF8="1")
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "calculate_models.py")],
                cwd=temp, capture_output=True, text=True, env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Model 11 requires valid GDPC1 and GDPPOT", result.stdout)
            for name in ("llms-models.json", "llms-models.txt"):
                self.assertEqual((temp / name).read_text(encoding="utf-8"), "existing snapshot")


if __name__ == "__main__":
    unittest.main()
