#!/usr/bin/env bash
#
# Hallway Watch — interactive installer
#
# One-liner (SSH into the Pi, then paste):
#   curl -fsSL https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/install.sh | bash
#
# Non-interactive (accept all defaults):
#   curl -fsSL https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/install.sh | bash -s -- -y
#
set -euo pipefail

# --- resolve project directory (clone from GitHub when curl-piped) ---------

INSTALL_DIR="${HALLWAY_WATCH_DIR:-$HOME/hallway-watch}"
REPO_URL="${HALLWAY_WATCH_REPO:-https://github.com/Byte-Developments/hallway-watch.git}"
DEFAULT_INSTALL_URL="https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/install.sh"

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  echo "==> Installing git (required to download Hallway Watch)"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y git
    return 0
  fi
  echo "git is required but could not be installed automatically." >&2
  exit 1
}

ensure_aplay() {
  if command -v aplay >/dev/null 2>&1; then
    return 0
  fi
  echo "==> aplay not found — installing alsa-utils for audio alerts"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y alsa-utils
    return 0
  fi
  echo "Warning: aplay not found and apt-get unavailable — audio alerts will not work." >&2
  echo "         Install alsa-utils manually or set audio.enabled: false in config.yaml." >&2
  return 1
}

find_project_dir() {
  local dir="$1"
  [[ -f "$dir/hallway_watch/main.py" && -f "$dir/requirements.txt" ]]
}

clone_or_update_repo() {
  ensure_git
  echo "==> Downloading Hallway Watch into ${INSTALL_DIR}"
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    git -C "${INSTALL_DIR}" pull --ff-only
  elif [[ -d "${INSTALL_DIR}" ]]; then
    rm -rf "${INSTALL_DIR}"
    git clone "${REPO_URL}" "${INSTALL_DIR}"
  else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
  fi
}

if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "bash" && "${BASH_SOURCE[0]}" != "-bash" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR=""
fi

if [[ -n "$SCRIPT_DIR" ]] && find_project_dir "$SCRIPT_DIR"; then
  PROJECT_DIR="$SCRIPT_DIR"
elif find_project_dir "$INSTALL_DIR"; then
  PROJECT_DIR="$INSTALL_DIR"
else
  clone_or_update_repo
  PROJECT_DIR="$INSTALL_DIR"
fi

if ! find_project_dir "$PROJECT_DIR"; then
  cat <<EOF
Could not find Hallway Watch after install.

Try the one-liner again:

  curl -fsSL ${DEFAULT_INSTALL_URL} | bash

EOF
  exit 1
fi

cd "$PROJECT_DIR"

# --- cli helpers ------------------------------------------------------------

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  CYAN=$'\033[36m'
  RESET=$'\033[0m'
else
  BOLD="" DIM="" GREEN="" YELLOW="" CYAN="" RESET=""
fi

banner() {
  echo
  echo "${BOLD}${CYAN}Hallway Watch installer${RESET}"
  echo "${DIM}Head detection for Raspberry Pi with browser notifications${RESET}"
  echo
}

can_prompt() {
  [[ -r /dev/tty ]]
}

read_tty() {
  # When curl-piped, stdin is the script — read prompts from the terminal instead.
  local __prompt=$1
  local __var=$2
  if can_prompt; then
    read -rp "$__prompt" "$__var" </dev/tty
  else
    read -rp "$__prompt" "$__var"
  fi
}

prompt() {
  local __var=$1
  local __text=$2
  local __default=$3
  local __input=""
  read_tty "${__text} [${__default}]: " __input
  printf -v "$__var" '%s' "${__input:-$__default}"
}

prompt_yn() {
  local __var=$1
  local __text=$2
  local __default=$3
  local __input=""
  local __hint="y/n"

  if [[ "$__default" == "y" ]]; then
    __hint="Y/n"
  elif [[ "$__default" == "n" ]]; then
    __hint="y/N"
  fi

  while true; do
    read_tty "${__text} [${__hint}]: " __input
    __input="${__input:-$__default}"
    case "${__input,,}" in
      y|yes) printf -v "$__var" '%s' "true"; return ;;
      n|no)  printf -v "$__var" '%s' "false"; return ;;
      *) echo "Please enter y or n." ;;
    esac
  done
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Install (on the Pi):

  curl -fsSL ${DEFAULT_INSTALL_URL} | bash

Options:
  -h, --help       Show this help
  -y, --yes        Accept all defaults (non-interactive)
  --config-only    Write config.yaml and exit (skip install)
  --no-service     Skip systemd setup

Environment:
  HALLWAY_WATCH_DIR   Install directory (default: ~/hallway-watch)
  HALLWAY_WATCH_REPO  Git repo URL (default: Byte-Developments/hallway-watch)
