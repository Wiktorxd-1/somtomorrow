from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
import subprocess
import os
from datetime import datetime, timezone
import requests

from .utils import excluded


auth_bp = Blueprint("auth", __name__)


project_dir = os.path.dirname(__file__)

while not os.path.isdir(os.path.join(project_dir, ".git")):
    project_dir = os.path.dirname(project_dir)

project_dir = os.path.abspath(project_dir)


def get_commit_and_deploy_date():
    with open(os.path.join(project_dir, "last_deploy.txt"), "r") as f:
        latest_deploy_date = f.read().strip()

    latest_commit_hash = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%h"], cwd=project_dir
        )
        .strip()
        .decode()
    )
    latest_commit_hash_long = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%H"], cwd=project_dir
        )
        .strip()
        .decode()
    )
    latest_commit_timestamp = int(
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%ct"], cwd=project_dir
        ).strip()
    )
    latest_commit_date = datetime.fromtimestamp(latest_commit_timestamp).strftime(
        "%d-%m-%Y at %H:%M:%S"
    )

    author_name = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%an"], cwd=project_dir
        )
        .strip()
        .decode()
    )
    author_email = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:%ae"], cwd=project_dir
        )
        .strip()
        .decode()
    )

    comdepdata = {
        "latest_deploy_date": latest_deploy_date,
        "latest_commit_hash": latest_commit_hash,
        "latest_commit_hash_long": latest_commit_hash_long,
        "latest_commit_date": latest_commit_date,
        "latest_commit_author_name": author_name,
        "latest_commit_author_email": author_email,
    }

    return comdepdata


comdepdata = get_commit_and_deploy_date()


@auth_bp.route("/login")
@excluded
def login():
    return render_template("pages/login/login.html", **comdepdata)


@auth_bp.route("/login/get_token", methods=["POST"])
@excluded
def get_token():
    school = request.form.get("school")
    username = request.form.get("username")
    password = request.form.get("password")

    # Robin's amazing Vik magic

    reqdata = {"school": school, "username": username, "password": password}

    response = requests.post("https://vik.dupunkto.org/api/authtoday", json=reqdata)

    if str(response.status_code) == "503":
        responsedata = response.json()
        errormessage = responsedata["error"]
        errormessage_formatted = (
            errormessage + "." if not errormessage.endswith(".") else errormessage
        )

        return jsonify({"status": "error", "message": errormessage_formatted}), 503

    else:
        response.raise_for_status()

        authdata = response.json()
        access_token = authdata["access_token"]
        success = set_token_and_info(access_token)

        if not success:
            return jsonify({"status": "error", "message": "Invalid token!"}), 400

        return jsonify({"status": "success"})


@auth_bp.route("/login/own_token", methods=["GET", "POST"])
@excluded
def login_own_token():
    if request.method == "POST":
        access_token_input = request.form.get("token")

        success = set_token_and_info(access_token_input)

        if not success:
            flash("Dat is geen geldige token!", "error")
            return render_template("pages/login/login_own_token.html")

        return redirect(url_for("base.dashboard"))

    return render_template("pages/login/login_own_token.html", **comdepdata)


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

    last_name = (
        f"{middle_name} {response_data['items'][0]['achternaam']}"
        if (middle_name := response_data["items"][0].get("voorvoegsel"))
        else response_data["items"][0]["achternaam"]
    )

    url_schooldata = (
        f"https://api.somtoday.nl/rest/v1/leerlingen/{student_id}/schoolgegevens"
    )

    headers_schooldata = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response_schooldata = requests.get(url_schooldata, headers=headers_schooldata)
    response_schooldata.raise_for_status()

    schooldata_data = response_schooldata.json()

    url_schoolyear = "https://api.somtoday.nl/rest/v1/schooljaren/huidig"

    headers_schoolyear = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response_schoolyear = requests.get(url_schoolyear, headers=headers_schoolyear)
    response_schoolyear.raise_for_status()

    schoolyear_data = response_schoolyear.json()

    session["student_id"] = student_id
    session["first_name"] = first_name
    session["last_name"] = last_name.replace(
        "Ten Berg", "ten Berg"
    )  # Yeah I did just hardcode a fix that my school made in my surname
    session["identicon_name"] = first_name.strip().lower().replace(
        " ", ""
    ) + last_name.strip().lower().replace(" ", "")
    session["school_name"] = schooldata_data["huidigeVestiging"]["naam"]
    session["main_class"] = schooldata_data["stamgroepnaam"]
    session["school_year"] = schoolyear_data

    session["token"] = token
    session["login_time"] = datetime.now(timezone.utc).timestamp()

    return True


@auth_bp.route("/login/new")
@excluded
def login_new():
    return render_template("pages/login/login_new.html", **comdepdata)


@auth_bp.route("/logout")
@excluded
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/login/dev")
@excluded
def logindev():
    user = request.args.get("user")

    with open(os.path.join(project_dir, f"rtoken{user}.txt"), "r") as file:
        rtoken = file.read()
    url = "https://somtoday.nl/oauth2/token"
    body = {
        "grant_type": "refresh_token",
        "refresh_token": rtoken,
        "client_id": "somtoday-leerling-native",
    }
    response = requests.post(url, data=body)

    data = response.json()

    with open(os.path.join(project_dir, f"rtoken{user}.txt"), "w") as file:
        file.write(data.get("refresh_token", rtoken))

    set_token_and_info(data.get("access_token"))

    return redirect(url_for("base.dashboard"))


# start devb


@auth_bp.route("/login/devauto")
@excluded
def logindevauto():
    with open(os.path.join(project_dir, "rtoken.txt"), "r") as file:
        rtoken = file.read()
    url = "https://somtoday.nl/oauth2/token"
    body = {
        "grant_type": "refresh_token",
        "refresh_token": rtoken,
        "client_id": "somtoday-leerling-native",
    }
    response = requests.post(url, data=body)

    data = response.json()

    with open(os.path.join(project_dir, "rtoken.txt"), "w") as file:
        file.write(data.get("refresh_token", rtoken))

    set_token_and_info(data.get("access_token"))

    return redirect(url_for("base.dashboard"))


@auth_bp.route("/login/devtester", methods=["GET", "POST"])
@excluded
def logindevtester():
    if request.method == "POST":
        choice = request.form.get("choice")

        with open(f"dev/rtoken{choice}.txt", "r") as file:
            rtoken = file.read()

        url = "https://somtoday.nl/oauth2/token"
        body = {
            "grant_type": "refresh_token",
            "refresh_token": rtoken,
            "client_id": "somtoday-leerling-native",
        }
        response = requests.post(url, data=body)

        data = response.json()

        with open(f"dev/rtoken{choice}.txt", "w") as file:
            file.write(data.get("refresh_token", rtoken))

        set_token_and_info(data.get("access_token"))

        return redirect(url_for("base.dashboard"))

    return """
        <form method="post">
            <label>Choose a token</label><br>

            <input type="radio" id="choice-a" name="choice" value="a">
            <label for="choice-a">a</label><br>

            <input type="radio" id="choice-b" name="choice" value="b">
            <label for="choice-b">b</label><br>

            <input type="radio" id="choice-c" name="choice" value="c">
            <label for="choice-c">c</label><br>

            <input type="submit" value="Continue">
        </form>
    """


# end devb
