#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
APP_DIR="${APP_DIR:-$HOME/app}"
REPO_URL="${REPO_URL:-https://github.com/Googool/RPi-2}"
BRANCH="${BRANCH:-main}"

# ---- Helpers ----
is_pi() {
  [[ -f /proc/device-tree/model ]] && grep -qi 'raspberry pi' /proc/device-tree/model
}

echo "[1/4] apt install base deps…"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip git i2c-tools

echo "[2/4] fetch code into ${APP_DIR}…"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only
else
  mkdir -p "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "[3/4] venv + python deps from pyproject…"
if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
python -m pip install --upgrade pip wheel setuptools

# Base project + extras on Pi (Blinka/SSD1305). Also ensure Pillow is present.
if is_pi; then
  python -m pip install -e ".[rpi]" Pillow
else
  python -m pip install -e . Pillow
fi

echo "[4/4] run web + oled (Ctrl-C to stop)…"
cd "$APP_DIR"
# Start OLED in background; keep PID to clean up on exit
./.venv/bin/python -m src.oled_status & OLED_PID=$!

cleanup() {
  echo; echo "[cleanup] stopping OLED…"
  kill "$OLED_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Start web in foreground
exec ./.venv/bin/python -m src
