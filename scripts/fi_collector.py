"""Collect recent Swedish PDMR transactions from Finansinspektionen.

The public register exposes paged HTML and an export function. This collector
uses a deliberately bounded number of result pages, identifies itself, and is
designed to accumulate records over scheduled GitHub Actions runs.
"""
from __future__ import annotations

import hashlib
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import date

from scoring import score_transaction
from update_data import classify

BASE = "https://marknadssok.fi.se/Publiceringsklient/sv-SE/Search/Search/Insyn"
MAX_PAGES = int(os.environ.get("MAX_FI_PAGES", "20"))


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict]] = []
        self.row: list[dict] | None = None
        self.cell: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr": self.row = []
        elif tag == "td" and self.row is not None: self.cell = {"text": [], "href": ""}
        elif tag == "a" and self.cell is not None and values.get("href"): self.cell["href"] = values["href"]

    def handle_data(self, data: str) -> None:
        if self.cell is not None: self.cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.cell is not None and self.row is not None:
            self.cell["text"] = " ".join("".join(self.cell["text"]).split())
            self.row.append(self.cell); self.cell = None
        elif tag == "tr" and self.row is not None:
            if len(self.row) >= 15: self.rows.append(self.row)
            self.row = None


def fetch_page(page: int) -> str:
    query = urllib.parse.urlencode({"SearchFunctionType": "Insyn", "button": "search", "language": "sv-se", "page": page, "paging": "True"})
    request = urllib.request.Request(f"{BASE}?{query}", headers={"User-Agent": os.environ.get("FI_USER_AGENT", "IceMarketIntelligence/3.0 contact@example.com")})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read().decode("utf-8", errors="replace")


def number_sv(value: str) -> float:
    cleaned = re.sub(r"[^0-9,.-]", "", value.replace("\xa0", "").replace(" ", ""))
    if not cleaned: return 0.0
    if "," in cleaned: cleaned = cleaned.replace(".", "").replace(",", ".")
    try: return float(cleaned)
    except ValueError: return 0.0


def parse_page(html: str) -> list[dict]:
    parser = TableParser(); parser.feed(html)
    rows = []
    for cells in parser.rows:
        texts = [cell["text"] for cell in cells]
        published, company, person, role, related, nature, instrument, instrument_type, isin, trade_date, volume, unit, price, currency, status = texts[:15]
        action = nature.casefold()
        if "förvärv" in action: trade_type, code = "buy", "P"
        elif "avyttring" in action: trade_type, code = "sell", "S"
        else: continue
        shares, price_value = number_sv(volume), number_sv(price)
        value = shares * price_value
        category, subcategory = classify(f"{company} {instrument}")
        source_href = cells[-1].get("href", "")
        source_url = urllib.parse.urljoin(BASE, source_href) if source_href else BASE
        person_id = hashlib.sha256(f"SE|{person}|{role}".encode()).hexdigest()[:14]
        tx_id = hashlib.sha256(f"FI|{company}|{person}|{trade_date}|{nature}|{volume}|{price}|{isin}".encode()).hexdigest()[:18]
        score, reasons = score_transaction(code=code, role=role, value_usd=value / 10, filing_date=published)
        reasons.append("Storlekspoäng använder konservativ SEK/USD-normalisering")
        role_key = role.casefold()
        person_type = "business_leader" if any(term in role_key for term in ("verkställande direktör", " vd", "ceo", "koncernchef")) else "corporate_insider"
        try:
            reporting_delay = max(0, (date.fromisoformat(published) - date.fromisoformat(trade_date)).days)
        except ValueError:
            reporting_delay = None
        rows.append({
            "id": tx_id, "person_id": person_id, "person_name": person, "person_role": role,
            "person_type": person_type, "issuer_cik": "", "company": company,
            "ticker": isin or instrument, "market": "Sverige", "country": "SE", "currency": currency or "SEK", "value_local": value,
            "category": category, "subcategory": subcategory, "transaction_date": trade_date,
            "filing_date": published, "reporting_delay_days": reporting_delay, "disclosure_type": "FI:s insynsregister", "type": trade_type,
            "transaction_code": code, "shares": shares, "purchase_price": price_value, "value_usd": 0.0,
            "score": score, "signal_label": "Offentlig svensk insynstransaktion", "score_reasons": reasons,
            "prices": {"day_minus_7": None, "purchase": price_value or None, "day_7": None, "day_30": None, "day_90": None},
            "returns": {"day_7": None, "day_30": None, "day_90": None}, "benchmark_return_90d": None,
            "excess_return_90d": None, "pattern_tags": [category, role, nature, "närstående" if related else "egen rapport"],
            "analysis": "Hämtad från Finansinspektionens offentliga insynsregister. FI publicerar rapportörens uppgifter automatiskt och granskar dem inte före publicering.",
            "source_url": source_url, "is_demo": False,
        })
    return rows


def collect_sweden() -> list[dict]:
    results = []
    for page in range(1, MAX_PAGES + 1):
        parsed = parse_page(fetch_page(page))
        if not parsed: break
        results.extend(parsed)
    return results
