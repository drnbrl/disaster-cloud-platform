from __future__ import annotations

import math
from typing import Any

RESOURCES = ("waterLiters", "tents", "medicalStaff", "blankets")
RESOURCE_CATEGORIES = ("water", "food", "shelter", "medical", "electricity", "general")


def _as_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _score(city: dict[str, Any], resource: str) -> float:
    critical = float(city.get("criticalRequests", 0))
    affected = float(city.get("affectedPeople", 0))
    if resource == "waterLiters":
        return float(city.get("waterRequests", 0)) * 5 + critical * 2 + affected * 0.05
    if resource == "tents":
        return float(city.get("shelterRequests", 0)) * 5 + critical + affected * 0.02
    if resource == "medicalStaff":
        return float(city.get("medicalRequests", 0)) * 8 + critical * 2 + float(city.get("injuredPeople", 0)) * 3
    if resource == "blankets":
        return float(city.get("shelterRequests", 0)) * 2 + critical + affected * 0.03
    raise ValueError(f"Unknown resource: {resource}")


def _category_score(city: dict[str, Any], category: str) -> float:
    critical = float(city.get("criticalRequests", 0))
    affected = float(city.get("affectedPeople", 0))
    injured = float(city.get("injuredPeople", 0))
    if category == "water":
        return _score(city, "waterLiters")
    if category == "food":
        return float(city.get("foodRequests", 0)) * 5 + critical + affected * 0.02
    if category == "shelter":
        return _score(city, "tents")
    if category == "medical":
        return _score(city, "medicalStaff")
    if category == "electricity":
        return float(city.get("electricityRequests", 0)) * 5 + critical + affected * 0.01
    if category == "general":
        need_requests = sum(
            float(city.get(key, 0))
            for key in ("waterRequests", "foodRequests", "shelterRequests", "medicalRequests", "electricityRequests", "babySupportRequests")
        )
        return (
            critical * 6
            + float(city.get("highRequests", 0)) * 4
            + float(city.get("mediumRequests", 0)) * 2
            + float(city.get("lowRequests", 0))
            + float(city.get("totalRequests", 0)) * 0.5
            + need_requests
            + affected * 0.03
            + injured * 2
        )
    raise ValueError(f"Unknown resource category: {category}")


def _largest_remainder(total: int, scores: dict[str, float]) -> tuple[dict[str, int], int]:
    total = max(0, total)
    positive = {city: score for city, score in scores.items() if score > 0}
    score_sum = sum(positive.values())
    if total <= 0 or score_sum <= 0:
        return {city: 0 for city in scores}, total
    exact = {city: total * score / score_sum for city, score in positive.items()}
    allocated = {city: math.floor(value) for city, value in exact.items()}
    remaining = total - sum(allocated.values())
    order = sorted(positive, key=lambda city: (exact[city] - allocated[city], positive[city], city), reverse=True)
    for city in order[:remaining]:
        allocated[city] += 1
    result = {city: allocated.get(city, 0) for city in scores}
    return result, total - sum(result.values())


def _custom_resources(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    raw_resources = inventory.get("customResources") or []
    if not isinstance(raw_resources, list):
        return []
    resources = []
    for item in raw_resources:
        if not isinstance(item, dict):
            continue
        quantity = _as_non_negative_int(item.get("quantity", 0))
        category = str(item.get("category", "general"))
        if quantity <= 0 or category not in RESOURCE_CATEGORIES:
            continue
        resources.append(
            {
                "name": str(item.get("name", "")).strip(),
                "quantity": quantity,
                "unit": str(item.get("unit", "")).strip(),
                "category": category,
            }
        )
    return resources


def calculate_allocation(inventory: dict[str, Any], city_stats: list[dict[str, Any]]) -> dict[str, Any]:
    cities = [str(item["city"]) for item in city_stats if item.get("city")]
    by_city = {str(item["city"]): item for item in city_stats if item.get("city")}
    distributions: dict[str, dict[str, int]] = {}
    unallocated: dict[str, Any] = {}
    fixed_need_scores = {
        city: {resource: round(_score(by_city[city], resource), 2) for resource in RESOURCES}
        for city in cities
    }
    for resource in RESOURCES:
        scores = {city: _score(by_city[city], resource) for city in cities}
        distributions[resource], unallocated[resource] = _largest_remainder(_as_non_negative_int(inventory.get(resource, 0)), scores)

    custom_resources = _custom_resources(inventory)
    custom_distributions = []
    for resource in custom_resources:
        scores = {city: _category_score(by_city[city], resource["category"]) for city in cities}
        distribution, remaining = _largest_remainder(resource["quantity"], scores)
        custom_distributions.append(
            {
                "resource": resource,
                "distribution": distribution,
                "remaining": remaining,
                "scores": scores,
            }
        )
    if custom_resources:
        unallocated["customResources"] = [
            {**item["resource"], "quantity": item["remaining"]}
            for item in custom_distributions
        ]

    allocations = []
    for city in cities:
        values = {resource: distributions[resource][city] for resource in RESOURCES}
        custom_values = [
            {**item["resource"], "quantity": item["distribution"].get(city, 0)}
            for item in custom_distributions
            if item["distribution"].get(city, 0) > 0
        ]
        if any(values.values()) or custom_values:
            allocation = {"city": city, **values, "needScores": fixed_need_scores[city]}
            if custom_resources:
                allocation["customResources"] = custom_values
            allocations.append(allocation)
    allocations.sort(
        key=lambda item: (
            sum(item["needScores"].values())
            + sum(custom["scores"].get(str(item["city"]), 0) for custom in custom_distributions)
        ),
        reverse=True,
    )
    return {"allocations": allocations, "unallocated": unallocated, "rulesVersion": "1.0.0"}
