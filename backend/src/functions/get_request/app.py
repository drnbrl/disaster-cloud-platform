from __future__ import annotations

import os
from typing import Any

import boto3

from shared.http import error, response
from shared.safe_views import public_request


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = (event.get("pathParameters") or {}).get("requestId")
    if not request_id:
        return error(400, "MISSING_REQUEST_ID", "requestId gereklidir.")
    item = boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE_NAME"]).get_item(
        Key={"requestId": request_id}, ConsistentRead=True
    ).get("Item")
    if not item:
        return error(404, "NOT_FOUND", "Talep bulunamadı.")
    return response(200, public_request(item))
