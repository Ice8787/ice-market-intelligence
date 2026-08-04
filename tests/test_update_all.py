import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_all import retain_top  # noqa: E402


class RankingTests(unittest.TestCase):
    def test_retains_100_per_market_and_category(self):
        rows = []
        for market in ("USA", "Sverige"):
            for index in range(125):
                rows.append({"id": f"{market}-{index}", "market": market, "category": "Teknik", "value_local": index, "transaction_date": "2026-01-01"})
        kept = retain_top(rows)
        self.assertEqual(len(kept), 200)
        for market in ("USA", "Sverige"):
            values = [row["value_local"] for row in kept if row["market"] == market]
            self.assertEqual(min(values), 25)
            self.assertEqual(max(values), 124)


if __name__ == "__main__": unittest.main()
