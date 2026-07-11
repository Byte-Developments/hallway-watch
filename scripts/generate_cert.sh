#!/usr/bin/env bash
# Generate a self-signed TLS cert for hallway.local (notification page).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="${ROOT}/certs"
HOSTNAME="${HALLWAY_HOSTNAME:-hallway}"
CN="${HOSTNAME}.local"

mkdir -p "$CERT_DIR"

if [[ -f "${CERT_DIR}/cert.pem" && "${REGENERATE_CERT:-0}" != "1" ]]; then
  echo "TLS certificate already exists at ${CERT_DIR}/cert.pem"
  exit 0
fi

echo "==> Generating TLS certificate for ${CN}"
openssl req -x509 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/key.pem" \
  -out "${CERT_DIR}/cert.pem" \
  -days 3650 -nodes \
  -subj "/CN=${CN}" \
  -addext "subjectAltName=DNS:${CN},DNS:${HOSTNAME},IP:127.0.0.1" 2>/dev/null

echo "    Saved to ${CERT_DIR}/"
