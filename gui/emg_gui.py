#!/usr/bin/env python3
"""
EMG Live GUI — multi-channel, tkinter + embedded matplotlib.

Reads from emg_api.py (default localhost:5555). Channel count, labels and
per-channel thresholds are discovered from the API at runtime — no GUI code
needs to change when channels are added in firmware/config.h.

Usage: python3 emg_gui.py [api_host] [api_port]
"""
from __future__ import annotations

import collections
import json
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import font as tkfont
from urllib.request import Request, urlopen

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ── config ───────────────────────────────────────────────────────────────────
API_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
API_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
BASE     = f"http://{API_HOST}:{API_PORT}"
WINDOW   = 300
CAL_SECS = 5
WIN_W, WIN_H = 1240, 760
BOT_H, SIDE_W = 110, 240

THEME = {
    "bg":       "#0d1117",
    "panel":    "#161b22",
    "border":   "#30363d",
    "fg":       "#c9d1d9",
    "muted":    "#8b949e",
    "accent":   "#58a6ff",
    "ok":       "#3fb950",
    "warn":     "#f85149",
    "tense_bg": "#b91c1c",
    "rest_bg":  "#166534",
    "lead_bg":  "#6e4018",
    "off_bg":   "#21262d",
}

# Color palette for channels — extend when needed.
CH_COLORS = [
    "#3fb950",   # green
    "#58a6ff",   # blue
    "#d29922",   # amber
    "#bc8cff",   # purple
    "#ff7b72",   # coral
    "#39c5cf",   # teal
    "#f0883e",   # orange
    "#a5d6ff",   # sky
]


# ── API helpers ──────────────────────────────────────────────────────────────
def api_get(path: str):
    with urlopen(f"{BASE}{path}", timeout=2) as r:
        return json.loads(r.read())


def api_post(path: str):
    req = Request(f"{BASE}{path}", method="POST", data=b"")
    with urlopen(req, timeout=CAL_SECS + 5) as r:
        return json.loads(r.read())


# ── shared state ─────────────────────────────────────────────────────────────
lock      = threading.Lock()
channels: list[dict] = []                # snapshots from /live
ch_meta:  list[dict] = []                # {"id": int, "label": str}
raw_bufs: list[collections.deque] = []
rms_bufs: list[collections.deque] = []
connected = {"value": False}
dirty = {"plot": False, "rebuild": False}
drag  = {"active_idx": None, "enabled": False}
cal   = {"step": 0, "active": False, "msg": "", "sub": "", "channel": 0}


def init_buffers(n: int) -> None:
    global raw_bufs, rms_bufs
    raw_bufs = [collections.deque([2048.0] * WINDOW, maxlen=WINDOW) for _ in range(n)]
    rms_bufs = [collections.deque([0.0] * WINDOW, maxlen=WINDOW) for _ in range(n)]


# ── poll thread ──────────────────────────────────────────────────────────────
def poll_loop() -> None:
    global ch_meta
    while True:
        try:
            d = api_get("/live")
            with lock:
                connected["value"] = bool(d.get("connected"))
                new_chs = d.get("channels", [])
                # Detect channel-count or label changes → trigger GUI rebuild.
                new_meta = [{"id": c["id"], "label": c["label"]} for c in new_chs]
                if new_meta != ch_meta:
                    ch_meta = new_meta
                    init_buffers(len(new_meta))
                    dirty["rebuild"] = True

                for i, snap in enumerate(new_chs):
                    if i >= len(raw_bufs):
                        break
                    raw_bufs[i].append(snap.get("raw", 2048))
                    # Plot the live RMS envelope, not the extra-smoothed value used
                    # for classification, otherwise short contractions look muted.
                    rms_bufs[i].append(snap.get("rms", 0))

                # Keep latest snapshots, but suppress threshold updates while
                # the user is actively dragging a channel's threshold line.
                active = drag["active_idx"]
                preserved_thr = (channels[active]["threshold"]
                                 if active is not None and active < len(channels)
                                 else None)
                channels[:] = []
                for i, snap in enumerate(new_chs):
                    if i == active and preserved_thr is not None:
                        snap = dict(snap)
                        snap["threshold"] = preserved_thr
                    channels.append(snap)
                dirty["plot"] = True
        except Exception as e:
            connected["value"] = False
            print(f"[poll] {e}", file=sys.stderr)
        time.sleep(0.04)


