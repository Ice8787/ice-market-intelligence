"""Enrich retained US transactions with daily price windows once per day."""
from __future__ import annotations

import json

from update_data import DATA, build_patterns, build_people, enrich_prices


def main() -> None:
    path = DATA / "transactions.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    live_us = [row for row in rows if row.get("market") == "USA" and not row.get("is_demo", True)]
    enrich_prices(live_us)
    for filename, payload in {"transactions.json": rows, "people.json": build_people(rows), "patterns.json": build_patterns(rows)}.items():
        (DATA / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
