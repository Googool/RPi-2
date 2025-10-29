from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta, time as dtime
import logging
import threading, time

LOGS_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"

_current_date: str | None = None
_file_handler: logging.FileHandler | None = None

def today_str() -> str:                  # ← public helper
    return datetime.now().strftime("%Y-%m-%d")

def log_path_for_date(ds: str | None = None) -> Path:
    ds = ds or today_str()
    return LOGS_DIR / f"{ds}.log"

def _ensure_logs_dir() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

def bind_logger_to_today() -> Path:
    global _current_date, _file_handler
    _ensure_logs_dir()
    today = today_str()
    path = log_path_for_date(today)

    if _current_date == today and _file_handler:
        return path

    root = logging.getLogger()

    if _file_handler:
        try:
            root.removeHandler(_file_handler)
            _file_handler.close()
        except Exception:
            pass
        _file_handler = None

    path.touch(exist_ok=True)
    fh = logging.FileHandler(path)
    fh.setLevel(logging.INFO)  # <-- ensure handler passes INFO
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root.addHandler(fh)

    # IMPORTANT: don’t guard this; set the root logger level to INFO
    root.setLevel(logging.INFO)  # <-- previously only if NOTSET

    _file_handler = fh
    _current_date = today
    print(f"[logs] Bound file handler to {path}")
    return path

class SocketIOHandler(logging.Handler):
    """Send log lines to all connected clients via Socket.IO."""
    def __init__(self, socketio, event: str = "log_line"):
        super().__init__()
        self.socketio = socketio
        self.event = event

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.socketio.emit(self.event, {"line": msg})
        except Exception as e:
            print(f"[SocketIOHandler] emit failed: {e!r}")
            pass

def schedule_midnight_rotation() -> None:
    def _loop():
        while True:
            now = datetime.now()
            target = datetime.combine((now + timedelta(days=1)).date(), dtime.min)
            delay = max(1.0, (target - now).total_seconds() + 1)
            time.sleep(delay)
            bind_logger_to_today()
    t = threading.Thread(target=_loop, daemon=True)
    t.start()

def init_logging(socketio) -> None:
    bind_logger_to_today()
    root = logging.getLogger()
    if not any(isinstance(h, SocketIOHandler) for h in root.handlers):
        sio_handler = SocketIOHandler(socketio)
        sio_handler.setLevel(logging.INFO)
        sio_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        root.addHandler(sio_handler)
    schedule_midnight_rotation()
    logging.getLogger(__name__).info("Live logging ready")
