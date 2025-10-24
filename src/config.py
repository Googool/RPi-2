from __future__ import annotations
from pathlib import Path
import json
from .utils import CFG_SNAP_DIR, cfg_path_for_date, today_str

# Always resolve to: <project root>/data/cfg.json (one level above src/)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "cfg.json"

# Make it possible to change the address and then run a script to change the raspi-config to that address and make the config mirror that in the config file.

# Default configuration written on first run
DEFAULT_CFG = {
    "network": {"interface": "wlan0", "mode": "dhcp", "address": None, "gateway": None},
    "gpio": [
        {"pin": 17, "name": "Power Relay", "mode": "output", "value": 0}
    ],
}

def initialize_config(*_ignored) -> Path:
    """
    Ensure <project root>/data/cfg.json exists.
    Prints whether it was created or found.
    Note: accepts extra args for backward-compat with initialize_config(app.root_path).
    """
    cfg_dir = CONFIG_PATH.parent
    created_dir = False
    created_file = False

    if not cfg_dir.exists():
        cfg_dir.mkdir(parents=True, exist_ok=True)
        created_dir = True

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CFG, indent=2), encoding="utf-8")
        created_file = True

    if created_dir or created_file:
        print(f"[config] Initialized at {CONFIG_PATH} (dir_created={created_dir}, file_created={created_file})")
    else:
        print(f"[config] Found existing config at {CONFIG_PATH}")

    return CONFIG_PATH

def load_cfg(path: Path | None = None) -> dict:
    p = path or initialize_config()
    return json.loads(Path(p).read_text(encoding="utf-8"))

def save_cfg(cfg: dict, path: Path | None = None) -> None:
    p = Path(path) if path else initialize_config()
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    # ALSO write a dated snapshot
    snap = Path(cfg_path_for_date(CFG_SNAP_DIR, today_str()))
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
