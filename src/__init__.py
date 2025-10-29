import os
from flask import Flask
from flask_socketio import SocketIO


app = Flask(__name__, static_folder='../static', template_folder='../templates')
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "really_secret_key")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=False, engineio_logger=False)

from .logger import init_logging
init_logging(socketio)

from .routes import create_app as _create_routes
_create_routes(app, socketio)