threading.Thread(target=poll_loop, daemon=True).start()


# ── calibration ──────────────────────────────────────────────────────────────
def set_cal(msg: str, sub: str = "") -> None:
    with lock:
        cal["msg"] = msg
        cal["sub"] = sub


def run_calibration(idx: int) -> None:
    label = ch_meta[idx]["label"] if idx < len(ch_meta) else f"CH{idx}"
    try:
        with lock: cal["step"] = 1
        set_cal(f"[{label}] Step 1 of 2: RELAX",
                "Press START when ready")
        while True:
            with lock:
                if cal["step"] == 2: break
            time.sleep(0.1)
        api_post(f"/channel/{idx}/calibration/reset")
        for i in range(CAL_SECS, 0, -1):
            set_cal(f"[{label}] Recording RELAXED…",
                    f"{i}s remaining — keep arm still")
            time.sleep(1)
        r1 = api_post(f"/channel/{idx}/record?label=relaxed&seconds={CAL_SECS}")

        with lock: cal["step"] = 3
        set_cal(f"[{label}] Step 2 of 2: TENSE / make fist",
                "Press START when ready")
        while True:
            with lock:
                if cal["step"] == 4: break
            time.sleep(0.1)
        for i in range(CAL_SECS, 0, -1):
            set_cal(f"[{label}] Recording TENSE…",
                    f"{i}s remaining — keep tensing")
            time.sleep(1)
        r2 = api_post(f"/channel/{idx}/record?label=tense&seconds={CAL_SECS}")

        thr = r2.get("suggested_threshold")
        with lock:
            cal["step"] = 5
            cal["active"] = False
        set_cal(f"[{label}] Calibration saved!",
                f"relaxed={r1['stats']['rms_mean']:.0f}  "
                f"tense={r2['stats']['rms_mean']:.0f}  "
                f"threshold={thr:.0f}" if thr else "")
    except Exception as e:
        with lock:
            cal["step"] = 0
            cal["active"] = False
        set_cal("Calibration failed.", str(e))


# ── threshold setter ─────────────────────────────────────────────────────────
def set_threshold(idx: int, val: float) -> None:
    val = max(0.0, min(2000.0, float(val)))
    threading.Thread(
        target=lambda: api_post(f"/channel/{idx}/threshold?value={val:.1f}"),
        daemon=True,
    ).start()
    with lock:
        if idx < len(channels):
            channels[idx]["threshold"] = val


# ── root window ──────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("EMG Monitor")
root.configure(bg=THEME["bg"])
root.geometry(f"{WIN_W}x{WIN_H}")
root.minsize(900, 600)

FONT_S  = tkfont.Font(family="monospace", size=8)
FONT_M  = tkfont.Font(family="monospace", size=9,  weight="bold")
FONT_L  = tkfont.Font(family="monospace", size=16, weight="bold")
FONT_XL = tkfont.Font(family="monospace", size=20, weight="bold")
FONT_XS = tkfont.Font(family="monospace", size=7)


# ── bottom bar (calibration controls) ────────────────────────────────────────
bot = tk.Frame(root, bg=THEME["bg"], height=BOT_H)
bot.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 6))
bot.pack_propagate(False)

state_frame = tk.Frame(bot, bg=THEME["rest_bg"], width=380, height=BOT_H)
state_frame.pack(side=tk.LEFT, padx=(0, 8))
state_frame.pack_propagate(False)
state_lbl = tk.Label(state_frame, text="connecting…",
                     bg=THEME["rest_bg"], fg="white",
                     font=FONT_L, justify="left")
state_lbl.place(relx=0.5, rely=0.5, anchor="center")

cal_frame = tk.Frame(bot, bg=THEME["panel"])
cal_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

cal_msg_lbl = tk.Label(cal_frame, text="Press CALIBRATE to begin",
                       bg=THEME["panel"], fg=THEME["muted"], font=FONT_S)
cal_msg_lbl.pack(pady=(8, 1))
cal_sub_lbl = tk.Label(cal_frame, text="",
                       bg=THEME["panel"], fg=THEME["accent"], font=FONT_XS)
cal_sub_lbl.pack()

