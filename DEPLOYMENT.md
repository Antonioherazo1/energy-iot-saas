# DEPLOYMENT — Energy IoT SaaS

> Documentación operativa del despliegue. Si entras a administrar este servidor con permisos,
> empieza por aquí. Última actualización: 2026-08-22.

---

## 1. Arquitectura general

```
[ESP32 medidor x4 canales]                    [Usuario (navegador)]
   |  MQTT 1883 (telemetría + comandos)          |  HTTPS 443
   v                                             v
[thinc.site - EC2 Ubuntu]
   ├── nginx (sistema) ──────────────► /var/www/thinc  (frontend React estático)
   │       ├── /api/v1/  → proxy → localhost:8000 (API)
   │       ├── /ws/      → proxy → WebSocket dashboard
   │       ├── /firmware/→ proxy → descargas OTA (.bin)
   │       └── /grafana/ → proxy → localhost:3000
   ├── Docker: energy_iot_api      (FastAPI + paho-mqtt, puerto 8000)
   ├── Docker: energy_iot_postgres (Postgres 16 + pg_stat_statements, 5432 solo interno*)
   └── Docker: energy_iot_mosquitto(broker MQTT, 1883 ABIERTO al mundo ⚠)

* El security group de AWS bloquea 5432 desde internet. Los puertos 1883 y 8000 SÍ están abiertos.
```

Flujo de datos: el ESP32 publica lecturas RMS en `energia/datos` → el API las ingesta a
`raw_telemetry` → un agregador las consolida en `telemetry` → el dashboard consulta la API
(REST) y recibe tiempo real por WebSocket.

## 2. Servidor

| Qué | Dónde / valor |
|---|---|
| Host | `ubuntu@thinc.site` (IP 3.150.74.86) |
| Llave SSH | `G:\Mi unidad\IOT\iot-key2.pem` (Windows local) |
| Proyecto live | `/home/ubuntu/energy-iot-saas` (repo git, rama `main`) |
| Stack Docker | compose en `backend/docker-compose.yml` |
| Frontend estático | `/var/www/thinc` ← **root real** |
| Config nginx LIVE | `/etc/nginx/sites-available/thinc` ← **no es la del repo** |
| Backups locales | `/home/ubuntu/backups/energy-iot/auto` |
| Script backup | `/usr/local/bin/energy_backup.sh` (cron 03:15 UTC diario) |

⚠ **Otros proyectos conviven en esta instancia — NO tocarlos:**
`safekid-backend` (contenedor `safekid-api`), `garage_mosquitto`,
nginx site `garaje.thinc.site`, `/opt/Control-Garaje`.

⚠ **Carpetas/configs muertas identificadas** (candidatas a limpieza, aún no borradas):
`~/energia-iot`, `~/backend`, `~/frontend` (180MB), `~/awscliv2.zip`,
nginx `sites-available/thinc.site` (huérfana) y los `.bak.*` generados hoy.

## 3. Secretos (nunca commitear)

Todos viven en `/home/ubuntu/energy-iot-saas/backend/.env`:

| Variable | Estado |
|---|---|
| `POSTGRES_PASSWORD` | Password fuerte (cambiado el 2026-08-22; antes era `change_me`) |
| `JWT_SECRET_KEY` | Revisar fortaleza; rotación invalida sesiones |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | Aún sin uso real; se activarán con el hardening MQTT |

El `docker-compose.yml` interpola `${POSTGRES_PASSWORD}` desde ese `.env`.

## 4. Backend (FastAPI)

- Puerto 8000, prefijo `/api/v1`. Salud: `GET /api/v1/health`.
- Auth JWT: access token 24h + refresh token 30 días con rotación (hash en tabla `refresh_tokens`).
- Rate limiting propio (`app/services/rate_limiter.py`, sin dependencias nuevas):
  login/register limitados a 10 intentos/email y 40/IP cada 5 min (ventana deslizante en memoria).
  Lee `X-Forwarded-For` (nginx lo envía).
- `pg_stat_statements` activo vía `command:` en compose. Query útil:
  ```sql
  SELECT calls, mean_exec_time::int AS ms, left(query,90)
  FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
  ```

## 5. Frontend (React + Vite)

