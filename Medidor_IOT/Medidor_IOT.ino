#include <WiFi.h>

#include "wifi_manager.h"
#include "mqtt_manager.h"
#include "sensor_rms.h"
#include "time_manager.h"

unsigned long lastMsg = 0;

// ======================
// DEVICE ID
// ======================

String deviceID;

// ======================

void setup() {

  Serial.begin(115200);

  // WIFI

  iniciarWiFi();

  // DEVICE ID

  deviceID =
    WiFi.macAddress();

  deviceID.replace(":", "");

  // MQTT

  iniciarMQTT();

  // SENSOR

  iniciarSensor();

  // TIME

  iniciarTiempo();

  Serial.println(
    "Sistema iniciado"
  );

  Serial.print(
    "Device ID: "
  );

  Serial.println(deviceID);
}
// ======================

void loop() {

  if (!client.connected()) {

    reconnectMQTT();
  }

  client.loop();

  unsigned long now =
    millis();

  if (
    now - lastMsg > 2000
  ) {

    lastMsg = now;

    // ======================
    // LEER 4 CANALES
    // ======================

    float corrientes[4];

    leerTodos(corrientes);

    // ======================
    // HORA
    // ======================

    String hora =
      obtenerHora();

    // ======================
    // JSON
    // ======================

    String payload = "{";

    payload +=
      "\"device_id\":\"";

    payload += deviceID;

    payload += "\",";
    
    payload +=
      "\"timestamp\":\"";

    payload += hora;

    payload += "\",";

    payload += "\"ch1\":";

    payload +=
      String(corrientes[0],2);

    payload += ",";

    payload += "\"ch2\":";

    payload +=
      String(corrientes[1],2);

    payload += ",";

    payload += "\"ch3\":";

    payload +=
      String(corrientes[2],2);

    payload += ",";

    payload += "\"ch4\":";

    payload +=
      String(corrientes[3],2);

    payload += "}";

    // ======================
    // SERIAL
    // ======================

    Serial.println(payload);

    // ======================
    // MQTT
    // ======================

    publicarMQTT(payload);
  }
}