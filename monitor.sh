#!/usr/bin/env bash
# Live EMG monitor — connects to ESP32 TCP stream over WiFi
set -euo pipefail

RESTART=0; STOP=0
for arg in "$@"; do
  [[ "$arg" == "--restart" ]] && RESTART=1
  [[ "$arg" == "--stop"    ]] && STOP=1
done

if [[ $STOP -eq 1 ]]; then
  echo "==> Stopping API and GUI..."
  pkill -f "emg_api.py" 2>/dev/null && echo "API stopped" || echo "API not running"
  pkill -f "emg_gui.py" 2>/dev/null && echo "GUI stopped" || echo "GUI not running"
  exit 0
fi

HOST="${EMG_HOST:-emg-esp32.local}"
PORT=8888
API_HOST="${EMG_API_HOST:-127.0.0.1}"
API_PORT="${EMG_API_PORT:-5555}"
BAR_WIDTH=40
THRESHOLD=80   # RMS above this = ACTIVE

# ANSI colors
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; RESET=$'\033[0m'

bar() {
  local val=$1 max=300
  local filled=$(( val * BAR_WIDTH / max ))
  [[ $filled -gt $BAR_WIDTH ]] && filled=$BAR_WIDTH
  local empty=$(( BAR_WIDTH - filled ))
  printf '%0.s█' $(seq 1 $filled 2>/dev/null) || true
  printf '%0.s░' $(seq 1 $empty  2>/dev/null) || true
}

echo -e "${CYAN}EMG Monitor → ${HOST}:${PORT}${RESET}"
echo -e "Threshold: ${THRESHOLD} RMS  |  Ctrl+C to quit\n"

# --restart: kill existing API + GUI before starting fresh
if [[ $RESTART -eq 1 ]]; then
  echo -e "${YELLOW}==> --restart: stopping existing API and GUI...${RESET}"
  pkill -f "emg_api.py" 2>/dev/null || true
  pkill -f "emg_gui.py" 2>/dev/null || true
  sleep 1
fi

if ! nc -z "$HOST" "$PORT" 2>/dev/null; then
  echo -e "${RED}ERROR: cannot reach ${HOST}:${PORT}${RESET}"
  echo "Is the ESP32 powered and on WiFi?"
  exit 1
fi

# start local API if it is not already running
API_SCRIPT="$(dirname "$0")/emg_api.py"
API_STARTED=0
if ! nc -z "$API_HOST" "$API_PORT" 2>/dev/null; then
  if [[ -f "$API_SCRIPT" ]]; then
    echo -e "${CYAN}==> Starting API on ${API_HOST}:${API_PORT}...${RESET}"
    python3 "$API_SCRIPT" "$HOST" "$PORT" "$API_PORT" "$API_HOST" &
    API_PID=$!
    API_STARTED=1
    for _ in $(seq 1 30); do
      if nc -z "$API_HOST" "$API_PORT" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if ! nc -z "$API_HOST" "$API_PORT" 2>/dev/null; then
      echo -e "${RED}ERROR: API did not start on ${API_HOST}:${API_PORT}${RESET}"
      kill "$API_PID" 2>/dev/null || true
      exit 1
    fi
  fi
fi

# launch GUI in background
GUI="$(dirname "$0")/gui/emg_gui.py"
if [[ -f "$GUI" ]]; then
  GUI_LOG="/tmp/emg_gui.log"
  echo -e "${CYAN}==> Starting GUI...${RESET}"
  python3 "$GUI" "$API_HOST" "$API_PORT" >"$GUI_LOG" 2>&1 &
  GUI_PID=$!
  trap 'kill $GUI_PID 2>/dev/null; [[ "${API_STARTED:-0}" -eq 1 ]] && kill "${API_PID:-0}" 2>/dev/null' EXIT
  sleep 1
  if ! kill -0 "$GUI_PID" 2>/dev/null; then
    echo -e "${RED}ERROR: GUI failed to start${RESET}"
    [[ -f "$GUI_LOG" ]] && sed -n '1,120p' "$GUI_LOG"
    exit 1
  fi
  echo -e "${CYAN}==> GUI uses the single ESP32 TCP stream via the local API.${RESET}"
  echo -e "${CYAN}==> Terminal live view is disabled while the GUI is running.${RESET}"
  wait "$GUI_PID"
  exit 0
fi

nc "$HOST" "$PORT" | while IFS=',' read -r raw rms; do
  # lead-off line
  if [[ "$raw" == "LEAD_OFF" ]]; then
    printf "\r${YELLOW}  ⚠  LEAD OFF — check electrodes ${RESET}%-20s" " "
    continue
  fi

  # strip decimals for integer compare
  rms_int=${rms%.*}
  rms_int=${rms_int:-0}

  if (( rms_int >= THRESHOLD )); then
    state="${RED}${BOLD}ACTIVE  ██${RESET}"
    color=$RED
  else
    state="${GREEN}relaxed   ${RESET}"
    color=$GREEN
  fi

  printf "\r${color}[$(bar $rms_int)]${RESET}  RMS: %5s  RAW: %4s  %s  " \
    "$rms" "$raw" "$state"
done
