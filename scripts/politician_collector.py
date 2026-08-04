"""Collect disclosed US congressional trades from public disclosure mirrors.

House and Senate filings are the legal source of record. Their public search
sites are not stable machine APIs, so this collector uses open JSON mirrors
and always preserves a link back to the original PTR when one is supplied.
Reported amounts are ranges; value_local is the midpoint estimate.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import date, datetime

from scoring import score_transaction
from update_data import classify

SOURCES = (
    ("House Stock Watcher", "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"),
    ("Senate Stock Watcher", "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"),
)
HOUSE_SEARCH = "https://disclosures-clerk.house.gov/FinancialDisclosure"
SENATE_SEARCH = "https://efdsearch.senate.gov/search/home/"


def fetch_json(url: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "IceMarketIntelligence/3.0 public-research"})
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else payload.get("data", [])


def parse_date(value: object, fallback: str | None = None) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return fallback or date.today().isoformat()


def amount_range(value: object) -> tuple[float, float, float]:
    numbers = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", str(value or ""))]
    if not numbers:
        return 0.0, 0.0, 0.0
    low, high = numbers[0], numbers[-1]
    if "million" in str(value).lower():
        low, high = low * 1_000_000, high * 1_000_000
    return low, high, (low + high) / 2


def normalize_type(value: object) -> str | None:
    text = str(value or "").lower()
    if any(word in text for word in ("purchase", "buy", "köp")):
        return "buy"
    if any(word in text for word in ("sale", "sell", "sälj")):
        return "sell"
    return None


def normalize_row(raw: dict, provider: str) -> dict | None:
    ticker = str(raw.get("ticker") or "").strip().upper().replace("--", "")
    tx_type = normalize_type(raw.get("type") or raw.get("transaction_type"))
    if not tx_type or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,8}", ticker):
        return None
    person = str(raw.get("representative") or raw.get("senator") or raw.get("name") or "Okänd politiker").strip()
    chamber = "Representanthuset" if "House" in provider else "Senaten"
    asset = str(raw.get("asset_description") or raw.get("asset_name") or ticker).strip()
    transaction_date = parse_date(raw.get("transaction_date"))
    filing_date = parse_date(raw.get("disclosure_date") or raw.get("filing_date"), transaction_date)
    low, high, midpoint = amount_range(raw.get("amount"))
    category, subcategory = classify(f"{asset} {ticker}")
    source_url = str(raw.get("ptr_link") or raw.get("source_url") or (HOUSE_SEARCH if chamber == "Representanthuset" else SENATE_SEARCH))
    score, reasons = score_transaction(code="P" if tx_type == "buy" else "S", role=chamber, value_usd=midpoint, filing_date=filing_date)
    if tx_type == "buy":
        score = min(100, score + 5)
        reasons.append("Offentligt rapporterat politikerköp")
    tx_id = hashlib.sha256(f"POL|{provider}|{person}|{ticker}|{transaction_date}|{tx_type}|{midpoint}".encode()).hexdigest()[:18]
    person_id = hashlib.sha256(f"POL|{person}|{chamber}".encode()).hexdigest()[:14]
    try:
        delay = max(0, (date.fromisoformat(filing_date) - date.fromisoformat(transaction_date)).days)
    except ValueError:
        delay = None
    return {
        "id": tx_id, "person_id": person_id, "person_name": person, "person_role": chamber,
        "person_type": "political", "issuer_cik": "", "company": asset, "ticker": ticker,
        "market": "USA", "country": "US", "currency": "USD", "value_local": midpoint,
        "amount_min": low, "amount_max": high, "amount_midpoint": midpoint,
        "category": category, "subcategory": subcategory, "transaction_date": transaction_date,
        "filing_date": filing_date, "reporting_delay_days": delay,
        "disclosure_type": f"Congressional PTR · {chamber}", "type": tx_type,
        "transaction_code": "P" if tx_type == "buy" else "S", "shares": 0.0,
        "purchase_price": 0.0, "value_usd": midpoint, "score": score,
        "signal_label": "Rapporterad politikertransaktion", "score_reasons": reasons,
        "prices": {"day_minus_7": None, "purchase": None, "day_7": None, "day_30": None, "day_90": None},
        "returns": {"day_7": None, "day_30": None, "day_90": None},
        "benchmark_return_90d": None, "excess_return_90d": None,
        "estimated_profit_30d": None, "estimated_profit_90d": None,
        "pattern_tags": ["politiker", chamber, category], "policy_matches": [],
        "analysis": "Beloppet är mittpunkten i rapporterat intervall. Kursreaktion och uppskattad vinst är modellvärden, inte deklarerad faktisk avkastning.",
        "source_provider": provider, "source_url": source_url, "is_demo": False,
    }


def collect_politicians(limit: int = 1000) -> tuple[list[dict], dict]:
    rows, status = [], {}
    for provider, url in SOURCES:
        try:
            raw_rows = fetch_json(url)
            parsed = [row for raw in raw_rows for row in [normalize_row(raw, provider)] if row]
            parsed.sort(key=lambda row: (row["transaction_date"], row["filing_date"]), reverse=True)
            rows.extend(parsed[:limit])
            status[provider] = {"ok": True, "records": len(parsed)}
        except Exception as error:
            status[provider] = {"ok": False, "error": str(error)}
    unique = {row["id"]: row for row in rows}
    return sorted(unique.values(), key=lambda row: row["transaction_date"], reverse=True), status
