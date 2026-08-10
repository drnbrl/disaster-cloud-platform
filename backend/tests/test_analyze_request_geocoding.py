from __future__ import annotations

from typing import Any

import pytest
from boto3.dynamodb.types import TypeDeserializer

import functions.analyze_request.app as analyzer
from shared.geocoding import LOCATION_SOURCE_GEOCODED_ADDRESS, LOCATION_SOURCE_UNRESOLVED_ADDRESS
from shared.mock_ai import analyze_with_mock
from shared.priority import calculate_priority


class FakeGeoClient:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.response = response or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def geocode(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeRequestsTable:
    def __init__(self, item: dict[str, Any]) -> None:
        self.items = {item["requestId"]: dict(item)}

    def get_item(self, Key: dict[str, str], ConsistentRead: bool = False) -> dict[str, Any]:
        assert ConsistentRead is True
        return {"Item": self.items.get(Key["requestId"])}


class FakeResource:
    def __init__(self, table: FakeRequestsTable) -> None:
        self.table = table

    def Table(self, table_name: str) -> FakeRequestsTable:
        assert table_name == "requests"
        return self.table


class FakeDynamoClient:
    def __init__(self, table: FakeRequestsTable) -> None:
        self.table = table
        self.deserializer = TypeDeserializer()

    def transact_write_items(self, TransactItems: list[dict[str, Any]]) -> None:
        request_update = TransactItems[0]["Update"]
        request_id = self.deserializer.deserialize(request_update["Key"]["requestId"])
        values = {
            key: self.deserializer.deserialize(value)
            for key, value in request_update["ExpressionAttributeValues"].items()
        }
        names = request_update.get("ExpressionAttributeNames", {})
        item = self.table.items[request_id]
        for assignment in request_update["UpdateExpression"].removeprefix("SET ").split(", "):
            attribute_name, value_name = assignment.split("=")
            item[names.get(attribute_name, attribute_name)] = values[value_name]


def test_analyzer_stores_geocoded_coordinates_without_changing_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    item = request_item()
    table = run_process(
        monkeypatch,
        item,
        FakeGeoClient({"ResultItems": [{"Position": [36.1604, 36.2021], "Title": "Antakya, Hatay"}]}),
    )
    stored = table.items[item["requestId"]]
    expected_priority = calculate_priority(analyze_with_mock(item["message"]))

    assert stored["analysisStatus"] == "COMPLETED"
    assert float(stored["latitude"]) == 36.2021
    assert float(stored["longitude"]) == 36.1604
    assert stored["locationSource"] == LOCATION_SOURCE_GEOCODED_ADDRESS
    assert stored["geocodeLabel"] == "Antakya, Hatay"
    assert stored["priorityScore"] == expected_priority["score"]
    assert stored["priorityLevel"] == expected_priority["level"]
    assert stored["priorityReasons"] == expected_priority["reasons"]


def test_analyzer_completes_when_geocoding_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    item = request_item(request_id="request-geocode-error")
    table = run_process(monkeypatch, item, FakeGeoClient(error=RuntimeError("synthetic failure")))
    stored = table.items[item["requestId"]]

    assert stored["analysisStatus"] == "COMPLETED"
    assert stored["locationSource"] == LOCATION_SOURCE_UNRESOLVED_ADDRESS
    assert "latitude" not in stored
    assert "longitude" not in stored


def test_analyzer_completes_when_geocoding_returns_no_result(monkeypatch: pytest.MonkeyPatch) -> None:
    item = request_item(request_id="request-no-geocode-result")
    table = run_process(monkeypatch, item, FakeGeoClient({"ResultItems": []}))
    stored = table.items[item["requestId"]]

    assert stored["analysisStatus"] == "COMPLETED"
    assert stored["locationSource"] == LOCATION_SOURCE_UNRESOLVED_ADDRESS
    assert "latitude" not in stored
    assert "longitude" not in stored


def request_item(request_id: str = "request-geocode-success") -> dict[str, Any]:
    return {
        "requestId": request_id,
        "createdAt": "2026-08-10T00:00:00Z",
        "updatedAt": "2026-08-10T00:00:00Z",
        "city": "Hatay",
        "district": "Antakya",
        "address": "Atatürk Caddesi, No: 15",
        "message": "25 kişiyiz. İçme suyumuz bitti. 2 yaralı var. Bebek maması gerekiyor.",
        "requestStatus": "RECEIVED",
        "analysisStatus": "PENDING",
    }


def run_process(monkeypatch: pytest.MonkeyPatch, item: dict[str, Any], geo_client: FakeGeoClient) -> FakeRequestsTable:
    table = FakeRequestsTable(item)
    dynamo_client = FakeDynamoClient(table)

    def fake_resource(service_name: str) -> FakeResource:
        assert service_name == "dynamodb"
        return FakeResource(table)

    def fake_client(service_name: str) -> FakeDynamoClient | FakeGeoClient:
        if service_name == "dynamodb":
            return dynamo_client
        if service_name == "geo-places":
            return geo_client
        raise AssertionError(f"unexpected client: {service_name}")

    monkeypatch.setenv("REQUESTS_TABLE_NAME", "requests")
    monkeypatch.setenv("STATISTICS_TABLE_NAME", "statistics")
    monkeypatch.setenv("USE_MOCK_AI", "true")
    monkeypatch.setattr(analyzer.boto3, "resource", fake_resource)
    monkeypatch.setattr(analyzer.boto3, "client", fake_client)

    analyzer._process(item["requestId"])
    return table
