#!/usr/bin/env bash
# Configure mDNS so the Pi is reachable at hallway.local on the LAN.
set -euo pipefail

HOSTNAME="${HALLWAY_HOSTNAME:-hallway}"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get not found — skipping mDNS setup"
  exit 0
fi

echo "==> Setting hostname to ${HOSTNAME} (${HOSTNAME}.local)"
sudo apt-get install -y avahi-daemon avahi-utils
sudo hostnamectl set-hostname "$HOSTNAME"

TMP="$(mktemp)"
sudo grep -v "^127.0.1.1" /etc/hosts > "$TMP" || true
printf '127.0.1.1\t%s.local %s\n' "$HOSTNAME" "$HOSTNAME" >> "$TMP"
sudo cp "$TMP" /etc/hosts
rm -f "$TMP"

sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon
echo "    Reachable at https://${HOSTNAME}.local:8765 (mDNS)"
