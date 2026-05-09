#!/usr/bin/env python3
"""
EMG Live GUI with built-in calibration wizard.
Reads from emg_api.py  (localhost:5555)
Usage: python3 emg_gui.py [api_host] [api_port]
"""
import sys, threading, time, collections, json
from urllib.request import urlopen, Request
from urllib.error import URLError
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import numpy as np

API_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
API_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
BASE     = f"http://{API_HOST}:{API_PORT}"

WINDOW   = 300   # display samples
POLL_HZ  = 25
CAL_SECS = 5

# ── shared state ──────────────────────────────────────────────────────────────
rms_buf = collections.deque([0.0]    * WINDOW, maxlen=WINDOW)
raw_buf = collections.deque([2048.0] * WINDOW, maxlen=WINDOW)
lock    = threading.Lock()
live    = {"state": "relaxed", "rms": 0.0, "rms_smooth": 0.0,
           "threshold": 80.0, "connected": False}

# calibration wizard state
cal = {
    "active":   False,
    "step":     0,       # 0=idle 1=await_relaxed 2=recording_relaxed
                         #        3=await_tense   4=recording_tense 5=done
    "countdown": 0,
    "result":   {},
    "msg":      "",
    "sub":      "",
}

# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(path):
    with urlopen(f"{BASE}{path}", timeout=2) as r:
        return json.loads(r.read())

def api_post(path):
    req = Request(f"{BASE}{path}", method="POST", data=b"")
    with urlopen(req, timeout=CAL_SECS + 5) as r:
        return json.loads(r.read())

# ── poll thread ───────────────────────────────────────────────────────────────
def poll_loop():
    while True:
        try:
            d = api_get("/live")
            with lock:
                live.update(d)
                rms_buf.append(d["rms_smooth"])
                raw_buf.append(d["raw"])
        except Exception:
            with lock:
                live["connected"] = False
        time.sleep(1.0 / POLL_HZ)

threading.Thread(target=poll_loop, daemon=True).start()

# ── calibration thread ────────────────────────────────────────────────────────
def run_calibration():
    def set_msg(msg, sub=""):
        with lock:
            cal["msg"] = msg
            cal["sub"] = sub

    def countdown(label):
        for i in range(CAL_SECS, 0, -1):
            set_msg(f"Recording {label}…", f"{i}s remaining — hold still")
            time.sleep(1)

    try:
        # ── Step 1: relaxed ──────────────────────────────────────────────────
        with lock: cal["step"] = 1
        set_msg("Step 1 of 2: RELAX your arm completely.",
                "Press  START  when ready")

        while True:
            with lock:
                if cal["step"] == 2:
                    break
            time.sleep(0.1)

        set_msg("Relax arm…", f"Recording for {CAL_SECS}s")
        api_post("/calibration/reset")
        countdown("relaxed")
        r1 = api_post(f"/record?label=relaxed&seconds={CAL_SECS}")

        # ── Step 2: tense ────────────────────────────────────────────────────
        with lock: cal["step"] = 3
        set_msg("Step 2 of 2: TENSE arm / make a fist.",
                "Press  START  when ready")

        while True:
            with lock:
                if cal["step"] == 4:
                    break
            time.sleep(0.1)

        set_msg("Tense arm…", f"Recording for {CAL_SECS}s")
        countdown("tense")
        r2 = api_post(f"/record?label=tense&seconds={CAL_SECS}")

        # ── done ─────────────────────────────────────────────────────────────
        thr = r2.get("suggested_threshold") or live["threshold"]
        api_post(f"/threshold?value={thr}")

        with lock:
            cal["result"] = {
                "relaxed_mean": r1["stats"]["rms_mean"],
                "tense_mean":   r2["stats"]["rms_mean"],
                "threshold":    thr,
            }
            cal["step"] = 5
            cal["active"] = False

        set_msg("Calibration saved!",
                f"relaxed={r1['stats']['rms_mean']:.0f}  "
                f"tense={r2['stats']['rms_mean']:.0f}  "
                f"threshold={thr:.0f}")

    except Exception as e:
        with lock:
            cal["step"] = 0
            cal["active"] = False
        set_msg("Calibration failed", str(e))

# ── figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(13, 8), facecolor="#0d1117")
fig.canvas.manager.set_window_title("EMG Monitor")

gs = gridspec.GridSpec(3, 2, hspace=0.5, wspace=0.35,
     top=0.92, bottom=0.08, left=0.07, right=0.97,
     height_ratios=[2.5, 2, 2],
     width_ratios=[2.2, 1])

ax_raw   = fig.add_subplot(gs[0, :])    # full width
ax_rms   = fig.add_subplot(gs[1, :])    # full width
ax_state = fig.add_subplot(gs[2, 0])    # left: state banner
ax_cal   = fig.add_subplot(gs[2, 1])    # right: calibration panel

t = np.arange(WINDOW)

