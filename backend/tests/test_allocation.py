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


def _custom_resource(resource_id: str, name: str, quantity: int, unit: str = "adet") -> dict[str, object]:
    return {"id": resource_id, "name": name, "quantity": quantity, "unit": unit}


def _allocated_resource_total(result: dict[str, object], resource_id: str) -> int:
    total = 0
    for allocation in result["allocations"]:
        assert isinstance(allocation, dict)
        for resource in allocation.get("resources", []):
            if resource["id"] == resource_id:
                total += resource["quantity"]
    return total


def _unallocated_resource_quantity(result: dict[str, object], resource_id: str) -> int:
    unallocated = result["unallocated"]
    assert isinstance(unallocated, dict)
    for resource in unallocated.get("resources", []):
        if resource["id"] == resource_id:
            return resource["quantity"]
    return 0


def test_never_exceeds_inventory():
    inventory = {"waterLiters": 500, "tents": 100, "medicalStaff": 20, "blankets": 50}
    result = calculate_allocation(inventory, CITY_STATS)
    for resource, total in inventory.items():
        used = sum(item[resource] for item in result["allocations"])
        assert used <= total
        assert used + result["unallocated"][resource] == total


def test_missing_custom_resources_defaults_to_empty_array_and_legacy_custom_fields_stay_absent():
    inventory = {"waterLiters": 10, "tents": 2, "medicalStaff": 1, "blankets": 3}
    payload = AllocationInput.model_validate({"resources": inventory})

    result = calculate_allocation(payload.inventory_payload(), CITY_STATS)

    assert payload.customResources == []
    assert payload.inventory_payload() == inventory
    assert "customResources" not in result["unallocated"]
    assert all("customResources" not in item for item in result["allocations"])


def test_allocates_yakit_custom_resource_exactly():
    inventory = {
        "waterLiters": 700,
        "tents": 20,
        "medicalStaff": 5,
        "blankets": 40,
        "customResources": [_custom_resource("fuel-1", "Yakıt", 250, "litre")],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    used = _allocated_resource_total(result, "fuel-1")
    unallocated = _unallocated_resource_quantity(result, "fuel-1")
    assert used > 0
    assert used == 250
    assert unallocated == 0


def test_allocates_jenerator_custom_resource_exactly():
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("generator-1", "Jeneratör", 5)],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    assert _allocated_resource_total(result, "generator-1") == 5
    assert _unallocated_resource_quantity(result, "generator-1") == 0


def test_allocates_multiple_custom_resources_independently():
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [
            _custom_resource("food-box-1", "Gıda kolisi", 11),
            _custom_resource("generator-1", "Jeneratör", 4),
            _custom_resource("fuel-1", "Yakıt", 250, "litre"),
        ],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    for resource_id, total in {"food-box-1": 11, "generator-1": 4, "fuel-1": 250}.items():
        assert _allocated_resource_total(result, resource_id) == total
        assert _unallocated_resource_quantity(result, resource_id) == 0


def test_custom_resource_quantity_zero_does_not_crash():
    payload = AllocationInput.model_validate(
        {
            "resources": FIXED_ZERO_INVENTORY,
            "customResources": [_custom_resource("fuel-1", "Yakıt", 0, "litre")],
        }
    )

    result = calculate_allocation(payload.inventory_payload(), CITY_STATS)

    assert _allocated_resource_total(result, "fuel-1") == 0
    assert _unallocated_resource_quantity(result, "fuel-1") == 0


def test_custom_resource_unit_and_name_survive_request_to_response():
    payload = AllocationInput.model_validate(
        {
            "resources": FIXED_ZERO_INVENTORY,
            "customResources": [_custom_resource("ambulance-1", "Ambulans", 3, "araç")],
        }
    )

    result = calculate_allocation(payload.inventory_payload(), CITY_STATS)
    returned = [
        resource
        for allocation in result["allocations"]
        for resource in allocation.get("resources", [])
        if resource["id"] == "ambulance-1"
    ]

    assert returned
    assert {resource["name"] for resource in returned} == {"Ambulans"}
    assert {resource["unit"] for resource in returned} == {"araç"}


