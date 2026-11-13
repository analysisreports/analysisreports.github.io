import unittest

import update_relationships as relationships


def entry(current, prior, current_date="2026-11-09", prior_date="2025-11-10"):
    return {
        "current_value": current, "year_ago_value": prior,
        "last_date": current_date, "year_ago_date": prior_date,
    }


class MacroTriggerTests(unittest.TestCase):
    def test_relationship_delta_dominant_opposing_and_clamp(self):
        triggers = {
            "IND_TRIGGER_HORMUZ_SPREAD": {"value": -0.4362, "status": "OK"},
            "IND_TRIGGER_OVX_ENERGY_PANIC": {"value": 0.5057, "status": "OK"},
            "IND_TRIGGER_GSCPI_LOGISTICS": {"value": 1.0, "status": "OK"},
        }
        delta, contributions, dominant = relationships.calc_relationship_trigger_delta("YE_IL", triggers)
        self.assertEqual([item["contribution"] for item in contributions], [0.4362, -0.5057, -1.0])
        self.assertEqual(dominant, "IND_TRIGGER_GSCPI_LOGISTICS")
        self.assertEqual(delta, -0.2)
        triggers["IND_TRIGGER_GSCPI_LOGISTICS"]["value"] = 0.8
        delta, _, _ = relationships.calc_relationship_trigger_delta("YE_IL", triggers)
        self.assertEqual(delta, -0.16278)
        triggers["IND_TRIGGER_GSCPI_LOGISTICS"]["value"] = 1.0
        triggers["IND_TRIGGER_HORMUZ_SPREAD"]["value"] = 1.0
        triggers["IND_TRIGGER_OVX_ENERGY_PANIC"]["value"] = 1.0
        delta, _, _ = relationships.calc_relationship_trigger_delta("YE_IL", triggers)
        self.assertEqual(delta, -0.2)
        for trigger in triggers.values():
            trigger["value"] = -1.0
        delta, _, _ = relationships.calc_relationship_trigger_delta("YE_IL", triggers)
        self.assertEqual(delta, 0.2)

    def test_relationship_delta_missing_trigger_and_tie(self):
        triggers = {
            "IND_TRIGGER_HORMUZ_SPREAD": {"value": 0.5, "status": "OK"},
            "IND_TRIGGER_GSCPI_LOGISTICS": {"value": 0.5, "status": "OK"},
        }
        delta, _, dominant = relationships.calc_relationship_trigger_delta("EG_IL", triggers)
        self.assertEqual(delta, 0.08)
        self.assertEqual(dominant, "IND_TRIGGER_HORMUZ_SPREAD")
        triggers["IND_TRIGGER_GSCPI_LOGISTICS"].update(value=None, status="MISSING_DATA")
        delta, contributions, dominant = relationships.calc_relationship_trigger_delta("EG_IL", triggers)
        self.assertIsNone(delta)
        self.assertIsNone(dominant)
        self.assertEqual(contributions[1]["status"], "MISSING_DATA")

    def test_relationship_regime_boundaries(self):
        self.assertEqual(relationships.get_regime(-0.4, "IL_IR"), "STRATEGIC_FRICTION")
        self.assertEqual(relationships.get_regime(-0.41, "IL_IR"), "PROXY_WAR")
        self.assertEqual(relationships.get_regime(-0.95, "IL_IR"), "PROXY_WAR")
        self.assertEqual(relationships.get_regime(-0.96, "IL_IR"), "KINETIC_WAR")
        self.assertEqual(relationships.get_regime(-1.0, "US_KP"), "PROXY_WAR")

    def test_ua_ru_grain_and_logistics_transmission(self):
        triggers = {
            "IND_TRIGGER_WHEAT_PRICE": {"value": 0.8, "status": "OK"},
            "IND_TRIGGER_CORN_PRICE": {"value": 0.5, "status": "OK"},
            "IND_TRIGGER_GSCPI_LOGISTICS": {"value": -0.2, "status": "OK"},
        }
        delta, contributions, dominant = relationships.calc_relationship_trigger_delta("UA_RU", triggers)
        self.assertEqual(delta, -0.172)
        self.assertEqual([item["contribution"] for item in contributions], [-0.8, -0.5, 0.2])
        self.assertEqual(dominant, "IND_TRIGGER_WHEAT_PRICE")
        self.assertEqual(relationships.get_regime(-0.96, "UA_RU"), "KINETIC_WAR")
        self.assertEqual(relationships.get_regime(-0.95, "UA_RU"), "PROXY_WAR")
        triggers["IND_TRIGGER_CORN_PRICE"].update(value=None, status="MISSING_DATA")
        delta, contributions, dominant = relationships.calc_relationship_trigger_delta("UA_RU", triggers)
        self.assertIsNone(delta)
        self.assertIsNone(contributions[1]["contribution"])
        self.assertIsNone(dominant)

    def test_baltic_negative_delta_floor(self):
        triggers = {
            "IND_TRIGGER_GSCPI_LOGISTICS": {"value": 1.0, "status": "OK"},
            "IND_TRIGGER_SOFR_DOLLAR_DRAIN": {"value": 0.0, "status": "OK"},
        }
        delta, _, _ = relationships.calc_relationship_trigger_delta("LT_RU", triggers)
        self.assertEqual(delta, -0.09)
        triggers["IND_TRIGGER_GSCPI_LOGISTICS"]["value"] = -1.0
        delta, _, _ = relationships.calc_relationship_trigger_delta("LT_RU", triggers)
        self.assertEqual(delta, 0.2)

    def test_brent_spread_natural_gas_and_sofr_annual_changes(self):
        series = {
            "DCOILBRENTEU": entry(120, 90),
            "DCOILWTICO": entry(100, 80),
            "DHHNGSP": entry(5, 4),
            "SOFR": entry(5, 4),
        }
        cases = [
            ("IND_TRIGGER_HORMUZ_SPREAD", "MODEL_25.19", ("DCOILBRENTEU", "DCOILWTICO"),
             lambda v: v["DCOILBRENTEU"] - v["DCOILWTICO"], ("DCOILBRENTEU", "DCOILWTICO"), 1.0),
            ("IND_TRIGGER_NATGAS_CRACK", "MODEL_25.19", ("DCOILWTICO", "DHHNGSP"),
             lambda v: v["DCOILWTICO"] / v["DHHNGSP"], ("DCOILWTICO", "DHHNGSP"), 0.0),
            ("IND_TRIGGER_SOFR_DOLLAR_DRAIN", "MODEL_25.19", ("SOFR",),
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
            "IND_TRIGGER_GSCPI_LOGISTICS", "MODEL_25.19", series, ("GSCPI",),
            lambda v: v["GSCPI"], use_difference=True,
        )
        self.assertEqual(result["value"], 1.0)
        self.assertEqual(result["status"], "OK")
        series["GSCPI"]["year_ago_date"] = None
        result = relationships.calc_annual_trigger(
            "IND_TRIGGER_GSCPI_LOGISTICS", "MODEL_25.19", series, ("GSCPI",),
            lambda v: v["GSCPI"], use_difference=True,
        )
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "MISSING_DATA")
        self.assertIn("GSCPI.year_ago_date", result["warning"])

    def test_nonpositive_prior_is_not_used_for_percentage_change(self):
        result = relationships.calc_annual_trigger(
            "IND_TRIGGER_SOFR_DOLLAR_DRAIN", "MODEL_25.19", {"SOFR": entry(1.0, 0.0)},
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
            "IND_TRIGGER_HORMUZ_SPREAD", "MODEL_25.19", series,
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
