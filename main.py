from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, g, send_file, jsonify, Response

from PIL import Image
from datetime import timedelta, datetime, timezone
from functools import wraps
import io
import json
import locale
import os
import pytz
import random
import re
import requests
import string
import subprocess
import time

from identicon import render_identicon

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(hours=1)

locale.setlocale(locale.LC_TIME, "nl_NL")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Things with logging in and getting the tokens


# All the routes that do not require login, so just the excluded routes
def excluded(endpoint):
    endpoint.is_excluded = True
    return endpoint


def logged_in():
    if "token" in session and datetime.now(timezone.utc).timestamp() - session.get("login_time", 0) < 3600:
        return True
    return False


def capit(string):
    return string[:1].upper() + string[1:]


def remove_html(string):
    if string:
        string_with_linebreaks = string.replace("<br>", " ")
        return re.sub(re.compile("<.*?>"), "", string_with_linebreaks)
    return string


def max_len(string, max_length):
    return string if len(string) <= max_length else string[: max_length - 3] + "..."


def print_json_data(data):
    def sterilize_data(inputdata):
        if isinstance(inputdata, dict):
            return {key: sterilize_data(value) for key, value in inputdata.items()}
        elif isinstance(inputdata, list):
            return [sterilize_data(item) for item in inputdata]
        elif isinstance(inputdata, tuple):
            return tuple(sterilize_data(item) for item in inputdata)
        elif isinstance(inputdata, set):
            return {sterilize_data(item) for item in inputdata}
        elif isinstance(inputdata, datetime):
            return inputdata.timestamp()
        else:
            return inputdata

    print(json.dumps(sterilize_data(data), indent=4))


def get_commit_and_deploy_date():
    with open(os.path.join(BASE_DIR, "last_deploy.txt"), "r") as f:
        latest_deploy_date = f.read().strip()

    latest_commit_hash = subprocess.check_output(["git", "log", "-1", "--pretty=format:%h"], cwd=BASE_DIR).strip().decode()
    latest_commit_hash_long = subprocess.check_output(["git", "log", "-1", "--pretty=format:%H"], cwd=BASE_DIR).strip().decode()
    latest_commit_timestamp = int(subprocess.check_output(["git", "log", "-1", "--pretty=format:%ct"], cwd=BASE_DIR).strip())
    latest_commit_date = datetime.fromtimestamp(latest_commit_timestamp).strftime("%d-%m-%Y at %H:%M:%S")

    author_name = subprocess.check_output(["git", "log", "-1", "--pretty=format:%an"], cwd=BASE_DIR).strip().decode()
    author_email = subprocess.check_output(["git", "log", "-1", "--pretty=format:%ae"], cwd=BASE_DIR).strip().decode()

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
        return redirect(url_for("logout"))


