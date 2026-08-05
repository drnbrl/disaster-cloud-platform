from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from shared.http import response
from shared.safe_views import admin_request

EMPTY = {
    "totalRequests": 0, "criticalRequests": 0, "highRequests": 0, "mediumRequests": 0, "lowRequests": 0,
    "waterRequests": 0, "foodRequests": 0, "shelterRequests": 0, "medicalRequests": 0,
    "electricityRequests": 0, "babySupportRequests": 0, "affectedPeople": 0, "injuredPeople": 0,
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    dynamodb = boto3.resource("dynamodb")
    stats = dynamodb.Table(os.environ["STATISTICS_TABLE_NAME"])
    requests = dynamodb.Table(os.environ["REQUESTS_TABLE_NAME"])
    global_item = stats.get_item(Key={"scope": "GLOBAL"}).get("Item") or {}
    global_stats = {**EMPTY, **{key: value for key, value in global_item.items() if key != "scope"}}
    city_items = stats.scan(FilterExpression=Attr("scope").begins_with("CITY#"), Limit=200).get("Items", [])
    city_items.sort(key=lambda item: int(item.get("criticalRequests", 0)), reverse=True)
    recent = requests.query(IndexName="CreatedIndex", KeyConditionExpression=Key("gsi4pk").eq("ALL"), ScanIndexForward=False, Limit=10).get("Items", [])
    return response(200, {"global": global_stats, "cities": city_items, "recentRequests": [admin_request(item) for item in recent]})
