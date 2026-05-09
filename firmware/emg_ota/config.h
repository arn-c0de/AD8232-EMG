#pragma once

// credentials are generated into secrets.h by flash.sh from .env
#include "secrets.h"

#define OTA_HOSTNAME  "emg-esp32"

// AD8232 pins — single module, forearm
#define EMG_OUT_PIN   34   // ADC1_CH6 analog signal
#define LO_PLUS_PIN   16   // lead-off detection +
#define LO_MINUS_PIN  17   // lead-off detection -

// Sampling
#define SAMPLE_RATE_HZ  1000
#define RMS_WINDOW_MS   200    // wider window = smoother envelope
#define TCP_PORT        8888
