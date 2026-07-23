#!/usr/bin/env bash
# Install Python deps with a Pi-safe CPU-only PyTorch.
# Usage: install_pip_deps.sh <project-dir> <pip-binary> [tmpdir]
set -euo pipefail

PROJECT_DIR="${1:?project dir required}"
PIP="${2:?pip binary required}"
PIP_TMP="${3:-}"
PYTHON="$(dirname "$PIP")/python"
TORCH_INDEX="https://download.pytorch.org/whl/cpu"

run_pip() {
  if [[ -n "$PIP_TMP" ]]; then
    mkdir -p "$PIP_TMP"
    TMPDIR="$PIP_TMP" "$PIP" "$@"
  else
    "$PIP" "$@"
  fi
}

echo "    Removing CUDA / NVIDIA torch packages if present"
run_pip freeze 2>/dev/null \
  | awk -F= 'BEGIN{IGNORECASE=1} /^torch/ || /^nvidia-/ || /^cuda-/ || /^triton==/ {print $1}' \
  | sort -u \
  | while read -r pkg; do
      run_pip uninstall -y "$pkg" >/dev/null 2>&1 || true
    done

# Recent official aarch64 wheels use ARMv8.1 LSE atomics. Pi 4 (Cortex-A72)
# lacks them and dies with SIGILL / Illegal instruction. Pi 5+ usually has LSE.
if grep -qw atomics /proc/cpuinfo 2>/dev/null; then
  echo "    Installing CPU-only PyTorch (current)"
  TORCH_PKGS=(torch torchvision)
else
  echo "    CPU lacks ARM LSE (typical Pi 4) — pinning torch 2.8 CPU"
  # 2.8 works on ARMv8.0; 2.10+ often SIGILL again on Pi 4.
  TORCH_PKGS=("torch==2.8.0" "torchvision==0.23.0")
fi

run_pip install --upgrade "${TORCH_PKGS[@]}" --index-url "$TORCH_INDEX"

echo "    Installing project requirements"
run_pip install -r "${PROJECT_DIR}/requirements.txt"

# Ultralytics may try to pull a newer/CUDA torch — reassert CPU torch.
echo "    Reasserting CPU-only PyTorch"
run_pip install --force-reinstall "${TORCH_PKGS[@]}" --index-url "$TORCH_INDEX"

echo "    Verifying torch import"
"$PYTHON" -c "import torch; print('    torch', torch.__version__, 'cuda=', torch.cuda.is_available())"
