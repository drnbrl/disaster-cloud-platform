import pytest
from pydantic import ValidationError

from shared.allocation import calculate_allocation
from shared.models import AllocationInput

CITY_STATS = [
    {
        "city": "Hatay",
        "totalRequests": 40,
        "criticalRequests": 10,
        "highRequests": 12,
        "mediumRequests": 10,
        "lowRequests": 8,
        "waterRequests": 20,
        "foodRequests": 16,
        "shelterRequests": 8,
        "medicalRequests": 5,
        "electricityRequests": 3,
        "babySupportRequests": 2,
        "affectedPeople": 500,
        "injuredPeople": 12,
    },
    {
        "city": "Adıyaman",
        "totalRequests": 24,
        "criticalRequests": 4,
        "highRequests": 6,
        "mediumRequests": 8,
        "lowRequests": 6,
        "waterRequests": 8,
        "foodRequests": 12,
        "shelterRequests": 12,
        "medicalRequests": 2,
        "electricityRequests": 6,
        "babySupportRequests": 1,
        "affectedPeople": 200,
        "injuredPeople": 4,
    },
]
FIXED_ZERO_INVENTORY = {"waterLiters": 0, "tents": 0, "medicalStaff": 0, "blankets": 0}


def _custom_resource(name: str, quantity: int, category: str, unit: str = "adet") -> dict[str, object]:
    return {"name": name, "quantity": quantity, "unit": unit, "category": category}


def _custom_allocated_total(result: dict[str, object], name: str) -> int:
    total = 0
    for allocation in result["allocations"]:
        assert isinstance(allocation, dict)
        for resource in allocation.get("customResources", []):
            if resource["name"] == name:
                total += resource["quantity"]
    return total


def _custom_unallocated_quantity(result: dict[str, object], name: str) -> int:
    unallocated = result["unallocated"]
    assert isinstance(unallocated, dict)
    for resource in unallocated.get("customResources", []):
        if resource["name"] == name:
            return resource["quantity"]
    return 0


def test_never_exceeds_inventory():
    inventory = {"waterLiters": 500, "tents": 100, "medicalStaff": 20, "blankets": 50}
    result = calculate_allocation(inventory, CITY_STATS)
    for resource, total in inventory.items():
        used = sum(item[resource] for item in result["allocations"])
        assert used <= total
        assert used + result["unallocated"][resource] == total


def test_missing_custom_resources_defaults_to_empty_array_without_changing_result_shape():
    inventory = {"waterLiters": 10, "tents": 2, "medicalStaff": 1, "blankets": 3}
    payload = AllocationInput.model_validate({"resources": inventory})

    result = calculate_allocation(payload.inventory_payload(), CITY_STATS)

    assert payload.customResources == []
    assert payload.inventory_payload() == inventory
    assert "customResources" not in result["unallocated"]
    assert all("customResources" not in item for item in result["allocations"])


def test_allocates_one_custom_resource_by_selected_category():
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("Gıda kolisi", 9, "food")],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    used = _custom_allocated_total(result, "Gıda kolisi")
    unallocated = _custom_unallocated_quantity(result, "Gıda kolisi")
    assert used > 0
    assert used <= 9
    assert used + unallocated == 9


def test_allocates_multiple_custom_resources_independently():
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [
            _custom_resource("Gıda kolisi", 11, "food"),
            _custom_resource("Jeneratör", 4, "electricity"),
        ],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    for name, total in {"Gıda kolisi": 11, "Jeneratör": 4}.items():
        used = _custom_allocated_total(result, name)
        unallocated = _custom_unallocated_quantity(result, name)
        assert used <= total
        assert used + unallocated == total


@pytest.mark.parametrize("quantity", [0, -1])
def test_custom_resource_zero_or_negative_quantities_are_rejected(quantity: int):
    with pytest.raises(ValidationError):
        AllocationInput.model_validate(
            {
                "resources": FIXED_ZERO_INVENTORY,
                "customResources": [_custom_resource("Yakıt", quantity, "general", "litre")],
            }
        )


def test_more_than_twenty_custom_resources_are_rejected():
    with pytest.raises(ValidationError):
        AllocationInput.model_validate(
            {
                "resources": FIXED_ZERO_INVENTORY,
                "customResources": [
                    _custom_resource(f"Kaynak {index}", 1, "general")
                    for index in range(21)
                ],
            }
        )


def test_custom_resource_totals_never_exceed_available_quantities():
    inventory = {
        "waterLiters": 13,
        "tents": 5,
        "medicalStaff": 2,
        "blankets": 7,
        "customResources": [
            _custom_resource("Hijyen kiti", 17, "general"),
            _custom_resource("Mobil şarj", 8, "electricity"),
        ],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    for resource in ("waterLiters", "tents", "medicalStaff", "blankets"):
        used = sum(item[resource] for item in result["allocations"])
        assert used <= inventory[resource]
        assert used + result["unallocated"][resource] == inventory[resource]
    for name, total in {"Hijyen kiti": 17, "Mobil şarj": 8}.items():
        used = _custom_allocated_total(result, name)
        assert used <= total
        assert used + _custom_unallocated_quantity(result, name) == total


def test_rounding_preserves_integer_totals():
    city_stats = [
        {"city": "A", "foodRequests": 1},
        {"city": "B", "foodRequests": 1},
        {"city": "C", "foodRequests": 1},
    ]
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("Kumanya", 10, "food")],
    }

    result = calculate_allocation(inventory, city_stats)

    assert _custom_allocated_total(result, "Kumanya") == 10
    assert _custom_unallocated_quantity(result, "Kumanya") == 0
    allocated_values = [
        resource["quantity"]
        for allocation in result["allocations"]
        for resource in allocation.get("customResources", [])
        if resource["name"] == "Kumanya"
    ]
    assert sorted(allocated_values) == [3, 3, 4]


def test_general_category_uses_overall_city_urgency_score():
    city_stats = [
        {"city": "Düşük", "totalRequests": 1, "criticalRequests": 0, "affectedPeople": 10},
        {"city": "Acil", "totalRequests": 20, "criticalRequests": 5, "affectedPeople": 300, "injuredPeople": 8},
    ]
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("Çok amaçlı destek paketi", 12, "general")],
    }

    result = calculate_allocation(inventory, city_stats)

    allocation_by_city = {
        item["city"]: sum(resource["quantity"] for resource in item.get("customResources", []))
        for item in result["allocations"]
    }
    assert allocation_by_city["Acil"] > allocation_by_city.get("Düşük", 0)
    assert _custom_allocated_total(result, "Çok amaçlı destek paketi") == 12


def test_empty_cities_keep_inventory():
    inventory = {"waterLiters": 10, "tents": 2, "medicalStaff": 1, "blankets": 3}
    result = calculate_allocation(inventory, [])
    assert result["allocations"] == []
    assert result["unallocated"] == inventory
