from flask import Blueprint, render_template

def create_app(app, socketio):
    bp = Blueprint("main", __name__)

    @bp.route("/", methods=["GET"])
    def _index():
        return render_template("index.html")

    app.register_blueprint(bp)

    @socketio.on("connect")
    def _connect():
        socketio.emit("server_message", {"message": "Connected!"})
