#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal
import os
import sys
from pathlib import Path
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from shared.geocoding import geocode_request_location, has_any_valid_coordinate  # noqa: E402


def main() -> int:
    args = parse_args()
    table_name = args.table_name or os.getenv("REQUESTS_TABLE_NAME")
    if not table_name:
        raise SystemExit("REQUESTS_TABLE_NAME or --table-name is required.")

    session = boto3.Session(region_name=args.region)
    table = session.resource("dynamodb").Table(table_name)
    geo_client = session.client("geo-places")

    counts = {"scanned": 0, "eligible": 0, "resolved": 0, "unresolved": 0, "skipped": 0}
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": Attr("latitude").not_exists() | Attr("longitude").not_exists(),
    }

    while True:
        page = table.scan(**scan_kwargs)
        for item in page.get("Items", []):
            counts["scanned"] += 1
            if not _has_address(item) or has_any_valid_coordinate(item):
                counts["skipped"] += 1
                continue

            counts["eligible"] += 1
            update = geocode_request_location(item, client=geo_client)
            if update.resolved:
                counts["resolved"] += 1
            else:
                counts["unresolved"] += 1
            if args.dry_run:
                continue
            _update_location_attributes(table, str(item["requestId"]), update.attributes)

        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    for key in ["scanned", "eligible", "resolved", "unresolved", "skipped"]:
        print(f"{key}: {counts[key]}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing request coordinates from stored addresses.")
    parser.add_argument("--table-name", help="Requests DynamoDB table name. Defaults to REQUESTS_TABLE_NAME.")
    parser.add_argument("--region", help="AWS Region for DynamoDB and Amazon Location.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing updates.")
    return parser.parse_args()


def _has_address(item: dict[str, Any]) -> bool:
    return isinstance(item.get("address"), str) and bool(item["address"].strip())


def _update_location_attributes(table: Any, request_id: str, attributes: dict[str, Any]) -> None:
    if not attributes:
        return
    names: dict[str, str] = {}
    values: dict[str, Any] = {}
    assignments = []
    for index, (name, value) in enumerate(attributes.items()):
        name_key = f"#location{index}"
        value_key = f":location{index}"
        names[name_key] = name
        values[value_key] = Decimal(str(value)) if isinstance(value, float) else value
        assignments.append(f"{name_key}={value_key}")
    table.update_item(
        Key={"requestId": request_id},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression="attribute_exists(requestId)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
