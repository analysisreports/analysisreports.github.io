import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from verify_country_relationships_source import compare_shelf


ROOT = Path(__file__).resolve().parent.parent


class CountryRelationshipsSourceTests(unittest.TestCase):
    def test_current_us_shelf_matches_json_twin(self):
        errors = compare_shelf(
            str(ROOT / "llms-country-relationships-us.txt"),
            str(ROOT / "llms-country-relationships-us.json"),
            "GEO_US",
            73,
        )
        self.assertEqual(errors, [])

    def test_reports_out_of_bounds_txt_stance(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "llms-country-relationships-us.txt"
            source = (ROOT / "llms-country-relationships-us.txt").read_text(
                encoding="utf-8"
            )
            temp_path.write_text(
                source.replace(
                    "Bilateral Stance: +0.95 (Special Relationship",
                    "Bilateral Stance: +1.25 (Special Relationship",
                    1,
                ),
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                errors = compare_shelf(
                    str(temp_path),
                    str(ROOT / "llms-country-relationships-us.json"),
                    "GEO_US",
                    73,
                )

        self.assertEqual(len(errors), 1)
        self.assertIn("Out-of-bounds Bilateral Stance", errors[0])


if __name__ == "__main__":
    unittest.main()
