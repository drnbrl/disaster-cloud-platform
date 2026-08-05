from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

from boto3.dynamodb.types import TypeSerializer

_serializer = TypeSerializer()


def to_dynamodb(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamodb(item) for item in value]
    return value


def from_dynamodb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: from_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_dynamodb(item) for item in value]
    return value


def serialize_values(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: _serializer.serialize(to_dynamodb(value)) for key, value in values.items()}


def encode_cursor(key: dict[str, Any] | None) -> str | None:
    if not key:
        return None
    raw = json.dumps(from_dynamodb(key), separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode((cursor + padding).encode())
        value = json.loads(raw.decode())
        if not isinstance(value, dict):
            raise ValueError
        return to_dynamodb(value)
    except Exception as exc:
        raise ValueError("Invalid pagination cursor.") from exc
