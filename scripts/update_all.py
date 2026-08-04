"""Merge US/S Swedish insiders, US politicians, policy events and trend data."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from fi_collector import collect_sweden
from policy_collector import attach_policy_matches, collect_policy_events
from politician_collector import collect_politicians
from trend_analyzer import build_trends
from update_data import DATA, build_patterns, build_people, collect_usa, enrich_prices

TOP_PER_GROUP = 100


def read_json(name: str, default):
    path = DATA / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def existing_verified() -> list[dict]:
    rows = read_json("transactions.json", [])
    verified = []
    for row in rows:
        if row.get("is_demo", True):
            continue
        if "market" not in row:
            row["market"] = "Sverige" if "fi.se" in row.get("source_url", "") else "USA"
            row["country"] = "SE" if row["market"] == "Sverige" else "US"
            row["currency"] = "SEK" if row["market"] == "Sverige" else "USD"
            row["value_local"] = row.get("value_usd", 0)
        verified.append(row)
    return verified


def retain_top(rows: list[dict]) -> list[dict]:
    unique = {row["id"]: row for row in rows}
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in unique.values():
        group = "political" if row.get("person_type") == "political" else "insider"
        groups[(row["market"], row["category"], group)].append(row)
    retained = []
    for trades in groups.values():
        trades.sort(key=lambda row: (row.get("value_local", 0), row.get("transaction_date", "")), reverse=True)
        retained.extend(trades[:TOP_PER_GROUP])
    return sorted(retained, key=lambda row: row.get("transaction_date", ""), reverse=True)


def main() -> None:
    current = existing_verified()
    source_status = {}
    try:
        usa = collect_usa()
        source_status["USA corporate"] = {"ok": True, "new_records": len(usa)}
    except Exception as error:
        usa = []
        source_status["USA corporate"] = {"ok": False, "error": str(error)}
    try:
        sweden = collect_sweden()
        source_status["Sverige"] = {"ok": True, "new_records": len(sweden)}
    except Exception as error:
        sweden = []
        source_status["Sverige"] = {"ok": False, "error": str(error)}
    try:
        politicians, political_sources = collect_politicians()
        source_status["US politicians"] = {"ok": bool(politicians), "new_records": len(politicians), "providers": political_sources}
        enrich_prices(politicians)
    except Exception as error:
        politicians = []
        source_status["US politicians"] = {"ok": False, "error": str(error)}
    try:
        policy_events, policy_status = collect_policy_events()
        source_status["Federal Register"] = policy_status
    except Exception as error:
        policy_events = read_json("policy_events.json", [])
        source_status["Federal Register"] = {"ok": False, "error": str(error), "preserved_records": len(policy_events)}
    attach_policy_matches(politicians, policy_events)
    if not current and not usa and not sweden and not politicians:
        raise RuntimeError("No verified records were available; preserving the existing published dataset")
    rows = retain_top([*current, *usa, *sweden, *politicians])
    people, patterns = build_people(rows), build_patterns(rows)
    try:
        trends, trend_status = build_trends(rows, int(os.environ.get("MAX_TREND_TICKERS", "25")))
        if not trends:
            trends = read_json("trends.json", [])
        source_status["Trend data"] = trend_status
    except Exception as error:
        trends = read_json("trends.json", [])
        source_status["Trend data"] = {"ok": False, "error": str(error), "preserved_records": len(trends)}
    DATA.mkdir(exist_ok=True)
    outputs = {
        "transactions.json": rows,
        "people.json": people,
        "patterns.json": patterns,
        "policy_events.json": policy_events,
        "trends.json": trends,
    }
    for filename, payload in outputs.items():
        (DATA / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    group_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        group = "political" if row.get("person_type") == "political" else "insider"
        group_counts[f"{row['market']}|{row['category']}|{group}"] += 1
    metadata = {
        "schema_version": 4,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "SEC EDGAR Form 4 + Finansinspektionen + congressional disclosure mirrors + Federal Register + Stooq/Yahoo EOD",
        "is_demo": False,
        "record_count": len(rows),
        "people_count": len(people),
        "political_trade_count": sum(row.get("person_type") == "political" for row in rows),
        "policy_event_count": len(policy_events),
        "trend_count": len(trends),
        "top_per_market_category": TOP_PER_GROUP,
        "group_counts": dict(group_counts),
        "source_status": source_status,
        "notice": "Högst 100 affärer per marknad, kategori och persontyp. Politikbelopp är mittpunkter i rapporterade intervall. Policyträffar är tidssamband, inte bevis. Trendpoäng är inte en kursprognos.",
    }
    (DATA / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
