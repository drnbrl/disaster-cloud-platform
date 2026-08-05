from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from local_app.dynamodb import get_dynamodb_client, get_tables
from local_app.settings import get_settings
from shared.allocation import calculate_allocation
from shared.mock_ai import analyze_with_mock
from shared.models import AiAnalysis, AllocationInput, CreateRequestInput, StatusUpdateInput
from shared.priority import calculate_priority
from shared.safe_views import admin_request, public_request
from shared.serialization import decode_cursor, encode_cursor, from_dynamodb, serialize_values, to_dynamodb
from shared.time_utils import utc_now_iso

PRIORITIES = {"low", "medium", "high", "critical"}
STATUSES = {"RECEIVED", "REVIEWED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"}

EMPTY_STATS = {
    "totalRequests": 0,
    "criticalRequests": 0,
    "highRequests": 0,
    "mediumRequests": 0,
    "lowRequests": 0,
    "waterRequests": 0,
    "foodRequests": 0,
    "shelterRequests": 0,
    "medicalRequests": 0,
    "electricityRequests": 0,
    "babySupportRequests": 0,
    "affectedPeople": 0,
    "injuredPeople": 0,
}


@dataclass(frozen=True)
class StoredRequest:
    status_code: int
    body: dict[str, Any]
    request_id: str
    should_analyze: bool


class LocalNotFoundError(Exception):
    pass


class LocalValidationError(Exception):
    pass


def request_id_from_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        return str(uuid.uuid4())
    value = idempotency_key.strip()
    if len(value) > 200:
        raise LocalValidationError("Idempotency-Key is too long.")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"disaster-request:{value}"))


