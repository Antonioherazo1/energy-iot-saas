# Medidor IOT — ESP32 + ADS1115

Firmware para ESP32 con ADC ADS1115 (4 canales), medición RMS de corriente, buffer en LittleFS ante pérdida de conexión, y control vía MQTT.

## Topics MQTT

| Dirección | Topic | Formato |
|---|---|---|
| Publica datos | `energia/datos` | JSON |
| Recibe comandos | `energia/comando/<deviceID>` | JSON |
| Responde comandos | `energia/respuesta/<deviceID>` | JSON |

El `<deviceID>` es la MAC del ESP32 sin `:` (ej: `AC67B223B3C1`).

## Formato de datos

Cada 2 segundos (por defecto) publica en `energia/datos`:

```json
{
  "device_id": "AC67B223B3C1",
  "timestamp": "2026-06-21 14:30:00",
  "ch1": 1.23,
  "ch2": 0.45,
  "ch3": 2.10,
  "ch4": 0.00
}
```

## Comandos MQTT

Envía un JSON a `energia/comando/<deviceID>`. El ESP32 responde en `energia/respuesta/<deviceID>`.

### 1. Estado del dispositivo

**Enviar:**
```json
{"cmd": "status"}
```
**Respuesta:**
```json
{
  "cmd": "status",
  "uptime": 3600,
  "rssi": -65,
  "buffer": 150,
  "firmware": "2.0",
  "settings": {
    "alpha": 0.2,
    "intervalo": 2000,
    "voltaje": 120.0,
    "calibracion": [1.0, 1.0, 1.0, 1.0],
    "noiseFloor": [0.05, 0.05, 0.05, 0.05],
    "canales": [true, true, true, true]
  }
}
```
- `uptime`: segundos desde el arranque
- `rssi`: intensidad de señal WiFi
- `buffer`: número de lecturas almacenadas (en espera de enviar)
- `firmware`: versión del firmware

### 2. Calibración por canal

Ajusta el factor multiplicador de la corriente RMS para un canal específico.

**Enviar:**
```json
{"cmd": "calibrar", "canal": 0, "valor": 1.05}
```
- `canal`: 0 a 3
- `valor`: factor de calibración (1.0 = sin ajuste)

**Respuesta:** `{"cmd":"calibrar","ok":true,"canal":0,"valor":1.05}`

### 3. Piso de ruido por canal

Debajo de este umbral la corriente se reporta como 0.

**Enviar:**
```json
{"cmd": "noise_floor", "canal": 0, "valor": 0.03}
```
- `valor`: amperios mínimos (default: 0.05)

### 4. Alpha del filtro EMA

Constante del filtro exponencial (0 < alpha ≤ 1). Valores bajos = más suavizado.

**Enviar:**
```json
{"cmd": "alpha", "valor": 0.15}
```

### 5. Intervalo de lectura

Tiempo entre lecturas en milisegundos.

**Enviar:**
```json
{"cmd": "intervalo", "valor": 5000}
```
- Rango válido: 200 a 60000 ms

### 6. Voltaje nominal

Para cálculos de potencia (solo almacenado, no usado actualmente en el firmware).

**Enviar:**
```json
{"cmd": "voltaje", "valor": 110}
```

### 7. Habilitar / deshabilitar canal

Activa o desactiva un canal. Un canal deshabilitado siempre reporta 0.0A.

**Enviar:**
```json
{"cmd": "habilitar_canal", "canal": 1, "habilitado": false}
```
- `canal`: 0 a 3
- `habilitado`: `true` o `false`

### 8. Limpiar buffer

Descarta todas las lecturas almacenadas en LittleFS.

**Enviar:**
```json
{"cmd": "limpiar_buffer"}
```

### 9. Reiniciar ESP32

Reinicia el microcontrolador.

**Enviar:**
```json
{"cmd": "reiniciar"}
```

## Buffer de datos (LittleFS)

Cuando el ESP32 pierde conexión WiFi o MQTT, almacena las lecturas en LittleFS (partición de ~1.5 MB).

### Formato binario

Cada lectura ocupa 20 bytes:

```
[uint32 epoch][float ch1][float ch2][float ch3][float ch4]
  bytes 0-3     bytes 4-7  bytes 8-11 bytes 12-15 bytes 16-19
```

### Capacidad

| Formato | Tamaño | Lecturas | Horas (c/2s) |
|---|---|---|---|
| Binario | 20 B/lectura | ~75.000 | ~41 h |

### Comportamiento en reconexión

1. Cuando se pierde conexión: las lecturas se acumulan en `buffer.dat`
2. Al reconectar: se renombra `buffer.dat` → `buffer_sending.dat` y se crea un `buffer.dat` nuevo
3. Cada ciclo de lectura se envían hasta **15 registros** del archivo de envío
4. Las lecturas nuevas durante el drenaje se guardan en el nuevo `buffer.dat`
5. Cuando `buffer_sending.dat` se vacía, se elimina y el ciclo continúa con el siguiente lote

### Límite de espacio

Si la partición LittleFS está casi llena, las nuevas lecturas se descartan (con mensaje en serial) para evitar corrupción.

## Configuración persistente

Todas las configuraciones se guardan en `/config.json` en LittleFS y se restauran al arrancar:

- Calibración por canal
- Piso de ruido por canal
- Canales habilitados
- Alpha del filtro
- Intervalo de lectura
- Voltaje nominal

## Parámetros de compilación (config.h)

| Constante | Default | Descripción |
|---|---|---|
| `MUESTRAS` | 300 | Muestras ADC para cálculo RMS |
| `ALPHA_DEFAULT` | 0.2 | Suavizado del filtro EMA |
| `NOISE_FLOOR_DEFAULT` | 0.05 | Umbral de ruido (A) |
| `CALIB_DEFAULT` | 1.0 | Factor de calibración |
| `VOLTAJE_DEFAULT` | 120.0 | Voltaje nominal |
| `INTERVALO_DEFAULT` | 2000 | Periodo de lectura (ms) |

## Dependencias (Arduino Libraries)

- `WiFiManager` — configuración WiFi con captive portal
- `PubSubClient` — cliente MQTT
- `Adafruit ADS1X15` — ADC ADS1115
- `LittleFS` — sistema de archivos flash