btn_row = tk.Frame(cal_frame, bg=THEME["panel"])
btn_row.pack(pady=(4, 0))

cal_ch_var = tk.StringVar(value="CH 0")


def selected_cal_channel() -> int:
    txt = cal_ch_var.get()
    try:
        return int(txt.replace("CH", "").strip().split()[0])
    except Exception:
        return 0


def on_calibrate() -> None:
    with lock:
        if cal["active"]:
            return
        cal["active"]  = True
        cal["step"]    = 1
        cal["channel"] = selected_cal_channel()
    threading.Thread(target=run_calibration,
                     args=(cal["channel"],),
                     daemon=True).start()


def on_start() -> None:
    with lock:
        step = cal["step"]
    if step == 1:
        with lock: cal["step"] = 2
    elif step == 3:
        with lock: cal["step"] = 4


def on_reset_cal() -> None:
    threading.Thread(target=lambda: api_post("/calibration/reset"),
                     daemon=True).start()
    set_cal("All calibration reset.", "")


cal_ch_menu = tk.OptionMenu(btn_row, cal_ch_var, "CH 0")
cal_ch_menu.configure(bg=THEME["off_bg"], fg="white",
                      activebackground=THEME["border"],
                      font=FONT_M, relief=tk.FLAT, highlightthickness=0,
                      width=6)
cal_ch_menu["menu"].configure(bg=THEME["off_bg"], fg="white", font=FONT_M)
cal_ch_menu.pack(side=tk.LEFT, padx=(0, 6))

btn_cal = tk.Button(btn_row, text="CALIBRATE", command=on_calibrate,
                    bg=THEME["off_bg"], fg="white",
                    activebackground=THEME["border"],
                    font=FONT_M, relief=tk.FLAT, padx=10, pady=5,
                    cursor="hand2")
btn_cal.pack(side=tk.LEFT, padx=(0, 5))

btn_start = tk.Button(btn_row, text="START", command=on_start,
                      bg="#0d4a1a", fg="white",
                      activebackground=THEME["rest_bg"],
                      font=FONT_M, relief=tk.FLAT, padx=14, pady=5,
                      cursor="hand2")
btn_start.pack(side=tk.LEFT, padx=(0, 5))

btn_reset = tk.Button(btn_row, text="RESET ALL", command=on_reset_cal,
                      bg="#3a1a1a", fg=THEME["warn"],
                      activebackground="#5a2a2a",
                      font=FONT_M, relief=tk.FLAT, padx=10, pady=5,
                      cursor="hand2")
btn_reset.pack(side=tk.LEFT)


# ── side panel (per-channel thresholds) ──────────────────────────────────────
side = tk.Frame(root, bg=THEME["panel"], width=SIDE_W)
side.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=(6, 0))
side.pack_propagate(False)

tk.Label(side, text="THRESHOLDS", bg=THEME["panel"], fg=THEME["fg"],
         font=FONT_M).pack(pady=(12, 6))

drag_btn_text = tk.StringVar(value="DRAG  OFF")


def on_toggle_drag() -> None:
    drag["enabled"] = not drag["enabled"]
    if drag["enabled"]:
        drag_btn_text.set("DRAG  ON ")
        drag_toggle_btn.configure(bg="#0d4a1a")
    else:
        drag_btn_text.set("DRAG  OFF")
        drag_toggle_btn.configure(bg=THEME["off_bg"])


drag_toggle_btn = tk.Button(side, textvariable=drag_btn_text,
                            command=on_toggle_drag,
                            bg=THEME["off_bg"], fg="white",
                            activebackground=THEME["border"],
                            font=FONT_M, relief=tk.FLAT, padx=8, pady=3,
                            cursor="hand2")
drag_toggle_btn.pack(pady=(0, 6))

tk.Label(side, text="(drag dashed line in plot)",
         bg=THEME["panel"], fg="#555d68", font=FONT_XS,
         justify="center").pack(pady=(0, 8))

# Container that gets rebuilt whenever channel count changes.
threshold_box = tk.Frame(side, bg=THEME["panel"])
threshold_box.pack(fill=tk.BOTH, expand=True, padx=8)

threshold_widgets: list[dict] = []   # one row of widgets per channel
channel_title_texts: list = []


