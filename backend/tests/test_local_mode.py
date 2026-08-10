from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from boto3.dynamodb.types import TypeDeserializer

import local_app.dynamodb as local_dynamodb
import local_app.service as local_service
from local_app.service import StoredRequest, create_request, process_request
from local_app.local_auth import LocalAdminPrincipal
from local_app.settings import LocalSettings, get_settings, validate_local_endpoint
from shared.models import CreateRequestInput


def test_rejects_amazonaws_endpoint():
    with pytest.raises(ValueError, match="amazonaws.com"):
        validate_local_endpoint("https://dynamodb.us-east-1.amazonaws.com")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://dynamodb-local:8000",
        "http://host.docker.internal:8000",
    ],
)
def test_allows_only_local_or_docker_service_endpoints(endpoint: str):
    assert validate_local_endpoint(endpoint) == endpoint


def test_dynamodb_resource_uses_explicit_local_endpoint(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []

    def fake_resource(service_name: str, **kwargs: str) -> object:
        calls.append({"service_name": service_name, **kwargs})
        return object()

    monkeypatch.setattr(local_dynamodb.boto3, "resource", fake_resource)
    settings = LocalSettings(
        dynamodb_endpoint="http://localhost:8000",
        requests_table_name="requests",
        statistics_table_name="statistics",
        admin_users_table_name="local-admin-users",
        allowed_origin="http://localhost:5173",
        jwt_secret="local-dev-only-insecure-jwt-secret-change-me",
        jwt_issuer="ai-disaster-cloud-platform-local",
        jwt_audience="local-admin-api",
        jwt_expiration_seconds=3600,
        aws_region="us-west-2",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    local_dynamodb.get_dynamodb_resource(settings)

    assert calls == [
        {
            "service_name": "dynamodb",
            "endpoint_url": "http://localhost:8000",
            "region_name": "us-west-2",
            "aws_access_key_id": "local",
            "aws_secret_access_key": "local",
        }
    ]
    assert "amazonaws.com" not in repr(calls).casefold()


def test_local_processing_never_initializes_bedrock_or_sqs(monkeypatch: pytest.MonkeyPatch):
    requested_clients: list[str] = []
    requests_table = FakeRequestsTable()
    stats_table = FakeStatsTable()

    def fake_resource(service_name: str, **kwargs: str) -> FakeResource:
        assert service_name == "dynamodb"
        assert kwargs["endpoint_url"] == "http://localhost:8000"
        assert "amazonaws.com" not in kwargs["endpoint_url"]
        return FakeResource(requests_table, stats_table)

    def fake_client(service_name: str, **kwargs: str) -> FakeDynamoClient:
        requested_clients.append(service_name)
        if service_name in {"bedrock-runtime", "sqs"}:
            raise AssertionError(f"{service_name} must not be initialized in local mode")
        assert service_name == "dynamodb"
        assert kwargs["endpoint_url"] == "http://localhost:8000"
        return FakeDynamoClient(requests_table, stats_table)

    monkeypatch.setenv("LOCAL_DYNAMODB_ENDPOINT", "http://localhost:8000")
    monkeypatch.setenv("REQUESTS_TABLE_NAME", "local-requests")
    monkeypatch.setenv("STATISTICS_TABLE_NAME", "local-statistics")
    monkeypatch.setenv("LOCAL_AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("LOCAL_AWS_SECRET_ACCESS_KEY", "local")
    get_settings.cache_clear()
    monkeypatch.setattr(local_dynamodb.boto3, "resource", fake_resource)
    monkeypatch.setattr(local_dynamodb.boto3, "client", fake_client)

    stored = create_request(
        CreateRequestInput(
            city="Hatay",
            district="Antakya",
            address="Atatürk Caddesi, No: 15, Antakya/Hatay",
            latitude=36.2021,
            longitude=36.1604,
            message="25 kişiyiz. İçme suyumuz bitti. 2 yaralı var. Bebek maması gerekiyor.",
        ),
        "local-test-idempotency-key",
    )
    process_request(stored.request_id)

    assert requested_clients == ["dynamodb"]
    assert requests_table.items[stored.request_id]["analysisStatus"] == "COMPLETED"
    assert requests_table.items[stored.request_id]["modelId"] == "local-mock"


def test_local_post_requests_accepts_valid_request(monkeypatch: pytest.MonkeyPatch):
    import local_app.main as local_main

    captured_payloads: list[CreateRequestInput] = []

    def fake_create_request(payload: CreateRequestInput, idempotency_key: str | None) -> StoredRequest:
        assert idempotency_key == "local-post-valid"
        captured_payloads.append(payload)
        return StoredRequest(
            status_code=202,
            body={
                "requestId": "local-request-id",
                "status": "RECEIVED",
                "analysisStatus": "PENDING",
                "message": "Talebiniz yerel geliştirme ortamında alınmıştır.",
                "createdAt": "2026-08-04T00:00:00Z",
            },
            request_id="local-request-id",
            should_analyze=False,
        )

    monkeypatch.setattr(local_main, "ensure_tables", lambda: None)
    monkeypatch.setattr(local_main.service, "create_request", fake_create_request)

    status_code, body = asyncio.run(
        post_json(
            local_main.app,
            "/v1/requests",
            {
                "city": " Hatay ",
                "district": " Antakya ",
                "address": " Atatürk Caddesi, No: 15, Antakya/Hatay ",
                "message": "25 kişiyiz. İçme suyumuz bitti. Yardım bekliyoruz.",
            },
            {"Idempotency-Key": "local-post-valid"},
        )
    )

    assert status_code == 202
    assert body["requestId"] == "local-request-id"
    assert captured_payloads[0].city == "Hatay"
    assert captured_payloads[0].district == "Antakya"
    assert captured_payloads[0].address == "Atatürk Caddesi, No: 15, Antakya/Hatay"


def test_local_allocation_invalid_custom_resource_returns_controlled_400(monkeypatch: pytest.MonkeyPatch):
    import local_app.main as local_main

    local_main.app.dependency_overrides[local_main.require_local_admin] = lambda: LocalAdminPrincipal(
        email="admin@example.com",
        display_name="Admin",
        role="admin",
    )
    try:
        status_code, body = asyncio.run(
            post_json(
                local_main.app,
                "/v1/admin/allocations",
                {
                    "resources": {"waterLiters": 0, "tents": 0, "medicalStaff": 0, "blankets": 0},
                    "customResources": [{"name": "Yakıt", "quantity": 1, "unit": "litre"}],
                },
                {"Authorization": "Bearer local-test"},
            )
        )
    finally:
        local_main.app.dependency_overrides.clear()

    assert status_code == 400
    assert body["error"] == "VALIDATION_ERROR"
    assert any(item["field"] == "customResources.0.id" for item in body["details"])


def test_local_create_request_stores_required_location_without_coordinates(monkeypatch: pytest.MonkeyPatch):
    requests_table = FakeRequestsTable()
    monkeypatch.setattr(local_service, "get_tables", lambda: (requests_table, FakeStatsTable()))

    stored = create_request(
        CreateRequestInput(
            city="Hatay",
            district="Antakya",
            address="Atatürk Caddesi, No: 15, Antakya/Hatay",
            message="Koordinat veremiyoruz ama su ve temel destek gerekiyor.",
        ),
        "local-without-coordinates",
    )

    item = requests_table.items[stored.request_id]
    assert stored.status_code == 202
    assert item["district"] == "Antakya"
    assert item["address"] == "Atatürk Caddesi, No: 15, Antakya/Hatay"
    assert "latitude" not in item
    assert "longitude" not in item


def test_local_create_request_stores_trimmed_location_fields(monkeypatch: pytest.MonkeyPatch):
    requests_table = FakeRequestsTable()
    monkeypatch.setattr(local_service, "get_tables", lambda: (requests_table, FakeStatsTable()))

    stored = create_request(
        CreateRequestInput(
            city=" Hatay ",
            district=" Antakya ",
            address=" Atatürk Caddesi, No: 15, Antakya/Hatay ",
            message="Adresimiz belli ama koordinat paylaşamıyoruz. Yardım bekliyoruz.",
        ),
        "local-trimmed-location",
    )

    item = requests_table.items[stored.request_id]
    assert item["city"] == "Hatay"
    assert item["district"] == "Antakya"
    assert item["address"] == "Atatürk Caddesi, No: 15, Antakya/Hatay"
    assert "latitude" not in item
    assert "longitude" not in item


def test_local_create_request_stores_coordinates_when_provided(monkeypatch: pytest.MonkeyPatch):
    requests_table = FakeRequestsTable()
    monkeypatch.setattr(local_service, "get_tables", lambda: (requests_table, FakeStatsTable()))

    stored = create_request(
        CreateRequestInput(
            city="Hatay",
            district="Antakya",
            address="Atatürk Caddesi, No: 15, Antakya/Hatay",
            latitude=36.2021,
            longitude=36.1604,
            message="Konum bilgimiz var. Su ve tıbbi destek gerekiyor.",
        ),
        "local-coordinates",
    )

    item = requests_table.items[stored.request_id]
    assert item["district"] == "Antakya"
    assert item["address"] == "Atatürk Caddesi, No: 15, Antakya/Hatay"
    assert float(item["latitude"]) == 36.2021
    assert float(item["longitude"]) == 36.1604


class FakeResource:
    def __init__(self, requests_table: "FakeRequestsTable", stats_table: "FakeStatsTable") -> None:
        self.requests_table = requests_table
        self.stats_table = stats_table

    def Table(self, table_name: str) -> object:
        if "statistics" in table_name:
            return self.stats_table
        return self.requests_table


async def post_json(app: Any, path: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode()
    response_messages: list[dict[str, Any]] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        response_messages.append(message)

    encoded_headers = [(b"content-type", b"application/json")]
    encoded_headers.extend((key.lower().encode(), value.encode()) for key, value in (headers or {}).items())
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": encoded_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }

    await app(scope, receive, send)
    start = next(message for message in response_messages if message["type"] == "http.response.start")
    body_bytes = b"".join(message.get("body", b"") for message in response_messages if message["type"] == "http.response.body")
    return int(start["status"]), json.loads(body_bytes.decode())


class FakeRequestsTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, Item: dict[str, Any], ConditionExpression: str) -> None:
        assert ConditionExpression == "attribute_not_exists(requestId)"
        self.items[Item["requestId"]] = dict(Item)

    def get_item(self, Key: dict[str, str], ConsistentRead: bool = False) -> dict[str, Any]:
        assert ConsistentRead is True
        item = self.items.get(Key["requestId"])
        return {"Item": item} if item else {}


class FakeStatsTable:
    pass


class FakeDynamoClient:
    def __init__(self, requests_table: FakeRequestsTable, stats_table: FakeStatsTable) -> None:
        self.requests_table = requests_table
        self.stats_table = stats_table
        self.deserializer = TypeDeserializer()

    def transact_write_items(self, TransactItems: list[dict[str, Any]]) -> None:
        request_update = TransactItems[0]["Update"]
        request_id = self.deserializer.deserialize(request_update["Key"]["requestId"])
        values = {
            key: self.deserializer.deserialize(value)
            for key, value in request_update["ExpressionAttributeValues"].items()
        }
        item = self.requests_table.items[request_id]
        item.update(
            {
                "analysisStatus": values[":completed"],
                "peopleCount": values[":people"],
                "injuredCount": values[":injured"],
                "needs": values[":needs"],
                "riskSignals": values[":signals"],
                "vulnerableGroups": values[":vulnerable"],
                "summary": values[":summary"],
                "priorityScore": values[":score"],
                "priorityLevel": values[":level"],
                "priorityReasons": values[":reasons"],
                "aiConfidence": values[":confidence"],
                "requiresHumanReview": values[":review"],
                "modelId": values[":model"],
                "promptVersion": values[":prompt"],
                "updatedAt": values[":now"],
                "gsi1pk": values[":gsi1pk"],
                "gsi1sk": values[":gsi1sk"],
                "gsi2pk": values[":gsi2pk"],
                "gsi2sk": values[":gsi2sk"],
            }
        )
