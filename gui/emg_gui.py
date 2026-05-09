#!/usr/bin/env python3
"""
EMG Live GUI — tkinter + embedded matplotlib
Reads from emg_api.py (localhost:5555)
Usage: python3 emg_gui.py [api_host] [api_port]
"""
import sys, threading, time, collections, json, tkinter as tk, traceback
from tkinter import font as tkfont
from urllib.request import urlopen, Request
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

API_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
API_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
BASE     = f"http://{API_HOST}:{API_PORT}"
WINDOW   = 300
CAL_SECS = 5
WIN_W, WIN_H = 1200, 740
BOT_H        = 110
SIDE_W       = 200

# ── shared state ──────────────────────────────────────────────────────────────
rms_buf  = collections.deque([0.0]    * WINDOW, maxlen=WINDOW)
raw_buf  = collections.deque([2048.0] * WINDOW, maxlen=WINDOW)
lock     = threading.Lock()
live     = {"state": "relaxed", "rms": 0.0, "rms_smooth": 0.0,
            "threshold": 80.0, "connected": False}
cal      = {"step": 0, "active": False, "msg": "", "sub": ""}
drag     = {"active": False, "enabled": False}
dirty    = {"plot": False}

# ── API helpers ───────────────────────────────────────────────────────────────
def api_get(path):
    with urlopen(f"{BASE}{path}", timeout=2) as r:
        return json.loads(r.read())

def api_post(path):
    req = Request(f"{BASE}{path}", method="POST", data=b"")
    with urlopen(req, timeout=CAL_SECS + 5) as r:
        return json.loads(r.read())

def set_threshold(val):
    val = max(0, min(2000, float(val)))
    threading.Thread(target=lambda: api_post(f"/threshold?value={val:.1f}"),
                     daemon=True).start()
    with lock:
        live["threshold"] = val

# ── poll thread ───────────────────────────────────────────────────────────────
def poll_loop():
    while True:
        try:
            d = api_get("/live")
            with lock:
                if drag["active"]:
                    d.pop("threshold", None)  # keep local value while dragging
                live.update(d)
                rms_val = d.get("rms_smooth") or d.get("rms", 0)
                rms_buf.append(rms_val)
                raw_buf.append(d.get("raw", 2048))
                dirty["plot"] = True
        except Exception as e:
            with lock:
                live["connected"] = False
            print(f"[poll] {e}", file=sys.stderr)
        time.sleep(0.04)

threading.Thread(target=poll_loop, daemon=True).start()

# ── calibration thread ────────────────────────────────────────────────────────
def set_cal(msg, sub=""):
    with lock:
        cal["msg"] = msg
        cal["sub"] = sub

def run_calibration():
    try:
        with lock: cal["step"] = 1
        set_cal("Step 1 of 2: RELAX your arm.", "Press START when ready")
        while True:
            with lock:
                if cal["step"] == 2: break
            time.sleep(0.1)
        api_post("/calibration/reset")
        for i in range(CAL_SECS, 0, -1):
            set_cal("Recording RELAXED…", f"{i}s remaining — keep arm still")
            time.sleep(1)
        r1 = api_post(f"/record?label=relaxed&seconds={CAL_SECS}")

        with lock: cal["step"] = 3
        set_cal("Step 2 of 2: TENSE arm / make fist.", "Press START when ready")
        while True:
            with lock:
                if cal["step"] == 4: break
            time.sleep(0.1)
        for i in range(CAL_SECS, 0, -1):
            set_cal("Recording TENSE…", f"{i}s remaining — keep tensing")
            time.sleep(1)
        r2 = api_post(f"/record?label=tense&seconds={CAL_SECS}")

        thr = r2.get("suggested_threshold") or live["threshold"]
        set_threshold(thr)
        with lock:
            cal["step"] = 5
            cal["active"] = False
        set_cal("Calibration saved!",
                f"relaxed={r1['stats']['rms_mean']:.0f}  "
                f"tense={r2['stats']['rms_mean']:.0f}  "
                f"threshold={thr:.0f}")
    except Exception as e:
        with lock:
            cal["step"] = 0
            cal["active"] = False
        set_cal("Calibration failed.", str(e))

# ── root window ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("EMG Monitor")
root.configure(bg="#0d1117")
root.geometry(f"{WIN_W}x{WIN_H}")
root.resizable(False, False)

FONT_MONO_S  = tkfont.Font(family="monospace", size=8)
FONT_MONO_M  = tkfont.Font(family="monospace", size=9,  weight="bold")
FONT_MONO_L  = tkfont.Font(family="monospace", size=18, weight="bold")
FONT_MONO_XS = tkfont.Font(family="monospace", size=7)

# ── bottom panel (packed first → always visible) ──────────────────────────────
bot = tk.Frame(root, bg="#0d1117", height=BOT_H)
bot.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 6))
bot.pack_propagate(False)

