#!/usr/bin/env bash
#
# Install with:
#   curl -fsSL https://raw.githubusercontent.com/Googool/webserver/master/install.sh | bash
#
# Idempotent: updates repo, venv, deps, and systemd units.

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/app}"
REPO_URL="${REPO_URL:-https://github.com/Googool/RPi-2}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-rpi-gpio}"        # base name (templated unit rpi-gpio@.service)
OLED_SERVICE_NAME="${OLED_SERVICE_NAME:-oled-status}"
EXTRAS="${EXTRAS:-}"                            # e.g. "rpi" to force; default auto on Pi
USER_NAME="$(id -un)"
UNIT_SRC_DIR_REL="${UNIT_SRC_DIR_REL:-systemd}" # where unit files live in the repo

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Please run as a normal user (not sudo). I'll sudo only when needed."
  exit 1
fi

is_pi() { [[ -f /proc/device-tree/model ]] && grep -qi 'raspberry pi' /proc/device-tree/model; }

echo "[1/7] apt install base deps..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip python3-dev \
  git build-essential libffi-dev libssl-dev ca-certificates

if is_pi; then
  echo "[1b/7] Raspberry Pi detected: enable I²C + tools…"
  # raspi-config exists on Raspberry Pi OS; ignore errors elsewhere
  if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_i2c 0 || true
  fi
  sudo apt-get install -y --no-install-recommends i2c-tools
  # Optional (font rendering if you later use PIL on the OLED)
  sudo apt-get install -y --no-install-recommends python3-pil || true
fi

echo "[2/7] fetch/update code into ${APP_DIR}..."
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only
else
  mkdir -p "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "[3/7] venv + python deps from pyproject.toml..."
# Create venv if missing
if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
python -m pip install --upgrade pip wheel setuptools

# Decide extras: default to rpi on Raspberry Pi unless EXTRAS was provided
if [[ -z "$EXTRAS" ]] && is_pi; then
  EXTRAS="rpi"
fi

cd "$APP_DIR"
if [[ -n "$EXTRAS" ]]; then
  python -m pip install -e ".[${EXTRAS}]"
else
  python -m pip install -e .
fi

echo "[4/7] data dir & groups…"
mkdir -p "$APP_DIR/data/logs"
# Safe on all OSes; present on Raspberry Pi OS
sudo groupadd -f gpio || true
sudo groupadd -f i2c || true
sudo usermod -aG gpio,i2c "$USER_NAME" || true

echo "[5/7] install systemd units from repo…"
UNIT_SRC_DIR="$APP_DIR/$UNIT_SRC_DIR_REL"
if [[ ! -d "$UNIT_SRC_DIR" ]]; then
  echo "ERROR: Unit directory '$UNIT_SRC_DIR' not found in repo. Expected to contain ${SERVICE_NAME}@.service and ${OLED_SERVICE_NAME}@.service"
  exit 2
fi

# Web app (templated)
if [[ -f "$UNIT_SRC_DIR/${SERVICE_NAME}@.service" ]]; then
  sudo install -m 0644 -D "$UNIT_SRC_DIR/${SERVICE_NAME}@.service" "/etc/systemd/system/${SERVICE_NAME}@.service"
else
  echo "ERROR: $UNIT_SRC_DIR/${SERVICE_NAME}@.service not found."
  exit 2
fi

# OLED status (templated, optional)
OLED_UNIT_FOUND=0
if [[ -f "$UNIT_SRC_DIR/${OLED_SERVICE_NAME}@.service" ]]; then
  sudo install -m 0644 -D "$UNIT_SRC_DIR/${OLED_SERVICE_NAME}@.service" "/etc/systemd/system/${OLED_SERVICE_NAME}@.service"
  OLED_UNIT_FOUND=1
fi

sudo systemctl daemon-reload

echo "[6/7] enable/launch services for user '${USER_NAME}'…"
# Enable & start web app instance
sudo systemctl enable --now "${SERVICE_NAME}@${USER_NAME}.service"
# Enable & start OLED instance if present
if [[ "$OLED_UNIT_FOUND" -eq 1 ]]; then
  sudo systemctl enable --now "${OLED_SERVICE_NAME}@${USER_NAME}.service" || true
fi

sudo systemctl --no-pager -l status "${SERVICE_NAME}@${USER_NAME}.service" || true
if [[ "$OLED_UNIT_FOUND" -eq 1 ]]; then
  sudo systemctl --no-pager -l status "${OLED_SERVICE_NAME}@${USER_NAME}.service" || true
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "[7/7] ready"
echo "- URL:  http://${IP:-localhost}:5000"
echo "- Logs: sudo journalctl -fu ${SERVICE_NAME}@${USER_NAME}.service"
if [[ "$OLED_UNIT_FOUND" -eq 1 ]]; then
  echo "- OLED: sudo journalctl -fu ${OLED_SERVICE_NAME}@${USER_NAME}.service"
fi
