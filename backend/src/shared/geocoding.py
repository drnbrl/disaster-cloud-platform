from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Protocol

import boto3

LOCATION_SOURCE_USER_COORDINATES = "USER_COORDINATES"
LOCATION_SOURCE_GEOCODED_ADDRESS = "GEOCODED_ADDRESS"
LOCATION_SOURCE_UNRESOLVED_ADDRESS = "UNRESOLVED_ADDRESS"

TURKEY_COUNTRY_NAME = "Türkiye"
TURKEY_COUNTRY_CODE = "TUR"
GEOCODE_LABEL_MAX_LENGTH = 500


class GeoPlacesClient(Protocol):
    def geocode(self, **kwargs: Any) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class LocationUpdate:
    attributes: dict[str, Any]
    geocoder_called: bool
    resolved: bool


def geocode_request_location(
    request: dict[str, Any],
    *,
    client: GeoPlacesClient | None = None,
    client_factory: Callable[[], GeoPlacesClient] | None = None,
) -> LocationUpdate:
    if has_valid_coordinate_pair(request):
        return LocationUpdate(
            attributes={"locationSource": LOCATION_SOURCE_USER_COORDINATES},
            geocoder_called=False,
            resolved=True,
        )

    query = build_geocode_query(request)
    if not query:
        return LocationUpdate(attributes={}, geocoder_called=False, resolved=False)

    try:
        geo_client = client or (client_factory() if client_factory else boto3.client("geo-places"))
        response = geo_client.geocode(
            QueryText=query,
            MaxResults=1,
            Filter={"IncludeCountries": [TURKEY_COUNTRY_CODE]},
            Language="tr",
            IntendedUse="Storage",
        )
    except Exception:
        return _unresolved()

    result = _first_valid_result(response)
    if not result:
        return _unresolved()

    longitude, latitude, label = result
    attributes: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "locationSource": LOCATION_SOURCE_GEOCODED_ADDRESS,
    }
    if label:
        attributes["geocodeLabel"] = label
    return LocationUpdate(attributes=attributes, geocoder_called=True, resolved=True)


def build_geocode_query(request: dict[str, Any]) -> str | None:
    address = _non_empty_text(request.get("address"))
    if not address:
        return None
    components = [
        address,
        _non_empty_text(request.get("district")),
        _non_empty_text(request.get("city")),
        TURKEY_COUNTRY_NAME,
    ]
    query = ", ".join(component for component in components if component)
    return query or None


def has_valid_coordinate_pair(request: dict[str, Any]) -> bool:
    return (
        _valid_number(request.get("latitude"), -90, 90) is not None
        and _valid_number(request.get("longitude"), -180, 180) is not None
    )


def has_any_valid_coordinate(request: dict[str, Any]) -> bool:
    return (
        _valid_number(request.get("latitude"), -90, 90) is not None
        or _valid_number(request.get("longitude"), -180, 180) is not None
    )


def _unresolved() -> LocationUpdate:
    return LocationUpdate(
        attributes={"locationSource": LOCATION_SOURCE_UNRESOLVED_ADDRESS},
        geocoder_called=True,
        resolved=False,
    )


def _first_valid_result(response: dict[str, Any]) -> tuple[float, float, str | None] | None:
    items = response.get("ResultItems")
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None

    position = first.get("Position")
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        return None
    longitude = _valid_number(position[0], -180, 180)
    latitude = _valid_number(position[1], -90, 90)
    if longitude is None or latitude is None:
        return None

    return longitude, latitude, _result_label(first)


def _result_label(result: dict[str, Any]) -> str | None:
    title = _non_empty_text(result.get("Title"))
    if title:
        return title[:GEOCODE_LABEL_MAX_LENGTH]
    address = result.get("Address")
    if isinstance(address, dict):
        label = _non_empty_text(address.get("Label"))
        if label:
            return label[:GEOCODE_LABEL_MAX_LENGTH]
    return None


def _valid_number(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        number = float(value)
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    if number < minimum or number > maximum:
        return None
    if number in {float("inf"), float("-inf")} or number != number:
        return None
    return number


def _non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
