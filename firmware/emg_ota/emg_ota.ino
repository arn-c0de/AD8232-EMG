#include <WiFi.h>
#include <ArduinoOTA.h>
#include <WiFiServer.h>
#include "config.h"

// ── Derived constants ────────────────────────────────────────────────────────
constexpr int           SAMPLES_PER_WINDOW   = (SAMPLE_RATE_HZ * RMS_WINDOW_MS) / 1000;
constexpr unsigned long SAMPLE_INTERVAL_US   = 1000000UL / SAMPLE_RATE_HZ;
constexpr unsigned long LEAD_OFF_INTERVAL_US = 100000UL;   // 10 Hz pulse rate per channel

// DC tracker removes electrode offset and slow drift (~2 Hz cutoff).
// HP filter removes motion artifacts and noise below ~20 Hz.
// Both run before RMS so only the muscle band enters the window.
constexpr float DC_ALPHA = 0.0005f;
constexpr float HP_ALPHA = 1.0f / (1.0f + (2.0f * 3.14159265f * 20.0f / SAMPLE_RATE_HZ));

// ── Per-channel signal-path state ────────────────────────────────────────────
struct Channel {
    float dcLevel    = 2048.0f;
    float hpPrevIn   = 0.0f;
    float hpPrevOut  = 0.0f;
    float rmsBuffer[SAMPLES_PER_WINDOW] = {};
    int   bufferIndex = 0;
    float bufferSum   = 0.0f;
    unsigned long lastLeadOffUs = 0;
};

static Channel       channels[NUM_CHANNELS];
static WiFiServer    tcpServer(TCP_PORT);
static WiFiClient    tcpClient;
static unsigned long lastSampleUs = 0;

// ── Stream helpers ───────────────────────────────────────────────────────────
static void sendLine(const char* line) {
    Serial.println(line);
    if (tcpClient && tcpClient.connected()) {
        tcpClient.println(line);
    }
}

// Header announces channel layout to the client on every new connection:
//   #CH:<n>,<label0>,<label1>,...
// The client uses this to size its buffers and label its plots.
static void sendStreamHeader() {
    char hdr[128];
    int n = snprintf(hdr, sizeof(hdr), "#CH:%d", NUM_CHANNELS);
    for (int i = 0; i < NUM_CHANNELS && n < (int)sizeof(hdr) - 1; i++) {
        n += snprintf(hdr + n, sizeof(hdr) - n, ",%s", CHANNELS[i].label);
    }
    sendLine(hdr);
}

// ── DSP per channel ──────────────────────────────────────────────────────────
static float processSample(int idx, int raw) {
    Channel& c = channels[idx];

    c.dcLevel += DC_ALPHA * (raw - c.dcLevel);
    float centered = raw - c.dcLevel;

    float hpOut = HP_ALPHA * (c.hpPrevOut + centered - c.hpPrevIn);
    c.hpPrevIn  = centered;
    c.hpPrevOut = hpOut;

    c.bufferSum -= c.rmsBuffer[c.bufferIndex] * c.rmsBuffer[c.bufferIndex];
    c.rmsBuffer[c.bufferIndex] = hpOut;
    c.bufferSum += hpOut * hpOut;
    c.bufferIndex = (c.bufferIndex + 1) % SAMPLES_PER_WINDOW;

    return sqrtf(c.bufferSum / SAMPLES_PER_WINDOW);
}

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    for (int i = 0; i < NUM_CHANNELS; i++) {
        pinMode(CHANNELS[i].lo_plus,  INPUT);
        pinMode(CHANNELS[i].lo_minus, INPUT);
    }

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
    ArduinoOTA.onStart([]() { Serial.println("OTA start"); });
    ArduinoOTA.onEnd  ([]() { Serial.println("\nOTA done"); });
    ArduinoOTA.onError([](ota_error_t e) { Serial.printf("OTA error[%u]\n", e); });
    ArduinoOTA.begin();

    tcpServer.begin();
    Serial.printf("TCP EMG stream on port %d  (channels: %d)\n",
                  TCP_PORT, NUM_CHANNELS);
}

// ── Main loop ────────────────────────────────────────────────────────────────
void loop() {
    ArduinoOTA.handle();

    // Accept a new client and announce the channel layout.
    if (!tcpClient || !tcpClient.connected()) {
        WiFiClient incoming = tcpServer.accept();
        if (incoming) {
            tcpClient = incoming;
            sendStreamHeader();
        }
    }

    unsigned long now = micros();
    if (now - lastSampleUs < SAMPLE_INTERVAL_US) return;
    lastSampleUs = now;

    // Per-channel lead-off pulses (throttled to 10 Hz each).
    // Pulses act as flags: clients clear "lead_off" after a short timeout.
    for (int i = 0; i < NUM_CHANNELS; i++) {
        bool off = digitalRead(CHANNELS[i].lo_plus) ||
                   digitalRead(CHANNELS[i].lo_minus);
        if (off && now - channels[i].lastLeadOffUs >= LEAD_OFF_INTERVAL_US) {
            char line[16];
            snprintf(line, sizeof(line), "LEAD_OFF:%d", i);
            sendLine(line);
            channels[i].lastLeadOffUs = now;
        }
    }

    // One CSV line per tick: raw0,rms0,raw1,rms1,...
    char line[24 * NUM_CHANNELS + 8];
    int  pos = 0;
    for (int i = 0; i < NUM_CHANNELS; i++) {
        int   raw = analogRead(CHANNELS[i].out);
        float rms = processSample(i, raw);
        pos += snprintf(line + pos, sizeof(line) - pos,
                        i == 0 ? "%d,%.1f" : ",%d,%.1f", raw, rms);
    }
    sendLine(line);
}