def style(ax, title, ylim):
    ax.set_facecolor("#161b22")
    ax.set_title(title, color="#c9d1d9", fontsize=9, pad=3)
    ax.set_xlim(0, WINDOW); ax.set_ylim(*ylim)
    ax.set_xticks([]); ax.tick_params(colors="#8b949e", labelsize=8)
    for sp in ax.spines.values(): sp.set_color("#30363d")
    ax.grid(color="#21262d", linewidth=0.5)

style(ax_raw, "Raw Signal  (ADC)", (0, 4095))
style(ax_rms, "RMS Envelope  (smoothed)", (0, 700))

line_raw, = ax_raw.plot(t, list(raw_buf), color="#58a6ff", lw=0.7)
line_rms, = ax_rms.plot(t, list(rms_buf), color="#3fb950", lw=1.1)
thr_line   = ax_rms.axhline(live["threshold"], color="#f85149",
                             lw=1.0, ls="--", label="threshold")
ax_rms.legend(handles=[thr_line], facecolor="#161b22",
              labelcolor="#c9d1d9", fontsize=8, loc="upper left")

# ── state banner ──────────────────────────────────────────────────────────────
ax_state.set_facecolor("#161b22"); ax_state.axis("off")
state_patch = mpatches.FancyBboxPatch(
    (0.02, 0.1), 0.96, 0.8, boxstyle="round,pad=0.02",
    facecolor="#166534", edgecolor="none", transform=ax_state.transAxes)
ax_state.add_patch(state_patch)
state_txt = ax_state.text(0.5, 0.5, "relaxed",
    ha="center", va="center", fontsize=20, fontweight="bold",
    color="white", transform=ax_state.transAxes)

# ── calibration panel ─────────────────────────────────────────────────────────
ax_cal.set_facecolor("#161b22"); ax_cal.axis("off")
cal_title = ax_cal.text(0.5, 0.92, "CALIBRATION",
    ha="center", va="top", fontsize=9, fontweight="bold",
    color="#c9d1d9", transform=ax_cal.transAxes)
cal_msg = ax_cal.text(0.5, 0.70, "Press CALIBRATE to start",
    ha="center", va="top", fontsize=8, color="#8b949e",
    transform=ax_cal.transAxes, wrap=True)
cal_sub = ax_cal.text(0.5, 0.48, "",
    ha="center", va="top", fontsize=7.5, color="#58a6ff",
    transform=ax_cal.transAxes, wrap=True)

# buttons
ax_btn_cal   = fig.add_axes([0.735, 0.115, 0.115, 0.055])
ax_btn_start = fig.add_axes([0.860, 0.115, 0.115, 0.055])

btn_cal   = Button(ax_btn_cal,   "CALIBRATE", color="#21262d", hovercolor="#30363d")
btn_start = Button(ax_btn_start, "START",     color="#0d4a1a", hovercolor="#166534")

for b in (btn_cal, btn_start):
    b.label.set_color("white")
    b.label.set_fontsize(8)
    b.label.set_fontweight("bold")

def on_calibrate(_):
    with lock:
        if cal["active"]:
            return
        cal["active"] = True
        cal["step"]   = 1
        cal["msg"]    = ""
        cal["sub"]    = ""
    threading.Thread(target=run_calibration, daemon=True).start()

def on_start(_):
    with lock:
        step = cal["step"]
    if step == 1:
        with lock: cal["step"] = 2
    elif step == 3:
        with lock: cal["step"] = 4

btn_cal.on_clicked(on_calibrate)
btn_start.on_clicked(on_start)

fig.suptitle(f"EMG Monitor  ·  {API_HOST}:{API_PORT}",
             color="#c9d1d9", fontsize=10)

# ── animation ─────────────────────────────────────────────────────────────────
def update(_):
    with lock:
        raw  = list(raw_buf)
        rms  = list(rms_buf)
        s    = dict(live)
        step = cal["step"]
        msg  = cal["msg"]
        sub  = cal["sub"]

    line_raw.set_ydata(raw)
    line_rms.set_ydata(rms)
    thr_line.set_ydata([s["threshold"], s["threshold"]])

    # state banner
    if not s["connected"]:
        state_patch.set_facecolor("#21262d")
        state_txt.set_text("NO CONNECTION")
        state_txt.set_fontsize(14)
    elif s["state"] == "lead_off":
        state_patch.set_facecolor("#6e4018")
        state_txt.set_text("LEAD OFF")
        state_txt.set_fontsize(18)
    elif s["state"] == "tense":
        state_patch.set_facecolor("#b91c1c")
        state_txt.set_text(f"ACTIVE\n{s['rms_smooth']:.0f}")
        state_txt.set_fontsize(20)
    else:
        state_patch.set_facecolor("#166534")
        state_txt.set_text(f"relaxed\n{s['rms_smooth']:.0f}")
        state_txt.set_fontsize(18)

    # calibration panel text
    if step == 0 and not msg:
        cal_msg.set_text("Press CALIBRATE to start")
        cal_sub.set_text("")
    else:
        cal_msg.set_text(msg)
        cal_sub.set_text(sub)

    # START button color: only active during await steps
    if step in (1, 3):
        btn_start.ax.set_facecolor("#0d4a1a")
    else:
        btn_start.ax.set_facecolor("#161b22")

ani = FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
plt.show()
