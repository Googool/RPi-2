import eventlet
eventlet.monkey_patch()

import os, logging
from flask import Flask
from flask_socketio import SocketIO


app = Flask(__name__, static_folder='../static', template_folder='../templates')
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "really_secret_key")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

from .logger import init_logging
init_logging(socketio)

def _start_heartbeat_once():
    if app.config.get("HEARTBEAT_STARTED"):
        return
    app.config["HEARTBEAT_STARTED"] = True

    def heartbeat_loop():
        log = logging.getLogger("heartbeat")
        log.info("Heartbeat loop started (2s interval)")
        i = 0
        while True:
            i += 1
            log.info("tick #%d", i)
            socketio.sleep(2)

    socketio.start_background_task(heartbeat_loop)

_start_heartbeat_once()

from .routes import create_app as _create_routes
_create_routes(app, socketio)
