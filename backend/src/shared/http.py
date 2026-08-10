from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from shared.serialization import from_dynamodb


def response(status: int, body: Any) -> dict[str, Any]:
    origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Headers": "Content-Type,Authorization,Idempotency-Key",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(from_dynamodb(body), ensure_ascii=False, separators=(",", ":")),
    }


def error(status: int, code: str, message: str) -> dict[str, Any]:
    return response(status, {"error": code, "message": message})


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if raw is None:
        raise ValueError("Request body is required.")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def validation_error_body(exc: ValidationError) -> dict[str, Any]:
    return {
        "error": "VALIDATION_ERROR",
        "message": "Request validation failed.",
        "details": [
            {
                "field": ".".join(str(part) for part in item["loc"]),
                "message": item["msg"],
            }
            for item in exc.errors()
        ],
    }


def validation_error(exc: ValidationError) -> dict[str, Any]:
    return response(400, validation_error_body(exc))


def header(event: dict[str, Any], name: str) -> str | None:
    for key, value in (event.get("headers") or {}).items():
        if key.lower() == name.lower() and isinstance(value, str):
            return value.strip()
    return None
