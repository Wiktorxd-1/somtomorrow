from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    session,
    send_from_directory,
    request,
    send_file,
    Response,
)
import random
import string
from datetime import datetime, timezone
from .utils import excluded, use_session_data
from .identicon import render_identicon
import io
from PIL import Image

base_bp = Blueprint("base", __name__)


@base_bp.route("/")
@excluded
def index():
    if (
        "token" in session
        and datetime.now(timezone.utc).timestamp() - session.get("login_time", 10000)
        <= 3600
    ):
        # If user is already logged in and the token is valid, redirect to dashboard
        return redirect(url_for("base.dashboard"))
    return redirect(url_for("auth.login"))


@base_bp.route("/favicon.ico")
@base_bp.route("/favicon")
@excluded
def favicon():
    return send_from_directory(
        "static", "images/favs/fav.ico", mimetype="image/vnd.microsoft.icon"
    )


@base_bp.route("/.well-known/security.txt")
@excluded
def securitytxt():
    return send_from_directory("static", "txts/security.txt", mimetype="text/plain")


@base_bp.route("/security.txt")
@excluded
def securitytxtredirect():
    return redirect(url_for("base.securitytxt")), 301


@base_bp.route("/robots")
@base_bp.route("/robots.txt")
@excluded
def robots():
    return send_from_directory("static", "txts/robots.txt", mimetype="text/plain")


@base_bp.route("/dashboard")
@use_session_data
def dashboard():
    return render_template("pages/main/dashboard.html")


@base_bp.route("/info")
@use_session_data
def info():
    return render_template("pages/main/info.html")


@base_bp.route("/api/identicon/<username>")
@excluded
def identicon(username):
    if username == "robinboers":
        return send_from_directory("static", "images/robin.png", mimetype="image/png")
    if username == "hansprosch":
        return send_from_directory("static", "images/hans.png", mimetype="image/png")

    image_bytes = render_identicon(username)
    image_io = io.BytesIO(image_bytes)
    return send_file(image_io, mimetype="image/png")


@base_bp.route("/api/loading.gif")
@excluded
def generate_gif():
    speed = int(request.args.get("speed", 670))

    images = [
        Image.open(
            io.BytesIO(
                render_identicon(
                    "".join(
                        random.choices(
                            string.ascii_letters + string.digits,
                            k=random.randint(5, 20),
                        )
                    ),
                    (0, 0, 0, 0),
                )
            )
        )
        for _ in range(20)
    ]

    gif_bytes = io.BytesIO()
    images[0].save(
        gif_bytes,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=speed,
        loop=0,
        disposal=2,
    )
    gif_bytes.seek(0)

    return Response(gif_bytes.read(), mimetype="image/gif")
