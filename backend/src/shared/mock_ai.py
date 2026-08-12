from __future__ import annotations

import re
import unicodedata

from shared.models import AiAnalysis, Needs


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text.casefold()).replace("\u0307", "")


def _number(patterns: list[str], text: str) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _has(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def analyze_with_mock(message: str) -> AiAnalysis:
    text = _norm(message)
    people = _number([r"(\d{1,7})\s*(?:kişiyiz|kisiyiz|kişi|kisi|insan)", r"(?:toplam|yaklaşık|yaklasik)\s*(\d{1,7})"], text)
    injured = _number([r"(\d{1,7})\s*(?:yaralı|yarali)", r"(?:yaralı|yarali)\s*[:\-]?\s*(\d{1,7})"], text)

    water = _has(
    text,
    "su yok",
    "suyumuz bitti",
    "suyumuz tüken",
    "suyumuz tuken",
    "su bitti",
    "içme su",
    "icme su",
    "su ihtiyac",
    "su deste",
    "su lazım",
    "su lazim",
    "susuz",
)
    food = _has(text, "gıda", "gida", "yiyecek", "yemek yok", "açız", "aciz")
    shelter = _has(text, "çadır", "cadir", "barın", "barin", "evsiz", "evimiz yıkıldı", "evimiz yikildi")
    medical = injured is not None or _has(text, "yaralı", "yarali", "ilaç", "ilac", "doktor", "ambulans", "sağlık", "saglik", "kanama")
    electricity = _has(text, "elektrik yok", "enerji yok", "şarj", "sarj", "jeneratör", "jenerator")
    baby = _has(text, "bebek", "mama", "bez", "yenidoğan", "yenidogan")

    vulnerable: list[str] = []
    if baby:
        vulnerable.append("babies")
    if _has(text, "yaşlı", "yasli"):
        vulnerable.append("elderly")
    if _has(text, "engelli", "tekerlekli sandalye"):
        vulnerable.append("disabled_people")
    if _has(text, "hamile", "gebe"):
        vulnerable.append("pregnant_people")

    signal_terms = {
        "trapped_people": ("mahsur", "enkaz altında", "enkaz altinda", "çıkamıyoruz", "cikamiyoruz"),
        "active_fire": ("yangın devam", "yangin devam", "alev", "yanıyor", "yaniyor"),
        "severe_bleeding": ("ciddi kanama", "çok kan kaybed", "cok kan kaybed"),
        "unconscious_person": ("bilinci kapalı", "bilinci kapali", "baygın", "baygin"),
        "breathing_difficulty": ("nefes alam", "solunum güçlüğü", "solunum guclugu"),
        "building_collapse_risk": ("çökme riski", "cokme riski", "bina çatlak", "bina catlak"),
        "child_in_immediate_danger": ("bebek nefes", "çocuk ağır", "cocuk agir"),
        "injured_people": ("yaralı", "yarali"),
        "no_drinking_water": ("su yok", "suyumuz bitti", "içme su", "icme su", "suyumuz tüken", "suyumuz tuken", "su bitti"),
    }
    signals = [name for name, terms in signal_terms.items() if _has(text, *terms)]
    categories = [name for name, active in {"su": water, "gıda": food, "barınma": shelter, "sağlık": medical, "elektrik": electricity, "bebek desteği": baby}.items() if active]
    summary = f"{people} kişi" if people is not None else "Kişi sayısı belirsiz"
    summary += "; ihtiyaçlar: " + (", ".join(categories) if categories else "açık kategori bulunamadı") + "."
    known = sum([water, food, shelter, medical, electricity, baby])
    confidence = min(0.55 + known * 0.06 + (0.08 if people is not None else 0), 0.95)

    return AiAnalysis(
        people_count=people,
        injured_count=injured,
        needs=Needs(water=water, food=food, shelter=shelter, medical=medical, electricity=electricity, baby_support=baby),
        vulnerable_groups=vulnerable,
        risk_signals=signals,
        location_text=None,
        summary=summary,
        confidence=confidence,
    )
