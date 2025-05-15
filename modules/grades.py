from flask import Blueprint, render_template, redirect, url_for, session, request
from datetime import datetime, timedelta
import pytz
import requests

from .utils import use_session_data, clean_somdata, get_icon, capit


grades_bp = Blueprint("grades", __name__)


@grades_bp.route("/cijfers")
@use_session_data
def grades_main():
    return redirect(url_for("grades.testgrades"))


@grades_bp.route("/cijfers/toetscijfers")
@use_session_data
def testgrades():
    return render_template("pages/main/grades/testgrades.html")


@grades_bp.route("/api/islands/grades/testgrades")
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
