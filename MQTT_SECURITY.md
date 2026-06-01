# MQTT Device Security

Cada dispositivo tiene una clave secreta (`device_key`). El backend guarda solo un hash de esa clave.

## Topic

```text
devices/{device_code}/telemetry
```

Ejemplo:

```text
devices/esp32-main-001/telemetry
```

## Payload MQTT

El ESP32 debe incluir `device_key`:

```json
{
  "device_key": "CLAVE_DEL_DISPOSITIVO",
  "voltage": 121.2,
  "current": 3.8,
  "power": 460.5,
  "energy_kwh": 12.9,
  "frequency": 60,
  "power_factor": 0.97
}
```

## Prueba desde EC2

```bash
docker exec mosquitto mosquitto_pub \
  -h 127.0.0.1 \
  -p 1883 \
  -t 'devices/esp32-main-001/telemetry' \
  -m '{"device_key":"CLAVE_DEL_DISPOSITIVO","voltage":121.2,"current":3.8,"power":460.5,"energy_kwh":12.9,"frequency":60,"power_factor":0.97}'
```

## Compatibilidad

Los dispositivos creados antes de esta mejora pueden tener `device_key_hash = NULL`. En ese caso se permite telemetria sin clave para no romper dispositivos existentes.

Para exigir clave, rota credenciales del dispositivo o crea uno nuevo desde la UI.