# state banner
state_frame = tk.Frame(bot, bg="#166534", width=380, height=BOT_H)
state_frame.pack(side=tk.LEFT, padx=(0, 8))
state_frame.pack_propagate(False)
state_lbl = tk.Label(state_frame, text="relaxed  0",
    bg="#166534", fg="white", font=FONT_MONO_L)
state_lbl.place(relx=0.5, rely=0.5, anchor="center")

# calibration controls
cal_frame = tk.Frame(bot, bg="#161b22")
cal_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

cal_msg_lbl = tk.Label(cal_frame, text="Press CALIBRATE to begin",
    bg="#161b22", fg="#8b949e", font=FONT_MONO_S)
cal_msg_lbl.pack(pady=(10, 1))
cal_sub_lbl = tk.Label(cal_frame, text="", bg="#161b22", fg="#58a6ff",
    font=FONT_MONO_XS)
cal_sub_lbl.pack()

btn_row = tk.Frame(cal_frame, bg="#161b22")
btn_row.pack(pady=(4, 0))

def on_calibrate():
    with lock:
        if cal["active"]: return
        cal["active"] = True
        cal["step"]   = 1
    threading.Thread(target=run_calibration, daemon=True).start()

def on_start():
    with lock: step = cal["step"]
    if step == 1:
        with lock: cal["step"] = 2
    elif step == 3:
        with lock: cal["step"] = 4

def on_reset_cal():
    threading.Thread(target=lambda: api_post("/calibration/reset"),
                     daemon=True).start()
    set_cal("Calibration reset.", "")

btn_cal = tk.Button(btn_row, text="CALIBRATE", command=on_calibrate,
    bg="#21262d", fg="white", activebackground="#30363d",
    font=FONT_MONO_M, relief=tk.FLAT, padx=10, pady=5, cursor="hand2")
btn_cal.pack(side=tk.LEFT, padx=(0, 5))

btn_start = tk.Button(btn_row, text="START", command=on_start,
    bg="#0d4a1a", fg="white", activebackground="#166534",
    font=FONT_MONO_M, relief=tk.FLAT, padx=14, pady=5, cursor="hand2")
btn_start.pack(side=tk.LEFT, padx=(0, 5))

btn_reset = tk.Button(btn_row, text="RESET CAL", command=on_reset_cal,
    bg="#3a1a1a", fg="#f85149", activebackground="#5a2a2a",
    font=FONT_MONO_M, relief=tk.FLAT, padx=10, pady=5, cursor="hand2")
btn_reset.pack(side=tk.LEFT)

# ── side panel (right) ────────────────────────────────────────────────────────
side = tk.Frame(root, bg="#161b22", width=SIDE_W)
side.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=(6, 0))
side.pack_propagate(False)

tk.Label(side, text="THRESHOLD", bg="#161b22", fg="#c9d1d9",
    font=FONT_MONO_M).pack(pady=(14, 4))

thr_val_lbl = tk.Label(side, text="80", bg="#161b22", fg="#f85149",
    font=tkfont.Font(family="monospace", size=22, weight="bold"))
thr_val_lbl.pack()

tk.Label(side, text="manual input:", bg="#161b22", fg="#8b949e",
    font=FONT_MONO_XS).pack(pady=(10, 2))

thr_entry = tk.Entry(side, width=8, justify="center",
    bg="#21262d", fg="white", insertbackground="white",
    font=FONT_MONO_M, relief=tk.FLAT)
thr_entry.pack()

def on_set_thr():
    try:
        val = float(thr_entry.get())
        set_threshold(val)
    except ValueError:
        pass

tk.Button(side, text="SET", command=on_set_thr,
    bg="#21262d", fg="white", activebackground="#30363d",
    font=FONT_MONO_M, relief=tk.FLAT, padx=8, pady=4,
    cursor="hand2").pack(pady=(4, 0))

tk.Frame(side, bg="#30363d", height=1).pack(fill=tk.X, padx=10, pady=14)

tk.Label(side, text="drag threshold line:", bg="#161b22", fg="#8b949e",
    font=FONT_MONO_XS).pack(pady=(0, 4))

drag_btn_text = tk.StringVar(value="DRAG  OFF")
drag_btn_color = {"bg": "#21262d"}

def on_toggle_drag():
    drag["enabled"] = not drag["enabled"]
    if drag["enabled"]:
        drag_btn_text.set("DRAG  ON ")
        drag_toggle_btn.configure(bg="#0d4a1a")
    else:
        drag_btn_text.set("DRAG  OFF")
        drag_toggle_btn.configure(bg="#21262d")

