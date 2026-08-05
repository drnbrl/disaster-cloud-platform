from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from shared.http import error, header, parse_body, response, validation_error
from shared.models import CreateRequestInput
from shared.serialization import to_dynamodb
from shared.time_utils import utc_now_iso

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _request_id(event: dict[str, Any]) -> str:
    key = header(event, "Idempotency-Key")
    if not key:
        return str(uuid.uuid4())
    if len(key) > 200:
        raise ValueError("Idempotency-Key is too long.")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"disaster-request:{key}"))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        payload = CreateRequestInput.model_validate(parse_body(event))
        request_id = _request_id(event)
    except ValidationError as exc:
        return validation_error(exc)
    except ValueError as exc:
        return error(400, "INVALID_REQUEST", str(exc))

    table = boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE_NAME"])
    queue = boto3.client("sqs")
    now = utc_now_iso()
    item = {
        "requestId": request_id,
        "createdAt": now,
        "updatedAt": now,
        "source": "WEB",
        "city": payload.city,
        "district": payload.district,
        "address": payload.address,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "message": payload.message,
        "requestStatus": "RECEIVED",
        "analysisStatus": "PENDING",
        "queueSubmitted": False,
        "gsi3pk": "STATUS#RECEIVED",
        "gsi3sk": now,
        "gsi4pk": "ALL",
        "gsi4sk": now,
        "schemaVersion": "1.0.0",
    }
    item = {key: value for key, value in item.items() if value is not None}
    duplicate = False

    try:
        table.put_item(Item=to_dynamodb(item), ConditionExpression="attribute_not_exists(requestId)")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            logger.exception("request_store_failed", extra={"requestId": request_id})
            return error(500, "STORE_FAILED", "Talep kaydedilemedi.")
        duplicate = True
        existing = table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
        if not existing:
            return error(409, "IDEMPOTENCY_CONFLICT", "Talep durumu doğrulanamadı.")
        item = existing

    if not item.get("queueSubmitted", False):
        try:
            queue.send_message(QueueUrl=os.environ["ANALYSIS_QUEUE_URL"], MessageBody=json.dumps({"requestId": request_id}))
            table.update_item(
                Key={"requestId": request_id},
                UpdateExpression="SET queueSubmitted=:yes, updatedAt=:now",
                ExpressionAttributeValues={":yes": True, ":now": utc_now_iso()},
            )
        except ClientError:
            logger.exception("request_queue_failed", extra={"requestId": request_id})
            return error(503, "QUEUE_FAILED", "Talep kaydedildi ancak analiz kuyruğuna aktarılamadı. Aynı istek anahtarıyla tekrar deneyin.")

    logger.info("request_received", extra={"requestId": request_id, "city": payload.city, "duplicate": duplicate})
    return response(
        200 if duplicate else 202,
        {
            "requestId": request_id,
            "status": item["requestStatus"],
            "analysisStatus": item["analysisStatus"],
            "message": "Talebiniz alınmıştır.",
            "createdAt": item["createdAt"],
        },
    )
