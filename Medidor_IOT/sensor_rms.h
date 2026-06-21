#ifndef SENSOR_RMS_H
#define SENSOR_RMS_H

#include <Arduino.h>

void iniciarSensor();
float leerCanal(int canal);
void leerTodos(float* salida);

#endif
