#!/usr/bin/env python3
import sys, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = "https://thinc.site/api/v1"
email = sys.argv[1] if len(sys.argv) > 1 else "admin@thinc.site"
password = sys.argv[2] if len(sys.argv) > 2 else "cambiame"

# Login
body = json.dumps({"email": email, "password": password}).encode()
r = urlopen(f"{API}/auth/login", data=body, headers={"Content-Type": "application/json"})
token = json.loads(r.read())["access_token"]

# Get latest raw telemetry
req = Request(f"{API}/telemetry/raw/latest?limit=5", headers={"Authorization": f"Bearer {token}"})
r = urlopen(req)
data = json.loads(r.read())

if isinstance(data, list) and len(data) > 0:
    payload = data[0].get("payload", "")
    if "lula" in payload:
        print("✅ OTA VERIFICADO - 'lula' detectado en los datos!")
        print(f"Último payload: {payload[:200]}")
    else:
        print("⏳ Esperando... el ESP32 aún no se actualizó")
        print(f"Último payload: {payload[:200]}")
else:
    print("No hay datos de telemetría aún")
