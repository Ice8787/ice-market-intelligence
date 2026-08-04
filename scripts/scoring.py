"""Transparent signal scoring for reported insider transactions."""
from __future__ import annotations

from datetime import date, datetime


def score_transaction(*, code: str, role: str, value_usd: float, filing_date: str, cluster_count: int = 1) -> tuple[int, list[str]]:
    score = 5
    reasons: list[str] = []
    if code == "P":
        score += 30
        reasons.append("Öppet marknadsköp")
    elif code == "S":
        score += 8
        reasons.append("Öppen marknadsförsäljning")
    else:
        reasons.append("Annan rapporterad transaktion")

    normalized_role = role.lower()
    if any(term in normalized_role for term in ("chief executive", "ceo", "chief financial", "cfo")):
        score += 15
        reasons.append("Ledande befattningshavare")
    elif "director" in normalized_role:
        score += 9
        reasons.append("Styrelseledamot")

    if value_usd >= 1_000_000:
        score += 22
        reasons.append("Mycket stort transaktionsvärde")
    elif value_usd >= 100_000:
        score += 15
        reasons.append("Stort transaktionsvärde")
    elif value_usd >= 10_000:
        score += 8
        reasons.append("Betydande transaktionsvärde")

    age = (date.today() - datetime.fromisoformat(filing_date).date()).days
    if age <= 7:
        score += 12
        reasons.append("Nyligen rapporterad")
    elif age <= 30:
        score += 7
        reasons.append("Rapporterad senaste månaden")

    if cluster_count >= 3:
        score += 16
        reasons.append("Kluster av minst tre insiders")
    elif cluster_count == 2:
        score += 9
        reasons.append("Två insiders i samma bolag")
    return min(score, 100), reasons
