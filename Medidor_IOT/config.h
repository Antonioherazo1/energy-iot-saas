#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

#define MQTT_MAX_PACKET_SIZE 512

// MQTT
inline const char* MQTT_SERVER = "thinc.site";
inline const int MQTT_PORT = 1883;
inline const char* MQTT_USER = "medidor";
inline const char* MQTT_PASS = "Mqt7!pEnergia2026";

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

// Buffer (LittleFS)
// Registro binario de 20 bytes: epoch(4) + ch1..ch4 float(16)
// Capacidad aproximada con particion LittleFS de 1MB: >50.000 registros (~29h a 2s)
// Con particion minima de 190KB: ~9.500 registros (~5h a 2s, ~13h a 5s)
#define BUFFER_FILE "/buffer.dat"
#define BUFFER_SENDING "/buffer_sending.dat"
#define BUFFER_MERGED "/buffer_merged.dat"
#define CONFIG_FILE "/config.json"
#define BUFFER_RECORD_SIZE 20

// Cuando no hay conexion, guardar como maximo una lectura por este periodo (ms).
// Reduce el uso de flash sin perder resolucion util para las graficas.
#define BUFFER_OFFLINE_MIN_MS 5000

struct Configuracion {
  float calibracion[4];
  float noiseFloor[4];
  bool canalesHabilitados[4];
  float alpha;
  int intervalo;
  float voltaje;

  Configuracion() {
    for (int i = 0; i < 4; i++) {
      calibracion[i] = CALIB_DEFAULT;
      noiseFloor[i] = NOISE_FLOOR_DEFAULT;
      canalesHabilitados[i] = true;
    }
    alpha = ALPHA_DEFAULT;
    intervalo = INTERVALO_DEFAULT;
    voltaje = VOLTAJE_DEFAULT;
  }
};

#endif
