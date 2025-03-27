from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, g
from datetime import timedelta, datetime
import requests
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("key")

app = Flask(__name__)
app.secret_key = key
app.permanent_session_lifetime = timedelta(hours=1)


# All the routes that do not require login, so just the excluded routes
def excluded(endpoint):
    endpoint.is_excluded = True
    return endpoint


@app.before_request
def check_login():
    view_func = app.view_functions.get(request.endpoint)

    if view_func and getattr(view_func, "is_excluded", False):
        return  # Skip token check if endpoint is excluded

    if "static" in request.endpoint or "favicon" in request.endpoint:
        return  # Static files are also excluded

    if "token" not in session or datetime.utcnow().timestamp() - session.get("login_time", 0) > 3600:
        return redirect(url_for("logout"))


def use_session_data(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        for key in session.keys():
            setattr(g, key, session[key])
        return f(*args, **kwargs)

    return wrapper


@app.route('/favicon.ico')
@app.route('/favicon')
def favicon():
    return send_from_directory('static', "tempfav.ico", mimetype='image/vnd.microsoft.icon')


@app.route("/")
@excluded
def index():
    if 'token' in session and datetime.utcnow().timestamp() - session.get("login_time", 10000) <= 3600:
        # If user is already logged in and the token is valid, redirect to dashboard
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login")
@excluded
def login():
    return render_template("login/login.html")


@app.route("/login/get_token", methods=["POST"])
@excluded
def get_token():
    school = request.form.get("school")
    username = request.form.get("username")
    password = request.form.get("password")

    # Robin's amazing Vik magic

    reqdata = {
        "school": school,
        "username": username,
        "password": password
    }

    response = requests.post("???", json=reqdata)

    response.raise_for_status()

    authdata = response.json()

    access_token = authdata["access_token"]

    success = set_token_and_info(access_token)

    if not success:
        flash("Dat is geen geldige token!", "error")
        return render_template("login/login.html")

    return redirect(url_for("dashboard"))


@app.route("/login/own_token", methods=["GET", "POST"])
@excluded
def login_own_token():
    if request.method == 'POST':
        access_token_input = request.form.get("token")

        success = set_token_and_info(access_token_input)

        if not success:
            flash("Dat is geen geldige token!", "error")
            return render_template("login/login_own_token.html")

        return redirect(url_for("dashboard"))

    return render_template("login/login_own_token.html")


def set_token_and_info(token):
    url = "https://api.somtoday.nl/rest/v1/leerlingen"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)

    if str(response.status_code) == "401":
        return False

    response_data = response.json()

    student_id = response_data["items"][0]["links"][0]["id"]
    first_name = response_data["items"][0]["roepnaam"]

    last_name = f"{middle_name} {response_data['items'][0]['achternaam']}" if (
        middle_name := response_data["items"][0].get("voorvoegsel")) else response_data['items'][0]['achternaam']

    url = f"https://api.somtoday.nl/rest/v1/leerlingen/{student_id}/schoolgegevens"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response_schooldata = requests.get(url, headers=headers)
    response_schooldata.raise_for_status()

    schooldata_data = response_schooldata.json()

    session["student_id"] = student_id
    session["first_name"] = first_name
    session["last_name"] = last_name
    session["school_name"] = schooldata_data["huidigeVestiging"]["naam"]
    session["main_class"] = schooldata_data["stamgroepnaam"]
    session["token"] = token
    session['login_time'] = datetime.utcnow().timestamp()

    return True


@app.route("/dashboard")
@use_session_data
def dashboard():
    return render_template("main/dashboard.html")


@app.route("/logout")
@excluded
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.errorhandler(404)
@excluded
def not_found(e):
    return render_template("other/404.html", e=e), 404


@app.errorhandler(500)
@excluded
def internal_server_error(e):
    return render_template('other/500.html', e=e), 500

if __name__ == "__main__":
    app.run(debug=True)
