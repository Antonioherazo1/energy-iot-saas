#ifndef TIME_MANAGER_H
#define TIME_MANAGER_H

#include <Arduino.h>

void iniciarTiempo();
String obtenerHora();
uint32_t obtenerUnixTime();
String formatearEpoch(uint32_t epoch);

#endif
