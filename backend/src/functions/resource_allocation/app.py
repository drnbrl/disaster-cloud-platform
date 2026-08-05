from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr
from pydantic import ValidationError

from shared.allocation import calculate_allocation
from shared.bedrock_ai import explain_allocation
from shared.http import error, parse_body, response, validation_error
from shared.models import AllocationInput


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        payload = AllocationInput.model_validate(parse_body(event))
    except ValidationError as exc:
        return validation_error(exc)
    except ValueError as exc:
        return error(400, "INVALID_REQUEST", str(exc))

    table = boto3.resource("dynamodb").Table(os.environ["STATISTICS_TABLE_NAME"])
    city_stats = table.scan(FilterExpression=Attr("scope").begins_with("CITY#"), Limit=200).get("Items", [])
    if payload.cities:
        selected = {city.casefold() for city in payload.cities}
        city_stats = [item for item in city_stats if str(item.get("city", "")).casefold() in selected]
    inventory = payload.inventory_payload()
    result = calculate_allocation(inventory, city_stats)
    result["explanation"] = explain_allocation(result, city_stats)
    result["inputResources"] = inventory
    return response(200, result)
