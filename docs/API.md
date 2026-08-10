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

`latitude` and `longitude` are optional but must be sent together when supplied. If both are supplied, the stored coordinates are authoritative. If they are omitted, the asynchronous analysis worker attempts server-side address geocoding from the stored `address`, `district` and `city`; geocoding failure does not fail request analysis.

## Administrator
Requires `Authorization: Bearer <Cognito access token>`.

- `GET /admin/dashboard`
- `GET /admin/requests?priority=critical&limit=25`
- `PATCH /admin/requests/{requestId}/status`
- `POST /admin/allocations`

`POST /admin/allocations` body keeps the standard resource object and may include arbitrary active inventory rows as `customResources`:
```json
{
  "resources": {
    "waterLiters": 700,
    "tents": 20,
    "medicalStaff": 5,
    "blankets": 40
  },
  "customResources": [
    {
      "id": "fuel-1",
      "name": "Yakıt",
      "quantity": 250,
      "unit": "litre"
    }
  ]
}
```

Allocation responses keep legacy fixed fields and include a canonical per-city `resources` array:
```json
{
  "allocations": [
    {
      "city": "Hatay",
      "waterLiters": 500,
      "tents": 9,
      "medicalStaff": 4,
      "blankets": 22,
      "resources": [
        {
          "id": "water",
          "name": "Su",
          "quantity": 500,
          "unit": "litre",
          "systemKey": "waterLiters"
        },
        {
          "id": "fuel-1",
          "name": "Yakıt",
          "quantity": 161,
          "unit": "litre"
        }
      ]
    }
  ],
  "unallocated": {
    "waterLiters": 0,
    "tents": 0,
    "medicalStaff": 0,
    "blankets": 0,
    "resources": []
  },
  "rulesVersion": "1.1.0"
}
```
