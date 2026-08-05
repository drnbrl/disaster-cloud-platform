# API

Base path: `/v1`

## Public
- `POST /requests`: stores a request and returns `202`.
- `GET /requests/{requestId}`: returns safe public status.

`POST /requests` body:
```json
{
  "city": "Hatay",
  "district": "Antakya",
  "address": "Atatürk Caddesi, No: 15, Antakya/Hatay",
  "latitude": 36.2021,
  "longitude": 36.1604,
  "message": "25 kişiyiz. İçme suyumuz bitti. 2 yaralı var."
}
```

## Administrator
Requires `Authorization: Bearer <Cognito access token>`.

- `GET /admin/dashboard`
- `GET /admin/requests?priority=critical&limit=25`
- `PATCH /admin/requests/{requestId}/status`
- `POST /admin/allocations`