- Build: `npm run build` → `dist/`.
- Deploy = copiar contenido de `dist` a `/var/www/thinc` (assets/, index.html, icons/).
- Caché nginx: `/assets/*` → `public, max-age=2592000, immutable` (30 días; filenames hasheados);
  `index.html` → `no-cache`. Esto arregló la lentitud de carga.
- Sesión: tokens en **localStorage** (sobrevive cerrar navegador). Al expirar el access token,
  el interceptor hace refresh automático y reintenta; sesión efectiva ~30 días por dispositivo.

## 6. MQTT

Topics:
- `energia/datos` — telemetría (ESP32 publica)
- `energia/comando/{MAC}` — comandos al dispositivo (backend publica)
- `energia/respuesta/{MAC}` — respuestas del dispositivo

Estado actual (2026-08-22): broker con `allow_anonymous true` — **inseguro**, cualquiera puede
publicar comandos o telemetría falsa. Hardening planificado en dos fases:

1. Firmware v2.6 (fuente lista en repo, **pendiente compilar/OTA**) que conecta con
   `MQTT_USER`/`MQTT_PASS` definidos en `Medidor_IOT/config.h`.
2. Cuando el device confirme `"fw":"2.6"`: crear passwd de mosquitto
   (`mosquitto_passwd -c ...`), montarlo en el contenedor, activar `password_file`,
   poner las mismas credenciales en `backend/.env` y reiniciar mosquitto + api.

**No activar auth del broker antes de confirmar que el firmware con credenciales corre en todos los medidores.**

## 7. Firmware ESP32 (`Medidor_IOT/`)

| Versión | Estado | Notas |
|---|---|---|
| 2.4 | anterior | — |
| 2.5 | **corriendo en producción** (device `3C8A1F50727C`) | Buffer offline 10h+, drenado rápido ~45 reg/s, decimación 1 lectura/5s offline, recuperación de envío interrumpido al boot, fs_total/fs_free en status |
| 2.6 | fuente lista, sin compilar | Agrega auth MQTT (`client.connect(id, MQTT_USER, MQTT_PASS)`) |

Compilar (arduino-cli):
```powershell
& "C:\Users\Anton\AppData\Local\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" `
  compile --fqbn esp32:esp32:esp32 `
  --build-path "C:\Users\Anton\AppData\Local\Temp\esp32-build" `
  "C:\...\Medidor_IOT"
```
El bin queda en `<build-path>/esp32.esp32.esp32/Medidor_IOT.ino.bin` (~1.26MB).

OTA: subir el bin al volumen `backend_firmware_data`
(`/var/lib/docker/volumes/backend_firmware_data/_data/`), registrarlo en tabla `firmware`
(vía API/dashboard), luego comando OTA por `energia/comando/{MAC}`. El ESP32 descarga de
`http://thinc.site/firmware/medidor_X.bin` (HTTP sin redirect, el ESP32 no sigue redirects),
responde en `energia/respuesta/{MAC}` con `descargando` → `completado`, reinicia y reconecta.

Nota: con señal débil (RSSI ≈ -80 dBm) la OTA puede tardar minutos en completarse y el device
desaparece del broker durante la escritura flash — no entrar en pánico antes de 5–10 min.

Buffer offline: LittleFS `buffer.dat` (registros binarios de 20B). Offline guarda máx 1 lectura/5s.
Al reconectar drena a ~45 reg/s en lotes MQTT. Si se corta a mitad de envío, al boot fusiona
`buffer_sending.dat` de vuelta para no perder registros.

## 8. Base de datos

Contenedor `energy_iot_postgres` (postgres:16-alpine), DB `energy_iot`, usuario `energy_iot`.

Tablas principales: `telemetry` (~350k filas, 80MB — crece sin límite, considerar retención a futuro),
`raw_telemetry` (se consolida rápido), `devices`, `device_channels`, `firmware`,
`refresh_tokens` (purga nocturna automática), `organization_settings`, `users`, `organizations`.

Acceso rápido:
```bash
sudo docker exec energy_iot_postgres psql -U energy_iot -d energy_iot -c "SELECT ..."
```

## 9. Backups

