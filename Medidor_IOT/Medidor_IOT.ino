#include <WiFi.h>
#include <LittleFS.h>

#include "wifi_manager.h"
#include "mqtt_manager.h"
#include "sensor_rms.h"
#include "time_manager.h"
#include "storage_manager.h"
#include "config.h"

String deviceID;
unsigned long ultimaLectura = 0;
static const int MAX_ENVIO_BUFFER = 15;

String safeFloat(float v) {
  if (isnan(v) || isinf(v)) return "0.00";
  return String(v, 2);
}

void setup() {
  Serial.begin(115200);

  iniciarWiFi();
  deviceID = WiFi.macAddress();
  deviceID.replace(":", "");

  iniciarStorage();
  cargarConfig(configApp);

  iniciarMQTT();
  iniciarSensor();
  iniciarTiempo();

  Serial.println("Sistema iniciado v2.1");
  Serial.print("Device ID: ");
  Serial.println(deviceID);
}

void enviarBatch() {
  uint8_t batch[BUFFER_RECORD_SIZE * MAX_ENVIO_BUFFER];
  int count = leerBufferBatch(batch, MAX_ENVIO_BUFFER);
  for (int i = 0; i < count; i++) {
    uint8_t* rec = batch + i * BUFFER_RECORD_SIZE;
    uint32_t recEpoch = ((uint32_t)rec[0] << 24) | ((uint32_t)rec[1] << 16) | ((uint32_t)rec[2] << 8) | rec[3];
    float ch1, ch2, ch3, ch4;
    memcpy(&ch1, rec + 4, 4);
    memcpy(&ch2, rec + 8, 4);
    memcpy(&ch3, rec + 12, 4);
    memcpy(&ch4, rec + 16, 4);
    String hora = formatearEpoch(recEpoch);
    String payload = "{";
    payload += "\"device_id\":\"";
    payload += deviceID;
    payload += "\",\"timestamp\":\"";
    payload += hora;
    payload += "\",\"ch1\":";
    payload += safeFloat(ch1);
    payload += ",\"ch2\":";
    payload += safeFloat(ch2);
    payload += ",\"ch3\":";
    payload += safeFloat(ch3);
    payload += ",\"ch4\":";
    payload += safeFloat(ch4);
    payload += "}";
    publicarMQTT(payload);
    delay(50);
  }
  if (count > 0) {
    Serial.print("Buffer enviados: ");
    Serial.println(count);
  }
}

void loop() {
  verificarWiFi();
  conectarMQTT();
  loopMQTT();

  unsigned long ahora = millis();
  if (ahora - ultimaLectura < (unsigned long)configApp.intervalo) return;
  ultimaLectura = ahora;

  float corrientes[4];
  leerTodos(corrientes);

  bool conectado = client.connected();
  uint32_t epoch = obtenerUnixTime();
  bool tsValido = tiempoValido();

  if (conectado) {
    if (contarRegistrosPendientes() > 0) {
      if (!hayEnvioPendiente()) {
        iniciarEnvioBuffer();
      }
      if (hayEnvioPendiente()) {
        enviarBatch();
        return;
      }
    }

    if (tsValido) {
      String hora = formatearEpoch(epoch);
      String payload = "{";
      payload += "\"device_id\":\"";
      payload += deviceID;
      payload += "\",";
      payload += "\"timestamp\":\"";
      payload += hora;
      payload += "\",";
      payload += "\"ch1\":";
      payload += safeFloat(corrientes[0]);
      payload += ",";
      payload += "\"ch2\":";
      payload += safeFloat(corrientes[1]);
      payload += ",";
      payload += "\"ch3\":";
      payload += safeFloat(corrientes[2]);
      payload += ",";
      payload += "\"ch4\":";
      payload += safeFloat(corrientes[3]);
      payload += "}";

      publicarMQTT(payload);
    }
  } else if (tsValido) {
    guardarLectura(epoch, corrientes[0], corrientes[1], corrientes[2], corrientes[3]);
    Serial.print("Sin conexion. Buffer: ");
    Serial.println(contarRegistrosPendientes());
  }
}
