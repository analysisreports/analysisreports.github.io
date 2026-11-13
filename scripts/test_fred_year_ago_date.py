import datetime
import unittest
from unittest.mock import patch

import update_fred_series as fred


class FredYearAgoDateTests(unittest.TestCase):
    def test_fetch_preserves_date_of_selected_year_ago_observation(self):
        observations = [
            {"date": "2023-12-29", "value": 20.0},
            {"date": "2024-12-30", "value": 25.0},
            {"date": "2025-12-31", "value": 30.0},
        ]
        data = {"metadata": {"units": "Index"}, "observations": observations}
        with patch.object(fred, "get_series_data_api", return_value=data):
            text, output = fred.build_outputs({"ANNUAL": ["OVXCLS"]}, "test-key")

        entry = output["series"]["OVXCLS"]
        self.assertEqual(entry["year_ago_date"], "2024-12-30")
        self.assertEqual(entry["year_ago_value"], 25.0)
        self.assertIn("Year Ago Date: 2024-12-30 | Year Ago Value: 25.0000", text)

    def test_insufficient_observations_leave_date_and_value_null(self):
        data = {
            "metadata": {"units": "Index"},
            "observations": [
                {"date": "2026-11-06", "value": 58.29},
                {"date": "2026-11-09", "value": 57.20},
            ],
        }
        with patch.object(fred, "get_series_data_api", return_value=data):
            text, output = fred.build_outputs({"DAILY": ["OVXCLS"]}, "test-key")

        entry = output["series"]["OVXCLS"]
        self.assertIsNone(entry["year_ago_date"])
        self.assertIsNone(entry["year_ago_value"])
        self.assertIn("Year Ago Date: N/A (observation date unavailable) | Year Ago Value: N/A", text)

    def test_sox_two_year_observation_is_saved_from_the_same_fetch(self):
        data = {
            "metadata": {"units": "Index"},
            "observations": [
                {"date": "2023-12-29", "value": 20.0},
                {"date": "2024-12-30", "value": 25.0},
                {"date": "2025-12-31", "value": 30.0},
            ],
        }
        with patch.object(fred, "get_series_data_api", return_value=data) as fetch:
            _, output = fred.build_outputs({"ANNUAL": ["NASDAQSOX"]}, "test-key")
        fetch.assert_called_once()
        entry = output["series"]["NASDAQSOX"]
        self.assertEqual(entry["two_years_ago_value"], 20.0)
        self.assertEqual(entry["two_years_ago_date"], "2023-12-29")

    def test_cached_value_does_not_invent_observation_date(self):
        cached = {
            "OVXCLS": {
                "series_id": "OVXCLS",
                "last_date": "2026-11-09",
                "last_synced_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "n_obs_per_yr": 260,
                "current_value": 57.20,
                "previous_value": 58.29,
                "year_ago_value": 38.96,
                "units": "Index",
            }
        }
        with patch.dict(fred.CACHE_TTL_DAYS, {"DAILY": 3}), patch.object(fred, "get_series_data_api") as fetch:
            text, output = fred.build_outputs({"DAILY": ["OVXCLS"]}, "test-key", cached)

        fetch.assert_not_called()
        entry = output["series"]["OVXCLS"]
        self.assertIsNone(entry["year_ago_date"])
        self.assertEqual(entry["year_ago_value"], 38.96)
        self.assertIn("Year Ago Date: N/A (observation date unavailable) | Year Ago Value: 38.9600", text)


if __name__ == "__main__":
    unittest.main()
