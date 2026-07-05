#!/usr/bin/env bash
set -euo pipefail

# Uso: bash scripts/ota_update.sh <firmware.bin> <version> [email] [password]
# Ej:   bash scripts/ota_update.sh Medidor_IOT/build/esp32.esp32.esp32/Medidor_IOT.ino.bin 2.1 admin@example.com mi_password

API="https://thinc.site/api/v1"
BIN="$1"
VERSION="$2"
EMAIL="${3:-admin@thinc.site}"
PASS="${4:-cambiame}"

if [ ! -f "$BIN" ]; then
  echo "Archivo no encontrado: $BIN" >&2
  exit 1
fi

echo "==> Login..."
PY="python"
# Force full path on Windows (bypass Microsoft Store alias)
for p in "/c/Python313/python.exe" "/c/Python312/python.exe" "/c/Python311/python.exe"; do
  [ -x "$p" ] && { PY="$p"; break; }
done
# Fallback: try python3, then python
if ! "$PY" -c "" 2>/dev/null; then
  PY="python3"
  if ! "$PY" -c "" 2>/dev/null; then
    PY="python"
    if ! "$PY" -c "" 2>/dev/null; then
      echo "ERROR: Python no encontrado. Instalalo o ajusta PY en el script." >&2
      exit 1
    fi
  fi
fi
TOKEN=$(curl -sf "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | $PY -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "==> Subiendo firmware v$VERSION..."
RES=$(curl -sf "$API/firmware/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "version=$VERSION" \
  -F "file=@$BIN")
FW_ID=$(echo "$RES" | $PY -c "import sys,json; print(json.load(sys.stdin)['firmware']['id'])")
echo "  Firmware ID: $FW_ID"

echo "==> Enviando OTA a TODOS los dispositivos..."
RES=$(curl -sf "$API/firmware/ota/all" \
  -H "Authorization: Bearer $TOKEN" \
  -F "firmware_id=$FW_ID")
echo "  $RES"

echo ""
echo "Dispositivos actualizandose. Verificar con:"
echo "  curl -sH 'Authorization: Bearer $TOKEN' $API/esp32/diagnostic | $PY -m json.tool"
