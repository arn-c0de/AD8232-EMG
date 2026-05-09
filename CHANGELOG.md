# Changelog

All notable changes to this project are documented here.

---

## [1.0.1 - Multi Channel update] — 2026-05-09

### Multi-channel architecture

- **`config.h`**: replaced fixed single-channel pin defines with a `ChannelPins` table. One row now defines one AD8232 module, and `NUM_CHANNELS` controls the layout.
- **`emg_ota.ino`**: firmware now processes all configured channels in a loop using per-channel filter, RMS window and lead-off state.
- **Wire protocol**: the ESP sends a self-describing header `#CH:<n>,<label0>,...` on every new TCP connection, followed by packed CSV samples `raw0,rms0,raw1,rms1,...`. Lead-off is now channel-specific via `LEAD_OFF:<idx>`.
- **`emg_api.py`**: REST API upgraded to a channel-aware model with `GET /channels`, `GET /channel/{id}`, `GET /channel/{id}/threshold`, `POST /channel/{id}/threshold`, `POST /channel/{id}/record`, `GET /channel/{id}/calibration`, `POST /channel/{id}/calibration/reset` and `POST /calibration/reset`.
- **Calibration persistence**: `calibration.json` now stores threshold and recordings per channel, while legacy single-channel calibration files are still accepted and migrated on load.

### ESP32-C5 WROOM migration

- **Hardware target changed to `ESP32-C5 WROOM`**.
- **`config.h`**: current default pin layout is CH0 `OUT=GPIO 0 / LO+=GPIO 6 / LO-=GPIO 7`, CH1 `OUT=GPIO 1 / LO+=GPIO 8 / LO-=GPIO 9`.
- **ADC note**: on ESP32-C5 only ADC1 pins `GPIO 0-6` are safe for analog sampling while WiFi is active.
- **`flash.sh`**: board target updated from classic ESP32 to `esp32:esp32:esp32c5`; OTA upload helper path is resolved against newer arduino-esp32 3.x core installs.
- **Core requirement**: moved from arduino-esp32 2.x to 3.3.8 for ESP32-C5 support.

### GUI and plotting

- **`gui/emg_gui.py`**: GUI layout is now fully dynamic and rebuilds automatically from the live channel header.
- One combined raw plot is shown at the top, with one RMS subplot per channel below it.
- Each channel now has its own threshold row, label, manual threshold input and live state display.
- Threshold dragging works independently per RMS plot.
- Calibration flow now supports selecting the active channel.
- Multi-channel plot refresh was fixed so later channels such as `CH1` are redrawn reliably after figure rebuilds instead of getting stuck on stale zero-state data.
- RMS panels now show clearer live feedback with current-value titles, endpoint markers and filled RMS areas.
- Global status banner now handles mixed states correctly, for example `ACTIVE` on one channel while another is `LEAD OFF`.

### Signal and runtime fixes

- Added guards in firmware against invalid RMS calculations and unstable square-root input.
- Updated the analog setup for the new board target, including attenuation handling and safer channel behavior.
- `emg_api.py`: root route `GET /` now returns API info instead of `404`.
- `emg_api.py`: standard deviation calculation was rewritten without `statistics.stdev`, improving Python 3.12 compatibility.

### Documentation and assets

- **`README.md`**: updated throughout for `ESP32-C5 WROOM`, multi-channel wiring, ADC constraints, runtime notes and terminology cleanup.
- **`API.md`**: documents the channel-aware API and wire format.
- **`images/main-gui.png`**: screenshot replaced with the current multi-channel GUI.

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
