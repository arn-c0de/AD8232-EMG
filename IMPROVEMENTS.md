# Codebase Improvements Review

This document summarizes concrete improvement opportunities found during a review of the codebase. No application code was changed.

## Findings

1. `emg_api.py`: `/record` samples duplicate the newest item instead of collecting a real time-series

At `emg_api.py:169`, the `/record` handler copies `history[-1]` every 50 ms until the recording window ends. That produces many duplicates of the latest sample instead of a true measurement series. As a result, the reported mean, standard deviation, and calibration values can be misleading.

Recommended improvement:
- Collect samples by timestamp from `history`, or append only new samples arriving after the recording starts.

2. `emg_api.py`: disconnect handling can leave stale connection state and trigger a tight reconnect loop

At `emg_api.py:68` and `emg_api.py:94`, a clean `recv()` EOF only breaks the inner loop. The code may leave `connected=True` longer than it should and can re-enter connection attempts without an intentional backoff on that path.

Recommended improvement:
- On EOF, close the socket, set `state["connected"] = False`, and apply a short reconnect delay before retrying.

3. `emg_api.py`: invalid threshold input can crash the request with HTTP 500

At `emg_api.py:208`, `float(value)` is not guarded. Invalid input such as `POST /threshold?value=abc` will raise `ValueError` and likely return an internal server error instead of a client error.

Recommended improvement:
- Wrap threshold parsing in `try/except ValueError` and return `400 Bad Request` with a clear error message.

4. `firmware/emg_ota/emg_ota.ino`: `LEAD_OFF` is sent at full sample rate

At `firmware/emg_ota/emg_ota.ino:54`, `LEAD_OFF` is emitted every loop iteration while the electrodes are detached. That generates unnecessary serial and TCP traffic and hurts responsiveness in the failure state.

Recommended improvement:
- Send `LEAD_OFF` only on state transitions, or throttle it to a small rate such as 5 to 10 Hz.

5. `gui/emg_gui.py`: exceptions are swallowed silently

At `gui/emg_gui.py:51` and `gui/emg_gui.py:253`, broad exceptions are ignored completely. That makes debugging difficult and can hide UI or networking faults.

Recommended improvement:
- Log the exception, or surface a concise error state in the GUI while keeping the app running.

6. `gui/emg_gui.py`: redraw frequency is higher than necessary

At `gui/emg_gui.py:226`, the plot is redrawn every 60 ms regardless of whether the visual state materially changed. For this use case, a lower redraw rate or conditional redraw would likely reduce CPU usage and improve GUI smoothness on weaker systems.

Recommended improvement:
- Redraw only when fresh data arrives, or reduce the refresh rate if end-to-end responsiveness remains acceptable.

7. `monitor.sh`: process management is too broad

At `monitor.sh:13` and `monitor.sh:44`, `pkill -f` is used with generic script names. That can terminate unrelated processes if the same names appear elsewhere on the machine.

Recommended improvement:
- Use PID files, targeted process ownership, or more specific matching per project instance.

8. `monitor.sh`: the default device host is hard-coded to one IP address

At `monitor.sh:18`, the default host is a fixed LAN IP. That reduces portability across networks and setups.

Recommended improvement:
- Default to `emg-esp32.local` and override with environment variables or CLI arguments when needed.

9. `firmware/emg_ota/emg_ota.ino`: Wi-Fi connect loop can block forever

At `firmware/emg_ota/emg_ota.ino:24`, startup waits indefinitely for Wi-Fi. If the network is unavailable, the device never transitions into a clear failure mode.

Recommended improvement:
- Add a timeout, retry strategy, and visible failure behavior for startup robustness.

10. Overall structure: responsibilities are still tightly coupled

The codebase is small, but a few responsibilities are combined in the same modules:
- `emg_api.py` mixes device reading, mutable state, calibration persistence, and HTTP handling.
- `gui/emg_gui.py` mixes polling, calibration workflow, state management, and rendering.
- Constants such as ports, thresholds, and timeouts are scattered across files.

Recommended improvement:
- Separate reader/state/API concerns in the backend.
- Separate polling/calibration/rendering concerns in the GUI.
- Centralize shared configuration defaults where practical.

## Verification

Syntax verification completed successfully with:

```bash
python3 -m py_compile emg_api.py gui/emg_gui.py
```

## Scope

This review was documentation-only. No application code was modified.
