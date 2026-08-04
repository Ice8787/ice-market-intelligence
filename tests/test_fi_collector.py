import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fi_collector import number_sv, parse_page  # noqa: E402


SAMPLE = """<table><tbody><tr>
<td>2026-08-03</td><td>Svensk Kraft AB</td><td>Anna Andersson</td><td>Verkställande direktör (VD)</td><td></td><td>Förvärv</td><td>Svensk Kraft B</td><td>Aktie</td><td>SE0000000000</td><td>2026-08-01</td><td>12 500</td><td>Antal</td><td>24,50</td><td>SEK</td><td></td><td><a href="/detail/1">Anmälan</a></td>
</tr></tbody></table>"""


class FiCollectorTests(unittest.TestCase):
    def test_swedish_number(self):
        self.assertEqual(number_sv("12 500"), 12500)
        self.assertEqual(number_sv("24,50"), 24.5)

    def test_public_row(self):
        rows = parse_page(SAMPLE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["market"], "Sverige")
        self.assertEqual(row["category"], "Energi")
        self.assertEqual(row["person_name"], "Anna Andersson")
        self.assertEqual(row["value_local"], 306250)
        self.assertEqual(row["currency"], "SEK")


if __name__ == "__main__": unittest.main()