def test_custom_resource_negative_quantity_is_rejected():
    with pytest.raises(ValidationError):
        AllocationInput.model_validate(
            {
                "resources": FIXED_ZERO_INVENTORY,
                "customResources": [_custom_resource("fuel-1", "Yakıt", -1, "litre")],
            }
        )


@pytest.mark.parametrize(
    "custom_resource",
    [
        {"name": "Yakıt", "quantity": 1, "unit": "litre"},
        {"id": "fuel-1", "name": "   ", "quantity": 1, "unit": "litre"},
        {"id": "fuel-1", "name": "Yakıt", "quantity": 1, "unit": "   "},
        {"id": "fuel-1", "name": "Yakıt", "quantity": 1.5, "unit": "litre"},
    ],
)
def test_invalid_custom_resource_contract_is_rejected(custom_resource: dict[str, object]):
    with pytest.raises(ValidationError):
        AllocationInput.model_validate({"resources": FIXED_ZERO_INVENTORY, "customResources": [custom_resource]})


def test_more_than_one_hundred_custom_resources_are_rejected():
    with pytest.raises(ValidationError):
        AllocationInput.model_validate(
            {
                "resources": FIXED_ZERO_INVENTORY,
                "customResources": [
                    _custom_resource(f"resource-{index}", f"Kaynak {index}", 1)
                    for index in range(101)
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
            _custom_resource("hygiene-1", "Hijyen kiti", 17),
            _custom_resource("charger-1", "Mobil şarj", 8),
        ],
    }

    result = calculate_allocation(inventory, CITY_STATS)

    for resource in ("waterLiters", "tents", "medicalStaff", "blankets"):
        used = sum(item[resource] for item in result["allocations"])
        assert used <= inventory[resource]
        assert used + result["unallocated"][resource] == inventory[resource]
    for resource_id, total in {"hygiene-1": 17, "charger-1": 8}.items():
        assert _allocated_resource_total(result, resource_id) == total
        assert _unallocated_resource_quantity(result, resource_id) == 0


def test_rounding_preserves_integer_totals():
    city_stats = [
        {"city": "A", "foodRequests": 1},
        {"city": "B", "foodRequests": 1},
        {"city": "C", "foodRequests": 1},
    ]
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("food-pack-1", "Kumanya", 10)],
    }

    result = calculate_allocation(inventory, city_stats)

    assert _allocated_resource_total(result, "food-pack-1") == 10
    assert _unallocated_resource_quantity(result, "food-pack-1") == 0
    allocated_values = [
        resource["quantity"]
        for allocation in result["allocations"]
        for resource in allocation.get("resources", [])
        if resource["id"] == "food-pack-1"
    ]
    assert sorted(allocated_values) == [3, 3, 4]


def test_custom_resources_use_overall_city_urgency_score():
    city_stats = [
        {"city": "Düşük", "totalRequests": 1, "criticalRequests": 0, "affectedPeople": 10},
        {"city": "Acil", "totalRequests": 20, "criticalRequests": 5, "affectedPeople": 300, "injuredPeople": 8},
    ]
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("support-pack-1", "Çok amaçlı destek paketi", 12)],
    }

    result = calculate_allocation(inventory, city_stats)

    allocation_by_city = {
        item["city"]: sum(resource["quantity"] for resource in item.get("resources", []) if resource["id"] == "support-pack-1")
        for item in result["allocations"]
    }
    assert allocation_by_city["Acil"] > allocation_by_city.get("Düşük", 0)
    assert _allocated_resource_total(result, "support-pack-1") == 12


def test_custom_resources_are_evenly_allocated_when_city_need_scores_are_zero():
    city_stats = [{"city": "A"}, {"city": "B"}]
    inventory = {
        **FIXED_ZERO_INVENTORY,
        "customResources": [_custom_resource("fuel-1", "Yakıt", 5, "litre")],
    }

    result = calculate_allocation(inventory, city_stats)

    assert _allocated_resource_total(result, "fuel-1") == 5
    assert _unallocated_resource_quantity(result, "fuel-1") == 0


def test_empty_cities_keep_inventory():
    inventory = {"waterLiters": 10, "tents": 2, "medicalStaff": 1, "blankets": 3}
    result = calculate_allocation(inventory, [])
    assert result["allocations"] == []
    for resource, total in inventory.items():
        assert result["unallocated"][resource] == total
