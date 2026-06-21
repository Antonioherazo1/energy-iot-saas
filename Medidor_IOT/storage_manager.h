#ifndef STORAGE_MANAGER_H
#define STORAGE_MANAGER_H

#include <Arduino.h>
#include "config.h"

bool iniciarStorage();
bool guardarLectura(uint32_t epoch, float ch1, float ch2, float ch3, float ch4);
int leerTodasLecturas(uint8_t* buffer, int maxBytes);
int contarRegistrosPendientes();
void limpiarBuffer();

bool iniciarEnvioBuffer();
int leerBufferBatch(uint8_t* buffer, int maxRecords);
bool hayEnvioPendiente();

bool guardarConfig(const Configuracion& cfg);
bool cargarConfig(Configuracion& cfg);

#endif
