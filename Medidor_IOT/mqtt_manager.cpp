#include <Arduino.h>
#include <WiFi.h>
#define MQTT_MAX_PACKET_SIZE 512
#include <PubSubClient.h>
#include <HTTPClient.h>
#include <Update.h>
#include "mqtt_manager.h"
#include "storage_manager.h"

WiFiClient espClient;
PubSubClient client(espClient);
Configuracion configApp;

static unsigned long ultimoIntento = 0;
static const unsigned long INTENTO_INTERVALO = 30000;

static bool descargarOTA(const String& url) {
  HTTPClient http;
  http.setTimeout(120000);
  http.begin(url);
  int code = http.GET();
  if (code != 200) {
    Serial.print("OTA HTTP error: ");
    Serial.println(code);
    http.end();
    return false;
  }
  int len = http.getSize();
  if (len <= 0) {
    Serial.println("OTA tamaño invalido");
    http.end();
    return false;
  }
  Serial.print("OTA descargando ");
  Serial.print(len);
  Serial.println(" bytes...");
  if (!Update.begin(len)) {
    Serial.print("OTA Update.begin error: ");
    Serial.println(Update.getError());
    http.end();
    return false;
  }
  WiFiClient* stream = http.getStreamPtr();
  uint8_t buf[256];
  int total = 0;
  while (http.connected() && total < len) {
    int r = stream->readBytes(buf, min((int)sizeof(buf), len - total));
    if (r == 0) break;
    Update.write(buf, r);
    total += r;
    if (total % 10000 == 0 || total == len) {
      Serial.print("OTA progreso: ");
      Serial.print(total * 100 / len);
      Serial.println("%");
    }
  }
  http.end();
  if (!Update.end() || !Update.isFinished()) {
    Serial.print("OTA error en Update.end: ");
    Serial.println(Update.getError());
    return false;
  }
  Serial.println("OTA completado");
  return true;
}

