import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_data import classify, parse_form4  # noqa: E402


SAMPLE_FORM4 = b"""<?xml version="1.0"?>
<ownershipDocument>
  <periodOfReport>2026-07-01</periodOfReport>
  <issuer><issuerCik>0001234567</issuerCik><issuerName>Example Energy Grid Inc</issuerName><issuerTradingSymbol>GRID</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>1</isOfficer><officerTitle><value>Chief Executive Officer</value></officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable><nonDerivativeTransaction>
    <transactionDate><value>2026-07-01</value></transactionDate>
    <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>25.50</value></transactionPricePerShare></transactionAmounts>
  </nonDerivativeTransaction></nonDerivativeTable>
</ownershipDocument>"""


class Form4Tests(unittest.TestCase):
    def test_purchase_fields_and_category(self):
        rows = parse_form4(SAMPLE_FORM4, "https://www.sec.gov/example", "2026-07-02")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["person_name"], "DOE JANE")
        self.assertEqual(row["ticker"], "GRID")
        self.assertEqual(row["category"], "Energi")
        self.assertEqual(row["shares"], 1000)
        self.assertEqual(row["value_usd"], 25500)
        self.assertEqual(row["type"], "buy")

    def test_unknown_category_is_explicit(self):
        self.assertEqual(classify("Acme Holdings")[0], "Övrigt")


if __name__ == "__main__":
    unittest.main()