EOF
}

# --- defaults ----------------------------------------------------------------

NONINTERACTIVE=false
CONFIG_ONLY=false
NO_SERVICE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -y|--yes) NONINTERACTIVE=true; shift ;;
    --config-only) CONFIG_ONLY=true; shift ;;
    --no-service) NO_SERVICE=true; shift ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# Curl-piped with no TTY and no -y → use defaults (non-interactive install)
if [[ "$NONINTERACTIVE" == "false" ]] && ! can_prompt; then
  echo "No terminal for prompts — using default settings (pass -y to silence this message)."
  NONINTERACTIVE=true
fi

RUN_USER="$(id -un)"
RUN_HOME="$(eval echo "~$RUN_USER")"
PI_HOSTNAME="hallway"

# config defaults
CAMERA_DEVICE=0
CAMERA_WIDTH=800
CAMERA_HEIGHT=600
CAMERA_FPS=8
DETECTION_CONFIDENCE=0.42
MOTION_THRESHOLD=18
MOTION_MIN_AREA=600
ALERT_COOLDOWN=15
VISIT_CLEAR_FRAMES=12
LOW_LIGHT_ENHANCE=true
CLAHE_CLIP_LIMIT=4.0
GAMMA=1.35
HEAD_HEIGHT_FRACTION=0.45
SMALL_BOX_HEIGHT=100
IMGSZ=736
CONFIRM_FRAMES=2
ROI_MASK=""
AUDIO_ENABLED=true
SOUND_FILE="assets/sounds/alert.wav"
AUDIO_DEVICE="default"
NOTIFICATIONS_ENABLED=true
NOTIFY_HOST="0.0.0.0"
NOTIFY_PORT=8765
NOTIFY_TITLE="Hallway Alert"
NOTIFY_MESSAGE="Someone is in the hallway"
TLS_ENABLED=true
TLS_CERT="certs/cert.pem"
TLS_KEY="certs/key.pem"
VAPID_CONTACT="mailto:hallway-watch@local"
LOG_LEVEL="INFO"
LOG_DEBUG_LEVEL="DEBUG"
DETECTION_LOG_DIR="logs/detections"
DEBUG_LOG_DIR="logs/debug"
SNAPSHOTS_ENABLED=true
SNAPSHOTS_DIR="snapshots"
SNAPSHOTS_RETENTION_DAYS=7
DETECTION_MODEL="models/yolov8n.pt"
START_SERVICE=true
INSTALL_LOG=""

# --- interactive config ------------------------------------------------------

banner

if [[ "$NONINTERACTIVE" == "false" ]]; then
  echo "${BOLD}Camera${RESET}"
  prompt CAMERA_DEVICE "  USB camera device number" "$CAMERA_DEVICE"
  prompt CAMERA_FPS "  Frames per second (lower = less CPU)" "$CAMERA_FPS"
  echo

  echo "${BOLD}Detection${RESET}"
  prompt DETECTION_CONFIDENCE "  Confidence (lower = distant/dim heads, try 0.38–0.50)" "$DETECTION_CONFIDENCE"
  prompt MOTION_THRESHOLD "  Motion sensitivity (lower = more sensitive)" "$MOTION_THRESHOLD"
  prompt ALERT_COOLDOWN "  Min seconds between separate visits" "$ALERT_COOLDOWN"
  prompt_yn LOW_LIGHT_ENHANCE "  Low-light mode (grayscale + contrast boost)" "y"
  prompt HEAD_HEIGHT_FRACTION "  Head box height fraction" "$HEAD_HEIGHT_FRACTION"
  prompt ROI_MASK "  ROI mask PNG path (leave blank to skip)" ""
  echo

  echo "${BOLD}Audio${RESET}"
  prompt_yn AUDIO_ENABLED "  Play sound on the Pi speaker" "y"
  prompt SOUND_FILE "  Alert sound (.wav)" "$SOUND_FILE"
  echo

  echo "${BOLD}Browser notifications${RESET}"
  prompt_yn NOTIFICATIONS_ENABLED "  Enable HTTPS notification page" "y"
  prompt NOTIFY_PORT "  Web page port" "$NOTIFY_PORT"
  prompt NOTIFY_TITLE "  Notification title" "$NOTIFY_TITLE"
  prompt NOTIFY_MESSAGE "  Notification message" "$NOTIFY_MESSAGE"
  echo

  echo "${BOLD}Service${RESET}"
  prompt_yn START_SERVICE "  Start hallway-watch when install finishes" "y"
  echo
else
  echo "Using default settings (-y)."
  echo
fi

