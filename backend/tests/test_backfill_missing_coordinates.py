from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backfill_missing_coordinates.py"
SPEC = importlib.util.spec_from_file_location("backfill_missing_coordinates", SCRIPT_PATH)
assert SPEC and SPEC.loader
backfill = importlib.util.module_from_spec(SPEC)
sys.modules["backfill_missing_coordinates"] = backfill
SPEC.loader.exec_module(backfill)


class FakeGeoClient:
    def geocode(self, **kwargs: Any) -> dict[str, Any]:
        return {"ResultItems": [{"Position": [36.1604, 36.2021], "Title": "Antakya, Hatay"}]}


class FakeTable:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.updates: list[dict[str, Any]] = []
        self.scan_kwargs: list[dict[str, Any]] = []

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.scan_kwargs.append(kwargs)
        return {"Items": self.items}

    def update_item(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)
        request_id = kwargs["Key"]["requestId"]
        names = kwargs["ExpressionAttributeNames"]
        values = kwargs["ExpressionAttributeValues"]
        item = next(item for item in self.items if item["requestId"] == request_id)
        for assignment in kwargs["UpdateExpression"].removeprefix("SET ").split(", "):
            name_key, value_key = assignment.split("=")
            item[names[name_key]] = values[value_key]


class FakeResource:
    def __init__(self, table: FakeTable) -> None:
        self.table = table

    def Table(self, table_name: str) -> FakeTable:
        assert table_name == "requests"
        return self.table


class FakeSession:
    def __init__(self, table: FakeTable) -> None:
        self.table = table

    def resource(self, service_name: str) -> FakeResource:
        assert service_name == "dynamodb"
        return FakeResource(self.table)

    def client(self, service_name: str) -> FakeGeoClient:
        assert service_name == "geo-places"
        return FakeGeoClient()


def test_backfill_never_overwrites_existing_coordinates(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    partial_coordinates = {
        "requestId": "partial",
        "address": "Atatürk Caddesi, No: 15",
        "district": "Antakya",
        "city": "Hatay",
        "latitude": Decimal("36.2021"),
    }
    missing_coordinates = {
        "requestId": "missing",
        "address": "Atatürk Caddesi, No: 15",
        "district": "Antakya",
        "city": "Hatay",
    }
    table = FakeTable([partial_coordinates, missing_coordinates])

    monkeypatch.setattr(backfill.boto3, "Session", lambda region_name=None: FakeSession(table))
    monkeypatch.setattr(sys, "argv", ["backfill_missing_coordinates.py", "--table-name", "requests"])

    assert backfill.main() == 0

    assert partial_coordinates == {
        "requestId": "partial",
        "address": "Atatürk Caddesi, No: 15",
        "district": "Antakya",
        "city": "Hatay",
        "latitude": Decimal("36.2021"),
    }
    assert len(table.updates) == 1
    assert table.updates[0]["Key"] == {"requestId": "missing"}
    assert missing_coordinates["latitude"] == Decimal("36.2021")
    assert missing_coordinates["longitude"] == Decimal("36.1604")
    assert table.scan_kwargs[0]["FilterExpression"] is not None
    output = capsys.readouterr().out
    assert "scanned: 2" in output
    assert "eligible: 1" in output
    assert "resolved: 1" in output
    assert "skipped: 1" in output
