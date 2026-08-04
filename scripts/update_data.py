"""Build live dashboard data from recent SEC Form 4 ownership filings.

SEC is the authoritative source for corporate-insider disclosures. Optional
Alpha Vantage enrichment adds daily prices when MARKET_DATA_API_KEY is set.
Political disclosures and 13F leader watchlists require separate collectors;
their planned source contracts are documented in docs/DATA_SOURCES.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scoring import score_transaction

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=only&count=100&output=atom"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAX_FILINGS = int(os.environ.get("MAX_SEC_FILINGS", "40"))
WATCHLIST_PATH = ROOT / "config" / "leader-watchlist.json"

CATEGORY_RULES = {
    "Försvar": ("defense", "aerospace", "weapon", "munition", "missile", "radar", "försvar", "vapen", "sensor"),
    "Energi": ("energy", "power", "solar", "nuclear", "uranium", "oil", "gas", "grid", "energi", "kraft", "elnät", "batteri"),
    "Teknik": ("technology", "software", "semiconductor", "comput", "cyber", "digital", "cloud", "data", "teknik", "system", "programvara"),
    "Hälsa": ("health", "medical", "pharma", "therapeut", "bio", "hospital", "hälsa", "läkemedel", "medicin", "vård"),
    "Finans": ("bank", "financial", "capital", "insurance", "credit", "finans", "försäkring", "kredit"),
    "Industri": ("industrial", "manufactur", "machinery", "material", "construction", "industri", "verkstad", "bygg"),
    "Konsument": ("retail", "consumer", "food", "beverage", "restaurant", "handel", "livsmedel", "konsument"),
    "Transport": ("airline", "transport", "automotive", "motor", "logistics", "shipping", "fordon", "sjöfart"),
}


def fetch(url: str, *, accept: str = "*/*") -> bytes:
    user_agent = os.environ.get("SEC_USER_AGENT", "IceMarketIntelligence/2.0 contact@example.com")
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": accept, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def node_text(node: ET.Element, path: str, default: str = "") -> str:
    value = node.findtext(path)
    return value.strip() if value else default


def as_float(value: str) -> float:
    try:
        return float(value.replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def classify(company: str) -> tuple[str, str]:
    lowered = company.lower()
    for category, words in CATEGORY_RULES.items():
        if any(word in lowered for word in words):
            return category, "Automatisk namnklassning – verifiera"
    return "Övrigt", "Ej klassificerad"


def leader_type(person: str, ticker: str) -> str:
    """Promote verified watchlist matches without inventing public figures."""
    try:
        watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))["leaders"]
    except (OSError, KeyError, json.JSONDecodeError):
        return "corporate_insider"
    person_key, ticker_key = person.casefold(), ticker.casefold()
    for leader in watchlist:
        names = [leader.get("name", ""), *leader.get("aliases", [])]
        tickers = [value.casefold() for value in leader.get("tickers", [])]
        if person_key in {name.casefold() for name in names} and (not tickers or ticker_key in tickers):
            return leader.get("person_type", "business_leader")
    return "corporate_insider"


def role_from(owner: ET.Element) -> str:
    relationship = owner.find("reportingOwnerRelationship")
    if relationship is None:
        return "Rapporteringsskyldig insider"
    title = node_text(relationship, "officerTitle/value")
    if title:
        return title
    roles = []
    if node_text(relationship, "isDirector") == "1": roles.append("Director")
    if node_text(relationship, "isOfficer") == "1": roles.append("Officer")
    if node_text(relationship, "isTenPercentOwner") == "1": roles.append("10% owner")
    if node_text(relationship, "isOther") == "1": roles.append("Other")
    return ", ".join(roles) or "Rapporteringsskyldig insider"


def find_form4_xml(index_url: str) -> str:
    html = fetch(index_url, accept="text/html").decode("utf-8", errors="replace")
    matches = re.findall(r'href=["\']([^"\']+\.xml)["\']', html, flags=re.I)
    candidates = [value for value in matches if "xsl" not in value.lower() and "primary_doc" not in value.lower()]
    if not candidates:
        raise ValueError("Form 4 XML document not found")
    return urllib.parse.urljoin(index_url, candidates[0])


def parse_form4(payload: bytes, source_url: str, filing_date: str) -> list[dict]:
    root = ET.fromstring(payload)
    company = node_text(root, "issuer/issuerName", "Okänt bolag")
    ticker = node_text(root, "issuer/issuerTradingSymbol", "N/A")
    cik = node_text(root, "issuer/issuerCik")
    period = node_text(root, "periodOfReport", filing_date)
    owners = root.findall("reportingOwner")
    category, subcategory = classify(company)
    rows: list[dict] = []
    transactions = root.findall("nonDerivativeTable/nonDerivativeTransaction")
    for owner in owners or [ET.Element("reportingOwner")]:
        person = node_text(owner, "reportingOwnerId/rptOwnerName", "Okänd rapportör")
        role = role_from(owner)
        person_id = hashlib.sha256(f"{person}|{role}".encode()).hexdigest()[:14]
        for tx in transactions:
            code = node_text(tx, "transactionCoding/transactionCode")
            if code not in {"P", "S"}:
                continue
            shares = as_float(node_text(tx, "transactionAmounts/transactionShares/value"))
            price = as_float(node_text(tx, "transactionAmounts/transactionPricePerShare/value"))
            transaction_date = node_text(tx, "transactionDate/value", period)
            try:
                reporting_delay = max(0, (date.fromisoformat(filing_date) - date.fromisoformat(transaction_date)).days)
            except ValueError:
                reporting_delay = None
            value = shares * price
            score, reasons = score_transaction(code=code, role=role, value_usd=value, filing_date=filing_date)
            tx_id = hashlib.sha256(f"{source_url}|{person}|{transaction_date}|{code}|{shares}".encode()).hexdigest()[:18]
            rows.append({
                "id": tx_id, "person_id": person_id, "person_name": person, "person_role": role,
                "person_type": leader_type(person, ticker), "issuer_cik": cik, "company": company, "ticker": ticker,
                "market": "USA", "country": "US", "currency": "USD", "value_local": value,
                "category": category, "subcategory": subcategory, "transaction_date": transaction_date,
                "filing_date": filing_date, "reporting_delay_days": reporting_delay, "disclosure_type": "SEC Form 4", "type": "buy" if code == "P" else "sell",
                "transaction_code": code, "shares": shares, "purchase_price": price, "value_usd": value,
                "score": score, "signal_label": "Verifierad Form 4-transaktion", "score_reasons": reasons,
                "prices": {"day_minus_7": None, "purchase": price or None, "day_7": None, "day_30": None, "day_90": None},
                "returns": {"day_7": None, "day_30": None, "day_90": None}, "benchmark_return_90d": None,
                "excess_return_90d": None, "pattern_tags": [category, role, "öppet marknadsköp" if code == "P" else "öppen marknadsförsäljning"],
                "analysis": "Transaktionen är hämtad från SEC Form 4. Kategori är automatisk och kursreaktion visas först när prisdata finns.",
                "source_url": source_url, "is_demo": False,
            })
    return rows


def parse_feed(payload: bytes) -> list[tuple[str, str]]:
    root = ET.fromstring(payload)
    filings = []
    for entry in root.findall("atom:entry", ATOM_NS)[:MAX_FILINGS]:
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS)
        link = entry.find("atom:link", ATOM_NS)
        if link is not None and link.attrib.get("href"):
            filings.append((link.attrib["href"], updated[:10] or date.today().isoformat()))
    return filings


def nearest_price(series: dict[str, float], target: date) -> float | None:
    for offset in range(0, 8):
        for candidate in (target + timedelta(days=offset), target - timedelta(days=offset)):
            value = series.get(candidate.isoformat())
            if value is not None:
                return value
    return None


def fetch_prices(ticker: str, api_key: str) -> dict[str, float]:
    params = urllib.parse.urlencode({"function": "TIME_SERIES_DAILY", "symbol": ticker, "outputsize": "compact", "apikey": api_key})
    payload = json.loads(fetch(f"https://www.alphavantage.co/query?{params}").decode("utf-8"))
    time_series = payload.get("Time Series (Daily)", {})
    return {day: as_float(values.get("4. close", "0")) for day, values in time_series.items()}


def enrich_prices(rows: list[dict]) -> None:
    api_key = os.environ.get("MARKET_DATA_API_KEY")
    max_tickers = int(os.environ.get("MAX_PRICE_TICKERS", "40"))
    stooq_fetch = None
    if not api_key:
        from trend_analyzer import fetch_market_series
        stooq_fetch = fetch_market_series
    cache: dict[str, dict[str, float]] = {}
    for row in rows:
        ticker = row["ticker"]
        if ticker not in cache and len(cache) >= max_tickers:
            continue
        if ticker not in cache:
            try:
                if api_key:
                    cache[ticker] = fetch_prices(ticker, api_key)
                else:
                    cache[ticker] = {item["date"]: item["close"] for item in stooq_fetch(ticker)}
            except Exception:
                cache[ticker] = {}
            time.sleep(0.8 if api_key else 0.15)
        series = cache[ticker]
        bought = date.fromisoformat(row["transaction_date"])
        purchase = nearest_price(series, bought) or row["purchase_price"] or None
        points = {"day_minus_7": -7, "purchase": 0, "day_7": 7, "day_30": 30, "day_90": 90}
        row["prices"] = {name: nearest_price(series, bought + timedelta(days=offset)) for name, offset in points.items()}
        row["prices"]["purchase"] = purchase
        if purchase:
            for horizon in (7, 30, 90):
                later = row["prices"][f"day_{horizon}"]
                row["returns"][f"day_{horizon}"] = round((later / purchase - 1) * 100, 2) if later else None
        midpoint = row.get("amount_midpoint")
        if midpoint:
            for horizon in (30, 90):
                result = row["returns"].get(f"day_{horizon}")
                row[f"estimated_profit_{horizon}d"] = round(midpoint * result / 100, 2) if result is not None else None


def build_people(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["type"] == "buy": groups[row["person_id"]].append(row)
    people = []
    for person_id, trades in groups.items():
        returns = [t["returns"]["day_90"] for t in trades if t["returns"]["day_90"] is not None]
        excess = [t["excess_return_90d"] for t in trades if t["excess_return_90d"] is not None]
        people.append({"id": person_id, "name": trades[0]["person_name"], "person_type": trades[0]["person_type"], "primary_role": trades[0]["person_role"], "categories": sorted({t["category"] for t in trades}), "history": {"tracked_buys": len(trades), "positive_90d_rate": round(100 * sum(v > 0 for v in returns) / len(returns)) if returns else 0, "median_return_90d": statistics.median(returns) if returns else None, "median_excess_90d": statistics.median(excess) if excess else None}, "history_note": "Beräknad från verifierade öppna marknadsköp som finns i den lokala datamängden."})
    return sorted(people, key=lambda item: item["history"]["tracked_buys"], reverse=True)


def build_patterns(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["type"] == "buy": groups[(row.get("market", "USA"), row["category"])].append(row)
    patterns = []
    for (market, category), trades in groups.items():
        if len(trades) < 2: continue
        values = [t["returns"]["day_90"] for t in trades if t["returns"]["day_90"] is not None]
        patterns.append({"id": f"category-{market.lower()}-{category.lower()}", "type": "Sektorkluster", "title": f"{len(trades)} insiderköp inom {category} · {market}", "description": "Flera rapporterade köp i samma marknad och breda kategori. Verifiera branschklassning, tidssamband och bolagsspecifika orsaker.", "categories": [market, category], "trade_ids": [t["id"] for t in trades], "trade_count": len(trades), "median_return_90d": statistics.median(values) if values else None})
    return patterns


def collect_usa() -> list[dict]:
    rows: list[dict] = []
    for index_url, filing_date in parse_feed(fetch(FEED, accept="application/atom+xml")):
        try:
            xml_url = find_form4_xml(index_url)
            rows.extend(parse_form4(fetch(xml_url, accept="application/xml"), index_url, filing_date))
        except Exception as error:
            print(f"warning: skipped {index_url}: {error}")
        time.sleep(0.15)
    enrich_prices(rows)
    return rows


def main() -> None:
    rows = collect_usa()
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    DATA.mkdir(exist_ok=True)
    outputs = {"transactions.json": rows, "people.json": build_people(rows), "patterns.json": build_patterns(rows)}
    for filename, payload in outputs.items():
        (DATA / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {"schema_version": 2, "generated_at": generated_at, "source": "SEC EDGAR Form 4" + (" + Alpha Vantage" if os.environ.get("MARKET_DATA_API_KEY") else ""), "is_demo": False, "record_count": len(rows), "people_count": len(outputs["people.json"]), "notice": "Transaktionerna kommer från SEC. Automatisk sektor och prisdata ska verifieras mot originalkälla."}
    (DATA / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