def use_session_data(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        for key in session.keys():
            setattr(g, key, session[key])
            g.capit = capit
        return f(*args, **kwargs)

    return wrapper


@app.route("/login")
@excluded
def login():
    return render_template("pages/login/login.html", **comdepdata)


@app.route("/login/get_token", methods=["POST"])
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
        errormessage_formatted = errormessage + "." if not errormessage.endswith(".") else errormessage

        return jsonify({"status": "error", "message": errormessage_formatted}), 503

    else:
        response.raise_for_status()

        authdata = response.json()
        access_token = authdata["access_token"]
        success = set_token_and_info(access_token)

        if not success:
            return jsonify({"status": "error", "message": "Invalid token!"}), 400

        return jsonify({"status": "success"})


@app.route("/login/own_token", methods=["GET", "POST"])
@excluded
def login_own_token():
    if request.method == "POST":
        access_token_input = request.form.get("token")

        success = set_token_and_info(access_token_input)

        if not success:
            flash("Dat is geen geldige token!", "error")
            return render_template("pages/login/login_own_token.html")

        return redirect(url_for("dashboard"))

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

    last_name = f"{middle_name} {response_data['items'][0]['achternaam']}" if (middle_name := response_data["items"][0].get("voorvoegsel")) else response_data["items"][0]["achternaam"]

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
    session["last_name"] = last_name.replace("Ten Berg", "ten Berg")
    session["identicon_name"] = first_name.strip().lower().replace(" ", "") + last_name.strip().lower().replace(" ", "")
    session["school_name"] = schooldata_data["huidigeVestiging"]["naam"]
    session["main_class"] = schooldata_data["stamgroepnaam"]

    session["token"] = token
    session["login_time"] = datetime.now(timezone.utc).timestamp()

    return True



@app.route("/login/new")
@excluded
def login_new():
    return render_template("pages/login/login_new.html", **comdepdata)


@app.route("/logout")
@excluded
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/login/dev")
@excluded
def logindev():
    user = request.args.get("user")

    with open(os.path.join(BASE_DIR, f"rtoken{user}.txt"), "r") as file:
        rtoken = file.read()
    url = "https://somtoday.nl/oauth2/token"
    body = {
        "grant_type": "refresh_token",
        "refresh_token": rtoken,
        "client_id": "somtoday-leerling-native",
    }
    response = requests.post(url, data=body)

    data = response.json()

    with open(os.path.join(BASE_DIR, f"rtoken{user}.txt"), "w") as file:
        file.write(data.get("refresh_token", rtoken))

    set_token_and_info(data.get("access_token"))

    return redirect(url_for("dashboard"))


# start devb


@app.route("/login/devauto")
@excluded
def logindevauto():
    with open(os.path.join(BASE_DIR, "rtoken.txt"), "r") as file:
        rtoken = file.read()
    url = "https://somtoday.nl/oauth2/token"
    body = {
        "grant_type": "refresh_token",
        "refresh_token": rtoken,
        "client_id": "somtoday-leerling-native",
    }
    response = requests.post(url, data=body)

    data = response.json()

    with open(os.path.join(BASE_DIR, "rtoken.txt"), "w") as file:
        file.write(data.get("refresh_token", rtoken))

    set_token_and_info(data.get("access_token"))

    return redirect(url_for("dashboard"))


@app.route("/login/devtester", methods=["GET", "POST"])
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

        return redirect(url_for("dashboard"))

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


@app.route("/")
@excluded
def index():
    if "token" in session and datetime.now(timezone.utc).timestamp() - session.get("login_time", 10000) <= 3600:
        # If user is already logged in and the token is valid, redirect to dashboard
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# Basic files


@app.route("/favicon.ico")
@app.route("/favicon")
@excluded
def favicon():
    return send_from_directory("static", "images/favs/fav.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/.well-known/security.txt")
@excluded
def securitytxt():
    return send_from_directory("static", "txts/security.txt", mimetype="text/plain")


@app.route("/security.txt")
@excluded
def securitytxtredirect():
    return redirect(url_for("securitytxt")), 301


@app.route("/robots")
@app.route("/robots.txt")
@excluded
def robots():
    return send_from_directory("static", "txts/robots.txt", mimetype="text/plain")


def clean_somdata(data):
    if isinstance(data, list):
        return [clean_somdata(item) for item in data]
    elif isinstance(data, dict):
        return {key: clean_somdata(value) for key, value in data.items() if key not in ["links", "permissions", "UUID"]}
    else:
        return data


# Main pages


@app.route("/dashboard")
@use_session_data
def dashboard():
    return render_template("pages/main/dashboard.html")


@app.route("/cijfers")
@use_session_data
def grades_main():
    return redirect(url_for("testgrades"))


@app.route("/cijfers/toetscijfers")
@use_session_data
def testgrades():
    return render_template("pages/main/grades/testgrades.html")


def get_icon(subject):
    subjects_icons = {
        "engels": '<img class="icon uk" src="/static/images/flags/uk.svg">',
        "nederlands": '<img class="icon nl" src="/static/images/flags/nl.svg">',
        "latijn": '<img class="icon la" src="/static/images/flags/va.svg">',
        "grieks": '<img class="icon gr" src="/static/images/flags/gr.svg">',
        "frans": '<img class="icon fr" src="/static/images/flags/fr.svg">',
        "spaans": '<img class="icon es" src="/static/images/flags/es.svg">',
        "duits": '<img class="icon de" src="/static/images/flags/de.svg">',
        "fries": '<img class="icon frr" src="/static/images/flags/frr.svg">',
        "italiaans": '<img class="icon it" src="/static/images/flags/it.svg">',
        "russisch": '<img class="icon it" src="/static/images/flags/ru.svg">',
        "arabisch": '<img class="icon ar" src="/static/images/flags/ar.svg">',
        "turks": '<img class="icon tr" src="/static/images/flags/tr.svg">',
        "chinees": '<img class="icon cn" src="/static/images/flags/cn.svg">',
        "scheikunde": '<i class="fa-solid fa-vial"></i>',
        "natuurkunde": '<i class="fa-solid fa-atom"></i>',
        "biologie": '<i class="fa-solid fa-seedling"></i>',
        "techniek": '<i class="fa-solid fa-screwdriver-wrench"></i>',
        "rekenen": '<i class="fa-solid fa-plus-minus"></i>',
        "dans": '<i class="fa-solid fa-person-rays"></i>',
        "maatschappijleer": '<i class="fa-solid fa-people-group"></i>',
        "burgerschap": '<i class="fa-solid fa-people-group"></i>',
        "onderzoek": '<i class="fa-solid fa-pen-ruler"></i>',
        "ontwerpen": 'i class="fa-solid fa-microscope"></i>',
        "kunst": '<i class="fa-solid fa-palette"></i>',
        "beeldende vorming": '<i class="fa-solid fa-palette"></i>',
        "muziek": '<i class="fa-solid fa-music"></i>',
        "natuur": '<i class="fa-solid fa-microscope"></i>',
        "technologie": '<i class="fa-solid fa-microscope"></i>',
        "drama": '<i class="fa-solid fa-masks-theater"></i>',
        "theater": '<i class="fa-solid fa-masks-theater"></i>',
        "geschiedenis": '<i class="fa-solid fa-landmark"></i>',
        "lichamelijke opvoeding": '<i class="fa-solid fa-futbol"></i>',
        "beweging": '<i class="fa-solid fa-futbol"></i>',
        "economie": '<i class="fa-solid fa-euro-sign"></i>',
        "aardrijkskunde": '<i class="fa-solid fa-earth-europe"></i>',
        "godsdienst": '<i class="fa-solid fa-dove"></i>',
        "levensbeschouwing": '<i class="fa-solid fa-dove"></i>',
        "digitale geletterdheid": '<i class="fa-solid fa-computer"></i>',
        "informatica": '<i class="fa-solid fa-code"></i>',
        "wiskunde": '<i class="fa-solid fa-calculator"></i>',
        "bedrijfseconomie": '<i class="fa-solid fa-building"></i>',
        "management": '<i class="fa-solid fa-building"></i>',
        "filosofie": '<i class="fa-solid fa-brain"></i>',
    }
    for key in subjects_icons:
        if key.lower() in subject.lower():
            return subjects_icons[key]
    return '<i class="fa-solid fa-book"></i>'


@app.route("/api/islands/grades/testgrades")
@use_session_data
def testgrades_island():
    student_id = session["student_id"]
    token = session["token"]

    api_url = f"https://api.somtoday.nl/rest/v1/resultaten/huidigVoorLeerling/{student_id}?additional=vaknaam&additional=resultaatkolom&additional=heeftalternatiefniveau&additional=naamalternatiefniveau&additional=naamstandaardniveau&additional=leerjaar&additional=periodeAfkorting&type=Toetskolom&type=SamengesteldeToetsKolom&type=Werkstukcijferkolom&type=Advieskolom&type=PeriodeGemiddeldeKolom&type=RapportGemiddeldeKolom&type=RapportCijferKolom&type=RapportToetskolom&type=SEGemiddeldeKolom&type=ToetssoortGemiddeldeKolom"

    headers_list = [
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=0-99",
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=100-199",
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=200-299",
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=300-399",
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=400-499",
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=500-599",
        },
    ]

    api_data = []

    for headers in headers_list:
        response = requests.get(api_url, headers=headers)
        responseData = response.json()
        for item in responseData["items"]:
            api_data.append(item)

    api_data = clean_somdata(api_data)

    types_to_include = ["Toetskolom", "Werkstukcijferkolom", "Advieskolom"]
    api_data = [item for item in api_data if item["type"] in types_to_include and ("geldendResultaat" in item or "resultaatLabelAfkorting" in item)]  # Filter unwanted grade types

    def format_date(dt_entered):
        now = datetime.now(pytz.timezone("Europe/Amsterdam"))
        if dt_entered.date() == now.date():
            formatted = f"Vandaag om {dt_entered.strftime('%H:%M:%S')}"
        elif dt_entered.date() == (now.date() - timedelta(days=1)):
            formatted = f"Gisteren om {dt_entered.strftime('%H:%M:%S')}"
        else:
            if dt_entered.year == now.year:
                formatted = dt_entered.strftime("%a %d %b om %H:%M:%S")
            else:
                formatted = dt_entered.strftime("%a %d %b %Y om %H:%M:%S")
        return formatted

    def grade_is_fail(number_grade, letter_grade):
        try:
            result_float = float(number_grade.replace(",", "."))

            if result_float < 5.5:
                is_fail = True
            else:
                is_fail = False
        except Exception:
            if letter_grade == "O":
                is_fail = True
            else:
                is_fail = False
        return is_fail

    for grade in api_data:
        if grade.get("resultaatLabelAfkorting"):
            result = grade["resultaatLabelAfkorting"]
            dt_entered = datetime.strptime(grade["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            result = grade["resultaat"]
            real_result = grade["geldendResultaat"]

            if result == real_result:
                dt_entered = datetime.strptime(grade["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")
            else:
                result = real_result
                dt_entered = datetime.strptime(grade["herkansing"]["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")

        formatted_dt_entered = format_date(dt_entered)

        grade_subject_name = grade["vak"]["naam"]
        grade_test_name = grade["omschrijving"]

        grade["subject_nice"] = capit(grade_subject_name)
        grade["datetime_sort"] = dt_entered.isoformat()
        grade["datetime_nice"] = formatted_dt_entered
        grade["datetime_nice_extended"] = dt_entered.strftime("%A %d %B %Y om %H:%M:%S")
        grade["icon"] = get_icon(grade["vak"]["naam"])
        grade["test_nice"] = capit(grade_test_name)
        grade["result"] = result
        grade["max_weight"] = max(grade["weging"], grade.get("examenWeging", 0))

        grade["is_fail"] = grade_is_fail(grade.get("geldendResultaat"), grade.get("resultaatLabelAfkorting"))

        grade["confetti"] = True if float(grade.get("geldendResultaat", "0.0").replace(",", ".")) >= 10 else False

        if grade.get("herkansing"):
            grade["retake"] = {
                "first_retake": {
                    "date": format_date(datetime.strptime(grade["herkansing"]["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")),
                    "result": grade["herkansing"].get("resultaat", "onbekend"),
                    "result_is_fail": grade_is_fail(grade["herkansing"].get("resultaat", "onbekend"), ""),
                    "result_is_confetti": True if float(grade["herkansing"].get("resultaat", "10.0").replace(",", ".")) >= 10 else False,
                    "effective_result": True if grade["geldendResultaat"] == grade["herkansing"].get("resultaat", "onbekend") else False,
                },
                "first_attempt": {
                    "date": format_date(datetime.strptime(grade["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")),
                    "result": grade["resultaat"],
                    "result_is_fail": grade_is_fail(grade.get("resultaat"), grade.get("resultaatLabelAfkorting")),
                    "result_is_confetti": True if float(grade.get("resultaat", grade.get("resultaatLabelAfkorting")).replace(",", ".")) >= 10 else False,
                    "effective_result": True if grade["resultaat"] == grade["geldendResultaat"] else False,
                },
            }
            grade["retake_is_effective_result"] = False if grade["resultaat"] == grade["geldendResultaat"] else True

    api_data = sorted(api_data, key=lambda x: x["datetime_sort"], reverse=True)

    max_amount = request.args.get("max")
    if max_amount:
        api_data = api_data[: int(max_amount)]

    return render_template("islands/grades/testgrades-island.html", gradelist=api_data)


def get_zipped_data_with_dates(year, weeknum, data):
    year = int(year)
    weeknum = int(weeknum)

    monday = datetime.strptime(f"{year}-W{weeknum - 1}-1", "%Y-W%W-%w").date()
    tuesday = monday + timedelta(days=1)
    wednesday = monday + timedelta(days=2)
    thursday = monday + timedelta(days=3)
    friday = monday + timedelta(days=4)

    dayname = [
        monday.strftime("%a %d %B"),
        tuesday.strftime("%a %d %B"),
        wednesday.strftime("%a %d %B"),
        thursday.strftime("%a %d %B"),
        friday.strftime("%a %d %B"),
    ]

    today = datetime.today().date()
    current_day_class = []

    for day in [monday, tuesday, wednesday, thursday, friday]:
        if day == today:
            current_day_class.append("today")
        else:
            current_day_class.append("")

    zipped_data = zip(data, dayname, current_day_class)

    days_to_include = request.args.get("days")

    if days_to_include == "today":
        if any(current_day_class):
            today_index = current_day_class.index("today")
            zipped_data = [list(zipped_data)[today_index]]
        else:
            zipped_data = [list(zipped_data)[0]]

    return zipped_data


@app.route("/rooster")
@use_session_data
def schedule_main():
    today = datetime.today()
    if today.weekday() in [5, 6]:
        next_week = today + timedelta(days=7 - today.weekday())
    else:
        next_week = today
    year = next_week.year
    weeknum = next_week.isocalendar()[1]
    return render_template("pages/main/schedule.html", current_weeknum=weeknum, current_year=year)


@app.route("/api/islands/schedule")
@use_session_data
def schedule_island():
    token = session["token"]
    student_id = session["student_id"]

    weeknum = request.args.get("w")
    year = request.args.get("y")

    if not weeknum or not year:
        today = datetime.today()
        if today.weekday() in [5, 6]:
            next_week = today + timedelta(days=7 - today.weekday())
        else:
            next_week = today
        weeknum = next_week.isocalendar()[1]
        year = next_week.year

    api_url = f"https://api.somtoday.nl/rest/v1/afspraakitems/{student_id}/jaar/{year}/week/{weeknum}?additional=docentAfkortingen"

    api_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    response = requests.get(api_url, headers=api_headers)
    api_data = response.json()

    api_data = clean_somdata(api_data)

    schedule_data = [[], [], [], [], []]

    for appointment in api_data["items"]:
        dt_start = datetime.strptime(appointment["beginDatumTijd"], "%Y-%m-%dT%H:%M:%S")
        dt_end = datetime.strptime(appointment["eindDatumTijd"], "%Y-%m-%dT%H:%M:%S")

        appointment["title"] = (capit(appointment["vak"]["naam"]).replace("e taal en literatuur", "") if len(appointment["vak"]["naam"].replace("e taal en literatuur", "")) < 20 else appointment["vak"]["afkorting"].upper()) if appointment.get("vak", {}).get("naam") else appointment["titel"]
        appointment["title_full"] = capit(appointment["vak"]["naam"]) if appointment.get("vak", {}).get("naam") else appointment["titel"]

        appointment["icon"] = get_icon(appointment["vak"]["naam"] if appointment.get("vak", {}).get("naam") else appointment["titel"])

        appointment["dt_start"] = dt_start
        appointment["dt_end"] = dt_end

        # The container goes from 8 to 18, so 10 hours, so 100% is 10 hours, so 10% is 60 minutes so 1 minute is 1/6%

        duration_minutes = int((dt_end - dt_start).total_seconds() // 60)

        eight_am = datetime(dt_start.year, dt_start.month, dt_start.day, 8, 0)
        minutes_since_8am = max(0, (dt_start - eight_am).total_seconds() // 60)

        appointment["height"] = duration_minutes * (1 / 6)
        appointment["top"] = minutes_since_8am * (1 / 6)

        if appointment.get("beginLesuur"):
            if appointment.get("eindLesuur"):
                appointment["lesson_hours"] = f"{appointment['beginLesuur']}e" if appointment["beginLesuur"] == appointment["eindLesuur"] else f"{appointment['beginLesuur']}e - {appointment['eindLesuur']}e"
            else:
                appointment["lesson_hours"] = f"{appointment['beginLesuur']}e"
        appointment["start_time"] = dt_start.strftime("%H:%M")
        appointment["end_time"] = dt_end.strftime("%H:%M")
        appointment["type"] = appointment["afspraakItemType"].lower()
        appointment["date"] = dt_start.strftime("%a %d %b")

        schedule_data[dt_start.weekday()].append(appointment)

    # This is very broken, but i dont want to fix

    for daydata in schedule_data:
        daydata = sorted(daydata, key=lambda x: x["dt_start"])

        for appt in daydata:
            overlapping = [a for a in daydata if not (a["dt_end"] <= appt["dt_start"] or a["dt_start"] >= appt["dt_end"])]
            count = len(overlapping)

            # Position is the percentage of left-margin that needs to be added

            if count == 1:
                appt["position"] = 0
                appt["width"] = 100
            else:
                index = sorted(overlapping, key=lambda x: x["dt_end"]).index(appt)
                appt["position"] = index * (100 / count)
                appt["width"] = 100 / count

    zipped_data = get_zipped_data_with_dates(year, weeknum, schedule_data)

    return render_template("islands/schedule-island.html", zipped_data=zipped_data)


@app.route("/planner")
@use_session_data
def planner_main():
    today = datetime.today()
    if today.weekday() in [5, 6]:
        next_week = today + timedelta(days=7 - today.weekday())
    else:
        next_week = today
    year = next_week.year
    weeknum = next_week.isocalendar()[1]

    return render_template("pages/main/planner.html", current_weeknum=weeknum, current_year=year)


@app.route("/api/islands/planner")
@use_session_data
def planner_island():
    token = session["token"]
    student_id = session["student_id"]

    weeknum = request.args.get("w")
    year = request.args.get("y")

    if not weeknum or not year:
        today = datetime.today()
        if today.weekday() in [5, 6]:
            next_week = today + timedelta(days=7 - today.weekday())
        else:
            next_week = today
        weeknum = next_week.isocalendar()[1]
        year = next_week.year

    api_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    api_url1 = f"https://api.somtoday.nl/rest/v1/studiewijzeritemafspraaktoekenningen?geenDifferentiatieOfGedifferentieerdVoorLeerling={student_id}&jaarWeek={year}~{weeknum}&additional=leerlingen&additional=swigemaaktVinkjes&additional=lesgroep&additional=leerlingenMetInleveringStatus&additional=leerlingProjectgroep&additional=studiewijzerId"

    response1 = requests.get(api_url1, headers=api_headers)
    api_data1 = response1.json()

    api_url2 = f"https://api.somtoday.nl/rest/v1/studiewijzeritemdagtoekenningen?geenDifferentiatieOfGedifferentieerdVoorLeerling={student_id}&jaarWeek={year}~{weeknum}&additional=leerlingen&additional=swigemaaktVinkjes&additional=lesgroep&additional=leerlingenMetInleveringStatus&additional=leerlingProjectgroep&additional=studiewijzerId"

    response2 = requests.get(api_url2, headers=api_headers)
    api_data2 = response2.json()

    api_data = api_data1["items"] + api_data2["items"]

    # api_data = clean_somdata(api_data)

    planner_data = [[], [], [], [], []]

    for homework in api_data:
        dt = datetime.strptime(homework["datumTijd"], "%Y-%m-%dT%H:%M:%S.%f%z")
        subject_name = homework["lesgroep"]["vak"]["naam"]
        homework["subject_long"] = capit(subject_name).replace("e taal en literatuur", "")
        homework["subject_short"] = homework["lesgroep"]["vak"]["afkorting"]

        if homework.get("studiewijzerItem"):
            if homework["studiewijzerItem"].get("onderwerp"):
                homework["title"] = max_len(remove_html(homework["studiewijzerItem"]["onderwerp"]), 35)
            else:
                homework["title"] = max_len(remove_html(homework["studiewijzerItem"]["omschrijving"]), 35)
        else:
            continue

        homework["icon"] = get_icon(subject_name)
        homework["type"] = "inleveropdracht" if homework["studiewijzerItem"]["inleverperiodes"] else homework["studiewijzerItem"].get("huiswerkType", "undefined").lower()
        planner_data[dt.weekday()].append(homework)

        if homework["additionalObjects"].get("swigemaaktVinkjes"):
            if homework["additionalObjects"]["swigemaaktVinkjes"].get("items"):
                homework["is_finished"] = homework["additionalObjects"]["swigemaaktVinkjes"]["items"][0]["gemaakt"]
                homework["id"] = homework["additionalObjects"]["swigemaaktVinkjes"]["items"][0]["swiToekenningId"]
            else:
                homework["is_finished"] = False
                homework["id"] = homework["links"][0]["id"]
        else:
            homework["is_finished"] = False
            homework["id"] = homework["links"][0]["id"]

    zipped_data = get_zipped_data_with_dates(year, weeknum, planner_data)

    return render_template("islands/planner-island.html", zipped_data=zipped_data)


@app.route("/api/finish_homework", methods=["PUT"])
def finish_homework():
    token = session["token"]
    student_id = session["student_id"]

    id = request.args.get("id")
    finish_status = request.args.get("action")

    api_url = "https://api.somtoday.nl/rest/v1/swigemaakt/cou"

    api_data = {
        "leerling": {
            "links": [
                {
                    "id": student_id,
                    "rel": "self",
                    "href": f"https://api.somtoday.nl/rest/v1/leerlingen/{student_id}",
                }
            ]
        },
        "swiToekenningId": id,
        "gemaakt": False if "unfinish" in finish_status.lower() else True,
    }

    api_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    response = requests.put(api_url, headers=api_headers, json=api_data)

    if response.status_code == requests.codes.ok:
        return "ok", 200
    else:
        return "error", 500


@app.route("/info")
@use_session_data
def info():
    return render_template("pages/main/info.html", **comdepdata)


# Identicons API


@app.route("/api/identicon/<username>")
@excluded
def identicon(username):
    if username == "robinboers":
        return send_from_directory("static", "images/robin.png", mimetype="image/png")
    if username == "hansprosch":
        return send_from_directory("static", "images/hans.png", mimetype="image/png")

    image_bytes = render_identicon(username)
    image_io = io.BytesIO(image_bytes)
    return send_file(image_io, mimetype="image/png")


# Loading icon API


@app.route("/api/loading.gif")
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
