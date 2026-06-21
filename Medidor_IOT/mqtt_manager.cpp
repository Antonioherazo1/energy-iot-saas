#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

#include "mqtt_manager.h"
#include "config.h"

WiFiClient espClient;

PubSubClient client(espClient);

void iniciarMQTT() {

  client.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );
}

void reconnectMQTT() {

  while (!client.connected()) {

    Serial.print("Conectando MQTT...");

    if (client.connect("ESP32Energia")) {

      Serial.println("conectado");

    } else {

      Serial.print("error=");

      Serial.println(client.state());

      delay(2000);
    }
  }
}

void publicarMQTT(String payload) {

  client.publish(
    TOPIC_DATOS,
    payload.c_str()
  );
}