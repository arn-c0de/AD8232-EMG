# EMG API — Reference for AI Agents

Local HTTP REST API. No auth. Returns JSON. Channel-aware: every endpoint
is parameterised by an integer channel index that comes from the firmware
configuration in `firmware/emg_ota/config.h`.

```
python3 emg_api.py
# → http://127.0.0.1:5555
```

The API binds to `127.0.0.1` by default because it has no authentication.
To expose it on the LAN intentionally:

```bash
python3 emg_api.py emg-esp32.local 8888 5555 0.0.0.0
```

---

## Endpoints

### GET /live
Full snapshot of every channel.

```json
{
  "connected": true,
  "channels": [
    {
      "id": 0, "label": "FCR",
      "raw": 2183, "rms": 142.3, "rms_smooth": 138.7,
      "threshold": 80.0,
      "state": "tense"
    },
    {
      "id": 1, "label": "ED",
      "raw": 1990, "rms": 24.6, "rms_smooth": 22.1,
      "threshold": 65.0,
      "state": "relaxed"
    }
  ]
}
```

`state` is one of `relaxed`, `tense`, `lead_off`.

---

### GET /channels
Channel metadata only — useful for clients that just need the layout.

```json
[
  { "id": 0, "label": "FCR" },
  { "id": 1, "label": "ED" }
]
```

---

### GET /channel/{id}
Single channel snapshot — same shape as one element of `/live.channels`.

### GET /channel/{id}/calibration
All labelled recordings stored for that channel.

```json
{
  "relaxed": { "rms_mean": 11.7, "rms_max": 15.5, ... },
  "tense":   { "rms_mean": 126.6, "rms_max": 182.2, ... }
}
```

### GET /channel/{id}/threshold
```json
{ "threshold": 80.0 }
```

---

### POST /channel/{id}/threshold?value=108
Set classification threshold for one channel.

### POST /channel/{id}/record?label=relaxed&seconds=5
Record a labelled sample on one channel.

| param | default | description |
|-------|---------|-------------|
| label | sample  | any string, e.g. `relaxed`, `tense`, `fist`, `pinch` |
| seconds | 5    | recording duration (1–30) |

```json
{
  "channel": 0,
  "label": "relaxed",
  "duration_seconds": 5,
  "stats": {
    "count": 100,
    "rms_mean": 34.1,
    "rms_max": 61.0,
    "rms_min": 18.2,
    "rms_stdev": 8.4,
    "raw_mean": 2049.3
  },
  "suggested_threshold": 108.5
}
```

`suggested_threshold` is non-null once both `relaxed` and `tense` have been
recorded for the channel — the API applies it automatically.

### POST /channel/{id}/calibration/reset
Clear stored recordings for one channel.

### POST /calibration/reset
Clear stored recordings for **all** channels.

---

## Typical Agent Workflow (per channel)

```
1. GET /channels                                       → discover channels
2. GET /live                                           → check connection
3. "User: arm ruhig halten"
   POST /channel/0/record?label=relaxed&seconds=5
4. "User: arm anspannen / Faust ballen"
   POST /channel/0/record?label=tense&seconds=5
5. Response contains suggested_threshold (already applied)
6. GET /live repeatedly                                → classify in real time
7. Repeat 3-5 for any additional channel.
```

---

## State machine (per channel)

```
rms_smooth < threshold  →  relaxed
rms_smooth >= threshold →  tense  (held for ~400 ms after peak)
LEAD_OFF pulses         →  lead_off  (auto-clears after ~400 ms of silence)
connected = false       →  ESP32 not reachable
```

## Default ports

| service | port |
|---------|------|
| EMG API | 5555 |
| ESP32 TCP stream | 8888 |
| ESP32 OTA | 3232 |

## ESP32 → API wire format

```
#CH:2,FCR,ED          header on every new connection
2105,42.3,1890,38.1   one CSV line per sample tick: rawN,rmsN per channel
LEAD_OFF:1            per-channel lead-off pulse (10 Hz while detached)
```
