from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

LOCAL_DOCKER_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "dynamodb-local", "host.docker.internal"}


@dataclass(frozen=True)
class LocalSettings:
    dynamodb_endpoint: str
    requests_table_name: str
    statistics_table_name: str
    admin_users_table_name: str
    allowed_origin: str
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_expiration_seconds: int
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str


def validate_local_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if "amazonaws.com" in value.casefold():
        raise ValueError("Local mode rejects amazonaws.com endpoints.")
    if parsed.scheme != "http":
        raise ValueError("Local mode requires an http endpoint.")
    if host not in LOCAL_DOCKER_HOSTS:
        raise ValueError(f"Local mode only allows local or Docker service hosts: {host}")
    if not parsed.port:
        raise ValueError("Local mode requires an explicit endpoint port.")
    return value.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> LocalSettings:
    endpoint = validate_local_endpoint(os.getenv("LOCAL_DYNAMODB_ENDPOINT", "http://localhost:8000"))
    return LocalSettings(
        dynamodb_endpoint=endpoint,
        requests_table_name=os.getenv("REQUESTS_TABLE_NAME", "local-disaster-requests"),
        statistics_table_name=os.getenv("STATISTICS_TABLE_NAME", "local-disaster-statistics"),
        admin_users_table_name=os.getenv("LOCAL_ADMIN_USERS_TABLE_NAME", "local-admin-users"),
        allowed_origin=os.getenv("LOCAL_ALLOWED_ORIGIN", "http://localhost:5173"),
        jwt_secret=os.getenv("LOCAL_JWT_SECRET", "local-dev-only-insecure-jwt-secret-change-me"),
        jwt_issuer=os.getenv("LOCAL_JWT_ISSUER", "ai-disaster-cloud-platform-local"),
        jwt_audience=os.getenv("LOCAL_JWT_AUDIENCE", "local-admin-api"),
        jwt_expiration_seconds=int(os.getenv("LOCAL_JWT_EXPIRATION_SECONDS", "3600")),
        aws_region=os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("LOCAL_AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.getenv("LOCAL_AWS_SECRET_ACCESS_KEY", "local"),
    )