void callbackMQTT(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }

  Serial.print("MQTT recv: "); Serial.println(msg);
  String resp;

  auto extraerStr = [&](const String& key) -> String {
    int s = msg.indexOf("\"" + key + "\":\"");
    if (s < 0) return "";
    s = s + key.length() + 4;
    int e = msg.indexOf('"', s);
    if (e < 0) return "";
    return msg.substring(s, e);
  };

  auto extraerFloat = [&](const String& key) -> float {
    int s = msg.indexOf("\"" + key + "\":");
    if (s < 0) return -9999;
    s = msg.indexOf(':', s) + 1;
    int e = msg.indexOf(',', s);
    if (e < 0) e = msg.indexOf('}', s);
    String val = msg.substring(s, e);
    val.trim();
    return val.toFloat();
  };

  auto extraerInt = [&](const String& key) -> int {
    return (int)extraerFloat(key);
  };

  auto extraerBool = [&](const String& key) -> bool {
    int s = msg.indexOf("\"" + key + "\":");
    if (s < 0) return false;
    s = msg.indexOf(':', s) + 1;
    int e = msg.indexOf(',', s);
    if (e < 0) e = msg.indexOf('}', s);
    String val = msg.substring(s, e);
    val.trim();
    return val == "true" || val == "1";
  };

  String cmd = extraerStr("cmd");
  Serial.print("cmd extraido: \""); Serial.print(cmd); Serial.println("\"");

  if (cmd == "status") {
    resp = "{\"cmd\":\"status\",\"uptime\":" + String(millis() / 1000);
    resp += ",\"rssi\":" + String(WiFi.RSSI());
    resp += ",\"buffer\":" + String(contarRegistrosPendientes());
    resp += ",\"firmware\":\"2.0\"";
    resp += ",\"settings\":{";
    resp += "\"alpha\":" + String(configApp.alpha, 4);
    resp += ",\"intervalo\":" + String(configApp.intervalo);
    resp += ",\"voltaje\":" + String(configApp.voltaje, 1);
    resp += ",\"calibracion\":[" + String(configApp.calibracion[0], 4) + "," + String(configApp.calibracion[1], 4) + "," + String(configApp.calibracion[2], 4) + "," + String(configApp.calibracion[3], 4) + "]";
    resp += ",\"noiseFloor\":[" + String(configApp.noiseFloor[0], 4) + "," + String(configApp.noiseFloor[1], 4) + "," + String(configApp.noiseFloor[2], 4) + "," + String(configApp.noiseFloor[3], 4) + "]";
    resp += ",\"canales\":[" + String(configApp.canalesHabilitados[0] ? "true" : "false") + "," + String(configApp.canalesHabilitados[1] ? "true" : "false") + "," + String(configApp.canalesHabilitados[2] ? "true" : "false") + "," + String(configApp.canalesHabilitados[3] ? "true" : "false") + "]";
    resp += "}}";
  } else if (cmd == "reiniciar") {
    publicarRespuestaMQTT("{\"cmd\":\"reiniciar\",\"ok\":true}");
    delay(500);
    ESP.restart();
  } else if (cmd == "limpiar_buffer") {
    limpiarBuffer();
    resp = "{\"cmd\":\"limpiar_buffer\",\"ok\":true}";
  } else if (cmd == "calibrar") {
    int canal = extraerInt("canal");
    float valor = extraerFloat("valor");
    if (canal >= 0 && canal < 4 && valor > 0) {
      configApp.calibracion[canal] = valor;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"calibrar\",\"ok\":true,\"canal\":" + String(canal) + ",\"valor\":" + String(valor, 4) + "}";
    } else {
      resp = "{\"cmd\":\"calibrar\",\"ok\":false,\"error\":\"parametros invalidos\"}";
    }
  } else if (cmd == "noise_floor") {
    int canal = extraerInt("canal");
    float valor = extraerFloat("valor");
    if (canal >= 0 && canal < 4 && valor >= 0) {
      configApp.noiseFloor[canal] = valor;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"noise_floor\",\"ok\":true,\"canal\":" + String(canal) + ",\"valor\":" + String(valor, 4) + "}";
    } else {
      resp = "{\"cmd\":\"noise_floor\",\"ok\":false,\"error\":\"parametros invalidos\"}";
    }
  } else if (cmd == "alpha") {
    float valor = extraerFloat("valor");
    if (valor > 0 && valor <= 1) {
      configApp.alpha = valor;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"alpha\",\"ok\":true,\"valor\":" + String(valor, 4) + "}";
    } else {
      resp = "{\"cmd\":\"alpha\",\"ok\":false,\"error\":\"parametros invalidos\"}";
    }
  } else if (cmd == "intervalo") {
    int valor = extraerInt("valor");
    if (valor >= 200 && valor <= 60000) {
      configApp.intervalo = valor;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"intervalo\",\"ok\":true,\"valor\":" + String(valor) + "}";
    } else {
      resp = "{\"cmd\":\"intervalo\",\"ok\":false,\"error\":\"parametros invalidos\"}";
    }
  } else if (cmd == "voltaje") {
    float valor = extraerFloat("valor");
    if (valor > 0) {
      configApp.voltaje = valor;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"voltaje\",\"ok\":true,\"valor\":" + String(valor, 1) + "}";
    } else {
      resp = "{\"cmd\":\"voltaje\",\"ok\":false,\"error\":\"parametros invalidos\"}";
    }
  } else if (cmd == "habilitar_canal") {
    int canal = extraerInt("canal");
    bool habilitado = extraerBool("habilitado");
    if (canal >= 0 && canal < 4) {
      configApp.canalesHabilitados[canal] = habilitado;
      guardarConfig(configApp);
      resp = "{\"cmd\":\"habilitar_canal\",\"ok\":true,\"canal\":" + String(canal) + ",\"habilitado\":" + (habilitado ? "true" : "false") + "}";
    } else {
      resp = "{\"cmd\":\"habilitar_canal\",\"ok\":false,\"error\":\"canal invalido\"}";
    }
  } else if (cmd == "ota") {
    String url = extraerStr("url");
    if (url.length() > 0) {
      publicarRespuestaMQTT("{\"cmd\":\"ota\",\"ok\":true,\"status\":\"descargando\"}");
      bool ok = descargarOTA(url);
      if (ok) {
        publicarRespuestaMQTT("{\"cmd\":\"ota\",\"ok\":true,\"status\":\"completado\"}");
        delay(500);
        ESP.restart();
      } else {
        publicarRespuestaMQTT("{\"cmd\":\"ota\",\"ok\":false,\"status\":\"error\"}");
      }
    } else {
      resp = "{\"cmd\":\"ota\",\"ok\":false,\"error\":\"url requerida\"}";
    }
  } else {
    resp = "{\"cmd\":\"" + cmd + "\",\"ok\":false,\"error\":\"comando desconocido\"}";
  }

  if (resp.length() > 0) {
    Serial.print("Respuesta: "); Serial.println(resp);
    publicarRespuestaMQTT(resp);
  }
}

void iniciarMQTT() {
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(callbackMQTT);
}

bool conectarMQTT() {
  if (client.connected()) return true;

  unsigned long ahora = millis();
  if (ahora - ultimoIntento < INTENTO_INTERVALO) return false;
  ultimoIntento = ahora;

  Serial.print("Conectando MQTT...");
  if (client.connect(("ESP32_" + deviceID).c_str())) {
    Serial.println("conectado");
    String topicComando = String(TOPIC_COMANDO) + deviceID;
    client.subscribe(topicComando.c_str());
    Serial.print("Suscrito a: ");
    Serial.println(topicComando);
    return true;
  } else {
    Serial.print("error=");
    Serial.println(client.state());
    return false;
  }
}

void publicarMQTT(const String& payload) {
  client.publish(TOPIC_DATOS, payload.c_str());
}

void publicarRespuestaMQTT(const String& payload) {
  String topic = String(TOPIC_RESPUESTA) + deviceID;
  client.publish(topic.c_str(), payload.c_str());
}

void loopMQTT() {
  client.loop();
}
