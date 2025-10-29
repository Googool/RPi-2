#!/usr/bin/env bash
set -euo pipefail

# --------- config (overridable via env) ----------
APP_DIR="${APP_DIR:-$HOME/app}"
REPO_URL="${REPO_URL:-https://github.com/Googool/RPi-2}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-rpi-gpio}"
OLED_SERVICE_NAME="${OLED_SERVICE_NAME:-oled-status}"
EXTRAS="${EXTRAS:-}"            # e.g. "rpi"
PI_USER="$(id -un)"

# --------- guards ----------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Please run as a normal user (not sudo). I'll sudo only when needed."
  exit 1
fi

is_pi() {
  [[ -f /proc/device-tree/model ]] && grep -qi 'raspberry pi' /proc/device-tree/model
}

# --------- 1) base deps ----------
echo "[1/6] apt install base deps..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip python3-dev \
  git build-essential libffi-dev libssl-dev ca-certificates

# OLED/i2c helpers (harmless elsewhere)
if is_pi; then
  sudo apt-get install -y --no-install-recommends i2c-tools python3-smbus raspi-config || true
fi

# --------- 2) fetch/update repo ----------
echo "[2/6] fetch code into ${APP_DIR}..."
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only
else
  mkdir -p "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# --------- 3) venv + deps ----------
echo "[3/6] venv + python deps from pyproject.toml..."
if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
python -m pip install --upgrade pip wheel setuptools

# Choose extras: default to rpi on a Pi unless caller already set EXTRAS
if [[ -z "$EXTRAS" ]] && is_pi; then
  EXTRAS="rpi"
fi

cd "$APP_DIR"
if [[ -n "$EXTRAS" ]]; then
  python -m pip install -e ".[${EXTRAS}]"
else
  python -m pip install -e .
fi

# --------- 4) groups & features ----------
echo "[4/6] ensure groups & data dir..."
mkdir -p "$APP_DIR/data/logs"
# Add user to gpio/i2c (ok if already a member)
sudo usermod -aG gpio "$PI_USER" || true
sudo usermod -aG i2c  "$PI_USER" || true

# Enable I2C on Raspberry Pi OS (best-effort)
if is_pi; then
  if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_i2c 0 || true
  fi
  # Ensure dtparam on both possible locations (Bookworm vs. legacy)
  for CFG in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -f "$CFG" ]] && ! grep -q '^dtparam=i2c_arm=on' "$CFG"; then
      echo 'dtparam=i2c_arm=on' | sudo tee -a "$CFG" >/dev/null || true
    fi
  done
fi

# --------- 5) install systemd units ----------
echo "[5/6] install systemd services..."
RPI_UNIT_SRC="$APP_DIR/rpi-gpio@.service"
OLED_UNIT_SRC="$APP_DIR/oled-status@.service"

if [[ ! -f "$RPI_UNIT_SRC" ]]; then
  echo "ERROR: $RPI_UNIT_SRC not found. Commit rpi-gpio@.service to the repo."; exit 2; fi
if [[ ! -f "$OLED_UNIT_SRC" ]]; then
  echo "ERROR: $OLED_UNIT_SRC not found. Commit oled-status@.service to the repo."; exit 2; fi

sudo install -m 0644 -D "$RPI_UNIT_SRC"  "/etc/systemd/system/rpi-gpio@.service"
sudo install -m 0644 -D "$OLED_UNIT_SRC" "/etc/systemd/system/oled-status@.service"

sudo systemctl daemon-reload

echo "[6/6] enable/launch services for user '${PI_USER}'…"
sudo systemctl enable --now "rpi-gpio@${PI_USER}.service"

# OLED service will be skipped if /dev/i2c-1 is absent (ConditionPathExists)
sudo systemctl enable --now "oled-status@${PI_USER}.service" || true

# Status (non-fatal)
echo
systemctl --no-pager -l status "rpi-gpio@${PI_USER}.service"  || true
systemctl --no-pager -l status "oled-status@${PI_USER}.service" || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Ready."
echo "- Web UI:  http://${IP:-localhost}:5000"
echo "- Logs:    sudo journalctl -fu rpi-gpio@${PI_USER}.service"
echo "- OLED:    sudo journalctl -fu oled-status@${PI_USER}.service"
