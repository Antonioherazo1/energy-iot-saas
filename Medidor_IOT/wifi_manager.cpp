#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>

void iniciarWiFi() {

  WiFiManager wm;

  bool res;

  res = wm.autoConnect("MedidorEnergia");

  if(!res) {

    Serial.println("No conectado");

    ESP.restart();

  } else {

    Serial.println("WiFi conectado");
  }
}