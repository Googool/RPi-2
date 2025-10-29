#!/usr/bin/env bash
# Install (no systemd): clone/update repo, make venv, install deps, run web + OLED
# Usage (SSH):
#   curl -fsSL https://raw.githubusercontent.com/Googool/RPi-2/main/install.sh | bash
#
# Options (env):
#   APP_DIR=~/app           # install path
#   REPO_URL=...            # repo url
#   BRANCH=main             # branch
#   EXTRAS=                 # pip extras; auto "rpi" on Pi if empty
#   RUNNER=tmux|nohup|fg    # how to run processes (default tmux)
#   OLED_ADDR=0x3C          # I2C address
#   OLED_REFRESH=5          # seconds
#   OLED_DEVICE=i2c         # i2c or spi

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/app}"
REPO_URL="${REPO_URL:-https://github.com/Googool/RPi-2}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-rpi-gpio}"  # unused now; kept for logs
EXTRAS="${EXTRAS:-}"
RUNNER="${RUNNER:-tmux}"
OLED_ADDR="${OLED_ADDR:-0x3C}"
OLED_REFRESH="${OLED_REFRESH:-5}"
OLED_DEVICE="${OLED_DEVICE:-i2c}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "Please run as a normal user (not sudo). I'll sudo only when needed."
  exit 1
fi

have() { command -v "$1" >/dev/null 2>&1; }
is_pi() { [[ -f /proc/device-tree/model ]] && grep -qi 'raspberry pi' /proc/device-tree/model; }

echo "[1/4] apt install base deps…"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip git build-essential libffi-dev libssl-dev ca-certificates \
  i2c-tools libjpeg-dev zlib1g-dev libopenjp2-7 libtiff5
if [[ "$RUNNER" == "tmux" ]] && ! have tmux; then
  sudo apt-get install -y tmux
fi

echo "[2/4] fetch code into ${APP_DIR}…"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only
else
  mkdir -p "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "[3/4] venv + python deps from pyproject.toml…"
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

echo "[4/4] prepare data dir + run apps…"
mkdir -p "$APP_DIR/data/logs"

# Helpful I2C hint
if is_pi && [[ ! -e /dev/i2c-1 ]]; then
  echo "⚠️  /dev/i2c-1 not found. Enable I2C first:"
  echo "    sudo raspi-config nonint do_i2c 0   (or via GUI raspi-config → Interface Options → I2C)"
fi

start_tmux() {
  local sess="rpi"
  # Create session (detached)
  tmux new-session -d -s "$sess" -c "$APP_DIR"
  tmux rename-window -t "$sess:0" 'web'
  tmux send-keys    -t "$sess:0" 'source .venv/bin/activate && python -m src' C-m

  tmux new-window   -t "$sess:1" -n 'oled' -c "$APP_DIR"
  tmux send-keys    -t "$sess:1" "source .venv/bin/activate && python -m src.oled_status --device ${OLED_DEVICE} --addr ${OLED_ADDR} --refresh ${OLED_REFRESH}" C-m

  echo
  echo "✅ Started in tmux session 'rpi'."
  echo "   Attach: tmux attach -t rpi"
  echo "   Stop:   tmux kill-session -t rpi"
}

start_nohup() {
  (cd "$APP_DIR"; nohup "$APP_DIR/.venv/bin/python" -m src \
      >> "$APP_DIR/data/logs/web.out" 2>&1 & echo $! > "$APP_DIR/web.pid")
  (cd "$APP_DIR"; nohup "$APP_DIR/.venv/bin/python" -m src.oled_status \
      --device "${OLED_DEVICE}" --addr "${OLED_ADDR}" --refresh "${OLED_REFRESH}" \
      >> "$APP_DIR/data/logs/oled.out" 2>&1 & echo $! > "$APP_DIR/oled.pid")
  echo
  echo "✅ Started with nohup:"
  echo "   Web PID : $(cat "$APP_DIR/web.pid")"
  echo "   OLED PID: $(cat "$APP_DIR/oled.pid")"
  echo "   Logs:    tail -f $APP_DIR/data/logs/web.out  $APP_DIR/data/logs/oled.out"
  echo "   Stop:    kill \$(cat $APP_DIR/web.pid) \$(cat $APP_DIR/oled.pid)"
}

start_fg() {
  echo "Starting web interface in foreground (Ctrl+C to stop)…"
  (cd "$APP_DIR"; source .venv/bin/activate; python -m src)
}

case "$RUNNER" in
  tmux)  start_tmux ;;
  nohup) start_nohup ;;
  fg)    start_fg ;;
  *)     echo "Unknown RUNNER='$RUNNER' (use tmux|nohup|fg)"; exit 2 ;;
esac

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Open the Web UI:  http://${IP:-localhost}:5000"
echo "Repo: $REPO_URL  (branch: $BRANCH)"
