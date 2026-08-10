from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared.geocoding import (
    LOCATION_SOURCE_GEOCODED_ADDRESS,
    LOCATION_SOURCE_UNRESOLVED_ADDRESS,
    LOCATION_SOURCE_USER_COORDINATES,
    geocode_request_location,
)


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


def test_supplied_coordinates_do_not_call_geocoder() -> None:
    called = False

    def client_factory() -> FakeGeoClient:
        nonlocal called
        called = True
        raise AssertionError("geo-places must not be initialized")

    update = geocode_request_location(
        {
            "address": "Atatürk Caddesi, No: 15, Antakya/Hatay",
            "district": "Antakya",
            "city": "Hatay",
            "latitude": Decimal("36.2021"),
            "longitude": Decimal("36.1604"),
        },
        client_factory=client_factory,
    )

    assert called is False
    assert update.geocoder_called is False
    assert update.attributes == {"locationSource": LOCATION_SOURCE_USER_COORDINATES}


def test_missing_coordinates_with_address_geocodes_and_preserves_position_order() -> None:
    client = FakeGeoClient(
        {
            "ResultItems": [
                {
                    "Position": [36.1604, 36.2021],
                    "Title": "Atatürk Caddesi, Antakya, Hatay, Türkiye",
                }
            ]
        }
    )

    update = geocode_request_location(
        {
            "address": "Atatürk Caddesi, No: 15",
            "district": "Antakya",
            "city": "Hatay",
        },
        client=client,
    )

    assert client.calls == [
        {
            "QueryText": "Atatürk Caddesi, No: 15, Antakya, Hatay, Türkiye",
            "MaxResults": 1,
            "Filter": {"IncludeCountries": ["TUR"]},
            "Language": "tr",
            "IntendedUse": "Storage",
        }
    ]
    assert update.resolved is True
    assert update.attributes["locationSource"] == LOCATION_SOURCE_GEOCODED_ADDRESS
    assert update.attributes["latitude"] == 36.2021
    assert update.attributes["longitude"] == 36.1604
    assert update.attributes["latitude"] != 36.1604
    assert update.attributes["longitude"] != 36.2021
    assert update.attributes["geocodeLabel"] == "Atatürk Caddesi, Antakya, Hatay, Türkiye"


def test_no_address_does_not_call_geocoder() -> None:
    called = False

    def client_factory() -> FakeGeoClient:
        nonlocal called
        called = True
        raise AssertionError("geo-places must not be initialized")

    update = geocode_request_location({"city": "Hatay", "district": "Antakya", "address": "   "}, client_factory=client_factory)

    assert called is False
    assert update.geocoder_called is False
    assert update.attributes == {}


def test_geocoding_exception_is_non_fatal() -> None:
    client = FakeGeoClient(error=RuntimeError("synthetic failure"))

    update = geocode_request_location(
        {"address": "Atatürk Caddesi, No: 15", "district": "Antakya", "city": "Hatay"},
        client=client,
    )

    assert update.geocoder_called is True
    assert update.resolved is False
    assert update.attributes == {"locationSource": LOCATION_SOURCE_UNRESOLVED_ADDRESS}


def test_no_geocode_result_is_non_fatal() -> None:
    client = FakeGeoClient({"ResultItems": []})

    update = geocode_request_location(
        {"address": "Atatürk Caddesi, No: 15", "district": "Antakya", "city": "Hatay"},
        client=client,
    )

    assert update.geocoder_called is True
    assert update.resolved is False
    assert update.attributes == {"locationSource": LOCATION_SOURCE_UNRESOLVED_ADDRESS}
