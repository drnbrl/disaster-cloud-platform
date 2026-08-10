from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared.bedrock_ai import analyze_message
from shared.geocoding import LocationUpdate, geocode_request_location
from shared.priority import calculate_priority
from shared.serialization import serialize_values
from shared.time_utils import utc_now_iso

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _stats_values(analysis: Any, priority: dict[str, Any], now: str) -> dict[str, Any]:
    return {
        ":one": 1,
        ":critical": int(priority["level"] == "critical"),
        ":high": int(priority["level"] == "high"),
        ":medium": int(priority["level"] == "medium"),
        ":low": int(priority["level"] == "low"),
        ":water": int(analysis.needs.water),
        ":food": int(analysis.needs.food),
        ":shelter": int(analysis.needs.shelter),
        ":medical": int(analysis.needs.medical),
        ":electricity": int(analysis.needs.electricity),
        ":baby": int(analysis.needs.baby_support),
        ":affected": analysis.people_count or 0,
        ":injured": analysis.injured_count or 0,
        ":updatedAt": now,
    }


def _stats_update(scope: str, values: dict[str, Any], city: str | None = None) -> dict[str, Any]:
    expression_values = dict(values)
    set_expr = "SET updatedAt=:updatedAt"
    names = None
    if city:
        set_expr += ", #city=if_not_exists(#city,:city)"
        expression_values[":city"] = city
        names = {"#city": "city"}
    update: dict[str, Any] = {
        "TableName": os.environ["STATISTICS_TABLE_NAME"],
        "Key": {"scope": serialize_values({":scope": scope})[":scope"]},
        "UpdateExpression": (
            f"{set_expr} ADD totalRequests :one, criticalRequests :critical, highRequests :high, "
            "mediumRequests :medium, lowRequests :low, waterRequests :water, foodRequests :food, "
            "shelterRequests :shelter, medicalRequests :medical, electricityRequests :electricity, "
            "babySupportRequests :baby, affectedPeople :affected, injuredPeople :injured"
        ),
        "ExpressionAttributeValues": serialize_values(expression_values),
    }
    if names:
        update["ExpressionAttributeNames"] = names
    return {"Update": update}


def _complete(request_id: str, item: dict[str, Any], analysis: Any, priority: dict[str, Any], location_update: LocationUpdate) -> None:
    now = utc_now_iso()
    city = item["city"]
    values = {
        ":completed": "COMPLETED",
        ":people": analysis.people_count,
        ":injured": analysis.injured_count,
        ":needs": analysis.needs.model_dump(),
        ":signals": analysis.risk_signals,
        ":vulnerable": analysis.vulnerable_groups,
        ":summary": analysis.summary,
        ":score": priority["score"],
        ":level": priority["level"],
        ":reasons": priority["reasons"],
        ":confidence": analysis.confidence,
        ":review": analysis.confidence < 0.70,
        ":model": os.getenv("BEDROCK_MODEL_ID") or "mock",
        ":prompt": os.getenv("PROMPT_VERSION", "1.0.0"),
        ":now": now,
        ":gsi1pk": f"PRIORITY#{priority['level']}",
        ":gsi1sk": item["createdAt"],
        ":gsi2pk": f"CITY#{city}",
        ":gsi2sk": f"{priority['score']:03d}#{item['createdAt']}",
    }
    location_assignments = []
    for index, (name, value) in enumerate(location_update.attributes.items()):
        name_key = f"#location{index}"
        value_key = f":location{index}"
        location_assignments.append(f"{name_key}={value_key}")
        values[value_key] = value
    request_update = {
        "Update": {
            "TableName": os.environ["REQUESTS_TABLE_NAME"],
            "Key": {"requestId": serialize_values({":id": request_id})[":id"]},
            "UpdateExpression": (
                "SET analysisStatus=:completed, peopleCount=:people, injuredCount=:injured, needs=:needs, "
                "riskSignals=:signals, vulnerableGroups=:vulnerable, summary=:summary, priorityScore=:score, "
                "priorityLevel=:level, priorityReasons=:reasons, aiConfidence=:confidence, requiresHumanReview=:review, "
                "modelId=:model, promptVersion=:prompt, updatedAt=:now, gsi1pk=:gsi1pk, gsi1sk=:gsi1sk, "
                "gsi2pk=:gsi2pk, gsi2sk=:gsi2sk"
                + (", " + ", ".join(location_assignments) if location_assignments else "")
            ),
            "ConditionExpression": "analysisStatus <> :completed",
            "ExpressionAttributeValues": serialize_values(values),
        }
    }
    if location_assignments:
        request_update["Update"]["ExpressionAttributeNames"] = {
            f"#location{index}": name
            for index, name in enumerate(location_update.attributes)
        }
    stats_values = _stats_values(analysis, priority, now)
    boto3.client("dynamodb").transact_write_items(
        TransactItems=[
            request_update,
            _stats_update("GLOBAL", stats_values),
            _stats_update(f"CITY#{city}", stats_values, city),
        ]
    )


def _process(request_id: str) -> None:
    table = boto3.resource("dynamodb").Table(os.environ["REQUESTS_TABLE_NAME"])
    item = table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
    if not item:
        logger.warning("request_missing", extra={"requestId": request_id})
        return
    if item.get("analysisStatus") == "COMPLETED":
        return
    analysis = analyze_message(item["message"])
    priority = calculate_priority(analysis)
    location_update = geocode_request_location(item)
    try:
        _complete(request_id, item, analysis, priority, location_update)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "TransactionCanceledException":
            latest = table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
            if latest and latest.get("analysisStatus") == "COMPLETED":
                return
        raise
    logger.info("analysis_completed", extra={"requestId": request_id, "city": item["city"], "priority": priority["level"], "priorityScore": priority["score"]})


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            body = json.loads(record["body"])
            request_id = body["requestId"]
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("Invalid requestId")
            _process(request_id)
        except Exception:
            logger.exception("analysis_failed", extra={"sqsMessageId": message_id})
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
