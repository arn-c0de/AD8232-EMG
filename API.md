# EMG API — Reference for AI Agents

Local HTTP REST API. No auth. Returns JSON.

```
python3 emg_api.py
# → http://127.0.0.1:5555
```

The API binds to `127.0.0.1` by default because it has no authentication.
To expose it on your LAN intentionally:

```bash
python3 emg_api.py emg-esp32.local 8888 5555 0.0.0.0
```

---

## Endpoints

### GET /live
Current sensor reading.
```json
{
  "raw": 2183,
  "rms": 142.3,
  "threshold": 80.0,
  "state": "tense",      // "relaxed" | "tense" | "lead_off"
  "connected": true
}
```

---

### POST /record?label=relaxed&seconds=5
Record a labeled sample for N seconds. Use this when the user holds a specific pose.

| param | default | description |
|-------|---------|-------------|
| label | sample  | any string, e.g. `relaxed`, `tense`, `fist`, `pinch` |
| seconds | 5    | recording duration (1–30) |

```json
{
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
  "suggested_threshold": 108.5   // null until both relaxed + tense recorded
}
```

---

### GET /calibration
All stored labeled recordings.
```json
{
  "relaxed": { "rms_mean": 34.1, "rms_max": 61.0, ... },
  "tense":   { "rms_mean": 183.0, "rms_max": 241.0, ... }
}
```

---

### POST /calibration/reset
Clear all stored recordings.

---

### GET /threshold
```json
{ "threshold": 80.0 }
```

### POST /threshold?value=108
Set classification threshold (rms >= threshold → tense).

---

## Typical Agent Workflow

```
1. GET /live                          → check connection
2. "User: arm ruhig halten"
   POST /record?label=relaxed&seconds=5
3. "User: arm anspannen / Faust ballen"
   POST /record?label=tense&seconds=5
4. Response contains suggested_threshold → apply it:
   POST /threshold?value=<suggested>
5. GET /live repeatedly               → classify in real time
```

---

## State machine

```
rms < threshold  →  relaxed
rms >= threshold →  tense
state = lead_off →  electrodes detached, ignore data
connected = false → ESP32 not reachable
```

## Default ports

| service | port |
|---------|------|
| EMG API | 5555 |
| ESP32 TCP stream | 8888 |
| ESP32 OTA | 3232 |
