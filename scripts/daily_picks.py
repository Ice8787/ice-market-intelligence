"""Create five transparent daily watchlist candidates, never guaranteed picks."""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date


def build_daily_picks(trends: list[dict], trades: list[dict], limit: int = 5) -> list[dict]:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        if trade.get("type") == "buy" and trade.get("ticker"):
            by_ticker[trade["ticker"]].append(trade)
    candidates = []
    for trend in trends:
        ticker = trend["ticker"]
        buys = sorted(by_ticker.get(ticker, []), key=lambda row: row.get("transaction_date", ""), reverse=True)
        recent = buys[:5]
        trade_signal = max((row.get("score", 0) for row in recent), default=0)
        cluster_bonus = min(12, max(0, len({row.get("person_id") for row in recent}) - 1) * 4)
        score = round(trend.get("trend_score", 0) * 0.72 + trade_signal * 0.18 + cluster_bonus)
        risks = []
        if (trend.get("rsi14") or 0) >= 72: risks.append("Hög RSI – rekylrisk")
        if (trend.get("volume_ratio") or 0) < 0.8: risks.append("Volymen bekräftar inte rörelsen")
        if (trend.get("momentum20") or 0) > 25: risks.append("Mycket snabb uppgång – förhöjd volatilitet")
        if not recent: risks.append("Ingen matchande offentlig köpsignal i datasetet")
        returns30 = [row.get("returns", {}).get("day_30") for row in buys if row.get("returns", {}).get("day_30") is not None]
        returns90 = [row.get("returns", {}).get("day_90") for row in buys if row.get("returns", {}).get("day_90") is not None]
        supporters = [{
            "person_name": row.get("person_name"), "person_type": row.get("person_type"),
            "date": row.get("transaction_date"), "value": row.get("value_local"),
            "currency": row.get("currency"), "source_url": row.get("source_url"),
        } for row in recent]
        confidence = "Stark bevakningssignal" if score >= 70 else "Måttlig bevakningssignal" if score >= 50 else "Svag bevakningssignal"
        candidates.append({
            "rank": 0, "ticker": ticker, "as_of": trend.get("as_of", date.today().isoformat()),
            "watch_score": max(0, min(100, score)), "label": confidence,
            "current_price": trend.get("current_price"), "momentum20": trend.get("momentum20"),
            "momentum60": trend.get("momentum60"), "volume_ratio": trend.get("volume_ratio"),
            "rsi14": trend.get("rsi14"), "trend_score": trend.get("trend_score"),
            "reasons": trend.get("reasons", []), "risk_flags": risks,
            "supporting_buys": supporters, "supporting_buy_count": len(buys),
            "historical_median_30d": statistics.median(returns30) if returns30 else None,
            "historical_median_90d": statistics.median(returns90) if returns90 else None,
            "notice": "Bevakningskandidat baserad på historisk pris/volym och offentliga rapporter. Inte personlig rådgivning eller garanti för uppgång.",
        })
    candidates.sort(key=lambda row: (row["watch_score"], row.get("volume_ratio") or 0, row.get("momentum20") or 0), reverse=True)
    selected = candidates[:limit]
    for index, row in enumerate(selected, 1): row["rank"] = index
    return selected
