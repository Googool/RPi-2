from __future__ import annotations
from pathlib import Path
import json, os, tempfile
import logging

# Always resolve to: <project root>/data/cfg.json (one level above src/)
CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "cfg.json"

# Default configuration written on first run
DEFAULT_CFG = {
    "network": {"interface": "wlan0", "mode": "dhcp", "address": None, "gateway": None},
    "gpio": [
        {"pin": 15, "name": "Power", "mode": "output", "value": 0}
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
        # atomic create with default content
        _atomic_write(CONFIG_PATH, DEFAULT_CFG)
        created_file = True

    if created_dir or created_file:
        logging.getLogger(__name__).info(
            "config_init path=%s dir_created=%s file_created=%s",
            CONFIG_PATH, created_dir, created_file
        )
    else:
        logging.getLogger(__name__).info(
            "config_found path=%s", CONFIG_PATH
        )

    return CONFIG_PATH

def load_cfg(path: Path | None = None) -> dict:
    """
    Load and return the JSON dict from cfg.json (creating it with defaults if missing).
    """
    p = Path(path) if path else initialize_config()
    cfg = json.loads(p.read_text(encoding="utf-8"))
    logging.getLogger(__name__).debug("config_load path=%s size=%dB", p, len(json.dumps(cfg)))
    return cfg

def save_cfg(cfg: dict, path: Path | None = None) -> None:
    """
    Persist config to cfg.json ONLY (no snapshot directory).
    Uses an atomic write to avoid partial files on power loss/crash.
    """
    p = Path(path) if path else initialize_config()
    _atomic_write(p, cfg)
    logging.getLogger(__name__).info("config_save path=%s", p)

def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # write to temp file in same directory, then replace
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, prefix=path.name + ".", suffix=".tmp") as tmp:
        json.dump(data, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)
