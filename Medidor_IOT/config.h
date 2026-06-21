#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// MQTT
inline const char* MQTT_SERVER = "thinc.site";
inline const int MQTT_PORT = 1883;

// Topics
inline const char* TOPIC_DATOS = "energia/datos";
inline const char* TOPIC_COMANDO = "energia/comando/";
inline const char* TOPIC_RESPUESTA = "energia/respuesta/";

// RMS defaults
inline const int MUESTRAS = 300;
inline const float ALPHA_DEFAULT = 0.2;
inline const float NOISE_FLOOR_DEFAULT = 0.05;
inline const float CALIB_DEFAULT = 1.0;
inline const float VOLTAJE_DEFAULT = 120.0;
inline const int INTERVALO_DEFAULT = 2000;

// Buffer
#define BUFFER_FILE "/buffer.dat"
#define BUFFER_SENDING "/buffer_sending.dat"
#define CONFIG_FILE "/config.json"
#define BUFFER_RECORD_SIZE 20

struct Configuracion {
  float calibracion[4];
  float noiseFloor[4];
  float alpha;
  int intervalo;
  float voltaje;

  Configuracion() {
    for (int i = 0; i < 4; i++) {
      calibracion[i] = CALIB_DEFAULT;
      noiseFloor[i] = NOISE_FLOOR_DEFAULT;
    }
    alpha = ALPHA_DEFAULT;
    intervalo = INTERVALO_DEFAULT;
    voltaje = VOLTAJE_DEFAULT;
  }
};

#endif
