#!/usr/bin/env python3
"""
EMG HTTP API — multi-channel, no external dependencies.

Connects to the ESP32 TCP stream and exposes a channel-aware REST API.

Stream protocol (ESP32 → API):
    #CH:<n>,<label0>,<label1>,...        header on every new connection
    raw0,rms0,raw1,rms1,...              one line per sample tick
    LEAD_OFF:<idx>                       per-channel lead-off pulse (10 Hz)

REST endpoints:
    GET  /live                                full snapshot of all channels
    GET  /channels                            channel metadata
    GET  /channel/<id>                        single channel snapshot
    POST /channel/<id>/threshold?value=80     set channel threshold
    POST /channel/<id>/record?label=relaxed&seconds=5
    GET  /channel/<id>/calibration            recordings for one channel
    POST /channel/<id>/calibration/reset      clear one channel
    POST /calibration/reset                   clear all channels

Start:
    python3 emg_api.py [esp_host] [esp_port] [api_port] [bind_host]
"""
from __future__ import annotations

import json
import os
import re
import socket
import statistics
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

# ── config ───────────────────────────────────────────────────────────────────
ESP_HOST = sys.argv[1] if len(sys.argv) > 1 else "emg-esp32.local"
ESP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
API_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 5555
API_BIND = sys.argv[4] if len(sys.argv) > 4 else "127.0.0.1"
CAL_FILE = os.path.join(os.path.dirname(__file__), "calibration.json")

DEFAULT_THRESHOLD = 80.0
SMOOTH_ALPHA      = 0.15    # backend smoothing — firmware does heavy filtering
HOLD_MS           = 400     # keep "tense" for at least this long after peak
LEAD_OFF_TIMEOUT  = 0.4     # clear lead_off if no pulse arrives within this window
HISTORY_PER_CH    = 5000    # ~5 s @ 1 kHz per channel

# ── shared state ─────────────────────────────────────────────────────────────
lock     = threading.Lock()
channels: list[dict] = []         # one dict per channel — see make_channel()
history:  list[deque] = []        # parallel list, one ring buffer per channel
connected = {"value": False}


def make_channel(idx: int, label: str) -> dict:
    return {
        "id": idx,
        "label": label,
        "raw": 0,
        "rms": 0.0,
        "rms_smooth": 0.0,
        "threshold": DEFAULT_THRESHOLD,
        "lead_off": False,
        "lead_off_until": 0.0,
        "tense_until": 0.0,
        "calibration": {},        # {"relaxed": {...}, "tense": {...}}
    }


def channel_state(ch: dict) -> str:
    if ch["lead_off"] and time.time() < ch["lead_off_until"]:
        return "lead_off"
    is_tense = (ch["rms_smooth"] >= ch["threshold"]
                or time.time() < ch["tense_until"])
    return "tense" if is_tense else "relaxed"


def channel_snapshot(ch: dict) -> dict:
    return {
        "id":         ch["id"],
        "label":      ch["label"],
        "raw":        ch["raw"],
        "rms":        round(ch["rms"], 2),
        "rms_smooth": round(ch["rms_smooth"], 2),
        "threshold":  ch["threshold"],
        "state":      channel_state(ch),
    }


def reshape_channels(labels: list[str]) -> None:
    """Resize the channels list to match a new stream header. Called under lock."""
    global channels, history
    n = len(labels)

    if len(channels) == n:
        # Just update labels; preserve thresholds, calibration and history.
        for i, label in enumerate(labels):
            channels[i]["label"] = label
        return

    # Build fresh state, carrying over per-index threshold and calibration.
    new_channels = []
    new_history  = []
    for i, label in enumerate(labels):
        ch = make_channel(i, label)
        if i < len(channels):
            ch["threshold"]   = channels[i]["threshold"]
            ch["calibration"] = channels[i]["calibration"]
        new_channels.append(ch)
        new_history.append(deque(maxlen=HISTORY_PER_CH))
    channels = new_channels
    history  = new_history


