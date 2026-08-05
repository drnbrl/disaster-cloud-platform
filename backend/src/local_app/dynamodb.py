from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError

from local_app.settings import LocalSettings, get_settings


def _boto3_kwargs(settings: LocalSettings) -> dict[str, str]:
    return {
        "endpoint_url": settings.dynamodb_endpoint,
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }


def get_dynamodb_resource(settings: LocalSettings | None = None) -> Any:
    local_settings = settings or get_settings()
    return boto3.resource("dynamodb", **_boto3_kwargs(local_settings))


def get_dynamodb_client(settings: LocalSettings | None = None) -> Any:
    local_settings = settings or get_settings()
    return boto3.client("dynamodb", **_boto3_kwargs(local_settings))


def get_tables(settings: LocalSettings | None = None) -> tuple[Any, Any]:
    local_settings = settings or get_settings()
    dynamodb = get_dynamodb_resource(local_settings)
    return dynamodb.Table(local_settings.requests_table_name), dynamodb.Table(local_settings.statistics_table_name)


def get_admin_users_table(settings: LocalSettings | None = None) -> Any:
    local_settings = settings or get_settings()
    return get_dynamodb_resource(local_settings).Table(local_settings.admin_users_table_name)


def ensure_tables(settings: LocalSettings | None = None) -> None:
    local_settings = settings or get_settings()
    client = get_dynamodb_client(local_settings)
    _ensure_requests_table(client, local_settings.requests_table_name)
    _ensure_statistics_table(client, local_settings.statistics_table_name)
    _ensure_admin_users_table(client, local_settings.admin_users_table_name)


def _table_exists(client: Any, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def _ensure_requests_table(client: Any, table_name: str) -> None:
    if _table_exists(client, table_name):
        return
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "requestId", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
            {"AttributeName": "gsi2pk", "AttributeType": "S"},
            {"AttributeName": "gsi2sk", "AttributeType": "S"},
            {"AttributeName": "gsi3pk", "AttributeType": "S"},
            {"AttributeName": "gsi3sk", "AttributeType": "S"},
            {"AttributeName": "gsi4pk", "AttributeType": "S"},
            {"AttributeName": "gsi4sk", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "requestId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "PriorityIndex",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "CityIndex",
                "KeySchema": [
                    {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "StatusIndex",
                "KeySchema": [
                    {"AttributeName": "gsi3pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi3sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "CreatedIndex",
                "KeySchema": [
                    {"AttributeName": "gsi4pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi4sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )
    client.get_waiter("table_exists").wait(TableName=table_name)


def _ensure_statistics_table(client: Any, table_name: str) -> None:
    if _table_exists(client, table_name):
        return
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "scope", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "scope", "KeyType": "HASH"}],
    )
    client.get_waiter("table_exists").wait(TableName=table_name)


def _ensure_admin_users_table(client: Any, table_name: str) -> None:
    if _table_exists(client, table_name):
        return
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
    )
    client.get_waiter("table_exists").wait(TableName=table_name)
