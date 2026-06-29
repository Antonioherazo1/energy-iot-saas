#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>

void iniciarWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);

  WiFiManager wm;
  wm.setConnectTimeout(10);
  wm.setConfigPortalTimeout(60);
  wm.setSaveParamsCallback([] {
    Serial.println("WiFi config guardada en NVS");
  });

  if (wm.autoConnect("MedidorEnergia")) {
    Serial.print("WiFi conectado. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi NO disponible - modo sin conexion");
  }
}