drag_toggle_btn = tk.Button(side, textvariable=drag_btn_text,
    command=on_toggle_drag,
    bg="#21262d", fg="white", activebackground="#30363d",
    font=FONT_MONO_M, relief=tk.FLAT, padx=8, pady=4, cursor="hand2")
drag_toggle_btn.pack()

tk.Label(side, text="(click & drag red line\nin RMS plot)",
    bg="#161b22", fg="#555d68", font=FONT_MONO_XS,
    justify="center").pack(pady=(4, 0))

# ── matplotlib figure ─────────────────────────────────────────────────────────
plot_w = WIN_W - SIDE_W - 18
FIG_H  = (WIN_H - BOT_H - 20) / 100
fig    = plt.figure(figsize=(plot_w / 100, FIG_H), facecolor="#0d1117")
gs     = gridspec.GridSpec(2, 1, hspace=0.45,
         top=0.93, bottom=0.09, left=0.07, right=0.98)

ax_raw = fig.add_subplot(gs[0])
ax_rms = fig.add_subplot(gs[1])
t      = np.arange(WINDOW)

for ax, title, ylim in [
    (ax_raw, "Raw Signal  (ADC)",       (0, 4095)),
    (ax_rms, "RMS Envelope (smoothed)", (0, 700)),
]:
    ax.set_facecolor("#161b22")
    ax.set_title(title, color="#c9d1d9", fontsize=9, pad=3)
    ax.set_xlim(0, WINDOW); ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.tick_params(colors="#8b949e", labelsize=8)
    for sp in ax.spines.values(): sp.set_color("#30363d")
    ax.grid(color="#21262d", linewidth=0.5)

line_raw, = ax_raw.plot(t, list(raw_buf), color="#58a6ff", lw=0.7)
line_rms, = ax_rms.plot(t, list(rms_buf), color="#3fb950", lw=1.1)
thr_line   = ax_rms.axhline(80, color="#f85149", lw=1.5, ls="--",
                             label="threshold", picker=6)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                            padx=(6, 2), pady=(6, 2))

# ── threshold line drag ───────────────────────────────────────────────────────
def on_press(event):
    if not drag["enabled"] or event.inaxes != ax_rms: return
    thr = live.get("threshold", 80)
    # click within 15 px of threshold line → start drag
    _, y_disp = ax_rms.transData.transform((0, thr))
    if abs(event.y - y_disp) < 15:
        drag["active"] = True

def on_motion(event):
    if not drag["active"] or event.inaxes != ax_rms: return
    y_data = max(0, min(700, event.ydata or 0))
    with lock:
        live["threshold"] = y_data

def on_release(event):
    if drag["active"]:
        drag["active"] = False
        thr = live.get("threshold", 80)
        set_threshold(thr)

canvas.mpl_connect("button_press_event",   on_press)
canvas.mpl_connect("motion_notify_event",  on_motion)
canvas.mpl_connect("button_release_event", on_release)

# ── refresh loop ──────────────────────────────────────────────────────────────
STATE_COLORS = {
    "tense":    "#b91c1c",
    "relaxed":  "#166534",
    "lead_off": "#6e4018",
    "no_conn":  "#21262d",
}

def refresh():
    try:
        with lock:
            raw  = list(raw_buf)
            rms  = list(rms_buf)
            s    = dict(live)
            step = cal["step"]
            msg  = cal["msg"]
            sub  = cal["sub"]

        thr = s.get("threshold", 80)

        with lock:
            need_redraw = dirty["plot"] or drag["active"]
            dirty["plot"] = False

        if need_redraw:
            line_raw.set_ydata(raw)
            line_rms.set_ydata(rms)
            thr_line.set_ydata([thr, thr])
            canvas.draw_idle()

        # state banner
        rms_val = s.get("rms_smooth") or s.get("rms", 0)
        if not s["connected"]:
            color, label = STATE_COLORS["no_conn"], "NO CONNECTION"
        elif s.get("state") == "lead_off":
            color, label = STATE_COLORS["lead_off"], "LEAD OFF"
        elif s.get("state") == "tense":
            color, label = STATE_COLORS["tense"], f"ACTIVE  {rms_val:.0f}"
        else:
            color, label = STATE_COLORS["relaxed"], f"relaxed  {rms_val:.0f}"
        state_frame.configure(bg=color)
        state_lbl.configure(bg=color, text=label)

        # side panel threshold value
        thr_val_lbl.configure(text=f"{thr:.0f}")

        # calibration text + button states
        cal_msg_lbl.configure(text=msg or "Press CALIBRATE to begin")
        cal_sub_lbl.configure(text=sub)
        btn_start.configure(bg="#0d4a1a" if step in (1, 3) else "#21262d")

    except Exception:
        traceback.print_exc(file=sys.stderr)
    finally:
        root.after(60, refresh)

root.after(200, refresh)
root.mainloop()
