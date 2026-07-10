#!/usr/bin/env bash
# Backwards-compatible wrapper — use ./install.sh at the repo root instead.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/install.sh" "$@"
