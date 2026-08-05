from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from shared.http import error, response
from shared.safe_views import admin_request
from shared.serialization import decode_cursor, encode_cursor

PRIORITIES = {"low", "medium", "high", "critical"}
STATUSES = {"RECEIVED", "REVIEWED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    priority = (params.get("priority") or "").lower()
    city = (params.get("city") or "").strip()
    status = (params.get("status") or "").upper()
    if priority and priority not in PRIORITIES:
        return error(400, "INVALID_PRIORITY", "Geçersiz öncelik filtresi.")
    if status and status not in STATUSES:
        return error(400, "INVALID_STATUS", "Geçersiz durum filtresi.")
    try:
        limit = min(max(int(params.get("limit", "25")), 1), 100)
        cursor = decode_cursor(params.get("cursor"))
    except ValueError as exc:
        return error(400, "INVALID_PAGINATION", str(exc))

    query: dict[str, Any] = {"Limit": limit, "ScanIndexForward": False}
    if priority:
        query.update(IndexName="PriorityIndex", KeyConditionExpression=Key("gsi1pk").eq(f"PRIORITY#{priority}"))
    elif city:
        query.update(IndexName="CityIndex", KeyConditionExpression=Key("gsi2pk").eq(f"CITY#{city}"))
    elif status:
        query.update(IndexName="StatusIndex", KeyConditionExpression=Key("gsi3pk").eq(f"STATUS#{status}"))
    else:
        query.update(IndexName="CreatedIndex", KeyConditionExpression=Key("gsi4pk").eq("ALL"))
    if cursor:
        query["ExclusiveStartKey"] = cursor

    result = boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE_NAME"]).query(**query)
    return response(200, {"items": [admin_request(item) for item in result.get("Items", [])], "nextCursor": encode_cursor(result.get("LastEvaluatedKey"))})
