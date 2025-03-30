from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, g, send_file
from datetime import timedelta, datetime, timezone
from functools import wraps
from dotenv import load_dotenv
from identicon import render_identicon
import os
import io
import requests
import pytz
import locale


load_dotenv()

key = os.getenv("key")

app = Flask(__name__)
app.secret_key = key
app.permanent_session_lifetime = timedelta(hours=1)

locale.setlocale(locale.LC_TIME, "nl_NL")



# Things with logging in and getting the tokens


# All the routes that do not require login, so just the excluded routes
def excluded(endpoint):
    endpoint.is_excluded = True
    return endpoint

def logged_in():
    if "token" in session and datetime.now(timezone.utc).timestamp() - session.get("login_time", 0) < 3600:
        return True
    return False

@app.before_request
def check_login():
    if request.endpoint is None:
        return  # For 404 and stuff

    view_func = app.view_functions.get(request.endpoint)

    if view_func and getattr(view_func, "is_excluded", False):
        return  # Skip token check if endpoint is excluded

    if any(keyword in request.endpoint for keyword in ["static", "favicon", "security", "robots"]):
        return  # Static files are also excluded

    if not logged_in():
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

    response = requests.post("https://vik.dupunkto.org/api/authtoday", json=reqdata)

    if str(response.status_code) == "503":
        responsedata = response.json()
        errormessage = responsedata['error']
        errormessage_formatted = errormessage + "." if not errormessage.endswith(".") else errormessage

        flash(f"Fout: {errormessage_formatted}", "error")
        return redirect(url_for("login"))
    else:
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
    session["last_name"] = last_name.replace("Ten Berg", "ten Berg")
    session["identicon_name"] = first_name.strip().lower().replace(" ", "") + last_name.strip().lower().replace(" ", "")
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
@app.route("/login/devauto")
@excluded
def logindevauto():
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


@app.route("/login/devtester",methods=["GET", "POST"])
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
            "client_id": "somtoday-leerling-native"
        }
        response = requests.post(url, data=body)

        data = response.json()

        with open(f"dev/rtoken{choice}.txt", "w") as file:
            file.write(data.get("refresh_token", rtoken))

        set_token_and_info(data.get("access_token"))

        return redirect(url_for("dashboard"))

    return '''
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
    '''





@app.route("/")
@excluded
def index():
    if 'token' in session and datetime.now(timezone.utc).timestamp() - session.get("login_time", 10000) <= 3600:
        # If user is already logged in and the token is valid, redirect to dashboard
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))




# Basic files

@app.route('/favicon.ico')
@app.route('/favicon')
@excluded
def favicon():
    return send_from_directory('static', "favs/fav.ico", mimetype='image/vnd.microsoft.icon')


@app.route("/.well-known/security.txt")
@excluded
def securitytxt():
    return send_from_directory('static', "txts/security.txt", mimetype="text/plain")

@app.route("/security.txt")
@excluded
def securitytxtredirect():
    return redirect(url_for('securitytxt')), 301


