"""Collect official US policy documents and correlate them without alleging causation."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date

from update_data import classify

API = "https://www.federalregister.gov/api/v1/documents.json"
TERMS = ("tariff", "trade", "export controls", "defense procurement")


def collect_policy_events(per_term: int = 35) -> tuple[list[dict], dict]:
    events: dict[str, dict] = {}
    status = {"ok": True, "terms": {}, "source": "Federal Register API"}
    for term in TERMS:
        params = urllib.parse.urlencode({"per_page": per_term, "order": "newest", "conditions[term]": term})
        request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "IceMarketIntelligence/3.0 public-research"})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                results = json.loads(response.read().decode("utf-8")).get("results", [])
            status["terms"][term] = {"ok": True, "records": len(results)}
            for item in results:
                title = str(item.get("title") or "")
                abstract = str(item.get("abstract") or "")
                category, subcategory = classify(f"{title} {abstract}")
                number = str(item.get("document_number") or item.get("html_url") or title)
                agencies = [a.get("name", "") for a in item.get("agencies", []) if isinstance(a, dict)]
                events[number] = {
                    "id": number, "title": title, "publication_date": item.get("publication_date"),
                    "document_type": item.get("type"), "abstract": abstract,
                    "category": category, "subcategory": subcategory, "search_term": term,
                    "agencies": agencies, "source_url": item.get("html_url"),
                    "is_official": True,
                }
        except Exception as error:
            status["ok"] = False
            status["terms"][term] = {"ok": False, "error": str(error)}
    return sorted(events.values(), key=lambda row: row.get("publication_date") or "", reverse=True), status


def attach_policy_matches(trades: list[dict], events: list[dict]) -> None:
    for trade in trades:
        if trade.get("person_type") != "political":
            continue
        try:
            traded = date.fromisoformat(trade["transaction_date"])
        except ValueError:
            continue
        matches = []
        for event in events:
            try:
                published = date.fromisoformat(event.get("publication_date") or "")
            except ValueError:
                continue
            delta = (traded - published).days
            same_category = event.get("category") == trade.get("category") and event.get("category") != "Övrigt"
            text = f"{event.get('title','')} {event.get('abstract','')}".lower()
            ticker_hit = trade.get("ticker", "").lower() in text
            if abs(delta) <= 45 and (same_category or ticker_hit):
                matches.append({"event_id": event["id"], "title": event["title"], "publication_date": event["publication_date"], "days_from_event": delta, "source_url": event["source_url"], "category": event["category"]})
        trade["policy_matches"] = sorted(matches, key=lambda row: abs(row["days_from_event"]))[:3]
        if matches:
            trade["score"] = min(100, trade.get("score", 0) + 7)
            trade.setdefault("score_reasons", []).append("Nära offentligt policybeslut – samband, inte bevis")
