#!/usr/bin/env python3
"""
EMG HTTP API — no external dependencies
Connects to ESP32 TCP stream, exposes REST endpoints for AI agents.

Endpoints:
  GET  /live                       current raw + rms + state
  POST /record?label=relaxed&seconds=5   record labeled sample, returns stats
  GET  /calibration                stored relaxed/tense baselines
  POST /calibration/reset          clear stored calibration
  GET  /threshold                  current threshold
  POST /threshold?value=80         set threshold

Start: python3 emg_api.py [esp_host] [esp_port] [api_port] [bind_host]
"""
import sys, os, socket, threading, time, json, statistics
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from collections import deque

# ── config ────────────────────────────────────────────────────────────────────
ESP_HOST   = sys.argv[1] if len(sys.argv) > 1 else "emg-esp32.local"
ESP_PORT   = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
API_PORT   = int(sys.argv[3]) if len(sys.argv) > 3 else 5555
API_BIND   = sys.argv[4] if len(sys.argv) > 4 else "127.0.0.1"
CAL_FILE   = os.path.join(os.path.dirname(__file__), "calibration.json")

# ── shared state ──────────────────────────────────────────────────────────────
state = {
    "raw": 0,
    "rms": 0.0,
    "rms_smooth": 0.0,
    "lead_off": False,
    "threshold": 80.0,
    "connected": False,
    "tense_until": 0.0,   # hold tense state until this timestamp
}
SMOOTH_ALPHA  = 0.3    # exponential smoothing (0=none, 1=raw)
HOLD_MS       = 400    # keep "tense" for at least this long after peak
calibration = {}

def load_calibration():
    global calibration
    if os.path.exists(CAL_FILE):
        with open(CAL_FILE) as f:
            data = json.load(f)
        calibration = data.get("calibration", {})
        with lock:
            state["threshold"] = data.get("threshold", 80.0)
        print(f"Calibration loaded from {CAL_FILE}  (threshold={state['threshold']})")

def save_calibration():
    with open(CAL_FILE, "w") as f:
        json.dump({"calibration": calibration, "threshold": state["threshold"]}, f, indent=2)
    print(f"Calibration saved → {CAL_FILE}")
history = deque(maxlen=5000)   # last 5 seconds @ 1kHz
lock = threading.Lock()

# ── ESP32 reader thread ────────────────────────────────────────────────────────
def esp_reader():
    while True:
        try:
            sock = socket.create_connection((ESP_HOST, ESP_PORT), timeout=5)
            with lock: state["connected"] = True
            buf = ""
            while True:
                chunk = sock.recv(512).decode("utf-8", errors="ignore")
                if not chunk: break
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line == "LEAD_OFF":
                        with lock: state["lead_off"] = True
                        continue
                    parts = line.split(",")
                    if len(parts) == 2:
                        try:
                            r, e = float(parts[0]), float(parts[1])
                            with lock:
                                state["raw"] = r
                                state["rms"] = e
                                state["rms_smooth"] = (
                                    SMOOTH_ALPHA * e +
                                    (1 - SMOOTH_ALPHA) * state["rms_smooth"]
                                )
                                if state["rms_smooth"] >= state["threshold"]:
                                    state["tense_until"] = time.time() + HOLD_MS / 1000
                                state["lead_off"] = False
                                history.append({"raw": r, "rms": e, "t": time.time()})
                        except ValueError:
                            pass
        except Exception:
            with lock: state["connected"] = False
            time.sleep(2)

threading.Thread(target=esp_reader, daemon=True).start()

# ── helpers ───────────────────────────────────────────────────────────────────
def calc_stats(samples):
    rms_vals = [s["rms"] for s in samples]
    raw_vals = [s["raw"] for s in samples]
    return {
        "count":      len(rms_vals),
        "rms_mean":   round(statistics.mean(rms_vals), 2),
        "rms_max":    round(max(rms_vals), 2),
        "rms_min":    round(min(rms_vals), 2),
        "rms_stdev":  round(statistics.stdev(rms_vals), 2) if len(rms_vals) > 1 else 0,
        "raw_mean":   round(statistics.mean(raw_vals), 2),
    }

def json_response(handler, code, data):
    body = json.dumps(data, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress per-request logs

    def do_GET(self):
        url = urlparse(self.path)
        params = parse_qs(url.query)

        if url.path == "/live":
            with lock:
                is_tense = (state["rms_smooth"] >= state["threshold"] or
                            time.time() < state["tense_until"])
                data = {
                    "raw":        state["raw"],
                    "rms":        round(state["rms"], 2),
                    "rms_smooth": round(state["rms_smooth"], 2),
                    "threshold":  state["threshold"],
                    "state":      "lead_off" if state["lead_off"]
                                  else ("tense" if is_tense else "relaxed"),
                    "connected":  state["connected"],
                }
            json_response(self, 200, data)

        elif url.path == "/calibration":
            with lock:
                json_response(self, 200, calibration)

        elif url.path == "/threshold":
            with lock:
                json_response(self, 200, {"threshold": state["threshold"]})

        else:
            json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        params = parse_qs(url.query)

        if url.path == "/record":
            label   = params.get("label",   ["sample"])[0]
            seconds = float(params.get("seconds", ["5"])[0])
            seconds = max(1.0, min(30.0, seconds))

            print(f"Recording '{label}' for {seconds}s …")
            t_end = time.time() + seconds
            samples = []
            while time.time() < t_end:
                with lock:
                    if history:
                        samples.append(history[-1])
                time.sleep(0.05)

            if not samples:
                json_response(self, 503, {"error": "no data from ESP32"})
                return

            stats = calc_stats(samples)
            with lock:
                calibration[label] = stats

            suggestion = None
            with lock:
                if "relaxed" in calibration and "tense" in calibration:
                    mid = (calibration["relaxed"]["rms_mean"] +
                           calibration["tense"]["rms_mean"]) / 2
                    suggestion = round(mid, 1)
                    if suggestion:
                        state["threshold"] = suggestion

            save_calibration()

            json_response(self, 200, {
                "label":              label,
                "duration_seconds":   seconds,
                "stats":              stats,
                "suggested_threshold": suggestion,
            })

        elif url.path == "/calibration/reset":
            with lock:
                calibration.clear()
            save_calibration()
            json_response(self, 200, {"status": "cleared"})

        elif url.path == "/threshold":
            value = params.get("value", [None])[0]
            if value is None:
                json_response(self, 400, {"error": "missing ?value="})
                return
            with lock:
                state["threshold"] = float(value)
            save_calibration()
            json_response(self, 200, {"threshold": state["threshold"]})

        else:
            json_response(self, 404, {"error": "not found"})

# ── start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    load_calibration()
    print(f"EMG API  →  http://{API_BIND}:{API_PORT}")
    print(f"ESP32    →  {ESP_HOST}:{ESP_PORT}\n")
    print("Endpoints:")
    print("  GET  /live")
    print("  POST /record?label=relaxed&seconds=5")
    print("  POST /record?label=tense&seconds=5")
    print("  GET  /calibration")
    print("  POST /calibration/reset")
    print("  POST /threshold?value=80\n")
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    ThreadedHTTPServer((API_BIND, API_PORT), Handler).serve_forever()
