#pragma once

// credentials are generated into secrets.h by flash.sh from .env
#include "secrets.h"

// ── OTA ──────────────────────────────────────────────────────────────────────
#define OTA_HOSTNAME  "emg-esp32"

// ── Sampling ─────────────────────────────────────────────────────────────────
#define SAMPLE_RATE_HZ  1000
#define RMS_WINDOW_MS   100      // 100 ms: low-latency muscle onset detection
#define TCP_PORT        8888

// ── Channels ─────────────────────────────────────────────────────────────────
// Each row defines one AD8232 module. Add or remove rows to scale the system,
// then update NUM_CHANNELS to match.
//
//   out      — AD8232 OUTPUT  → ESP32 ADC1 input (GPIO 32, 33, 34, 35, 36, 39)
//   lo_plus  — AD8232 LO+     → any free GPIO (lead-off detect, digital input)
//   lo_minus — AD8232 LO-     → any free GPIO
//   label    — short tag shown in the stream header, REST API and GUI
//
// NOTE: ESP32 ADC2 pins (GPIO 0/2/4/12-15/25-27) do NOT work while WiFi is
//       active — always wire AD8232 OUTPUT to an ADC1 pin.

#define NUM_CHANNELS 2

struct ChannelPins {
    uint8_t     out;
    uint8_t     lo_plus;
    uint8_t     lo_minus;
    const char* label;
};

static const ChannelPins CHANNELS[NUM_CHANNELS] = {
    { 34, 16, 17, "FCR" },   // CH0 — forearm flexor   (palm-up,   near elbow)
    { 35, 18, 19, "ED"  },   // CH1 — forearm extensor (palm-down, near elbow)
 // { 36, 21, 22, "FCU" },   // CH2 — ulnar flexor
 // { 39, 23, 25, "BRD" },   // CH3 — brachioradialis / radial extensors
};
