#include <Arduino.h>
#include <time.h>
#include "time_manager.h"

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -5 * 3600;
const int daylightOffset_sec = 0;

static uint32_t bootMillis = 0;
static uint32_t lastValidEpoch = 0;

void iniciarTiempo() {
  bootMillis = millis();
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
}

String obtenerHora() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "2000-01-01 00:00:00";
  }
  char buf[20];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
  return String(buf);
}

uint32_t obtenerUnixTime() {
  time_t now;
  time(&now);
  if (now > 100000) {
    lastValidEpoch = (uint32_t)now;
    bootMillis = millis();
    return lastValidEpoch;
  }
  if (lastValidEpoch > 0) {
    return lastValidEpoch + (millis() - bootMillis) / 1000;
  }
  return 0;
}

bool tiempoValido() {
  time_t now;
  time(&now);
  return now > 100000 || lastValidEpoch > 0;
}