- **Cron**: diario 03:15 UTC (crontab de ubuntu): `/usr/local/bin/energy_backup.sh`
- **Qué hace**: dump custom-format (`pg_dump -Fc`) → verificación de integridad
  (`pg_restore --list`) → subida a S3 → purga de `refresh_tokens` expirados → retención local 7 dumps.
- **S3**: `s3://energy-iot-backups-tono/energy-iot/daily/`, lifecycle borra a los 30 días.
  Credenciales: rol IAM `EC2-S3-Backup-Role` adjunto a la instancia (sin llaves estáticas).
- **Logs**: `/home/ubuntu/backups/energy-iot/backup.log`

**Restore** (probado conceptualmente, hacer drill periódico):
```bash
# copiar dump al contenedor y restaurar
sudo docker cp energy_iot_XXXX.dump energy_iot_postgres:/tmp/r.dump
sudo docker exec energy_iot_postgres pg_restore -U energy_iot -d energy_iot --clean --if-exists /tmp/r.dump
```

Backup manual adicional descargado al PC local: `Documents\Codex\backups-energy-iot\2026-08-22\`.

## 10. CI/CD

Workflow `.github/workflows/deploy.yml` — disparo **manual** (workflow_dispatch) con elección
frontend/backend/ambos. Ejecuta por SSH exactamente los mismos pasos del deploy manual.

Secrets requeridos en GitHub → Settings → Secrets and variables → Actions:
- `EC2_HOST`: `thinc.site`
- `EC2_SSH_KEY`: contenido completo de la PEM

## 11. Deploy manual (procedimiento canónico)

**Frontend**
```bash
cd ~/energy-iot-saas && sudo git pull origin main
cd frontend && [ -d node_modules ] || sudo npm ci --silent
sudo npm run build --silent
sudo rm -rf /var/www/thinc/assets /var/www/thinc/index.html
sudo cp -r dist/assets /var/www/thinc/assets
sudo cp -f dist/index.html /var/www/thinc/index.html
```

**Backend**
```bash
cd ~/energy-iot-saas && sudo git pull origin main
cd backend && sudo docker compose build api && sudo docker compose up -d api
curl http://localhost:8000/api/v1/health
```

## 12. Tareas pendientes

1. **Alertas por correo de dispositivo offline** — sin implementar. Diseño propuesto:
   task asíncrona en FastAPI que cada 5 min compara `max(recorded_at)` vs now;
   umbral 15 min, cooldown 6h; email vía smtplib (stdlib, Gmail app-password).
   Falta SMTP host/user/pass del dueño.
2. **Hardening MQTT** — fases 1 y 2 de la sección 6 (v2.6 compilada + OTA + switch broker).
3. **GitHub secrets** para el workflow (los agrega el dueño).
4. **Limpieza de carpetas muertas** — listar arriba; borrar solo tras confirmación.
5. **Cerrar puertos 8000 y 1883? no—1883 necesario** — cerrar 8000 en el security group
   (el API debe llegarle solo vía nginx). 1883 se queda abierto pero con auth tras hardening.
6. **WiFi del medidor** (RSSI -80 dBm): repetidor/router más cerca — causa raíz de los gaps.
7. **Largo plazo**: retención/particionado de `telemetry`; revisar fortaleza de `JWT_SECRET_KEY`.

## 13. Gotchas conocidos

- **PowerShell → SSH**: los heredocs multilínea llegan con CRLF y rompen bash. Patrón seguro:
  escribir script local → `scp` → `ssh "sed -i 's/\r//' script && bash script"`.
- PowerShell no soporta `< file` como stdin de ssh.
- Editar UTF-8 sin BOM desde PowerShell: `[System.IO.File]::ReadAllText/WriteAllText` con
  `UTF8Encoding($false)` (Get-Content/Set-Content corrompe acentos).
- La config nginx del repo (`frontend/nginx.conf`) NO es la que corre; la live es
  `/etc/nginx/sites-available/thinc`. Mantener ambas sincronizadas o eliminar la del repo.
- El root web es `/var/www/thinc` — existe también `/var/www/thinc.site` (muerto).
- Tras cambiar tokens de sessionStorage a localStorage (2026-08-22) cada usuario debió iniciar
  sesión una última vez; desde entonces persiste ~30 días.
