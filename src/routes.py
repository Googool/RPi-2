from __future__ import annotations
import logging
import shutil, time
from flask import Blueprint, render_template, redirect, send_file, url_for, jsonify, request
from pathlib import Path
from .gpio import GpioManager
from .utils import (
    today_str, date_to_compact, compact_to_date,
    LOGS_DIR,
    log_path_for_date,
    list_log_compacts,
    _secure_log_from_compact_or_404,
)

def create_app(app, socketio):
    bp = Blueprint("main", __name__)
    log = logging.getLogger(__name__)
    gpio = GpioManager(socketio)

    # helper: best-effort client ip
    def _client_ip():
        return request.headers.get("X-Forwarded-For", request.remote_addr or "-")

    @bp.get("/")
    def index():
        return render_template("index.html")

    # ---------- LOGS: page + download ----------

    @bp.get("/logs")
    def logs_root():
        return redirect(url_for("main.stream_logs_page", compact=date_to_compact(today_str())))

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
            stream_url=None,
            download_url=url_for("main.logs_download", compact=compact),
            files=files,
            current_name=compact,
            picker_base="/stream/logs",
        )

    @bp.get("/download/logs/<compact>")
    def logs_download(compact: str):
        path: Path = _secure_log_from_compact_or_404(compact)
        return send_file(path, as_attachment=True, download_name=path.name)

    # ---------- GPIO ----------

    @bp.get("/api/gpio")
    def api_gpio_list():
        return jsonify(gpio.state())

    # ADD: create
    @bp.post("/api/gpio")
    def api_gpio_add():
        data = request.get_json(silent=True) or {}
        try:
            pin = int(data.get("pin"))
            name = (data.get("name") or f"Pin {pin}").strip()
            mode = (data.get("mode") or "output").strip()
            value = int(data.get("value") or 0)
            item = gpio.add_pin(pin, name, mode, value)
            log.info("api_gpio_add ip=%s pin=%d name=%s mode=%s value=%d ok=1", _client_ip(), pin, name, mode, value)
            return jsonify(item), 201
        except (TypeError, ValueError) as e:
            log.warning("api_gpio_add ip=%s data=%r ok=0 err=%s", _client_ip(), data, e)
            return jsonify({"error": str(e)}), 400

    # ADD: rename or set (PATCH)
    @bp.patch("/api/gpio/<int:pin>")
    def api_gpio_patch(pin: int):
        data = request.get_json(silent=True) or {}
        try:
            if "name" in data:
                item = gpio.rename_pin(pin, str(data["name"]))
                log.info("api_gpio_rename ip=%s pin=%d name=%s ok=1", _client_ip(), pin, item["name"])
                return jsonify(item)
            if "value" in data:
                item = gpio.set_value(pin, int(data["value"]))
                log.info("api_gpio_set ip=%s pin=%d to=%d ok=1", _client_ip(), pin, item["value"])
                return jsonify(item)
            log.warning("api_gpio_patch ip=%s pin=%d ok=0 err=nothing-to-update", _client_ip(), pin)
            return jsonify({"error": "nothing to update"}), 400
        except (KeyError, ValueError) as e:
            log.warning("api_gpio_patch ip=%s pin=%d data=%r ok=0 err=%s", _client_ip(), pin, data, e)
            return jsonify({"error": str(e)}), 400

    # ADD: delete
    @bp.delete("/api/gpio/<int:pin>")
    def api_gpio_delete(pin: int):
        try:
            gpio.remove_pin(pin)
            log.info("api_gpio_delete ip=%s pin=%d ok=1", _client_ip(), pin)
            return jsonify({"ok": True, "pin": pin})
        except KeyError as e:
            log.warning("api_gpio_delete ip=%s pin=%d ok=0 err=%s", _client_ip(), pin, e)
            return jsonify({"error": str(e)}), 404

    # SYSTEM: summary
    @bp.get("/api/sys")
    def api_sys():
        # RAM via /proc/meminfo
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.strip().split()[0]) * 1024  # kB -> B
            ram_total = mem.get("MemTotal", 0)
            ram_free = mem.get("MemAvailable", 0)
            ram_used = max(0, ram_total - ram_free)
        except Exception:
            ram_total = 512 * 1024 * 1024
            ram_used = 220 * 1024 * 1024

        # Disk via shutil
        try:
            du = shutil.disk_usage("/")
            disk_total, disk_used = du.total, du.used
        except Exception:
            disk_total = 8 * 1024**3
            disk_used  = 3.2 * 1024**3

        # CPU: simple 1-sec load snapshot -> % of 1 core (rough)
        try:
            # Prefer /proc/stat delta
            def _read_cpu():
                with open("/proc/stat") as f:
                    parts = f.readline().split()[1:]
                    vals = list(map(int, parts[:7]))
                    idle = vals[3] + vals[4]
                    total = sum(vals)
                    return idle, total
            i1,t1 = _read_cpu(); time.sleep(0.2); i2,t2 = _read_cpu()
            cpu = (1 - (i2 - i1) / max(1, (t2 - t1))) * 100.0
        except Exception:
            cpu = 12.0

        # Temp (Pi): /sys/class/thermal or vcgencmd
        temp_c = None
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp_c = int(f.read().strip()) / 1000.0
        except Exception:
            # dev pc mock
            temp_c = 41.3

        return jsonify({
            "cpu": round(cpu, 1),
            "ram": {"used": ram_used, "total": ram_total},
            "disk": {"used": disk_used, "total": disk_total},
            "temp_c": temp_c
        })

    # ---------- Socket.IO ----------
    @socketio.on("connect")
    def _connect():
        socketio.emit("server_message", {"message": "Connected!"})

    app.register_blueprint(bp)