@app.route("/robots")
@app.route("/robots.txt")
@excluded
def robots():
    return send_from_directory("static", "txts/robots.txt", mimetype="text/plain")






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

    api_url = f"https://api.somtoday.nl/rest/v1/resultaten/huidigVoorLeerling/{student_id}?additional=vaknaam&additional=resultaatkolom&additional=heeftalternatiefniveau&additional=naamalternatiefniveau&additional=naamstandaardniveau&additional=leerjaar&additional=periodeAfkorting&type=Toetskolom&type=SamengesteldeToetsKolom&type=Werkstukcijferkolom&type=Advieskolom&type=PeriodeGemiddeldeKolom&type=RapportGemiddeldeKolom&type=RapportCijferKolom&type=RapportToetskolom&type=SEGemiddeldeKolom&type=ToetssoortGemiddeldeKolom"

    headers_list = [
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=0-99"
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=100-199"
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=200-299"
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=300-399"
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=400-499"
        },
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://somtoday.nl",
            "Range": "items=500-599"
        }
    ]

    api_data = []

    for headers in headers_list:
        response = requests.get(api_url, headers = headers)
        responseData = response.json()
        for item in responseData["items"]:
            api_data.append(item)


    types_to_include = ["Toetskolom", "Werkstukcijferkolom", "Advieskolom"]
    api_data = [item for item in api_data if item["type"] in types_to_include and ("geldendResultaat" in item or "resultaatLabelAfkorting" in item)] # Filter unwanted grade types


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
            "filosofie": '<i class="fa-solid fa-brain"></i>'
        }
        for key in subjects_icons:
            if key.lower() in subject.lower():
                return subjects_icons[key]
        return '<i class="fa-solid fa-book"></i>'
    
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
        except (TypeError, AttributeError):
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

        grade["subject_nice"] = grade_subject_name[:1].upper() + grade_subject_name[1:]
        grade["datetime_sort"] = dt_entered.isoformat()
        grade["datetime_nice"] = formatted_dt_entered
        grade["datetime_nice_extended"] = dt_entered.strftime("%A %d %B %Y om %H:%M:%S")
        grade["icon"] = get_icon(grade["vak"]["naam"])
        grade["test_nice"] = grade_test_name[:1].upper() + grade_test_name[1:]
        grade["result"] = result
        grade["max_weight"] = max(grade["weging"], grade.get("examenWeging", 0))

        grade["is_fail"] = grade_is_fail(grade.get("geldendResultaat"), grade.get("resultaatLabelAfkorting"))

        grade["confetti"] = True if float(grade.get("geldendResultaat", "0.0").replace(",", ".")) >= 10 else False
        

        if grade.get("herkansing"):
            grade["retake"] = {
                "first_retake": {
                    "date": format_date(datetime.strptime(grade["herkansing"]["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")),
                    "result": grade["herkansing"]["resultaat"],
                    "result_is_fail": grade_is_fail(grade["herkansing"]["resultaat"], ""),
                    "effective_result": True if grade["geldendResultaat"] == grade["herkansing"]["resultaat"] else False,
                },
                "first_attempt": {
                    "date": format_date(datetime.strptime(grade["datumInvoer"], "%Y-%m-%dT%H:%M:%S.%f%z")),
                    "result": grade["resultaat"],
                    "result_is_fail": grade_is_fail(grade.get("resultaat"), grade.get("resultaatLabelAfkorting")),
                    "effective_result": True if grade["resultaat"] == grade["geldendResultaat"] else False,
                }
            }
            grade["retake_is_effective_result"] = False if grade["resultaat"] == grade["geldendResultaat"] else True


    api_data = sorted(api_data, key=lambda x: x["datetime_sort"], reverse=True)

    return render_template("main/grades/all_test_grades.html", gradelist = api_data)


@app.route("/rooster")
@use_session_data
def schedule_main():
    token = session["token"]

    weeknum = request.args.get('w')
    year = request.args.get('y')

    if not weeknum or not year:
        today = datetime.today()
        if today.weekday() in [5, 6]:
            next_week = today + timedelta(days=7 - today.weekday())
        else:
            next_week = today
        weeknum = next_week.isocalendar()[1]
        year = next_week.year

    api_url = f"https://api.somtoday.nl/rest/v1/afspraakitems/2366141886835/jaar/{year}/week/{weeknum}"

    api_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Origin": "https://somtoday.nl",
        "Range": "items=0-99"
    }

    response = requests.get(api_url, headers = api_headers)
    api_data = response.json()

    return render_template("main/schedule.html", schedule_data = api_data)




# Profile pictures

@app.route('/identicon/<username>')
@excluded
def identicon(username):
    if username == "robinboers":
        return send_from_directory("static", "images/robin.png", mimetype="image/png")
    image_bytes = render_identicon(username)
    image_io = io.BytesIO(image_bytes)
    return send_file(image_io, mimetype='image/png')


@app.errorhandler(404)
@excluded
def not_found(e):
    return render_template("other/404.html", e=e, login=logged_in()), 404


@app.errorhandler(500)
@excluded
def internal_server_error(e):
    return render_template('other/500.html', e=e, login=logged_in()), 500

if __name__ == "__main__":
    app.run(debug=True)
