from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from shared.http import error, parse_body, response, validation_error
from shared.models import StatusUpdateInput
from shared.safe_views import admin_request
from shared.time_utils import utc_now_iso


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = (event.get("pathParameters") or {}).get("requestId")
    if not request_id:
        return error(400, "MISSING_REQUEST_ID", "requestId gereklidir.")
    try:
        payload = StatusUpdateInput.model_validate(parse_body(event))
    except ValidationError as exc:
        return validation_error(exc)
    except ValueError as exc:
        return error(400, "INVALID_REQUEST", str(exc))

    now = utc_now_iso()
    try:
        result = boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE_NAME"]).update_item(
            Key={"requestId": request_id},
            UpdateExpression="SET requestStatus=:status, updatedAt=:now, gsi3pk=:gsi3pk, gsi3sk=:gsi3sk",
            ConditionExpression="attribute_exists(requestId)",
            ExpressionAttributeValues={":status": payload.status, ":now": now, ":gsi3pk": f"STATUS#{payload.status}", ":gsi3sk": now},
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error(404, "NOT_FOUND", "Talep bulunamadı.")
        raise
    return response(200, admin_request(result["Attributes"]))
