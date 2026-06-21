#include <Arduino.h>
#include <time.h>
#include "time_manager.h"

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -5 * 3600;
const int daylightOffset_sec = 0;

void iniciarTiempo() {
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
  return (uint32_t)now;
}

String formatearEpoch(uint32_t epoch) {
  time_t t = (time_t)epoch;
  struct tm* timeinfo = localtime(&t);
  if (!timeinfo) {
    return "2000-01-01 00:00:00";
  }
  char buf[20];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", timeinfo);
  return String(buf);
}
