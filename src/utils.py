from __future__ import annotations
import os, re
from datetime import datetime
from pathlib import Path
import threading, time

# Project paths
ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR: Path = ROOT / "data" / "logs"

_COMPACT_RE = re.compile(r"^\d{8}$")  # e.g. 20251024

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
        datetime(y, d, m)  # may raise if invalid
        return f"{y:04d}-{d:02d}-{m:02d}"

# ---------- per-day log file paths ----------

def log_path_for_date(log_dir: str | os.PathLike, date: str | None = None) -> str:
    """
    Return '<log_dir>/YYYY-MM-DD.log', ensuring directory exists.
    """
    ensure_dir(log_dir)
    ds = date or today_str()
    return str(Path(log_dir) / f"{ds}.log")

# ---------- listings (logs) ----------

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

# ---------- route helper (logs) ----------

def _secure_log_from_compact_or_404(compact: str) -> Path:
    """
    Map a compact date (YYYYMMDD or YYYYDDMM) to a log file path in LOGS_DIR.
    404 if invalid or missing.
    """
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

def _read_cpu():
    # Return (idle, total) jiffies from /proc/stat
    with open("/proc/stat") as f:
        parts = f.readline().split()[1:]
        vals = list(map(int, parts[:7]))
        idle = vals[3] + vals[4]
        total = sum(vals)
        return idle, total
