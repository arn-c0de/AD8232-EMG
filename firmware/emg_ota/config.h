#pragma once

// credentials are generated into secrets.h by flash.sh from .env
#include "secrets.h"

// ── OTA ──────────────────────────────────────────────────────────────────────
#define OTA_HOSTNAME  "emg-esp32"

// ── Sampling ─────────────────────────────────────────────────────────────────
#define SAMPLE_RATE_HZ  1000
#define RMS_WINDOW_MS   100      // 100 ms: low-latency muscle onset detection
#define TCP_PORT        8888

// ── Channels — ESP32-C5 WROOM pin layout ─────────────────────────────────────
// Each row defines one AD8232 module. Add or remove rows to scale the system,
// then update NUM_CHANNELS to match.
//
//   out      — AD8232 OUTPUT  → ADC1-capable GPIO (ESP32-C5: GPIO 0–6)
//   lo_plus  — AD8232 LO+     → any free GPIO (lead-off detect, digital input)
//   lo_minus — AD8232 LO-     → any free GPIO
//   label    — short tag shown in the stream header, REST API and GUI
//
// ESP32-C5 ADC note:
//   ADC1 channels (safe with WiFi active): GPIO 0–6  (ADC1_CH0–CH6)
//   ADC2 channels are unusable while WiFi is on — do NOT use them for OUTPUT.
//   LO+ / LO- are digital inputs; any free GPIO works.
//
// ESP32-C5-WROOM-1 suggested layout (2 channels, 4-channel template below):
//
//   GPIO 0–3 are avoided for OUTPUT: on most dev boards GPIO 0 carries a
//   BOOT pull-down that corrupts ADC readings. Use GPIO 4–6 instead.
//
//   CH0  FCR  OUT=GPIO 4 (ADC1_CH4)  LO+=GPIO 6   LO-=GPIO 7
//   CH1  ED   OUT=GPIO 5 (ADC1_CH5)  LO+=GPIO 8   LO-=GPIO 10
//   CH2  FCU  OUT=GPIO 2 (ADC1_CH2)  LO+=GPIO 11  LO-=GPIO 12  (future)
//   CH3  BRD  OUT=GPIO 3 (ADC1_CH3)  LO+=GPIO 12  LO-=GPIO 13  (future)

#define NUM_CHANNELS 2

struct ChannelPins {
    uint8_t     out;
    uint8_t     lo_plus;
    uint8_t     lo_minus;
    const char* label;
};

static const ChannelPins CHANNELS[NUM_CHANNELS] = {
    {  4,  6,  7, "FCR" },   // CH0 — forearm flexor   (palm-up,   near elbow)
    {  5,  8, 10, "ED"  },   // CH1 — forearm extensor (palm-down, near elbow)
 // {  2, 10, 11, "FCU" },   // CH2 — ulnar flexor
 // {  3, 12, 13, "BRD" },   // CH3 — brachioradialis / radial extensors
};
