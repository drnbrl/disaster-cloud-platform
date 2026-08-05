from shared.models import AiAnalysis, Needs
from shared.priority import calculate_priority


def analysis(**changes):
    data = {"people_count": None, "injured_count": None, "needs": Needs(), "vulnerable_groups": [], "risk_signals": [], "location_text": None, "summary": "Sentetik test.", "confidence": 0.9}
    data.update(changes)
    return AiAnalysis(**data)


def test_empty_is_low():
    result = calculate_priority(analysis())
    assert result["level"] == "low"
    assert 0 <= result["score"] <= 100


def test_medical_water_baby_is_critical():
    result = calculate_priority(analysis(people_count=25, injured_count=2, needs=Needs(water=True, medical=True, baby_support=True), vulnerable_groups=["babies"]))
    assert result["level"] == "critical"
    assert result["score"] == 86


def test_immediate_risk_overrides():
    assert calculate_priority(analysis(risk_signals=["breathing_difficulty"]))["level"] == "critical"
