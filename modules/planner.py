from flask import Blueprint, render_template, session, request
from datetime import datetime, timedelta

import requests

from .utils import (
    use_session_data,
    get_zipped_data_with_dates,
    get_icon,
    capit,
    max_len,
    remove_html,
)


planner_bp = Blueprint("planner", __name__)


@planner_bp.route("/planner")
@use_session_data
def planner_main():
    today = datetime.today()
    if today.weekday() in [5, 6]:
        next_week = today + timedelta(days=7 - today.weekday())
    else:
        next_week = today
    year = next_week.year
    weeknum = next_week.isocalendar()[1]

    return render_template(
        "pages/main/planner.html", current_weeknum=weeknum, current_year=year
    )


@planner_bp.route("/api/islands/planner")
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
        homework["subject_long"] = capit(subject_name).replace(
            "e taal en literatuur", ""
        )
        homework["subject_short"] = homework["lesgroep"]["vak"]["afkorting"]

        if homework.get("studiewijzerItem"):
            if homework["studiewijzerItem"].get("onderwerp"):
                homework["title"] = max_len(
                    remove_html(homework["studiewijzerItem"]["onderwerp"]), 35
                )
            else:
                homework["title"] = max_len(
                    remove_html(homework["studiewijzerItem"]["omschrijving"]), 35
                )
        else:
            continue

        homework["icon"] = get_icon(subject_name)
        homework["type"] = (
            "inleveropdracht"
            if homework["studiewijzerItem"]["inleverperiodes"]
            else homework["studiewijzerItem"].get("huiswerkType", "undefined").lower()
        )
        planner_data[dt.weekday()].append(homework)

        if homework["additionalObjects"].get("swigemaaktVinkjes"):
            if homework["additionalObjects"]["swigemaaktVinkjes"].get("items"):
                homework["is_finished"] = homework["additionalObjects"][
                    "swigemaaktVinkjes"
                ]["items"][0]["gemaakt"]
                homework["id"] = homework["additionalObjects"]["swigemaaktVinkjes"][
                    "items"
                ][0]["swiToekenningId"]
            else:
                homework["is_finished"] = False
                homework["id"] = homework["links"][0]["id"]
        else:
            homework["is_finished"] = False
            homework["id"] = homework["links"][0]["id"]

    zipped_data = get_zipped_data_with_dates(
        year, weeknum, planner_data, request.args.get("days")
    )

    return render_template("islands/planner-island.html", zipped_data=zipped_data)


@planner_bp.route("/api/finish_homework", methods=["PUT"])
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
