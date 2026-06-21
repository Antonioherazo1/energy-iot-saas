#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <PubSubClient.h>

extern PubSubClient client;

void iniciarMQTT();

void reconnectMQTT();

void publicarMQTT(String payload);

#endif