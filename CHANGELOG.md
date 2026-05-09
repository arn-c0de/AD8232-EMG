# Changelog

All notable changes to this project are documented here.

---

## [1.0.1] — 2026-05-09

### Signal Quality
- **Adaptive DC tracker** replaces fixed 2048 offset — tracks electrode drift and ADC bias in real time (`α = 0.0005`, ~2 Hz)
- **IIR high-pass filter at ~20 Hz** applied before RMS — removes motion artifacts and low-frequency noise so only the muscle-band signal enters the RMS window
- **RMS window reduced from 200 ms to 100 ms** — faster muscle onset detection with lower latency
- **Backend smoothing reduced** (`SMOOTH_ALPHA` 0.3 → 0.15) — firmware now handles heavy filtering; API smoothing no longer adds unnecessary latency

### Firmware
- WiFi connect loop now times out after 20 s and reboots instead of blocking forever
- `LEAD_OFF` transmission throttled to 10 Hz in firmware and API — prevents flooding the TCP stream when electrodes are detached
- `rmsBuffer` size is now derived from `SAMPLES_PER_WINDOW` at compile time instead of being hard-coded to 50

### API (`emg_api.py`)
- Switched from `HTTPServer` to `ThreadingMixIn` — `/live` requests are now served concurrently while `/record` is running, preventing broken pipe errors and GUI disconnects during calibration
- `/record` now collects only unique samples by timestamp — eliminates duplicate-sample bias in calibration statistics
- `/threshold` returns `400 Bad Request` with a clear message on invalid float input instead of crashing with HTTP 500
- ESP32 socket is explicitly closed and `connected` is set to `False` on EOF — no more stale connection state or tight reconnect loops

### GUI (`gui/emg_gui.py`)
- Rebuilt with native tkinter buttons — no more flickering or missed clicks from matplotlib widget redraws
- **Draggable threshold line** in RMS plot (toggle with DRAG button) — poll loop no longer overwrites local threshold position during active drag
- **Manual threshold input** field with SET button in side panel
- **RESET CAL** button clears stored calibration without restarting
- Canvas redraws only when new data arrives (dirty flag) — reduces CPU usage on slower systems
- Exceptions logged to stderr instead of being silently swallowed

### Monitor (`monitor.sh`)
- `--restart` flag kills existing API and GUI processes before starting fresh
- `--stop` flag cleanly stops API and GUI and exits
- API server auto-started if not already running; GUI launched automatically
- Fixed USB serial port detection (`find /dev` replaces broken `ls` glob)

### Documentation
- README rewritten in English with updated electrode placement diagram, calibration workflow, and project structure
- `API.md` added — complete REST API reference for AI agents
- GUI screenshot added to README
- Contact section moved to bottom of README

---

## [1.0.0] — 2026-05-09

Initial release.

- ESP32 firmware with ArduinoOTA support — wireless flashing after first USB flash
- Single AD8232 channel, forearm surface EMG
- `flash.sh` — compiles with `arduino-cli`, flashes via OTA or USB fallback; WiFi credentials injected from `.env` at build time via generated `secrets.h`
- `emg_api.py` — local HTTP REST API (stdlib only, no pip dependencies) with calibration persistence (`calibration.json`)
- `gui/emg_gui.py` — live matplotlib plots embedded in tkinter
- `monitor.sh` — terminal ASCII bar monitor
- Calibration wizard: record relaxed and tense states, auto-compute threshold
