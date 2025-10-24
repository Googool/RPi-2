from __future__ import annotations
import logging, json
from pathlib import Path
from flask import Blueprint, render_template, redirect, send_file, url_for, Response, stream_with_context
from .config import load_cfg, CONFIG_PATH
from .utils import (
    today_str, date_to_compact, compact_to_date,
    LOGS_DIR, CFG_SNAP_DIR,
    log_path_for_date, cfg_path_for_date,
    list_log_compacts, list_cfg_compacts,
    _secure_log_from_compact_or_404, _secure_cfg_from_compact_or_404,
)

def create_app(app, socketio):
    bp = Blueprint("main", __name__)

    @bp.get("/")
    def index():
        return render_template("index.html")

    # ---------- LOGS: page + download ----------

    @bp.get("/logs")
    def logs_root():
        # Redirect to today's log stream page using compact date
        return redirect(url_for("main.stream_logs_page",
                                compact=date_to_compact(today_str())))

    # Page: /stream/logs/<compact>
    @bp.get("/stream/logs/<compact>")
    def stream_logs_page(compact: str):
        path: Path = _secure_log_from_compact_or_404(compact)
        initial = path.read_text(encoding="utf-8")
        live = (compact_to_date(compact) == today_str())
        files = list_log_compacts(LOGS_DIR, exclude_today=True)
        return render_template(
            "stream.html",
            title=f"Logs · {compact}",
            initial=initial,
            live=live,
            # logs stream via Socket.IO already; no SSE stream URL needed
            stream_url=None,
            download_url=url_for("main.logs_download", compact=compact),
            files=files,
            current_name=compact,
            picker_base="/stream/logs",
            mode="logs",
        )

    # Download: /download/logs/<compact>
    @bp.get("/download/logs/<compact>")
    def logs_download(compact: str):
        path: Path = _secure_log_from_compact_or_404(compact)
        return send_file(path, as_attachment=True, download_name=path.name)

    # ---------- CONFIG: page + download (polling refresh when live) ----------

    # Page: /stream/cfg  (shows the current config; not live)
    @bp.get("/stream/cfg")
    def stream_cfg_page():
        cfg = load_cfg()  # ensures file exists and loads it
        initial = json.dumps(cfg, indent=2)
        return render_template(
            "stream.html",
            title="Config",
            initial=initial,
            live=False,                 # no live streaming for config
            mode="cfg",                 # lets the template/nav know it's config
            stream_url=None,            # not used in cfg mode
            download_url=url_for("main.cfg_download"),
            files=None,                 # no picker for config
            picker_base=None,
            current_name=None,
        )

    # Download: /download/cfg  (downloads cfg.json)
    @bp.get("/download/cfg")
    def cfg_download():
        return send_file(CONFIG_PATH, as_attachment=True, download_name="cfg.json")

    # ---------- Socket.IO (unchanged) ----------
    @socketio.on("connect")
    def _connect():
        logging.info("Socket.IO client connected")
        socketio.emit("server_message", {"message": "Connected!"})

    app.register_blueprint(bp)
