from __future__ import annotations

from typing import Any

from shared.models import AiAnalysis

IMMEDIATE_RISKS = {
    "trapped_people",
    "active_fire",
    "severe_bleeding",
    "unconscious_person",
    "breathing_difficulty",
    "building_collapse_risk",
    "child_in_immediate_danger",
}


def calculate_priority(analysis: AiAnalysis) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    people = analysis.people_count or 0
    injured = analysis.injured_count or 0
    risks = set(analysis.risk_signals)
    immediate = bool(risks & IMMEDIATE_RISKS)

    if immediate:
        score += 30
        reasons.append("Doğrudan hayati tehlike sinyali bulundu")
    if "trapped_people" in risks:
        score += 25
        reasons.append("Mahsur kalan kişi bildirildi")
    if analysis.needs.medical:
        score += 20
        reasons.append("Sağlık desteği gerekiyor")
    if injured:
        score += min(injured * 8, 30)
        reasons.append(f"{injured} yaralı bildirildi")
    if analysis.needs.water:
        score += 12
        reasons.append("İçme suyu ihtiyacı var")
    if analysis.needs.shelter:
        score += 10
        reasons.append("Barınma ihtiyacı var")
    if analysis.needs.baby_support or analysis.vulnerable_groups:
        score += 10
        reasons.append("Hassas gruplar için destek gerekiyor")
    if analysis.needs.food:
        score += 6
        reasons.append("Gıda ihtiyacı var")
    if analysis.needs.electricity:
        score += 4
        reasons.append("Elektrik ihtiyacı var")

    active_needs = sum([
        analysis.needs.water, analysis.needs.food, analysis.needs.shelter,
        analysis.needs.medical, analysis.needs.electricity, analysis.needs.baby_support,
    ])
    if active_needs >= 3:
        score += 15
        reasons.append("Birden fazla temel ihtiyaç aynı anda bildirildi")
    if injured >= 2:
        score += 5
        reasons.append("Birden fazla yaralı bildirildi")

    if people >= 100:
        score += 18
        reasons.append("100 veya daha fazla kişi etkileniyor")
    elif people >= 50:
        score += 12
        reasons.append("50 veya daha fazla kişi etkileniyor")
    elif people >= 10:
        score += 8
        reasons.append("10 veya daha fazla kişi etkileniyor")

    score = min(score, 100)
    level = "critical" if immediate or score >= 80 else "high" if score >= 60 else "medium" if score >= 30 else "low"
    return {"score": score, "level": level, "reasons": reasons or ["Açık yüksek risk sinyali bulunamadı"]}
