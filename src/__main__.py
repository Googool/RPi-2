from . import app, socketio
import logging

if __name__ == "__main__":
    logging.getLogger(__name__).info("server_start port=5000 debug=False async=eventlet")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)
