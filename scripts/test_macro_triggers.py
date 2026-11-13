import unittest

import update_relationships as relationships


def entry(current, prior, current_date="2026-11-09", prior_date="2025-11-10"):
    return {
        "current_value": current, "year_ago_value": prior,
        "last_date": current_date, "year_ago_date": prior_date,
    }


class MacroTriggerTests(unittest.TestCase):
    def test_brent_spread_natural_gas_and_sofr_annual_changes(self):
        series = {
            "DCOILBRENTEU": entry(120, 90),
            "DCOILWTICO": entry(100, 80),
            "DHHNGSP": entry(5, 4),
            "SOFR": entry(5, 4),
        }
        cases = [
            ("IND_TRIGGER_HORMUZ_SPREAD", "MODEL_25.12", ("DCOILBRENTEU", "DCOILWTICO"),
             lambda v: v["DCOILBRENTEU"] - v["DCOILWTICO"], ("DCOILBRENTEU", "DCOILWTICO"), 1.0),
            ("IND_TRIGGER_NATGAS_CRACK", "MODEL_25.8", ("DCOILWTICO", "DHHNGSP"),
             lambda v: v["DCOILWTICO"] / v["DHHNGSP"], ("DCOILWTICO", "DHHNGSP"), 0.0),
            ("IND_TRIGGER_SOFR_DOLLAR_DRAIN", "IND_SOFR", ("SOFR",),
             lambda v: v["SOFR"], (), 0.25),
        ]
        for entity_id, model, ids, metric, positive, expected in cases:
            with self.subTest(entity_id=entity_id):
                result = relationships.calc_annual_trigger(entity_id, model, series, ids, metric, positive)
                self.assertEqual(result["status"], "OK")
                self.assertEqual(result["value"], expected)

    def test_signed_gscpi_and_missing_dates(self):
        series = {"GSCPI": entry(1.2619, -0.0842)}
        result = relationships.calc_annual_trigger(
            "IND_TRIGGER_GSCPI_LOGISTICS", "IND_GSCPI", series, ("GSCPI",),
            lambda v: v["GSCPI"], use_difference=True,
        )
        self.assertEqual(result["value"], 1.0)
        self.assertEqual(result["status"], "OK")
        series["GSCPI"]["year_ago_date"] = None
        result = relationships.calc_annual_trigger(
            "IND_TRIGGER_GSCPI_LOGISTICS", "IND_GSCPI", series, ("GSCPI",),
            lambda v: v["GSCPI"], use_difference=True,
        )
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "MISSING_DATA")
        self.assertIn("GSCPI.year_ago_date", result["warning"])

    def test_nonpositive_prior_is_not_used_for_percentage_change(self):
        result = relationships.calc_annual_trigger(
            "IND_TRIGGER_SOFR_DOLLAR_DRAIN", "IND_SOFR", {"SOFR": entry(1.0, 0.0)},
            ("SOFR",), lambda v: v["SOFR"],
        )
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "INVALID_DATA")

    def test_spread_accepts_distinct_year_ago_dates_and_keeps_current_value(self):
        series = {
            "DCOILBRENTEU": entry(92.14, 65.44, prior_date="2025-10-31"),
            "DCOILWTICO": entry(89.62, 60.97, prior_date="2025-10-28"),
        }
        args = (
            "IND_TRIGGER_HORMUZ_SPREAD", "MODEL_25.12", series,
            ("DCOILBRENTEU", "DCOILWTICO"),
            lambda v: v["DCOILBRENTEU"] - v["DCOILWTICO"],
            ("DCOILBRENTEU", "DCOILWTICO"),
        )
        result = relationships.calc_annual_trigger(*args)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["current_model_value"], 2.52)
        self.assertEqual(result["year_ago_model_value"], 4.47)
        self.assertEqual(result["value"], -0.4362)
        series["DCOILWTICO"]["year_ago_date"] = None
        result = relationships.calc_annual_trigger(*args)
        self.assertEqual(result["status"], "MISSING_DATA")
        self.assertEqual(result["current_model_value"], 2.52)
        self.assertIsNone(result["year_ago_model_value"])
        self.assertIsNone(result["value"])

    def test_gscpi_date_is_taken_from_matching_observation(self):
        observations = [{"date": f"2025-{month:02d}-28", "value": month} for month in range(1, 13)]
        observations.append({"date": "2026-01-28", "value": 13})
        source = {"GSCPI": {
            "last_date": "2026-01-28", "current_value": 13,
            "year_ago_value": 1, "recent_observations": observations,
        }}
        self.assertEqual(relationships.gscpi_with_year_ago_date(source)["year_ago_date"], "2025-01-28")
        source["GSCPI"]["year_ago_value"] = 2
        self.assertNotIn("year_ago_date", relationships.gscpi_with_year_ago_date(source))

    def test_chip_trigger_reconstructs_both_model_values(self):
        sox = entry(120, 100, prior_date="2025-10-29")
        sox.update(two_years_ago_value=80, two_years_ago_date="2024-11-11")
        series = {"NASDAQSOX": sox, "VIXCLS": entry(20, 18, prior_date="2025-11-07")}
        gscpi = entry(1.5, 1.2, "2026-10-31", "2025-10-31")
        result = relationships.calc_chip_trigger(series, gscpi)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["value"], 0.18)
        del sox["two_years_ago_value"]
        result = relationships.calc_chip_trigger(series, gscpi)
        self.assertIsNone(result["value"])
        self.assertIn("NASDAQSOX.two_years_ago_value", result["warning"])


if __name__ == "__main__":
    unittest.main()
