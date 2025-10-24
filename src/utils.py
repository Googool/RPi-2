from __future__ import annotations
import os, re
from datetime import datetime
from pathlib import Path

# Project paths
ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR: Path = ROOT / "data" / "logs"
CFG_SNAP_DIR: Path = ROOT / "data" / "cfg"       # date-stamped config snapshots live here
CONFIG_PATH: Path = ROOT / "data" / "cfg.json"   # current config file

_COMPACT_RE = re.compile(r"^\d{8}$")  # 20251024

def ensure_dir(path: str | os.PathLike) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

# ---------- date helpers ----------

def today_str(dt: datetime | None = None) -> str:
    return (dt or datetime.now()).strftime("%Y-%m-%d")

def date_to_compact(date_str: str) -> str:
    return date_str.replace("-", "")

def compact_to_date(compact: str) -> str:
    """
    Accept 'YYYYMMDD' (and also tolerate 'YYYYDDMM' like 20252410).
    Return 'YYYY-MM-DD' or raise ValueError.
    """
    if not _COMPACT_RE.fullmatch(compact or ""):
        raise ValueError("invalid compact date")
    y = int(compact[0:4]); m = int(compact[4:6]); d = int(compact[6:8])
    try:
        datetime(y, m, d)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        # support YYYYDDMM by swapping
        datetime(y, d, m)  # may raise
        return f"{y:04d}-{d:02d}-{m:02d}"

# ---------- per-day file paths ----------

def log_path_for_date(log_dir: str | os.PathLike, date: str | None = None) -> str:
    ensure_dir(log_dir)
    ds = date or today_str()
    return str(Path(log_dir) / f"{ds}.log")

def cfg_path_for_date(cfg_dir: str | os.PathLike, date: str | None = None) -> str:
    ensure_dir(cfg_dir)
    ds = date or today_str()
    return str(Path(cfg_dir) / f"{ds}.json")

# ---------- listings ----------

def list_log_dates(log_dir: str | os.PathLike, *, exclude_today: bool = False) -> list[str]:
    p = Path(log_dir); ensure_dir(p)
    dates = [f.stem for f in p.glob("*.log") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.stem)]
    dates.sort(reverse=True)
    if exclude_today:
        t = today_str()
        dates = [d for d in dates if d != t]
    return dates

def list_log_compacts(log_dir: str | os.PathLike, *, exclude_today: bool = False) -> list[str]:
    return [date_to_compact(d) for d in list_log_dates(log_dir, exclude_today=exclude_today)]

def list_cfg_dates(cfg_dir: str | os.PathLike, *, exclude_today: bool = False) -> list[str]:
    p = Path(cfg_dir); ensure_dir(p)
    dates = [f.stem for f in p.glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.stem)]
    dates.sort(reverse=True)
    if exclude_today:
        t = today_str()
        dates = [d for d in dates if d != t]
    return dates

def list_cfg_compacts(cfg_dir: str | os.PathLike, *, exclude_today: bool = False) -> list[str]:
    return [date_to_compact(d) for d in list_cfg_dates(cfg_dir, exclude_today=exclude_today)]

# ---------- route helpers ----------

def _secure_log_from_compact_or_404(compact: str) -> Path:
    from flask import abort
    if not _COMPACT_RE.fullmatch(compact or ""):
        abort(404)
    try:
        iso = compact_to_date(compact)
    except ValueError:
        abort(404)
    path = Path(log_path_for_date(LOGS_DIR, iso))
    if not path.exists() or not path.is_file():
        abort(404)
    return path

def _secure_cfg_from_compact_or_404(compact: str) -> Path:
    """
    Map a compact id to a config snapshot path.
    - If <data>/cfg/YYYY-MM-DD.json exists, use it.
    - If it's today and snapshot doesn't exist, fall back to current CONFIG_PATH.
    """
    from flask import abort
    if not _COMPACT_RE.fullmatch(compact or ""):
        abort(404)
    try:
        iso = compact_to_date(compact)
    except ValueError:
        abort(404)

    snap = Path(cfg_path_for_date(CFG_SNAP_DIR, iso))
    if snap.exists() and snap.is_file():
        return snap

    # For "today", allow falling back to the current config file
    if iso == today_str():
        if Path(CONFIG_PATH).exists():
            return Path(CONFIG_PATH)

    abort(404)
