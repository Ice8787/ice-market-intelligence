"""Merge US and Swedish sources and retain top 100 trades per category/market."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from fi_collector import collect_sweden
from update_data import DATA, build_patterns, build_people, collect_usa

TOP_PER_GROUP = 100


def existing_verified() -> list[dict]:
    path = DATA / "transactions.json"
    if not path.exists(): return []
    try: rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return []
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
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in unique.values(): groups[(row["market"], row["category"])].append(row)
    retained = []
    for trades in groups.values():
        trades.sort(key=lambda row: (row.get("value_local", 0), row.get("transaction_date", "")), reverse=True)
        retained.extend(trades[:TOP_PER_GROUP])
    return sorted(retained, key=lambda row: row.get("transaction_date", ""), reverse=True)


def main() -> None:
    current = existing_verified()
    source_status = {}
    try: usa = collect_usa(); source_status["USA"] = {"ok": True, "new_records": len(usa)}
    except Exception as error: usa = []; source_status["USA"] = {"ok": False, "error": str(error)}
    try: sweden = collect_sweden(); source_status["Sverige"] = {"ok": True, "new_records": len(sweden)}
    except Exception as error: sweden = []; source_status["Sverige"] = {"ok": False, "error": str(error)}
    if not current and not usa and not sweden:
        raise RuntimeError("No verified records were available; preserving the existing published dataset")
    rows = retain_top([*current, *usa, *sweden])
    people, patterns = build_people(rows), build_patterns(rows)
    DATA.mkdir(exist_ok=True)
    for filename, payload in {"transactions.json": rows, "people.json": people, "patterns.json": patterns}.items():
        (DATA / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    group_counts: dict[str, int] = defaultdict(int)
    for row in rows: group_counts[f"{row['market']}|{row['category']}"] += 1
    metadata = {"schema_version": 3, "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "source": "SEC EDGAR Form 4 + Finansinspektionens insynsregister", "is_demo": False, "record_count": len(rows), "people_count": len(people), "top_per_market_category": TOP_PER_GROUP, "group_counts": dict(group_counts), "source_status": source_status, "notice": "Visar högst 100 största bevarade affärer per marknad och kategori, sorterat på rapporterat värde i lokal valuta."}
    (DATA / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
