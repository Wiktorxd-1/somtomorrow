from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, g
from datetime import timedelta, datetime, timezone
from functools import wraps
import os
from dotenv import load_dotenv
import requests
import pytz
import locale
import json

load_dotenv()

key = os.getenv("key")

app = Flask(__name__)
app.secret_key = key
app.permanent_session_lifetime = timedelta(hours=1)

locale.setlocale(locale.LC_TIME, "nl_NL")




# Basics and files


@app.route('/favicon.ico')
@app.route('/favicon')
def favicon():
    return send_from_directory('static', "favs/tempfav.ico", mimetype='image/vnd.microsoft.icon')


@app.route("/.well-known/security.txt")
def securitytxt():
    return send_from_directory('static', "txts/security.txt", mimetype="text/plain")

@app.route("/security.txt")
def securitytxtredirect():
    return redirect(url_for('securitytxt')), 301


@app.route("/robots")
@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "txts/robots.txt", mimetype="text/plain")




# Things with logging in and getting the tokens


# All the routes that do not require login, so just the excluded routes
def excluded(endpoint):
    endpoint.is_excluded = True
    return endpoint


@app.before_request
def check_login():
    if request.endpoint is None:
        return  # For 404 and stuff

    view_func = app.view_functions.get(request.endpoint)

    if view_func and getattr(view_func, "is_excluded", False):
        return  # Skip token check if endpoint is excluded

    if "static" in request.endpoint or "favicon" in request.endpoint:
        return  # Static files are also excluded

    if "token" not in session or datetime.now(timezone.utc).timestamp() - session.get("login_time", 0) > 3600:
        return redirect(url_for("logout"))


def use_session_data(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        for key in session.keys():
            setattr(g, key, session[key])
        return f(*args, **kwargs)

    return wrapper


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

    last_name = f"{middle_name} {response_data['items'][0]['achternaam']}" if (middle_name := response_data["items"][0].get("voorvoegsel")) else response_data['items'][0]['achternaam']

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
    session['login_time'] = datetime.now(timezone.utc).timestamp()

    
    return True


@app.route("/logout")
@excluded
def logout():
    session.clear()
    return redirect(url_for("login"))


# TEMPORARY
@app.route("/login/dev")
@excluded
def logindev():
    with open("rtoken.txt", "r") as file:
        rtoken = file.read()
    url = "https://somtoday.nl/oauth2/token"
    body = {
        "grant_type": "refresh_token",
        "refresh_token": rtoken,
        "client_id": "somtoday-leerling-native"
    }
    response = requests.post(url, data=body)

    data = response.json()

    with open("rtoken.txt", "w") as file:
        file.write(data.get("refresh_token", rtoken))


    set_token_and_info(data.get("access_token"))

    return redirect(url_for("dashboard"))



@app.route("/")
@excluded
def index():
    if 'token' in session and datetime.now(timezone.utc).timestamp() - session.get("login_time", 10000) <= 3600:
        # If user is already logged in and the token is valid, redirect to dashboard
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# Main pages


@app.route("/dashboard")
@use_session_data
def dashboard():
    return render_template("main/dashboard.html")


@app.route("/cijfers")
@use_session_data
def grades_main():
    return redirect(url_for("grades_all"))

@app.route("/cijfers/toetscijfers")
@use_session_data
def grades_all():
    student_id = session["student_id"]
    token = session["token"]

    api_url = f"https://api.somtoday.nl/rest/v1/resultaten/huidigVoorLeerling/{student_id}"

    api_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Origin": "https://somtoday.nl",
        "Range": "items=0-1000"
    }

    response = requests.get(api_url, headers=api_headers)
    response_data = response.json()
    api_data = response_data["items"]


    types_to_remove = ["PeriodeGemiddeldeKolom", "RapportGemiddeldeKolom", "SEGemiddeldeKolom"]
    api_data = [item for item in api_data if item["type"] not in types_to_remove and ("geldendResultaat" in item or "resultaatLabelAfkorting" in item)] # Filter unwanted grade types

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
            "biologie": '<i class="fa-solid fa-seedling"></i>',
            "techniek": '<i class="fa-solid fa-screwdriver-wrench"></i>',
            "rekenen": '<i class="fa-solid fa-plus-minus"></i>',
            "dans": '<i class="fa-solid fa-person-rays"></i>',
            "maatschappijleer": '<i class="fa-solid fa-people-group"></i>',
            "burgerschap": '<i class="fa-solid fa-people-group"></i>',
            "onderzoek & ontwerpen": '<i class="fa-solid fa-pen-ruler"></i>',
            "kunst": '<i class="fa-solid fa-palette"></i>',
            "beeldende vorming": '<i class="fa-solid fa-palette"></i>',
            "muziek": '<i class="fa-solid fa-music"></i>',
            "natuur": '<i class="fa-solid fa-microscope"></i>',
            "technologie": '<i class="fa-solid fa-microscope"></i>',
            "drama": '<i class="fa-solid fa-masks-theater"></i>',
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
            "natuurkunde": '<i class="fa-solid fa-atom"></i>'
        }
        for key in subjects_icons:
            if key.lower() in subject.lower():
                return subjects_icons[key]
        return '<i class="fa-solid fa-book"></i>'
    
    

    now = datetime.now(pytz.timezone("Europe/Amsterdam"))

    for grade in api_data:
        dt_entered = datetime.strptime(grade["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")

        if dt_entered.date() == now.date():
            formatted = f"Vandaag om {dt_entered.strftime('%H:%M:%S')}"
        elif dt_entered.date() == (now.date() - timedelta(days=1)):
            formatted = f"Gisteren om {dt_entered.strftime('%H:%M:%S')}"
        else:
            formatted = dt_entered.strftime("%a %d %B om %H:%M:%S")

        grade["subject_nice"] = grade["vak"]["naam"][:1].upper() + grade["vak"]["naam"][1:]
        grade["datetime_sort"] = dt_entered.isoformat()
        grade["datetime_nice"] = formatted
        grade["icon"] = get_icon(grade["vak"]["naam"])
        grade["test_nice"] = grade["omschrijving"][:37] + "..." if len(grade["omschrijving"]) > 40 else grade["omschrijving"]



    api_data = sorted(api_data, key=lambda x: x["datetime_sort"], reverse=True)

    with open("temp.json", "w") as jsonfile:
        json.dump(api_data, jsonfile, indent=4)
    

    return render_template("main/grades/all_test_grades.html", gradelist = api_data)









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
