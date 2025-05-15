from flask import Flask, request, redirect, url_for, render_template
from modules.auth import auth_bp
from modules.base import base_bp
from modules.grades import grades_bp
from modules.planner import planner_bp
from modules.schedule import schedule_bp

from modules.utils import logged_in, excluded

from datetime import timedelta
import os
import locale


app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(hours=1)


locale.setlocale(locale.LC_TIME, "nl_NL")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


@app.before_request
def check_login():
    if request.endpoint is None:
        return  # For 404 and stuff

    view_func = app.view_functions.get(request.endpoint)

    if view_func and getattr(view_func, "is_excluded", False):
        return  # Skip token check if endpoint is excluded

    excluded_pages = ["static", "favicon", "security", "robots"]

    if any(keyword in request.endpoint for keyword in excluded_pages) or any(keyword in request.url for keyword in excluded_pages):
        return

    if not logged_in():
        if "api" in request.url or "island" in request.url:
            return "Token not valid", 401  # Sometimes you can't return the logout page
        return redirect(url_for("auth.logout"))


app.register_blueprint(auth_bp)
app.register_blueprint(base_bp)
app.register_blueprint(grades_bp)
app.register_blueprint(planner_bp)
app.register_blueprint(schedule_bp)


# Error pages


@app.errorhandler(404)
@excluded
def not_found(e):
    return render_template("pages/other/404.html", e=e, login=logged_in()), 404


@app.errorhandler(500)
@excluded
def internal_server_error(e):
    return render_template("pages/other/500.html", e=e, login=logged_in()), 500


if __name__ == "__main__":
    app.run(debug=True, port=4000)
