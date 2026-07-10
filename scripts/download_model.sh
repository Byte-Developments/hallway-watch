#!/usr/bin/env bash
# Download YOLOv8n weights into models/yolov8n.pt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL_DIR="$ROOT/models"
MODEL_FILE="$MODEL_DIR/yolov8n.pt"
MODEL_URL="${HALLWAY_WATCH_MODEL_URL:-https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt}"
MIN_BYTES=5000000

mkdir -p "$MODEL_DIR"

if [[ -f "$MODEL_FILE" ]] && [[ "$(wc -c < "$MODEL_FILE" | tr -d ' ')" -ge "$MIN_BYTES" ]]; then
  echo "Model already present: $MODEL_FILE"
  exit 0
fi

download() {
  local url=$1
  local dest=$2
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$dest" "$url"
  else
    echo "curl or wget required to download the model" >&2
    return 1
  fi
}

echo "Downloading yolov8n.pt..."
download "$MODEL_URL" "$MODEL_FILE.part"
mv "$MODEL_FILE.part" "$MODEL_FILE"

if [[ "$(wc -c < "$MODEL_FILE" | tr -d ' ')" -lt "$MIN_BYTES" ]]; then
  echo "Downloaded model file looks too small — check your network." >&2
  rm -f "$MODEL_FILE"
  exit 1
fi

echo "Saved to $MODEL_FILE"