# ── calibration persistence ──────────────────────────────────────────────────
def load_calibration() -> None:
    """Load calibration.json. Supports the legacy single-channel format too."""
    if not os.path.exists(CAL_FILE):
        reshape_channels(["CH0"])
        return

    try:
        with open(CAL_FILE) as f:
            data = json.load(f)
    except Exception as e:
        print(f"[cal] failed to load {CAL_FILE}: {e}", file=sys.stderr)
        reshape_channels(["CH0"])
        return

    with lock:
        if "channels" in data and isinstance(data["channels"], list):
            labels = [c.get("label", f"CH{i}") for i, c in enumerate(data["channels"])]
            reshape_channels(labels)
            for i, c in enumerate(data["channels"]):
                channels[i]["threshold"]   = c.get("threshold", DEFAULT_THRESHOLD)
                channels[i]["calibration"] = c.get("calibration", {})
        else:
            # Legacy format: {"calibration": {...}, "threshold": <float>}
            reshape_channels(["CH0"])
            channels[0]["threshold"]   = data.get("threshold", DEFAULT_THRESHOLD)
            channels[0]["calibration"] = data.get("calibration", {})

    print(f"[cal] loaded {len(channels)} channel(s) from {CAL_FILE}")


def save_calibration() -> None:
    with lock:
        payload = {
            "channels": [
                {
                    "id":          ch["id"],
                    "label":       ch["label"],
                    "threshold":   ch["threshold"],
                    "calibration": ch["calibration"],
                }
                for ch in channels
            ]
        }
    with open(CAL_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# ── stream parsing ───────────────────────────────────────────────────────────
HEADER_RE   = re.compile(r"^#CH:(\d+)(?:,(.*))?$")
LEAD_OFF_RE = re.compile(r"^LEAD_OFF(?::(\d+))?$")


def handle_header(line: str) -> bool:
    m = HEADER_RE.match(line)
    if not m:
        return False
    n = int(m.group(1))
    raw_labels = (m.group(2) or "").split(",") if m.group(2) else []
    labels = [(raw_labels[i].strip() if i < len(raw_labels) and raw_labels[i].strip()
               else f"CH{i}") for i in range(n)]
    with lock:
        reshape_channels(labels)
    print(f"[stream] header: {n} channel(s) → {labels}")
    return True


def handle_lead_off(line: str) -> bool:
    m = LEAD_OFF_RE.match(line)
    if not m:
        return False
    idx = int(m.group(1)) if m.group(1) is not None else 0   # legacy: no index
    with lock:
        if 0 <= idx < len(channels):
            channels[idx]["lead_off"] = True
            channels[idx]["lead_off_until"] = time.time() + LEAD_OFF_TIMEOUT
    return True


def handle_data(line: str) -> None:
    """Parse a comma-packed sample line: raw0,rms0,raw1,rms1,..."""
    parts = line.split(",")
    if len(parts) < 2 or len(parts) % 2 != 0:
        return
    pairs = [(parts[i], parts[i + 1]) for i in range(0, len(parts), 2)]

    now = time.time()
    with lock:
        if len(pairs) != len(channels):
            # Stream shape changed without a header — defer to next header.
            return
        for i, (r_str, e_str) in enumerate(pairs):
            try:
                r = float(r_str)
                e = float(e_str)
            except ValueError:
                continue
            ch = channels[i]
            ch["raw"] = r
            ch["rms"] = e
            ch["rms_smooth"] = (
                SMOOTH_ALPHA * e + (1 - SMOOTH_ALPHA) * ch["rms_smooth"]
            )
            if ch["rms_smooth"] >= ch["threshold"]:
                ch["tense_until"] = now + HOLD_MS / 1000
            # Lead-off self-clears once no pulses arrive for LEAD_OFF_TIMEOUT.
            if ch["lead_off"] and now >= ch["lead_off_until"]:
                ch["lead_off"] = False
            history[i].append({"raw": r, "rms": e, "t": now})


# ── ESP32 reader thread ──────────────────────────────────────────────────────
def esp_reader() -> None:
    while True:
        sock = None
        try:
            sock = socket.create_connection((ESP_HOST, ESP_PORT), timeout=5)
            connected["value"] = True
            buf = ""
            while True:
                chunk = sock.recv(1024).decode("utf-8", errors="ignore")
                if not chunk:
                    break
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        handle_header(line)
                    elif line.startswith("LEAD_OFF"):
                        handle_lead_off(line)
                    else:
                        handle_data(line)
        except Exception:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            connected["value"] = False
            time.sleep(2)


threading.Thread(target=esp_reader, daemon=True).start()


# ── stats helpers ────────────────────────────────────────────────────────────
def calc_stats(samples: list[dict]) -> dict:
    rms_vals = [s["rms"] for s in samples]
    raw_vals = [s["raw"] for s in samples]
    return {
        "count":     len(rms_vals),
        "rms_mean":  round(statistics.mean(rms_vals), 2),
        "rms_max":   round(max(rms_vals), 2),
        "rms_min":   round(min(rms_vals), 2),
        "rms_stdev": round(statistics.stdev(rms_vals), 2) if len(rms_vals) > 1 else 0,
        "raw_mean":  round(statistics.mean(raw_vals), 2),
    }


def record_channel(idx: int, label: str, seconds: float) -> tuple[int, dict]:
    seconds = max(1.0, min(30.0, seconds))
    print(f"[record] CH{idx} '{label}' for {seconds}s …")

    t_end   = time.time() + seconds
    samples: list[dict] = []
    last_ts = 0.0
    while time.time() < t_end:
        with lock:
            if 0 <= idx < len(history) and history[idx] and history[idx][-1]["t"] > last_ts:
                samples.append(dict(history[idx][-1]))
                last_ts = history[idx][-1]["t"]
        time.sleep(0.005)

    if not samples:
        return 503, {"error": f"no data on channel {idx}"}

    stats = calc_stats(samples)
    suggestion = None
    with lock:
        ch = channels[idx]
        ch["calibration"][label] = stats
        cal = ch["calibration"]
        if "relaxed" in cal and "tense" in cal:
            suggestion = round((cal["relaxed"]["rms_mean"] +
                                cal["tense"]["rms_mean"]) / 2, 1)
            ch["threshold"] = suggestion

    save_calibration()
    return 200, {
        "channel":             idx,
        "label":               label,
        "duration_seconds":    seconds,
        "stats":               stats,
        "suggested_threshold": suggestion,
    }


# ── HTTP layer ───────────────────────────────────────────────────────────────
def json_response(handler: BaseHTTPRequestHandler, code: int, data) -> None:
    body = json.dumps(data, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


CHANNEL_PATH_RE = re.compile(r"^/channel/(\d+)(?:/([\w/]+))?$")


def find_channel(idx: int) -> dict | None:
    with lock:
        if 0 <= idx < len(channels):
            return channels[idx]
    return None


def legacy_single_channel_path(path: str) -> tuple[int, str | None] | None:
    """Map pre-multichannel routes to channel 0 for backward compatibility."""
    if path == "/threshold":
        return 0, "threshold"
    if path == "/record":
        return 0, "record"
    if path == "/calibration":
        return 0, "calibration"
    if path == "/calibration/reset":
        return 0, "calibration/reset"
    return None


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # silence per-request stderr
        pass

    # ── GET ──
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/favicon.ico"):
            with lock:
                ch_list = [{"id": c["id"], "label": c["label"]} for c in channels]
            return json_response(self, 200, {
                "service":   "EMG API",
                "connected": connected["value"],
                "channels":  ch_list,
                "endpoints": [
                    "GET  /live",
                    "GET  /channels",
                    "GET  /channel/<id>",
                    "GET  /channel/<id>/threshold",
                    "GET  /channel/<id>/calibration",
                    "POST /channel/<id>/threshold?value=80",
                    "POST /channel/<id>/record?label=relaxed&seconds=5",
                    "POST /channel/<id>/calibration/reset",
                    "POST /calibration/reset",
                ],
            })

        if path == "/live":
            with lock:
                data = {
                    "connected": connected["value"],
                    "channels":  [channel_snapshot(c) for c in channels],
                }
            return json_response(self, 200, data)

        if path == "/channels":
            with lock:
                data = [{"id": c["id"], "label": c["label"]} for c in channels]
            return json_response(self, 200, data)

        m = CHANNEL_PATH_RE.match(path)
        legacy = legacy_single_channel_path(path)
        if not m and legacy is not None:
            idx, sub = legacy
        elif m:
            idx, sub = int(m.group(1)), m.group(2)
        else:
            idx, sub = None, None
        if idx is not None:
            ch = find_channel(idx)
            if ch is None:
                return json_response(self, 404, {"error": f"channel {idx} not found"})
            with lock:
                if sub is None:
                    return json_response(self, 200, channel_snapshot(ch))
                if sub == "calibration":
                    return json_response(self, 200, ch["calibration"])
                if sub == "threshold":
                    return json_response(self, 200, {"threshold": ch["threshold"]})
            return json_response(self, 404, {"error": f"no GET handler for /{sub}"})

        json_response(self, 404, {"error": "not found"})

    # ── POST ──
    def do_POST(self):
        url    = urlparse(self.path)
        path   = url.path
        params = parse_qs(url.query)

        if path == "/calibration/reset":
            with lock:
                for c in channels:
                    c["calibration"].clear()
            save_calibration()
            return json_response(self, 200, {"status": "cleared"})

        m = CHANNEL_PATH_RE.match(path)
        legacy = legacy_single_channel_path(path)
        if not m and legacy is not None:
            idx, sub = legacy
        elif m:
            idx, sub = int(m.group(1)), m.group(2)
        else:
            idx, sub = None, None

        if idx is not None:
            if find_channel(idx) is None:
                return json_response(self, 404, {"error": f"channel {idx} not found"})

            if sub == "threshold":
                value = params.get("value", [None])[0]
                if value is None:
                    return json_response(self, 400, {"error": "missing ?value="})
                try:
                    thr = float(value)
                except ValueError:
                    return json_response(self, 400, {"error": f"invalid value: {value!r}"})
                with lock:
                    channels[idx]["threshold"] = thr
                save_calibration()
                return json_response(self, 200,
                                     {"channel": idx, "threshold": thr})

            if sub == "record":
                label   = params.get("label",   ["sample"])[0]
                seconds = float(params.get("seconds", ["5"])[0])
                code, body = record_channel(idx, label, seconds)
                return json_response(self, code, body)

            if sub == "calibration/reset":
                with lock:
                    channels[idx]["calibration"].clear()
                save_calibration()
                return json_response(self, 200,
                                     {"channel": idx, "status": "cleared"})

            return json_response(self, 404, {"error": f"no POST handler for /{sub}"})

        json_response(self, 404, {"error": "not found"})


# ── main ─────────────────────────────────────────────────────────────────────
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    load_calibration()
    print(f"EMG API  →  http://{API_BIND}:{API_PORT}")
    print(f"ESP32    →  {ESP_HOST}:{ESP_PORT}\n")
    print("Endpoints:")
    print("  GET  /live")
    print("  GET  /channels")
    print("  GET  /channel/<id>")
    print("  GET  /channel/<id>/calibration")
    print("  GET  /channel/<id>/threshold")
    print("  POST /channel/<id>/threshold?value=80")
    print("  POST /channel/<id>/record?label=relaxed&seconds=5")
    print("  POST /channel/<id>/calibration/reset")
    print("  POST /calibration/reset\n")
    ThreadedHTTPServer((API_BIND, API_PORT), Handler).serve_forever()
