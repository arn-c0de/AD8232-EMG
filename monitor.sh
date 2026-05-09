#!/usr/bin/env bash
# Live EMG monitor — connects to ESP32 TCP stream over WiFi
set -euo pipefail

HOST="${EMG_HOST:-emg-esp32.local}"
PORT=8888
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

if ! nc -z "$HOST" "$PORT" 2>/dev/null; then
  echo -e "${RED}ERROR: cannot reach ${HOST}:${PORT}${RESET}"
  echo "Is the ESP32 powered and on WiFi?"
  exit 1
fi

# launch GUI in background
GUI="$(dirname "$0")/gui/emg_gui.py"
if [[ -f "$GUI" ]]; then
  echo -e "${CYAN}==> Starting GUI...${RESET}"
  DISPLAY="${DISPLAY:-:0}" python3 "$GUI" localhost 5555 "$THRESHOLD" &
  GUI_PID=$!
  trap 'kill $GUI_PID 2>/dev/null' EXIT
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
