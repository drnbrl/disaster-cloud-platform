from typing import Any

PUBLIC_FIELDS = {
    "requestId", "createdAt", "updatedAt", "city", "district", "address", "latitude", "longitude",
    "analysisStatus", "requestStatus", "peopleCount", "injuredCount", "needs", "summary",
    "priorityScore", "priorityLevel", "priorityReasons", "aiConfidence", "requiresHumanReview",
}


def public_request(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key in PUBLIC_FIELDS}


def admin_request(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("gsi")}
