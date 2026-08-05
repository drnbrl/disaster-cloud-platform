from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.models import CreateRequestInput


BASE_REQUEST = {
    "city": "Hatay",
    "district": "Antakya",
    "address": "Atatürk Caddesi, No: 15, Antakya/Hatay",
    "message": "25 kişiyiz. İçme suyumuz bitti. Yardım bekliyoruz.",
}


def test_valid_request_with_district_and_address():
    payload = CreateRequestInput.model_validate(BASE_REQUEST)

    assert payload.city == "Hatay"
    assert payload.district == "Antakya"
    assert payload.address == "Atatürk Caddesi, No: 15, Antakya/Hatay"


def test_required_location_fields_are_trimmed():
    payload = CreateRequestInput.model_validate(
        {
            **BASE_REQUEST,
            "city": " Hatay ",
            "district": " Antakya ",
            "address": " Atatürk Caddesi, No: 15, Antakya/Hatay ",
        }
    )

    assert payload.city == "Hatay"
    assert payload.district == "Antakya"
    assert payload.address == "Atatürk Caddesi, No: 15, Antakya/Hatay"


def test_missing_district_is_rejected():
    payload = {key: value for key, value in BASE_REQUEST.items() if key != "district"}

    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate(payload)


def test_blank_district_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "district": "   "})


def test_missing_address_is_rejected():
    payload = {key: value for key, value in BASE_REQUEST.items() if key != "address"}

    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate(payload)


def test_blank_address_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "address": "   "})


def test_address_shorter_than_five_characters_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "address": "1234"})


def test_address_longer_than_five_hundred_characters_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "address": "A" * 501})


def test_request_without_coordinates_is_valid():
    payload = CreateRequestInput.model_validate(BASE_REQUEST)

    assert payload.latitude is None
    assert payload.longitude is None
    assert payload.address == "Atatürk Caddesi, No: 15, Antakya/Hatay"


def test_request_with_both_coordinates_is_valid():
    payload = CreateRequestInput.model_validate({**BASE_REQUEST, "latitude": 36.2021, "longitude": 36.1604})

    assert payload.latitude == 36.2021
    assert payload.longitude == 36.1604


def test_latitude_without_longitude_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "latitude": 36.2021})


def test_longitude_without_latitude_is_rejected():
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "longitude": 36.1604})


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (-90.1, 36.1604),
        (90.1, 36.1604),
        (36.2021, -180.1),
        (36.2021, 180.1),
    ],
)
def test_invalid_coordinate_ranges_are_rejected(latitude: float, longitude: float):
    with pytest.raises(ValidationError):
        CreateRequestInput.model_validate({**BASE_REQUEST, "latitude": latitude, "longitude": longitude})
