#!/usr/bin/env bash
#
# Hallway Watch — curl bootstrap
#
# Always clones/pulls the latest repo, then runs the local installer.
# Safe to curl|bash even when GitHub's raw CDN is briefly stale.
#
#   curl -fsSL https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/scripts/bootstrap.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/scripts/bootstrap.sh | bash -s -- -y
#
set -euo pipefail

INSTALL_DIR="${HALLWAY_WATCH_DIR:-$HOME/hallway-watch}"
REPO_URL="${HALLWAY_WATCH_REPO:-https://github.com/Byte-Developments/hallway-watch.git}"

if ! command -v git >/dev/null 2>&1; then
  echo "==> Installing git"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y git
  else
    echo "git is required but could not be installed automatically." >&2
    exit 1
  fi
fi

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  echo "==> Updating Hallway Watch in ${INSTALL_DIR}"
  git -C "${INSTALL_DIR}" remote set-url origin "$REPO_URL" 2>/dev/null || true
  git -C "${INSTALL_DIR}" pull --ff-only
elif [[ -d "${INSTALL_DIR}" ]]; then
  echo "==> Replacing non-git install at ${INSTALL_DIR}"
  rm -rf "${INSTALL_DIR}"
  git clone --depth 1 "$REPO_URL" "${INSTALL_DIR}"
else
  echo "==> Cloning Hallway Watch into ${INSTALL_DIR}"
  git clone --depth 1 "$REPO_URL" "${INSTALL_DIR}"
fi

exec "${INSTALL_DIR}/install.sh" "$@"