# --- write config.yaml -------------------------------------------------------

write_config() {
  local roi_block=""
  if [[ -n "$ROI_MASK" ]]; then
    roi_block="  roi_mask: ${ROI_MASK}"
  else
    roi_block="  # roi_mask: assets/roi_mask.png"
  fi

  cat > config.yaml <<EOF
# Generated by install.sh on $(TZ=America/New_York date +"%Y-%m-%dT%H:%M:%S %Z")

camera:
  device: ${CAMERA_DEVICE}
  width: ${CAMERA_WIDTH}
  height: ${CAMERA_HEIGHT}
  fps: ${CAMERA_FPS}
  recovery_enabled: true
  recovery_max_failures: 15

detection:
  model: ${DETECTION_MODEL}
  confidence: ${DETECTION_CONFIDENCE}
  motion_threshold: ${MOTION_THRESHOLD}
  motion_min_area: ${MOTION_MIN_AREA}
  alert_cooldown_seconds: ${ALERT_COOLDOWN}
  visit_clear_frames: ${VISIT_CLEAR_FRAMES}
  low_light_enhance: ${LOW_LIGHT_ENHANCE}
  clahe_clip_limit: ${CLAHE_CLIP_LIMIT}
  clahe_tile_size: 8
  gamma: ${GAMMA}
  denoise: true
  head_height_fraction: ${HEAD_HEIGHT_FRACTION}
  small_box_height: ${SMALL_BOX_HEIGHT}
  imgsz: ${IMGSZ}
  confirm_frames: ${CONFIRM_FRAMES}
${roi_block}

audio:
  enabled: ${AUDIO_ENABLED}
  sound_file: ${SOUND_FILE}
  device: ${AUDIO_DEVICE}

notifications:
  enabled: ${NOTIFICATIONS_ENABLED}
  host: ${NOTIFY_HOST}
  port: ${NOTIFY_PORT}
  title: ${NOTIFY_TITLE}
  message: ${NOTIFY_MESSAGE}
  tls_enabled: ${TLS_ENABLED}
  tls_cert: ${TLS_CERT}
  tls_key: ${TLS_KEY}
  vapid_contact: ${VAPID_CONTACT}

snapshots:
  enabled: ${SNAPSHOTS_ENABLED}
  dir: ${SNAPSHOTS_DIR}
  retention_days: ${SNAPSHOTS_RETENTION_DAYS}

logging:
  level: ${LOG_LEVEL}
  debug_level: ${LOG_DEBUG_LEVEL}
  detection_log_dir: ${DETECTION_LOG_DIR}
  debug_log_dir: ${DEBUG_LOG_DIR}
EOF

  echo "${GREEN}✓${RESET} Wrote config.yaml"
}

write_config

if [[ "$CONFIG_ONLY" == "true" ]]; then
  echo
  echo "Config written. Run without --config-only to install dependencies."
  exit 0
fi

# --- background install (system packages, pip, model, certs, service) --------

INSTALL_LOG="${PROJECT_DIR}/install.log"
chmod +x "${PROJECT_DIR}/scripts/download_model.sh" 2>/dev/null || true
chmod +x "${PROJECT_DIR}/scripts/setup_mdns.sh" 2>/dev/null || true
chmod +x "${PROJECT_DIR}/scripts/generate_cert.sh" 2>/dev/null || true

spinner() {
  local pid=$1
  local chars='|/-\'
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf '\r  %s Installing... %s ' "$1" "${chars:$i:1}"
    sleep 0.25
  done
  printf '\r%-60s\r' ' '
}

