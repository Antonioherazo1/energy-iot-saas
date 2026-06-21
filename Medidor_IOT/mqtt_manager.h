#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <Arduino.h>
#include <PubSubClient.h>
#include "config.h"

extern PubSubClient client;
extern Configuracion configApp;
extern String deviceID;

void iniciarMQTT();
bool conectarMQTT();
void publicarMQTT(const String& payload);
void publicarRespuestaMQTT(const String& payload);
void loopMQTT();

#endif
