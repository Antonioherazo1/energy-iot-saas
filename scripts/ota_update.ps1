param(
  [string]$Bin = "Medidor_IOT/build/esp32.esp32.esp32/Medidor_IOT.ino.bin",
  [string]$Version = "2.1-test",
  [string]$Email = "admin@thinc.site",
  [string]$Pass = "cambiame"
)

$ErrorActionPreference = "Stop"
$api = "https://thinc.site/api/v1"

Write-Host "==> Login..."
$body = @{email=$Email; password=$Pass} | ConvertTo-Json
$token = curl.exe -s "$api/auth/login" -H "Content-Type: application/json" -d $body | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

Write-Host "==> Subiendo firmware v$Version..."
$res = curl.exe -s "$api/firmware/upload" -H "Authorization: Bearer $token" -F "version=$Version" -F "file=@$Bin"
$fw_id = $res | python -c "import sys,json; print(json.load(sys.stdin)['firmware']['id'])"
Write-Host "  Firmware ID: $fw_id"

Write-Host "==> Enviando OTA a TODOS los dispositivos..."
$res = curl.exe -s "$api/firmware/ota/all" -H "Authorization: Bearer $token" -F "firmware_id=$fw_id"
Write-Host "  $res"
