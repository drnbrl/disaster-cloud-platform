# Local Development

This mode runs the internship MVP fully locally. It does not require an AWS account, AWS credentials, AWS deployment, Amazon Bedrock, cloud DynamoDB, cloud SQS, Cognito, API Gateway or any `amazonaws.com` endpoint.

Use synthetic data only.

## Services

- Frontend: `http://localhost:5173`
- FastAPI backend: `http://localhost:8001`
- Health: `http://localhost:8001/health`
- DynamoDB Local: `http://localhost:8000`

`docker-compose.local.yml` starts:

- `dynamodb-local` with persistent Docker volume `dynamodb-local-data`
- `backend` running `uvicorn local_app.main:app` on port `8001`
- `frontend` running Vite on port `5173`

The local backend validates its DynamoDB endpoint at startup. It allows only local or Docker service hosts such as `localhost`, `127.0.0.1`, `dynamodb-local` and `host.docker.internal`, and rejects any endpoint containing `amazonaws.com`.

Local DynamoDB tables are created automatically:

- `local-disaster-requests`
- `local-disaster-statistics`
- `local-admin-users`

## Commands

```bash
./scripts/local-up.sh
./scripts/local-seed.sh 15
./scripts/local-test.sh
./scripts/local-down.sh
```

Reset DynamoDB Local data and Docker volumes:

```bash
./scripts/local-reset.sh
```

## Local Administrator Accounts

Create an administrator after `./scripts/local-up.sh`:

```bash
./scripts/create-local-admin.sh \
  admin@example.com \
  "Strong-Local-Password-123!" \
  "Admin Name"
```

Create another administrator the same way with a different email. Duplicate email addresses are rejected after normalization to lowercase.

Change a password:

```bash
./scripts/change-local-admin-password.sh \
  admin@example.com \
  "New-Strong-Local-Password-123!"
```

Disable an administrator:

```bash
./scripts/disable-local-admin.sh admin@example.com
```

The scripts call the local Python CLI, preferring the running backend container when it is available, and store only Argon2 password hashes in DynamoDB Local. Plaintext passwords are never written to DynamoDB.

The local frontend sends administrator login requests to `POST /v1/local-auth/login` and stores the returned JWT in `sessionStorage`. In production mode the frontend keeps the existing Cognito/Amplify authentication path.

## Local API

Public:

- `GET /health`
- `POST /v1/requests`
- `GET /v1/requests/{requestId}`

Admin, protected by the local JWT:

- `POST /v1/local-auth/login`
- `GET /v1/local-auth/me`
- `GET /v1/admin/requests`
- `GET /v1/admin/requests/{requestId}`
- `PATCH /v1/admin/requests/{requestId}/status`
- `GET /v1/admin/dashboard`
- `POST /v1/admin/allocations`

Example:

```bash
curl -fsS http://localhost:8001/health

curl -fsS -X POST http://localhost:8001/v1/requests \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: local-demo-1' \
  -d '{"city":"Hatay","district":"Antakya","address":"Atatürk Caddesi, No: 15, Antakya/Hatay","latitude":36.2021,"longitude":36.1604,"message":"25 kişiyiz. İçme suyumuz bitti. 2 yaralı var. Bebek maması gerekiyor."}'

TOKEN="$(
  curl -fsS -X POST http://localhost:8001/v1/local-auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"admin@example.com","password":"Strong-Local-Password-123!"}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])'
)"

curl -fsS http://localhost:8001/v1/local-auth/me \
  -H "Authorization: Bearer $TOKEN"

curl -fsS http://localhost:8001/v1/admin/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

## Behavior

- Public requests are stored in DynamoDB Local before AI processing.
- Local AI processing uses `shared.mock_ai.analyze_with_mock`.
- Local mode never initializes Cognito, Bedrock, cloud DynamoDB or cloud SQS.
- AI extraction is validated with Pydantic models.
- `shared.priority.calculate_priority` deterministically calculates priority.
- `shared.allocation.calculate_allocation` deterministically calculates allocation quantities.
- Allocation explanations are local mock text only.
- Local administrator authentication uses Argon2 password hashes and signed JWTs with issuer, audience, email, role and expiration claims.
- CORS is configured for `http://localhost:5173`.
- The local map avoids remote tiles in local auth mode.

## Limitations

- Local request analysis uses FastAPI background tasks, not Amazon SQS. The production SQS architecture is unchanged.
- Local admin authentication is not Cognito. It is for local development only and uses the fake default `LOCAL_JWT_SECRET=local-dev-only-insecure-jwt-secret-change-me` from `docker-compose.local.yml`.
- Never use the fake local JWT secret in production or expose it through a `VITE_` variable. Production administrator routes remain protected by Cognito through the unchanged AWS SAM configuration.
- DynamoDB Local is useful for development behavior, but it is not a substitute for production DynamoDB operational testing.
- First local startup may need Docker images and npm/Python package installation if they are not already cached locally.
