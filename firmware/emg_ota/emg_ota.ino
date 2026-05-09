#include <WiFi.h>
#include <ArduinoOTA.h>
#include <WiFiServer.h>
#include "config.h"

WiFiServer tcpServer(TCP_PORT);
WiFiClient tcpClient;

const int SAMPLES_PER_WINDOW = (SAMPLE_RATE_HZ * RMS_WINDOW_MS) / 1000;
const unsigned long SAMPLE_INTERVAL_US = 1000000UL / SAMPLE_RATE_HZ;

// DC tracker: very slow EMA removes electrode offset + long-term drift
// HP filter:  removes motion artifacts and low-freq noise below ~20 Hz
// Both run before RMS so only true muscle signal enters the window.
const float DC_ALPHA = 0.0005f;                  // ~2 Hz tracker
const float HP_ALPHA = 1.0f / (1.0f + (float)(2.0f * 3.14159f * 20.0f / SAMPLE_RATE_HZ));

unsigned long lastSampleUs   = 0;
unsigned long lastLeadOffUs  = 0;
float dcLevel    = 2048.0f;
float hpPrevIn   = 0.0f;
float hpPrevOut  = 0.0f;
float rmsBuffer[SAMPLES_PER_WINDOW];
int   bufferIndex = 0;
float bufferSumF  = 0.0f;

void setup() {
  Serial.begin(115200);
  pinMode(LO_PLUS_PIN,  INPUT);
  pinMode(LO_MINUS_PIN, INPUT);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - wifiStart > 20000) {
      Serial.println("\nWiFi timeout — rebooting");
      ESP.restart();
    }
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());

  ArduinoOTA.setHostname(OTA_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]()  { Serial.println("OTA start"); });
  ArduinoOTA.onEnd([]()    { Serial.println("\nOTA done"); });
  ArduinoOTA.onError([](ota_error_t e) { Serial.printf("OTA error[%u]\n", e); });
  ArduinoOTA.begin();

  tcpServer.begin();
  Serial.printf("TCP EMG stream on port %d\n", TCP_PORT);
}

void loop() {
  ArduinoOTA.handle();

  // accept new GUI client
  if (!tcpClient || !tcpClient.connected()) {
    tcpClient = tcpServer.accept();
  }

  unsigned long now = micros();
  if (now - lastSampleUs < SAMPLE_INTERVAL_US) return;
  lastSampleUs = now;

  // lead-off check — throttled to 10 Hz to avoid flooding the stream
  if (digitalRead(LO_PLUS_PIN) || digitalRead(LO_MINUS_PIN)) {
    if (now - lastLeadOffUs >= 100000UL) {
      sendLine("LEAD_OFF");
      lastLeadOffUs = now;
    }
    return;
  }

  int raw = analogRead(EMG_OUT_PIN);  // 0–4095 (12-bit)

  // 1. Adaptive DC removal — tracks slow electrode drift
  dcLevel   += DC_ALPHA * (raw - dcLevel);
  float centered = raw - dcLevel;

  // 2. High-pass IIR at ~20 Hz — removes motion artifacts
  float hpOut = HP_ALPHA * (hpPrevOut + centered - hpPrevIn);
  hpPrevIn  = centered;
  hpPrevOut = hpOut;

  // 3. Running RMS on filtered signal
  bufferSumF -= rmsBuffer[bufferIndex] * rmsBuffer[bufferIndex];
  rmsBuffer[bufferIndex] = hpOut;
  bufferSumF += hpOut * hpOut;
  bufferIndex  = (bufferIndex + 1) % SAMPLES_PER_WINDOW;

  float rms = sqrtf(bufferSumF / SAMPLES_PER_WINDOW);

  // CSV: raw,rms
  char line[32];
  snprintf(line, sizeof(line), "%d,%.1f", raw, rms);
  sendLine(line);
}

void sendLine(const char* line) {
  Serial.println(line);
  if (tcpClient && tcpClient.connected()) {
    tcpClient.println(line);
  }
}
