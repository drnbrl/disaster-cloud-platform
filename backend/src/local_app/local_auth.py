from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field

from local_app.dynamodb import get_admin_users_table
from local_app.settings import LocalSettings, get_settings
from shared.time_utils import utc_now_iso

GENERIC_LOGIN_ERROR = "E-posta veya şifre hatalı."
ADMIN_ROLE = "admin"
JWT_ALGORITHM = "HS256"

password_hasher = PasswordHasher()


class LocalLoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


@dataclass(frozen=True)
class LocalAdminPrincipal:
    email: str
    display_name: str
    role: str


class LocalAuthenticationError(Exception):
    pass


class LocalAuthorizationError(Exception):
    pass


class LocalDuplicateAdminError(Exception):
    pass


class LocalAdminNotFoundError(Exception):
    pass


class LocalAdminValidationError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def public_admin_user(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": str(item["email"]),
        "displayName": str(item["displayName"]),
        "role": str(item["role"]),
        "isActive": bool(item["isActive"]),
        "createdAt": str(item["createdAt"]),
        "updatedAt": str(item["updatedAt"]),
    }


def principal_view(principal: LocalAdminPrincipal) -> dict[str, str]:
    return {
        "email": principal.email,
        "displayName": principal.display_name,
        "role": principal.role,
    }


def create_admin_user(email: str, password: str, display_name: str, role: str = ADMIN_ROLE) -> dict[str, Any]:
    normalized_email = _validate_email(email)
    normalized_display_name = display_name.strip()
    normalized_role = role.strip() or ADMIN_ROLE
    if not normalized_display_name:
        raise LocalAdminValidationError("Display name is required.")
    if not password:
        raise LocalAdminValidationError("Password is required.")
    now = utc_now_iso()
    item = {
        "email": normalized_email,
        "displayName": normalized_display_name,
        "passwordHash": password_hasher.hash(password),
        "role": normalized_role,
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    }
    table = get_admin_users_table()
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(email)")
    except ClientError as exc:
        if _error_code(exc) == "ConditionalCheckFailedException":
            raise LocalDuplicateAdminError(f"Local administrator already exists: {normalized_email}") from exc
        raise
    return public_admin_user(item)


def disable_admin_user(email: str) -> dict[str, Any]:
    normalized_email = _validate_email(email)
    now = utc_now_iso()
    table = get_admin_users_table()
    try:
        result = table.update_item(
            Key={"email": normalized_email},
            UpdateExpression="SET isActive=:inactive, updatedAt=:updatedAt",
            ConditionExpression="attribute_exists(email)",
            ExpressionAttributeValues={":inactive": False, ":updatedAt": now},
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if _error_code(exc) == "ConditionalCheckFailedException":
            raise LocalAdminNotFoundError(f"Local administrator not found: {normalized_email}") from exc
        raise
    return public_admin_user(result["Attributes"])


def change_admin_password(email: str, password: str) -> dict[str, Any]:
    normalized_email = _validate_email(email)
    if not password:
        raise LocalAdminValidationError("Password is required.")
    now = utc_now_iso()
    table = get_admin_users_table()
    try:
        result = table.update_item(
            Key={"email": normalized_email},
            UpdateExpression="SET passwordHash=:passwordHash, updatedAt=:updatedAt",
            ConditionExpression="attribute_exists(email)",
            ExpressionAttributeValues={":passwordHash": password_hasher.hash(password), ":updatedAt": now},
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if _error_code(exc) == "ConditionalCheckFailedException":
            raise LocalAdminNotFoundError(f"Local administrator not found: {normalized_email}") from exc
        raise
    return public_admin_user(result["Attributes"])


def login(payload: LocalLoginInput) -> dict[str, Any]:
    email = normalize_email(payload.email)
    table = get_admin_users_table()
    item = table.get_item(Key={"email": email}, ConsistentRead=True).get("Item")
    if not item or not item.get("isActive", False):
        raise LocalAuthenticationError(GENERIC_LOGIN_ERROR)
    password_hash = str(item.get("passwordHash", ""))
    try:
        password_is_valid = password_hasher.verify(password_hash, payload.password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        password_is_valid = False
    if not password_is_valid:
        raise LocalAuthenticationError(GENERIC_LOGIN_ERROR)

    principal = _principal_from_item(item)
    settings = get_settings()
    return {
        "accessToken": create_access_token(principal, settings),
        "tokenType": "Bearer",
        "expiresIn": settings.jwt_expiration_seconds,
        "user": principal_view(principal),
    }


def verify_access_token(token: str, settings: LocalSettings | None = None) -> LocalAdminPrincipal:
    local_settings = settings or get_settings()
    try:
        claims = jwt.decode(
            token,
            local_settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            audience=local_settings.jwt_audience,
            issuer=local_settings.jwt_issuer,
            options={"require": ["aud", "email", "exp", "iss", "role"]},
        )
    except jwt.PyJWTError as exc:
        raise LocalAuthenticationError("Oturum geçersiz.") from exc

    email = normalize_email(str(claims.get("email", "")))
    role = str(claims.get("role", ""))
    if not email or role != ADMIN_ROLE:
        raise LocalAuthorizationError("Bu işlem için yetki yok.")

    table = get_admin_users_table(local_settings)
    item = table.get_item(Key={"email": email}, ConsistentRead=True).get("Item")
    if not item or not item.get("isActive", False):
        raise LocalAuthenticationError("Oturum geçersiz.")
    principal = _principal_from_item(item)
    if principal.role != role:
        raise LocalAuthorizationError("Bu işlem için yetki yok.")
    return principal


def create_access_token(
    principal: LocalAdminPrincipal,
    settings: LocalSettings | None = None,
    expires_in_seconds: int | None = None,
    issued_at: datetime | None = None,
) -> str:
    local_settings = settings or get_settings()
    now = issued_at or datetime.now(UTC)
    expires_in = expires_in_seconds if expires_in_seconds is not None else local_settings.jwt_expiration_seconds
    claims = {
        "iss": local_settings.jwt_issuer,
        "aud": local_settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "email": principal.email,
        "role": principal.role,
    }
    return jwt.encode(claims, local_settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _principal_from_item(item: dict[str, Any]) -> LocalAdminPrincipal:
    return LocalAdminPrincipal(
        email=str(item["email"]),
        display_name=str(item["displayName"]),
        role=str(item["role"]),
    )


def _validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise LocalAdminValidationError("Valid email is required.")
    return normalized


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))