def rebuild_threshold_panel() -> None:
    for w in threshold_box.winfo_children():
        w.destroy()
    threshold_widgets.clear()

    for i, m in enumerate(ch_meta):
        color = CH_COLORS[i % len(CH_COLORS)]
        row = tk.Frame(threshold_box, bg=THEME["panel"])
        row.pack(fill=tk.X, pady=(0, 8))

        head = tk.Frame(row, bg=THEME["panel"])
        head.pack(fill=tk.X)
        tk.Label(head, text="●", bg=THEME["panel"], fg=color,
                 font=FONT_M).pack(side=tk.LEFT)
        tk.Label(head, text=f"CH{m['id']}  {m['label']}",
                 bg=THEME["panel"], fg=THEME["fg"], font=FONT_M
                 ).pack(side=tk.LEFT, padx=(2, 0))
        state_lbl = tk.Label(head, text="—", bg=THEME["panel"],
                             fg=THEME["muted"], font=FONT_S)
        state_lbl.pack(side=tk.RIGHT, padx=(8, 0))
        val_lbl = tk.Label(head, text="—", bg=THEME["panel"],
                           fg=THEME["warn"], font=FONT_L)
        val_lbl.pack(side=tk.RIGHT)
        rms_lbl = tk.Label(row, text="RMS live: —", bg=THEME["panel"],
                           fg=THEME["accent"], font=FONT_S, anchor="w")
        rms_lbl.pack(fill=tk.X, pady=(2, 0))

        entry_row = tk.Frame(row, bg=THEME["panel"])
        entry_row.pack(fill=tk.X, pady=(2, 0))
        entry = tk.Entry(entry_row, width=8, justify="center",
                         bg=THEME["off_bg"], fg="white",
                         insertbackground="white",
                         font=FONT_M, relief=tk.FLAT)
        entry.pack(side=tk.LEFT, padx=(0, 4))

        def make_setter(ch_idx: int, ent: tk.Entry):
            def _set():
                try:
                    set_threshold(ch_idx, float(ent.get()))
                except ValueError:
                    pass
            return _set

        tk.Button(entry_row, text="SET", command=make_setter(m["id"], entry),
                  bg=THEME["off_bg"], fg="white",
                  activebackground=THEME["border"],
                  font=FONT_M, relief=tk.FLAT, padx=6, pady=2,
                  cursor="hand2").pack(side=tk.LEFT)

        threshold_widgets.append({
            "val": val_lbl,
            "entry": entry,
            "state": state_lbl,
            "rms": rms_lbl,
        })

    # Update calibration channel selector to match.
    menu = cal_ch_menu["menu"]
    menu.delete(0, "end")
    for m in ch_meta:
        label = f"CH {m['id']}"
        menu.add_command(label=label,
                         command=lambda v=label: cal_ch_var.set(v))
    if ch_meta:
        cur = cal_ch_var.get()
        valid = [f"CH {m['id']}" for m in ch_meta]
        if cur not in valid:
            cal_ch_var.set(valid[0])


# ── matplotlib figure ────────────────────────────────────────────────────────
fig    = plt.figure(facecolor=THEME["bg"])
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                            padx=(6, 2), pady=(6, 2))

ax_raw      = None                   # one Raw plot showing all channels
ax_rms_list: list = []               # one RMS subplot per channel
line_raw_list: list = []             # raw lines (one per channel)
line_rms_list: list = []             # rms lines (one per channel)
thr_lines:     list = []             # threshold dashed lines
last_points:   list = []             # latest RMS point markers
fill_polys:    list = []             # filled RMS areas
t = np.arange(WINDOW)


