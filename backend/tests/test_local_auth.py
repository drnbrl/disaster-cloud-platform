from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from botocore.exceptions import ClientError

import local_app.local_auth as local_auth
from local_app.local_auth import (
    GENERIC_LOGIN_ERROR,
    LocalAdminPrincipal,
    LocalAuthenticationError,
    LocalDuplicateAdminError,
    LocalLoginInput,
)
from local_app.settings import LocalSettings

PASSWORD = "Strong-Local-Password-123!"


def test_valid_login_returns_signed_jwt(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    settings = configure_local_auth(monkeypatch, table)
    add_admin_user(table, "ADMIN@Example.COM", PASSWORD)

    response = local_auth.login(LocalLoginInput(email="admin@example.com", password=PASSWORD))

    assert response["tokenType"] == "Bearer"
    assert response["user"] == {"email": "admin@example.com", "displayName": "Admin Name", "role": "admin"}
    claims = jwt.decode(
        response["accessToken"],
        settings.jwt_secret,
        algorithms=[local_auth.JWT_ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    assert claims["email"] == "admin@example.com"
    assert claims["role"] == "admin"
    assert "exp" in claims


def test_invalid_password_returns_generic_login_error(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    configure_local_auth(monkeypatch, table)
    add_admin_user(table, "admin@example.com", PASSWORD)

    with pytest.raises(LocalAuthenticationError, match=GENERIC_LOGIN_ERROR):
        local_auth.login(LocalLoginInput(email="admin@example.com", password="wrong-password"))


def test_unknown_email_returns_generic_login_error(monkeypatch: pytest.MonkeyPatch):
    configure_local_auth(monkeypatch, FakeAdminUsersTable())

    with pytest.raises(LocalAuthenticationError, match=GENERIC_LOGIN_ERROR):
        local_auth.login(LocalLoginInput(email="missing@example.com", password=PASSWORD))


def test_inactive_user_returns_generic_login_error(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    configure_local_auth(monkeypatch, table)
    add_admin_user(table, "admin@example.com", PASSWORD, is_active=False)

    with pytest.raises(LocalAuthenticationError, match=GENERIC_LOGIN_ERROR):
        local_auth.login(LocalLoginInput(email="admin@example.com", password=PASSWORD))


def test_expired_jwt_is_rejected(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    settings = configure_local_auth(monkeypatch, table)
    add_admin_user(table, "admin@example.com", PASSWORD)
    token = local_auth.create_access_token(
        LocalAdminPrincipal(email="admin@example.com", display_name="Admin Name", role="admin"),
        settings,
        expires_in_seconds=-1,
        issued_at=datetime.now(UTC),
    )

    with pytest.raises(LocalAuthenticationError):
        local_auth.verify_access_token(token)


def test_invalid_jwt_is_rejected(monkeypatch: pytest.MonkeyPatch):
    configure_local_auth(monkeypatch, FakeAdminUsersTable())

    with pytest.raises(LocalAuthenticationError):
        local_auth.verify_access_token("not-a-valid-jwt")


def test_admin_endpoint_without_token_is_rejected():
    import local_app.main as local_main

    status_code, body = asyncio.run(request_json(local_main.app, "GET", "/v1/admin/dashboard"))

    assert status_code == 401
    assert body["detail"] == "Oturum bulunamadı."


def test_admin_endpoint_with_valid_token_can_access_dashboard(monkeypatch: pytest.MonkeyPatch):
    import local_app.main as local_main

    table = FakeAdminUsersTable()
    settings = configure_local_auth(monkeypatch, table)
    add_admin_user(table, "admin@example.com", PASSWORD)
    token = local_auth.create_access_token(
        LocalAdminPrincipal(email="admin@example.com", display_name="Admin Name", role="admin"),
        settings,
    )
    monkeypatch.setattr(local_main.service, "dashboard", lambda: {"global": {"totalRequests": 0}, "cities": [], "recentRequests": []})

    status_code, body = asyncio.run(
        request_json(local_main.app, "GET", "/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    )

    assert status_code == 200
    assert body["global"]["totalRequests"] == 0


def test_duplicate_user_creation_is_rejected(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    configure_local_auth(monkeypatch, table)
    local_auth.create_admin_user("Admin@Example.com", PASSWORD, "Admin Name")

    with pytest.raises(LocalDuplicateAdminError):
        local_auth.create_admin_user("admin@example.com", "Another-Password-123!", "Second Admin")


def test_password_is_stored_only_as_hash(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    configure_local_auth(monkeypatch, table)

    local_auth.create_admin_user("admin@example.com", PASSWORD, "Admin Name")

    stored = table.items["admin@example.com"]
    assert stored["passwordHash"] != PASSWORD
    assert str(stored["passwordHash"]).startswith("$argon2")
    assert "password" not in stored


def test_plaintext_password_is_never_returned(monkeypatch: pytest.MonkeyPatch):
    table = FakeAdminUsersTable()
    configure_local_auth(monkeypatch, table)

    created = local_auth.create_admin_user("admin@example.com", PASSWORD, "Admin Name")
    login_response = local_auth.login(LocalLoginInput(email="admin@example.com", password=PASSWORD))
    token = login_response["accessToken"]
    principal = local_auth.verify_access_token(token)
    response_text = json.dumps(
        {"created": created, "login": login_response, "me": local_auth.principal_view(principal)},
        ensure_ascii=False,
    )

    assert PASSWORD not in response_text
    assert "passwordHash" not in response_text


def configure_local_auth(monkeypatch: pytest.MonkeyPatch, table: "FakeAdminUsersTable") -> LocalSettings:
    settings = LocalSettings(
        dynamodb_endpoint="http://localhost:8000",
        requests_table_name="local-disaster-requests",
        statistics_table_name="local-disaster-statistics",
        admin_users_table_name="local-admin-users",
        allowed_origin="http://localhost:5173",
        jwt_secret="test-only-local-jwt-secret-with-enough-length",
        jwt_issuer="ai-disaster-cloud-platform-local",
        jwt_audience="local-admin-api",
        jwt_expiration_seconds=3600,
        aws_region="us-west-2",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
    monkeypatch.setattr(local_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(local_auth, "get_admin_users_table", lambda settings=None: table)
    return settings


def add_admin_user(table: "FakeAdminUsersTable", email: str, password: str, is_active: bool = True) -> None:
    normalized_email = local_auth.normalize_email(email)
    table.items[normalized_email] = {
        "email": normalized_email,
        "displayName": "Admin Name",
        "passwordHash": local_auth.password_hasher.hash(password),
        "role": "admin",
        "isActive": is_active,
        "createdAt": "2026-08-04T00:00:00Z",
        "updatedAt": "2026-08-04T00:00:00Z",
    }


class FakeAdminUsersTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def put_item(self, Item: dict[str, Any], ConditionExpression: str) -> None:
        assert ConditionExpression == "attribute_not_exists(email)"
        email = str(Item["email"])
        if email in self.items:
            raise conditional_check_failed()
        self.items[email] = dict(Item)

    def get_item(self, Key: dict[str, str], ConsistentRead: bool = False) -> dict[str, Any]:
        assert ConsistentRead is True
        item = self.items.get(Key["email"])
        return {"Item": dict(item)} if item else {}

    def update_item(
        self,
        Key: dict[str, str],
        UpdateExpression: str,
        ConditionExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        ReturnValues: str,
    ) -> dict[str, Any]:
        assert ConditionExpression == "attribute_exists(email)"
        assert ReturnValues == "ALL_NEW"
        item = self.items.get(Key["email"])
        if not item:
            raise conditional_check_failed()
        if "isActive" in UpdateExpression:
            item["isActive"] = ExpressionAttributeValues[":inactive"]
        if "passwordHash" in UpdateExpression:
            item["passwordHash"] = ExpressionAttributeValues[":passwordHash"]
        item["updatedAt"] = ExpressionAttributeValues[":updatedAt"]
        return {"Attributes": dict(item)}


def conditional_check_failed() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "conditional check failed"}},
        "PutItem",
    )


async def request_json(
    app: Any,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload or {}).encode() if payload is not None else b""
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
        "method": method,
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