def create_request(payload: CreateRequestInput, idempotency_key: str | None) -> StoredRequest:
    request_id = request_id_from_idempotency_key(idempotency_key)
    requests_table, _ = get_tables()
    now = utc_now_iso()
    item = {
        "requestId": request_id,
        "createdAt": now,
        "updatedAt": now,
        "source": "LOCAL_WEB",
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
        requests_table.put_item(Item=to_dynamodb(item), ConditionExpression="attribute_not_exists(requestId)")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        duplicate = True
        existing = requests_table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
        if not existing:
            raise LocalValidationError("Stored request state could not be verified.")
        item = existing

    return StoredRequest(
        status_code=200 if duplicate else 202,
        request_id=request_id,
        should_analyze=item.get("analysisStatus") != "COMPLETED",
        body={
            "requestId": request_id,
            "status": item["requestStatus"],
            "analysisStatus": item["analysisStatus"],
            "message": "Talebiniz yerel geliştirme ortamında alınmıştır.",
            "createdAt": item["createdAt"],
        },
    )


def process_request(request_id: str) -> None:
    requests_table, _ = get_tables()
    item = requests_table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
    if not item or item.get("analysisStatus") == "COMPLETED":
        return
    analysis = AiAnalysis.model_validate(analyze_with_mock(str(item["message"])).model_dump())
    priority = calculate_priority(analysis)
    complete_analysis(request_id, item, analysis, priority)


def complete_analysis(request_id: str, item: dict[str, Any], analysis: AiAnalysis, priority: dict[str, Any]) -> None:
    settings = get_settings()
    now = utc_now_iso()
    city = str(item["city"])
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
        ":model": "local-mock",
        ":prompt": "local-1.0.0",
        ":now": now,
        ":gsi1pk": f"PRIORITY#{priority['level']}",
        ":gsi1sk": item["createdAt"],
        ":gsi2pk": f"CITY#{city}",
        ":gsi2sk": f"{priority['score']:03d}#{item['createdAt']}",
    }
    request_update = {
        "Update": {
            "TableName": settings.requests_table_name,
            "Key": {"requestId": serialize_values({":id": request_id})[":id"]},
            "UpdateExpression": (
                "SET analysisStatus=:completed, peopleCount=:people, injuredCount=:injured, needs=:needs, "
                "riskSignals=:signals, vulnerableGroups=:vulnerable, summary=:summary, priorityScore=:score, "
                "priorityLevel=:level, priorityReasons=:reasons, aiConfidence=:confidence, requiresHumanReview=:review, "
                "modelId=:model, promptVersion=:prompt, updatedAt=:now, gsi1pk=:gsi1pk, gsi1sk=:gsi1sk, "
                "gsi2pk=:gsi2pk, gsi2sk=:gsi2sk"
            ),
            "ConditionExpression": "analysisStatus <> :completed",
            "ExpressionAttributeValues": serialize_values(values),
        }
    }
    stats_values = _stats_values(analysis, priority, now)
    try:
        get_dynamodb_client(settings).transact_write_items(
            TransactItems=[
                request_update,
                _stats_update(settings.statistics_table_name, "GLOBAL", stats_values),
                _stats_update(settings.statistics_table_name, f"CITY#{city}", stats_values, city),
            ]
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "TransactionCanceledException":
            latest, _ = get_tables(settings)
            existing = latest.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
            if existing and existing.get("analysisStatus") == "COMPLETED":
                return
        raise


def get_public_request(request_id: str) -> dict[str, Any]:
    requests_table, _ = get_tables()
    item = requests_table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
    if not item:
        raise LocalNotFoundError
    return from_dynamodb(public_request(item))


def get_admin_request(request_id: str) -> dict[str, Any]:
    requests_table, _ = get_tables()
    item = requests_table.get_item(Key={"requestId": request_id}, ConsistentRead=True).get("Item")
    if not item:
        raise LocalNotFoundError
    return from_dynamodb(admin_request(item))


def list_admin_requests(
    *,
    priority: str = "",
    city: str = "",
    status: str = "",
    limit: int = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    normalized_priority = priority.lower()
    normalized_city = city.strip()
    normalized_status = status.upper()
    if normalized_priority and normalized_priority not in PRIORITIES:
        raise LocalValidationError("Geçersiz öncelik filtresi.")
    if normalized_status and normalized_status not in STATUSES:
        raise LocalValidationError("Geçersiz durum filtresi.")
    bounded_limit = min(max(limit, 1), 100)
    requests_table, _ = get_tables()
    query: dict[str, Any] = {"Limit": bounded_limit, "ScanIndexForward": False}
    if normalized_priority:
        query.update(IndexName="PriorityIndex", KeyConditionExpression=Key("gsi1pk").eq(f"PRIORITY#{normalized_priority}"))
    elif normalized_city:
        query.update(IndexName="CityIndex", KeyConditionExpression=Key("gsi2pk").eq(f"CITY#{normalized_city}"))
    elif normalized_status:
        query.update(IndexName="StatusIndex", KeyConditionExpression=Key("gsi3pk").eq(f"STATUS#{normalized_status}"))
    else:
        query.update(IndexName="CreatedIndex", KeyConditionExpression=Key("gsi4pk").eq("ALL"))
    decoded_cursor = decode_cursor(cursor)
    if decoded_cursor:
        query["ExclusiveStartKey"] = decoded_cursor
    result = requests_table.query(**query)
    return {
        "items": [from_dynamodb(admin_request(item)) for item in result.get("Items", [])],
        "nextCursor": encode_cursor(result.get("LastEvaluatedKey")),
    }


def update_request_status(request_id: str, payload: StatusUpdateInput) -> dict[str, Any]:
    requests_table, _ = get_tables()
    now = utc_now_iso()
    try:
        result = requests_table.update_item(
            Key={"requestId": request_id},
            UpdateExpression="SET requestStatus=:status, updatedAt=:now, gsi3pk=:gsi3pk, gsi3sk=:gsi3sk",
            ConditionExpression="attribute_exists(requestId)",
            ExpressionAttributeValues={":status": payload.status, ":now": now, ":gsi3pk": f"STATUS#{payload.status}", ":gsi3sk": now},
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise LocalNotFoundError from exc
        raise
    return from_dynamodb(admin_request(result["Attributes"]))


def dashboard() -> dict[str, Any]:
    requests_table, stats_table = get_tables()
    global_item = stats_table.get_item(Key={"scope": "GLOBAL"}).get("Item") or {}
    global_stats = {**EMPTY_STATS, **{key: value for key, value in global_item.items() if key != "scope"}}
    city_items = stats_table.scan(FilterExpression=Attr("scope").begins_with("CITY#"), Limit=200).get("Items", [])
    city_items.sort(key=lambda item: int(item.get("criticalRequests", 0)), reverse=True)
    recent = requests_table.query(
        IndexName="CreatedIndex",
        KeyConditionExpression=Key("gsi4pk").eq("ALL"),
        ScanIndexForward=False,
        Limit=10,
    ).get("Items", [])
    return from_dynamodb(
        {
            "global": global_stats,
            "cities": city_items,
            "recentRequests": [admin_request(item) for item in recent],
        }
    )


def allocate(payload: AllocationInput) -> dict[str, Any]:
    _, stats_table = get_tables()
    city_stats = stats_table.scan(FilterExpression=Attr("scope").begins_with("CITY#"), Limit=200).get("Items", [])
    city_stats = [from_dynamodb(item) for item in city_stats]
    if payload.cities:
        selected = {city.casefold() for city in payload.cities}
        city_stats = [item for item in city_stats if str(item.get("city", "")).casefold() in selected]
    inventory = payload.inventory_payload()
    result = calculate_allocation(inventory, city_stats)
    result["explanation"] = _local_allocation_explanation(result)
    result["inputResources"] = inventory
    return result


def _stats_values(analysis: AiAnalysis, priority: dict[str, Any], now: str) -> dict[str, Any]:
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


def _stats_update(table_name: str, scope: str, values: dict[str, Any], city: str | None = None) -> dict[str, Any]:
    expression_values = dict(values)
    set_expr = "SET updatedAt=:updatedAt"
    names = None
    if city:
        set_expr += ", #city=if_not_exists(#city,:city)"
        expression_values[":city"] = city
        names = {"#city": "city"}
    update: dict[str, Any] = {
        "TableName": table_name,
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


def _local_allocation_explanation(result: dict[str, Any]) -> str:
    allocations = result.get("allocations", [])
    if not allocations:
        return "Kayıtlı yerel ihtiyaç skoru bulunmadığı için kaynaklar dağıtılmadı."
    leaders = ", ".join(str(item["city"]) for item in allocations[:3])
    return f"Dağıtım yerel sentetik verilerdeki ihtiyaç skorlarına göre hesaplandı. İlk öncelikli şehirler: {leaders}."