def style_axis(ax, title: str, ylim: tuple) -> None:
    ax.set_facecolor(THEME["panel"])
    ax.set_title(title, color=THEME["fg"], fontsize=9, pad=3, loc="left")
    ax.set_xlim(0, WINDOW)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.tick_params(colors=THEME["muted"], labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(THEME["border"])
    ax.grid(color="#21262d", linewidth=0.5)


def rms_ylim(values: list[float], threshold: float) -> tuple[float, float]:
    peak = max([threshold, 50.0] + values[-WINDOW:])
    top = min(2000.0, max(120.0, peak * 1.25))
    return (0.0, top)


def rebuild_figure() -> None:
    global ax_raw, ax_rms_list, line_raw_list, line_rms_list, thr_lines, channel_title_texts, last_points, fill_polys

    fig.clear()
    ax_rms_list, line_raw_list, line_rms_list, thr_lines, channel_title_texts, last_points, fill_polys = [], [], [], [], [], [], []

    n = max(1, len(ch_meta))
    # Layout: 1 raw plot on top + N rms subplots stacked below.
    gs = gridspec.GridSpec(1 + n, 1,
                           hspace=0.55, top=0.95, bottom=0.07,
                           left=0.07, right=0.98,
                           height_ratios=[1.4] + [1.0] * n)

    ax_raw = fig.add_subplot(gs[0])
    style_axis(ax_raw, "Raw Signal  (ADC)", (0, 4095))

    for i, m in enumerate(ch_meta):
        color = CH_COLORS[i % len(CH_COLORS)]
        line, = ax_raw.plot(t, [2048.0] * WINDOW, color=color, lw=0.6,
                            alpha=0.85, label=f"CH{m['id']} {m['label']}")
        line_raw_list.append(line)

    if ch_meta:
        leg = ax_raw.legend(loc="upper right", fontsize=7,
                            facecolor=THEME["panel"],
                            edgecolor=THEME["border"], labelcolor=THEME["fg"])
        for txt in leg.get_texts():
            txt.set_color(THEME["fg"])

    for i, m in enumerate(ch_meta):
        color = CH_COLORS[i % len(CH_COLORS)]
        ax = fig.add_subplot(gs[i + 1])
        style_axis(ax, "", (0, 700))
        title = ax.set_title(f"RMS  CH{m['id']}  {m['label']}  |  live: 0.0",
                             color=THEME["fg"], fontsize=9, pad=3, loc="left")
        line, = ax.plot(t, [0.0] * WINDOW, color=color, lw=1.8)
        point, = ax.plot([WINDOW - 1], [0.0], marker="o", ms=5, color=color)
        fill = ax.fill_between(t, [0.0] * WINDOW, 0, color=color, alpha=0.16)
        thr_line = ax.axhline(80, color=THEME["warn"], lw=1.4, ls="--",
                              picker=6)
        ax_rms_list.append(ax)
        line_rms_list.append(line)
        thr_lines.append(thr_line)
        channel_title_texts.append(title)
        last_points.append(point)
        fill_polys.append(fill)

    canvas.draw_idle()
    rebuild_threshold_panel()


# ── threshold drag (any RMS axis) ────────────────────────────────────────────
def axis_to_index(ax) -> int | None:
    for i, a in enumerate(ax_rms_list):
        if a is ax:
            return i
    return None


def on_press(event):
    if not drag["enabled"] or event.inaxes is None:
        return
    idx = axis_to_index(event.inaxes)
    if idx is None or idx >= len(channels):
        return
    thr = channels[idx].get("threshold", 80)
    _, y_disp = event.inaxes.transData.transform((0, thr))
    if abs(event.y - y_disp) < 15:
        drag["active_idx"] = idx


def on_motion(event):
    idx = drag["active_idx"]
    if idx is None or event.inaxes is None or event.ydata is None:
        return
    y = max(0, min(700, event.ydata))
    with lock:
        if idx < len(channels):
            channels[idx]["threshold"] = y


def on_release(event):
    idx = drag["active_idx"]
    if idx is not None:
        drag["active_idx"] = None
        if idx < len(channels):
            set_threshold(idx, channels[idx]["threshold"])


canvas.mpl_connect("button_press_event",   on_press)
canvas.mpl_connect("motion_notify_event",  on_motion)
canvas.mpl_connect("button_release_event", on_release)


# ── refresh loop ─────────────────────────────────────────────────────────────
def refresh() -> None:
    try:
        with lock:
            need_rebuild = dirty["rebuild"]
            dirty["rebuild"] = False
            need_redraw = dirty["plot"] or drag["active_idx"] is not None
            dirty["plot"] = False
            snap = [dict(c) for c in channels]
            is_connected = connected["value"]
            step = cal["step"]
            msg, sub = cal["msg"], cal["sub"]
            raw_lists = [list(b) for b in raw_bufs]
            rms_lists = [list(b) for b in rms_bufs]

        if need_rebuild:
            rebuild_figure()
            # Re-read the current buffers after a rebuild so plots and titles do
            # not render from a stale single-channel snapshot.
            with lock:
                snap = [dict(c) for c in channels]
                raw_lists = [list(b) for b in raw_bufs]
                rms_lists = [list(b) for b in rms_bufs]
            need_redraw = True

        if need_redraw and ax_raw is not None:
            for i, line in enumerate(line_raw_list):
                if i < len(raw_lists):
                    line.set_ydata(raw_lists[i])
                elif i < len(snap):
                    line.set_ydata([float(snap[i].get("raw", 2048.0))] * WINDOW)
            for i, line in enumerate(line_rms_list):
                if i < len(rms_lists):
                    values = rms_lists[i]
                elif i < len(snap):
                    live_rms = float(snap[i].get("rms", 0.0))
                    values = [live_rms] * WINDOW
                else:
                    continue

                line.set_ydata(values)
                thr = snap[i]["threshold"] if i < len(snap) else 80.0
                ax_rms_list[i].set_ylim(*rms_ylim(values, thr))
                if i < len(snap) and i < len(channel_title_texts) and i < len(ch_meta):
                    live_rms = float(snap[i].get("rms", 0.0))
                    channel_title_texts[i].set_text(
                        f"RMS  CH{ch_meta[i]['id']}  {ch_meta[i]['label']}  |  live: {live_rms:.1f}"
                    )
                line.set_alpha(1.0 if any(v > 0.0 for v in values[-12:]) else 0.35)
                if i < len(last_points):
                    last_points[i].set_data([WINDOW - 1], [values[-1] if values else 0.0])
                if i < len(fill_polys):
                    fill_polys[i].remove()
                    fill_polys[i] = ax_rms_list[i].fill_between(
                        t, values, 0, color=CH_COLORS[i % len(CH_COLORS)], alpha=0.16
                    )
            for i, thr_line in enumerate(thr_lines):
                if i < len(snap):
                    thr_line.set_ydata([snap[i]["threshold"]] * 2)
            canvas.draw_idle()

        # Per-channel threshold panel + state banner aggregation
        any_tense    = False
        any_lead_off = False
        active_count = 0
        for i, c in enumerate(snap):
            if i >= len(threshold_widgets):
                break
            threshold_widgets[i]["val"].configure(text=f"{c['threshold']:.0f}")
            threshold_widgets[i]["rms"].configure(
                text=f"RMS live: {float(c.get('rms', 0.0)):.1f}"
            )
            st = c.get("state")
            if st == "tense":
                state_text = "ACTIVE"
                state_color = THEME["warn"]
            elif st == "lead_off":
                state_text = "LEAD OFF"
                state_color = "#f0b36b"
            else:
                state_text = "RELAXED"
                state_color = THEME["ok"]
            threshold_widgets[i]["state"].configure(text=state_text, fg=state_color)
            if st == "tense":
                any_tense = True
                active_count += 1
            elif st == "lead_off":
                any_lead_off = True

        if not is_connected:
            color, label = THEME["off_bg"], "NO CONNECTION"
        elif any_tense and any_lead_off:
            color = THEME["tense_bg"]
            label = f"ACTIVE  {active_count}/{len(snap)}  |  LEAD OFF"
        elif any_tense:
            color = THEME["tense_bg"]
            label = (f"ACTIVE  {active_count}/{len(snap)}"
                     if len(snap) > 1 else "ACTIVE")
        elif any_lead_off:
            color, label = THEME["lead_bg"], "LEAD OFF"
        else:
            color, label = THEME["rest_bg"], "relaxed"
        state_frame.configure(bg=color)
        state_lbl.configure(bg=color, text=label)

        cal_msg_lbl.configure(text=msg or "Press CALIBRATE to begin")
        cal_sub_lbl.configure(text=sub)
        btn_start.configure(bg="#0d4a1a" if step in (1, 3) else THEME["off_bg"])

    except Exception:
        traceback.print_exc(file=sys.stderr)
    finally:
        root.after(60, refresh)


# Build the figure once before any data arrives so the canvas is not blank.
init_buffers(1)
rebuild_figure()
root.after(200, refresh)
root.mainloop()