run_install() {
  echo "==> [1/5] System packages + model download (parallel)"
  local pid_apt="" pid_model=""

  if command -v apt-get >/dev/null 2>&1; then
    (
      sudo apt-get update -qq
      sudo apt-get install -y \
        python3 python3-venv python3-pip \
        alsa-utils libatlas-base-dev libgl1 openssl git curl avahi-daemon avahi-utils
    ) &
    pid_apt=$!
  else
    echo "    apt-get not found — skipping system packages"
  fi

  bash "${PROJECT_DIR}/scripts/download_model.sh" &
  pid_model=$!

  if [[ -n "$pid_apt" ]]; then wait "$pid_apt"; fi
  wait "$pid_model"

  ensure_aplay || true

  echo "==> [2/5] Python virtual environment + pip libraries"
  python3 -m venv "${PROJECT_DIR}/.venv"
  "${PROJECT_DIR}/.venv/bin/pip" install --upgrade pip -q
  "${PROJECT_DIR}/.venv/bin/pip" install -r "${PROJECT_DIR}/requirements.txt" -q

  echo "==> [3/5] Model weights"
  if [[ -f "${PROJECT_DIR}/models/yolov8n.pt" ]]; then
    echo "    OK: models/yolov8n.pt ($(du -h "${PROJECT_DIR}/models/yolov8n.pt" | awk '{print $1}'))"
  else
    echo "    Model missing after download" >&2
    exit 1
  fi

  mkdir -p "${PROJECT_DIR}/assets/sounds" "${PROJECT_DIR}/data" "${PROJECT_DIR}/certs"
  mkdir -p "${PROJECT_DIR}/logs/detections" "${PROJECT_DIR}/logs/debug"
  mkdir -p "${PROJECT_DIR}/snapshots"

  echo "==> [4/5] mDNS hostname + TLS certificate"
  bash "${PROJECT_DIR}/scripts/setup_mdns.sh"
  bash "${PROJECT_DIR}/scripts/generate_cert.sh"

  if [[ "$NO_SERVICE" == "false" ]] && command -v systemctl >/dev/null 2>&1; then
    echo "==> systemd service"
    sudo tee /etc/systemd/system/hallway-watch.service > /dev/null <<EOF
[Unit]
Description=Hallway Watch - head detection
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/.venv/bin/python -m hallway_watch.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable hallway-watch
    if [[ "$START_SERVICE" == "true" ]]; then
      sudo systemctl restart hallway-watch
    fi
  fi

  echo "==> hwatch CLI command"
  chmod +x "${PROJECT_DIR}/bin/hwatch"
  sudo tee /etc/hallway-watch.conf > /dev/null <<EOF
HALLWAY_WATCH_DIR=${PROJECT_DIR}
HALLWAY_WATCH_REPO=${REPO_URL}
EOF
  sudo ln -sf "${PROJECT_DIR}/bin/hwatch" /usr/local/bin/hwatch

  echo "==> Install finished at $(TZ=America/New_York date +"%Y-%m-%dT%H:%M:%S %Z")"
}

echo "==> Installing code, pip libraries, and model weights in the background"
echo "    Log: ${INSTALL_LOG}"
echo

: > "$INSTALL_LOG"
(
  cd "$PROJECT_DIR"
  run_install
) >> "$INSTALL_LOG" 2>&1 &
INSTALL_PID=$!

spinner "Background" "$INSTALL_PID"
wait "$INSTALL_PID" || {
  echo "${YELLOW}!${RESET} Install failed. Last 30 lines of ${INSTALL_LOG}:"
  echo
  tail -30 "$INSTALL_LOG"
  exit 1
}

echo "${GREEN}✓${RESET} All dependencies installed"
grep -E '^==>' "$INSTALL_LOG" | sed 's/^/    /' || true
echo

if [[ ! -f "$SOUND_FILE" ]]; then
  echo "${YELLOW}!${RESET} Sound file not found at ${SOUND_FILE}"
  echo "    Add a .wav file there (e.g. a doorbell sound)."
fi

if [[ "$NO_SERVICE" == "false" ]] && command -v systemctl >/dev/null 2>&1; then
  echo "${GREEN}✓${RESET} Service enabled for user ${RUN_USER}"
  if [[ "$START_SERVICE" == "true" ]]; then
    echo "${GREEN}✓${RESET} Service started"
  fi
fi

# --- finish ------------------------------------------------------------------

PI_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"

echo
echo "${BOLD}${GREEN}Installation complete!${RESET}"
echo
echo "  Project:  ${PROJECT_DIR}"
echo "  Config:   ${PROJECT_DIR}/config.yaml"
if [[ -n "$PI_IP" ]]; then
  echo "  Notify:   https://hallway.local:${NOTIFY_PORT}  (or https://${PI_IP}:${NOTIFY_PORT})"
else
  echo "  Notify:   https://hallway.local:${NOTIFY_PORT}"
fi
echo
echo "Next steps:"
echo "  1. Open the Notify URL on your Mac"
echo "  2. Accept the certificate warning (self-signed)"
echo "  3. Click ${BOLD}Enable notifications${RESET} — then you can close the page"
if [[ ! -f "$SOUND_FILE" ]]; then
  echo "  4. Add a sound file: ${SOUND_FILE}"
fi
echo
echo "Useful commands:"
echo "  Preview:  cd ${PROJECT_DIR} && source .venv/bin/activate && python -m hallway_watch.main --preview"
echo "  Service:  sudo systemctl status hallway-watch"
echo "  Logs:     journalctl -u hallway-watch -f"
echo "  Install:  tail -f ${INSTALL_LOG}"
echo "  Update:   hwatch update"
echo "  Status:   hwatch status"
echo "  Reconfig: ${PROJECT_DIR}/install.sh --config-only"
echo
