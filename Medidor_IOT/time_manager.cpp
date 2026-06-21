#include <Arduino.h>
#include <time.h>

#include "time_manager.h"

const char* ntpServer =
"pool.ntp.org";

const long gmtOffset_sec =
-5 * 3600;

const int daylightOffset_sec =
0;

void iniciarTiempo() {

  configTime(
    gmtOffset_sec,
    daylightOffset_sec,
    ntpServer
  );
}

String obtenerHora() {

  struct tm timeinfo;

  if (!getLocalTime(&timeinfo)) {

    return "00:00:00";
  }

  char hora[9];

  strftime(
    hora,
    sizeof(hora),
    "%H:%M:%S",
    &timeinfo
  );

  return String(hora);
}