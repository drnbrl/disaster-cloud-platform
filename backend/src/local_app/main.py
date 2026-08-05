from __future__ import annotations

from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from local_app.dynamodb import ensure_tables, get_dynamodb_client
from local_app import local_auth
from local_app import service
from local_app.local_auth import LocalAdminPrincipal, LocalLoginInput
from local_app.service import LocalNotFoundError, LocalValidationError
from local_app.settings import get_settings
from shared.models import AllocationInput, CreateRequestInput, StatusUpdateInput

bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="Disaster Platform Local API", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
)


@app.on_event("startup")
def startup() -> None:
    ensure_tables()


def require_local_admin(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> LocalAdminPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum bulunamadı.")
    try:
        return local_auth.verify_access_token(credentials.credentials)
    except local_auth.LocalAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except local_auth.LocalAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    local_settings = get_settings()
    get_dynamodb_client(local_settings).list_tables(Limit=1)
    return {
        "status": "ok",
        "mode": "local",
        "dynamodbEndpoint": local_settings.dynamodb_endpoint,
        "requestsTable": local_settings.requests_table_name,
        "statisticsTable": local_settings.statistics_table_name,
    }


@app.post("/v1/local-auth/login")
def login(payload: LocalLoginInput) -> dict[str, object]:
    try:
        return local_auth.login(payload)
    except local_auth.LocalAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.get("/v1/local-auth/me")
def me(principal: Annotated[LocalAdminPrincipal, Depends(require_local_admin)]) -> dict[str, str]:
    return local_auth.principal_view(principal)


@app.post("/v1/requests", status_code=status.HTTP_202_ACCEPTED)
def create_request(
    payload: CreateRequestInput,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    try:
        result = service.create_request(payload, idempotency_key)
    except LocalValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    response.status_code = result.status_code
    if result.should_analyze:
        background_tasks.add_task(service.process_request, result.request_id)
    return result.body


@app.get("/v1/requests/{request_id}")
def get_request(request_id: str) -> dict[str, object]:
    try:
        return service.get_public_request(request_id)
    except LocalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talep bulunamadı.") from exc


@app.get("/v1/admin/requests", dependencies=[Depends(require_local_admin)])
def list_admin_requests(
    priority: str = "",
    city: str = "",
    request_status: Annotated[str, Query(alias="status")] = "",
    limit: int = 25,
    cursor: str | None = None,
) -> dict[str, object]:
    try:
        return service.list_admin_requests(priority=priority, city=city, status=request_status, limit=limit, cursor=cursor)
    except (LocalValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/v1/admin/requests/{request_id}", dependencies=[Depends(require_local_admin)])
def get_admin_request(request_id: str) -> dict[str, object]:
    try:
        return service.get_admin_request(request_id)
    except LocalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talep bulunamadı.") from exc


@app.patch("/v1/admin/requests/{request_id}/status", dependencies=[Depends(require_local_admin)])
def update_request_status(request_id: str, payload: StatusUpdateInput) -> dict[str, object]:
    try:
        return service.update_request_status(request_id, payload)
    except LocalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talep bulunamadı.") from exc


@app.get("/v1/admin/dashboard", dependencies=[Depends(require_local_admin)])
def dashboard() -> dict[str, object]:
    return service.dashboard()


@app.post("/v1/admin/allocations", dependencies=[Depends(require_local_admin)])
def allocate(payload: AllocationInput) -> dict[str, object]:
    return service.allocate(payload)
