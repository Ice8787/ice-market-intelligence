"""Collect increases in selected institutional managers' quarterly 13F holdings."""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date

from update_data import classify, fetch

MANAGERS = (
    ("Berkshire Hathaway", "0001067983"),
    ("Bridgewater Associates", "0001350694"),
    ("Pershing Square Capital Management", "0001336528"),
    ("Soros Fund Management", "0001029160"),
)


def text_by_local(node: ET.Element, name: str) -> str:
    for child in node.iter():
        if child.tag.split("}")[-1] == name and child.text:
            return child.text.strip()
    return ""


def filing_rows(cik: str) -> list[dict]:
    payload = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{cik}.json", accept="application/json").decode("utf-8"))
    recent = payload.get("filings", {}).get("recent", {})
    rows = []
    for index, form in enumerate(recent.get("form", [])):
        if form == "13F-HR":
            rows.append({key: recent.get(key, [""] * (index + 1))[index] for key in ("accessionNumber", "filingDate", "reportDate", "primaryDocument")})
    return rows[:2]


def holdings(cik: str, filing: dict) -> dict[str, dict]:
    accession = filing["accessionNumber"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/"
    index = json.loads(fetch(base + "index.json", accept="application/json").decode("utf-8"))
    names = [item.get("name", "") for item in index.get("directory", {}).get("item", [])]
    candidates = [name for name in names if name.lower().endswith(".xml") and ("info" in name.lower() or "table" in name.lower())]
    if not candidates:
        candidates = [name for name in names if name.lower().endswith(".xml") and name != filing.get("primaryDocument")]
    if not candidates:
        return {}
    root = ET.fromstring(fetch(base + candidates[0], accept="application/xml"))
    result = {}
    for item in root.iter():
        if item.tag.split("}")[-1] != "infoTable":
            continue
        cusip = text_by_local(item, "cusip")
        issuer = text_by_local(item, "nameOfIssuer")
        try: shares = float(text_by_local(item, "sshPrnamt").replace(",", ""))
        except ValueError: shares = 0.0
        try: value = float(text_by_local(item, "value").replace(",", "")) * 1000
        except ValueError: value = 0.0
        if cusip: result[cusip] = {"issuer": issuer, "shares": shares, "value": value}
    return result


def collect_institutional() -> tuple[list[dict], dict]:
    all_rows, status = [], {}
    for manager, cik in MANAGERS:
        try:
            filings = filing_rows(cik)
            if len(filings) < 2: raise ValueError("Färre än två 13F-HR-rapporter")
            current, previous = holdings(cik, filings[0]), holdings(cik, filings[1])
            rows = []
            for cusip, item in current.items():
                old = previous.get(cusip, {"shares": 0, "value": 0})
                share_change = item["shares"] - old["shares"]
                value_change = max(0, item["value"] - old["value"])
                if share_change <= 0: continue
                category, subcategory = classify(item["issuer"])
                source = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filings[0]['accessionNumber'].replace('-', '')}/"
                row_id = hashlib.sha256(f"13F|{cik}|{cusip}|{filings[0]['reportDate']}".encode()).hexdigest()[:18]
                person_id = hashlib.sha256(f"13F|{cik}".encode()).hexdigest()[:14]
                rows.append({
                    "id": row_id, "person_id": person_id, "person_name": manager, "person_role": "Institutionell kapitalförvaltare",
                    "person_type": "institutional_investor", "issuer_cik": "", "company": item["issuer"], "ticker": cusip,
                    "market": "USA", "country": "US", "currency": "USD", "value_local": value_change,
                    "category": category, "subcategory": subcategory, "transaction_date": filings[0]["reportDate"],
                    "filing_date": filings[0]["filingDate"], "reporting_delay_days": max(0, (date.fromisoformat(filings[0]["filingDate"]) - date.fromisoformat(filings[0]["reportDate"])).days),
                    "disclosure_type": "SEC Form 13F-HR positionsökning", "type": "buy", "transaction_code": "13F+",
                    "shares": share_change, "purchase_price": 0.0, "value_usd": value_change, "score": 45,
                    "signal_label": "Kvartalsvis positionsökning", "score_reasons": ["Ökat rapporterat aktieantal mellan två kvartal"],
                    "prices": {"day_minus_7": None, "purchase": None, "day_7": None, "day_30": None, "day_90": None},
                    "returns": {"day_7": None, "day_30": None, "day_90": None}, "benchmark_return_90d": None, "excess_return_90d": None,
                    "pattern_tags": ["13F", category, "positionsökning"],
                    "analysis": "Beräknad ökning mellan två kvartalsvisa 13F-innehav. Det är inte ett exakt köpdatum, köppris eller bevis på att positionen fortfarande ägs.",
                    "source_provider": "SEC EDGAR 13F-HR", "source_url": source, "is_demo": False,
                })
            all_rows.extend(rows)
            status[manager] = {"ok": True, "records": len(rows), "report_date": filings[0]["reportDate"]}
        except Exception as error:
            status[manager] = {"ok": False, "error": str(error)}
    return all_rows, status
