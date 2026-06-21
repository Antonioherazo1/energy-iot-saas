#ifndef CONFIG_H
#define CONFIG_H

// ======================
// MQTT
// ======================

inline const char* MQTT_SERVER =
"thinc.site";

inline const int MQTT_PORT =
1883;

// ======================
// TOPICS
// ======================

inline const char* TOPIC_DATOS =
"energia/datos";

// ======================
// RMS
// ======================

inline const int MUESTRAS =
300;

inline const float ALPHA =
0.2;

#endif