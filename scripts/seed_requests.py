#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, random, time, urllib.error, urllib.request, uuid

SAMPLES = [
    {"city":"Hatay","district":"Antakya","address":"Atatürk Caddesi, No: 15, Antakya/Hatay","latitude":36.2021,"longitude":36.1604,"message":"25 kişiyiz. İçme suyumuz bitti. 2 yaralı var. Bebek maması gerekiyor."},
    {"city":"Adıyaman","district":"Merkez","address":"Gölbaşı Caddesi, Merkez/Adıyaman","latitude":37.7648,"longitude":38.2786,"message":"40 kişilik grubuz. Çadır ve battaniye gerekiyor. Aramızda yaşlılar var."},
    {"city":"Kahramanmaraş","district":"Onikişubat","address":"Trabzon Bulvarı, Onikişubat/Kahramanmaraş","latitude":37.5753,"longitude":36.9228,"message":"10 kişiyiz, 3 yaralı var. Doktor ve ambulans desteği gerekiyor."},
    {"city":"Malatya","district":"Battalgazi","address":"İnönü Caddesi, Battalgazi/Malatya","latitude":38.3552,"longitude":38.3095,"message":"Elektrik yok ve telefonlarımızın şarjı bitiyor. 15 kişiyiz."},
    {"city":"Gaziantep","district":"Nurdağı","address":"Cumhuriyet Mahallesi, Nurdağı/Gaziantep","latitude":37.1684,"longitude":36.7362,"message":"Enkaz altında mahsur kaldık. 6 kişiyiz, bir kişinin bilinci kapalı."}
]

def post(api_url: str, payload: dict[str, object]) -> None:
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/requests",
        data=json.dumps(payload, ensure_ascii=False).encode(), method="POST",
        headers={"Content-Type":"application/json","Idempotency-Key":str(uuid.uuid4())}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.code, exc.read().decode())

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    for _ in range(args.count):
        post(args.api_url, random.choice(SAMPLES)); time.sleep(.15)

if __name__ == "__main__": main()
