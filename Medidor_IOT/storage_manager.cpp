#include <Arduino.h>
#include <LittleFS.h>
#include "storage_manager.h"

static File sendingFile;
static bool sendingMode = false;
static bool fsOk = false;

bool iniciarStorage() {
  if (LittleFS.begin()) {
    fsOk = true;
    Serial.println("LittleFS montado");
  } else {
    Serial.println("LittleFS no disponible - buffer desactivado");
    return false;
  }
  if (LittleFS.exists(BUFFER_SENDING)) {
    LittleFS.remove(BUFFER_SENDING);
  }
  return true;
}

bool guardarLectura(uint32_t epoch, float ch1, float ch2, float ch3, float ch4) {
  if (!fsOk) return false;
  if (LittleFS.totalBytes() - LittleFS.usedBytes() < BUFFER_RECORD_SIZE + 512) {
    Serial.println("Espacio LittleFS agotado, descartando lectura");
    return false;
  }
  File f = LittleFS.open(BUFFER_FILE, "a");
  if (!f) return false;
  uint8_t data[BUFFER_RECORD_SIZE];
  data[0] = epoch >> 24 & 0xFF;
  data[1] = epoch >> 16 & 0xFF;
  data[2] = epoch >> 8 & 0xFF;
  data[3] = epoch & 0xFF;
  memcpy(data + 4, &ch1, 4);
  memcpy(data + 8, &ch2, 4);
  memcpy(data + 12, &ch3, 4);
  memcpy(data + 16, &ch4, 4);
  size_t written = f.write(data, BUFFER_RECORD_SIZE);
  f.close();
  return written == BUFFER_RECORD_SIZE;
}

int contarRegistrosPendientes() {
  if (!fsOk) return 0;
  if (sendingMode) {
    size_t total = sendingFile.size();
    size_t restantes = total - sendingFile.position();
    return restantes / BUFFER_RECORD_SIZE;
  }
  if (!LittleFS.exists(BUFFER_FILE)) return 0;
  File f = LittleFS.open(BUFFER_FILE, "r");
  if (!f) return 0;
  int count = f.size() / BUFFER_RECORD_SIZE;
  f.close();
  return count;
}

int leerTodasLecturas(uint8_t* buffer, int maxBytes) {
  if (!fsOk) return 0;
  if (!LittleFS.exists(BUFFER_FILE)) return 0;
  File f = LittleFS.open(BUFFER_FILE, "r");
  if (!f) return 0;
  int readBytes = f.read(buffer, maxBytes);
  f.close();
  return readBytes;
}

void limpiarBuffer() {
  if (!fsOk) return;
  if (sendingMode) {
    sendingFile.close();
    LittleFS.remove(BUFFER_SENDING);
    sendingMode = false;
  }
  LittleFS.remove(BUFFER_FILE);
}

bool iniciarEnvioBuffer() {
  if (!fsOk) return false;
  if (!LittleFS.exists(BUFFER_FILE)) return false;
  LittleFS.remove(BUFFER_SENDING);
  if (!LittleFS.rename(BUFFER_FILE, BUFFER_SENDING)) return false;
  sendingFile = LittleFS.open(BUFFER_SENDING, "r");
  if (!sendingFile) {
    LittleFS.remove(BUFFER_SENDING);
    return false;
  }
  sendingMode = true;
  return true;
}

int leerBufferBatch(uint8_t* buffer, int maxRecords) {
  if (!sendingMode) return 0;
  int leidos = 0;
  for (int i = 0; i < maxRecords; i++) {
    if (sendingFile.read(buffer + leidos * BUFFER_RECORD_SIZE, BUFFER_RECORD_SIZE) != BUFFER_RECORD_SIZE) {
      break;
    }
    leidos++;
  }
  if (sendingFile.available() == 0) {
    sendingFile.close();
    LittleFS.remove(BUFFER_SENDING);
    sendingMode = false;
  }
  return leidos;
}

bool hayEnvioPendiente() {
  return sendingMode;
}

bool guardarConfig(const Configuracion& cfg) {
  if (!fsOk) return false;
  File f = LittleFS.open(CONFIG_FILE, "w");
  if (!f) return false;
  String json = "{";
  json += "\"calibracion\":[";
  for (int i = 0; i < 4; i++) {
    if (i > 0) json += ",";
    json += String(cfg.calibracion[i], 4);
  }
  json += "],";
  json += "\"noiseFloor\":[";
  for (int i = 0; i < 4; i++) {
    if (i > 0) json += ",";
    json += String(cfg.noiseFloor[i], 4);
  }
  json += "],";
  json += "\"alpha\":" + String(cfg.alpha, 4) + ",";
  json += "\"intervalo\":" + String(cfg.intervalo) + ",";
  json += "\"voltaje\":" + String(cfg.voltaje, 1) + ",";
  json += "\"canales\":[";
  for (int i = 0; i < 4; i++) {
    if (i > 0) json += ",";
    json += cfg.canalesHabilitados[i] ? "true" : "false";
  }
  json += "]";
  json += "}";
  f.print(json);
  f.close();
  return true;
}

bool cargarConfig(Configuracion& cfg) {
  if (!fsOk) return false;
  if (!LittleFS.exists(CONFIG_FILE)) return false;
  File f = LittleFS.open(CONFIG_FILE, "r");
  if (!f) return false;
  String json = f.readString();
  f.close();

  auto extraerArr = [&](const String& key, float* arr) {
    int s = json.indexOf("\"" + key + "\":[");
    if (s < 0) return;
    s = json.indexOf('[', s) + 1;
    for (int i = 0; i < 4; i++) {
      int e = json.indexOf(',', s);
      if (e < 0) e = json.indexOf(']', s);
      arr[i] = json.substring(s, e).toFloat();
      s = e + 1;
    }
  };

  auto extraerFloat = [&](const String& key) -> float {
    int s = json.indexOf("\"" + key + "\":");
    if (s < 0) return -1;
    s = json.indexOf(':', s) + 1;
    int e = json.indexOf(',', s);
    if (e < 0) e = json.indexOf('}', s);
    return json.substring(s, e).toFloat();
  };

  extraerArr("calibracion", cfg.calibracion);
  extraerArr("noiseFloor", cfg.noiseFloor);

  {
    int s = json.indexOf("\"canales\":[");
    if (s >= 0) {
      s = json.indexOf('[', s) + 1;
      for (int i = 0; i < 4; i++) {
        int e = json.indexOf(',', s);
        if (e < 0) e = json.indexOf(']', s);
        String val = json.substring(s, e);
        val.trim();
        cfg.canalesHabilitados[i] = (val == "true");
        s = e + 1;
      }
    }
  }

  float v = extraerFloat("alpha");
  if (v >= 0) cfg.alpha = v;
  v = extraerFloat("intervalo");
  if (v >= 0) cfg.intervalo = (int)v;
  v = extraerFloat("voltaje");
  if (v >= 0) cfg.voltaje = v;

  return true;
}
