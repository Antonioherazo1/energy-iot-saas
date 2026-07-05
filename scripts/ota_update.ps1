param(
  [string]$Bin = "Medidor_IOT/build/esp32.esp32.esp32/Medidor_IOT.ino.bin",
  [string]$Version = "2.1-test",
  [string]$Email = "admin@thinc.site",
  [string]$Pass = "cambiame"
)

$ErrorActionPreference = "Stop"
$api = "https://thinc.site/api/v1"

Write-Host "==> Login..."
$body = @{email = $Email; password = $Pass} | ConvertTo-Json
$headers = @{"Content-Type" = "application/json"}
$resp = Invoke-RestMethod -Uri "$api/auth/login" -Method Post -Body $body -ContentType "application/json"
$token = $resp.access_token

Write-Host "==> Subiendo firmware v$Version..."
$form = @{
  version = $Version
  file = Get-Item -LiteralPath $Bin
}
$resp = Invoke-RestMethod -Uri "$api/firmware/upload" -Method Post -Headers @{Authorization = "Bearer $token"} -Form $form
$fw_id = $resp.firmware.id
Write-Host "  Firmware ID: $fw_id"

Write-Host "==> Enviando OTA a TODOS los dispositivos..."
$form2 = @{firmware_id = $fw_id}
$resp = Invoke-RestMethod -Uri "$api/firmware/ota/all" -Method Post -Headers @{Authorization = "Bearer $token"} -Form $form2
Write-Host "  $resp"
