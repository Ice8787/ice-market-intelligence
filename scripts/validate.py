"""Validate repository layout and dashboard data schema."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["index.html", "assets/app.js", "assets/fallback-data.js", "assets/styles.css", "assets/market.css", "start-windows.bat", "start-local.ps1", "config/leader-watchlist.json", "data/transactions.json", "data/people.json", "data/patterns.json", "data/metadata.json", ".github/workflows/pages.yml", ".github/workflows/update-data.yml", ".gitignore", ".nojekyll"]


def read(name: str):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def main() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing: raise SystemExit(f"Missing required paths: {', '.join(missing)}")
    for path in sorted((ROOT / "data").glob("*.json")):
        json.loads(path.read_text(encoding="utf-8")); print(f"valid JSON: {path.relative_to(ROOT)}")
    json.loads((ROOT / "config/leader-watchlist.json").read_text(encoding="utf-8"))
    trades, people, patterns, meta = read("transactions.json"), read("people.json"), read("patterns.json"), read("metadata.json")
    trade_keys = {"id","person_id","person_name","person_type","company","ticker","market","country","currency","value_local","category","subcategory","shares","purchase_price","value_usd","prices","returns","score","source_url","is_demo"}
    for index, row in enumerate(trades):
        absent = trade_keys - row.keys()
        if absent: raise SystemExit(f"transactions[{index}] missing: {sorted(absent)}")
        if row["type"] not in {"buy","sell"} or not 0 <= row["score"] <= 100: raise SystemExit(f"transactions[{index}] invalid type or score")
        if set(row["prices"]) != {"day_minus_7","purchase","day_7","day_30","day_90"}: raise SystemExit(f"transactions[{index}] invalid price windows")
        if set(row["returns"]) != {"day_7","day_30","day_90"}: raise SystemExit(f"transactions[{index}] invalid return windows")
    person_ids = {p["id"] for p in people}
    if any(t["type"] == "buy" and t["person_id"] not in person_ids for t in trades): raise SystemExit("buy references person missing from people.json")
    trade_ids = {t["id"] for t in trades}
    if any(not set(p["trade_ids"]).issubset(trade_ids) for p in patterns): raise SystemExit("pattern references missing trade")
    if meta.get("schema_version") != 3: raise SystemExit("metadata schema_version must be 3")
    if meta.get("top_per_market_category") != 100: raise SystemExit("top_per_market_category must be 100")
    print("repository layout and dual-market v3 data schema are valid")


if __name__ == "__main__": main()
