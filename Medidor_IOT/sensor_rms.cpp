#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include "sensor_rms.h"
#include "config.h"
#include "mqtt_manager.h"

Adafruit_ADS1115 ads;
float corrienteFiltrada[4] = {0, 0, 0, 0};

void iniciarSensor() {
  if (!ads.begin()) {
    Serial.println("ADS1115 no detectado");
    while (1);
  }
  ads.setGain(GAIN_ONE);
  ads.setDataRate(RATE_ADS1115_860SPS);
}

float leerCanal(int canal) {
  float voltajes[MUESTRAS];
  double sumaOffset = 0;

  for (int i = 0; i < MUESTRAS; i++) {
    int16_t adc = ads.readADC_SingleEnded(canal);
    float voltage = adc * 0.125 / 1000.0;
    voltajes[i] = voltage;
    sumaOffset += voltage;
  }

  float offset = sumaOffset / MUESTRAS;
  double sumaCuadrados = 0;

  for (int i = 0; i < MUESTRAS; i++) {
    float ac = voltajes[i] - offset;
    sumaCuadrados += ac * ac;
  }

  float vrms = sqrt(sumaCuadrados / MUESTRAS);
  float irms = vrms * 100.0 * configApp.calibracion[canal];
  return irms;
}

void leerTodos(float* salida) {
  for (int i = 0; i < 4; i++) {
    if (!configApp.canalesHabilitados[i]) {
      corrienteFiltrada[i] = 0;
      salida[i] = 0;
      continue;
    }
    float irms = leerCanal(i);
    corrienteFiltrada[i] = configApp.alpha * irms + (1 - configApp.alpha) * corrienteFiltrada[i];

    if (corrienteFiltrada[i] < configApp.noiseFloor[i]) {
      corrienteFiltrada[i] = 0;
    }

    salida[i] = corrienteFiltrada[i];
  }
}
