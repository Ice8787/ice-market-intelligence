"""End-of-day momentum radar. It describes conditions; it does not predict price."""
from __future__ import annotations

import csv
import io
import math
import urllib.request


def fetch_stooq(ticker: str) -> list[dict]:
    symbol = ticker.lower().replace(".", "-") + ".us"
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    request = urllib.request.Request(url, headers={"User-Agent": "IceMarketIntelligence/3.0"})
    with urllib.request.urlopen(request, timeout=35) as response:
        text = response.read().decode("utf-8", errors="replace")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            rows.append({"date": row["Date"], "close": float(row["Close"]), "volume": float(row.get("Volume") or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    return rows[-260:]


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gains = sum(max(0, value) for value in changes) / period
    losses = sum(max(0, -value) for value in changes) / period
    return 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses)


def analyze_ticker(ticker: str) -> dict | None:
    series = fetch_stooq(ticker)
    if len(series) < 55:
        return None
    closes = [row["close"] for row in series]
    volumes = [row["volume"] for row in series]
    current = closes[-1]
    sma20, sma50 = sum(closes[-20:]) / 20, sum(closes[-50:]) / 50
    momentum20 = (current / closes[-21] - 1) * 100
    momentum60 = (current / closes[-61] - 1) * 100 if len(closes) > 61 else None
    avg_volume = sum(volumes[-21:-1]) / 20 or 1
    volume_ratio = volumes[-1] / avg_volume
    current_rsi = rsi(closes)
    score = 0
    reasons = []
    if current > sma20: score += 20; reasons.append("Kurs över 20-dagars medelvärde")
    if sma20 > sma50: score += 20; reasons.append("20-dagars trend över 50-dagars trend")
    if momentum20 > 5: score += 20; reasons.append("Positivt 20-dagars momentum")
    if volume_ratio > 1.5: score += 20; reasons.append("Ovanligt hög dagsvolym")
    if current_rsi is not None and 50 <= current_rsi <= 70: score += 15; reasons.append("RSI visar styrka utan extrem överköpt nivå")
    if current_rsi is not None and current_rsi > 80: score -= 10; reasons.append("Mycket hög RSI – rekylrisk")
    label = "Stark momentumtrend" if score >= 70 else "Positiv trend" if score >= 45 else "Neutral/svag trend"
    return {"ticker": ticker, "as_of": series[-1]["date"], "current_price": current, "sma20": round(sma20, 2), "sma50": round(sma50, 2), "momentum20": round(momentum20, 2), "momentum60": round(momentum60, 2) if momentum60 is not None else None, "volume_ratio": round(volume_ratio, 2), "rsi14": round(current_rsi, 1) if current_rsi is not None else None, "trend_score": max(0, min(100, score)), "label": label, "reasons": reasons, "warning": "Trendpoäng beskriver historiskt pris och volym. Den förutsäger inte en GameStop-liknande uppgång och innehåller inte realtidsorderbok eller verifierad blankningsgrad."}


def build_trends(trades: list[dict], limit: int = 80) -> tuple[list[dict], dict]:
    tickers = []
    for row in sorted(trades, key=lambda item: item.get("transaction_date", ""), reverse=True):
        ticker = row.get("ticker", "")
        if row.get("market") == "USA" and ticker and ticker not in tickers:
            tickers.append(ticker)
    trends, errors = [], {}
    for ticker in tickers[:limit]:
        try:
            trend = analyze_ticker(ticker)
            if trend: trends.append(trend)
        except Exception as error:
            errors[ticker] = str(error)
    return sorted(trends, key=lambda row: row["trend_score"], reverse=True), {"ok": bool(trends), "records": len(trends), "errors": errors}
