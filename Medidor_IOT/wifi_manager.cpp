#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>

static unsigned long lastWifiCheck = 0;
static const unsigned long WIFI_CHECK_INTERVAL = 15000;
static int consecutiveFailures = 0;
static const int MAX_FAILURES_BEFORE_RESET = 20;

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

void verificarWiFi() {
  unsigned long ahora = millis();
  if (ahora - lastWifiCheck < WIFI_CHECK_INTERVAL) return;
  lastWifiCheck = ahora;

  if (WiFi.status() == WL_CONNECTED) {
    consecutiveFailures = 0;
    return;
  }

  consecutiveFailures++;
  Serial.print("WiFi caído (");
  Serial.print(consecutiveFailures);
  Serial.print("/");
  Serial.print(MAX_FAILURES_BEFORE_RESET);
  Serial.println(")");

  if (consecutiveFailures < 5) {
    return;
  }

  Serial.println("WiFi: intentando reconnect...");
  WiFi.disconnect();
  delay(100);
  WiFi.reconnect();
  delay(5000);

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi reconectado. IP: ");
    Serial.println(WiFi.localIP());
    consecutiveFailures = 0;
  } else if (consecutiveFailures >= MAX_FAILURES_BEFORE_RESET) {
    Serial.println("WiFi: demasiados fallos, reiniciando ESP32...");
    delay(1000);
    ESP.restart();
  }
}
