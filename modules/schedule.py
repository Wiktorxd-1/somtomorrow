from flask import Blueprint, render_template, session, request
from datetime import datetime, timedelta
import requests

from .utils import use_session_data, clean_somdata, get_icon, capit, get_zipped_data_with_dates


schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/rooster")
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


@schedule_bp.route("/api/islands/schedule")
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

    for appo in api_data["items"]:
        dt_start = datetime.strptime(appo["beginDatumTijd"], "%Y-%m-%dT%H:%M:%S")
        dt_end = datetime.strptime(appo["eindDatumTijd"], "%Y-%m-%dT%H:%M:%S")

        appo["title"] = (capit(appo["vak"]["naam"]).replace("e taal en literatuur", "") if len(appo["vak"]["naam"].replace("e taal en literatuur", "")) < 20 else appo["vak"]["afkorting"].upper()) if appo.get("vak", {}).get("naam") else appo["titel"]
        appo["title_full"] = capit(appo["vak"]["naam"]) if appo.get("vak", {}).get("naam") else appo["titel"]

        appo["icon"] = get_icon(appo["vak"]["naam"] if appo.get("vak", {}).get("naam") else appo["titel"])

        appo["dt_start"] = dt_start
        appo["dt_end"] = dt_end

        # The container goes from 8 to 18, so 10 hours, so 100% is 10 hours, so 10% is 60 minutes so 1 minute is 1/6%

        duration_minutes = int((dt_end - dt_start).total_seconds() // 60)

        eight_am = datetime(dt_start.year, dt_start.month, dt_start.day, 8, 0)
        minutes_since_8am = max(0, (dt_start - eight_am).total_seconds() // 60)

        appo["height"] = duration_minutes * (1 / 6)
        appo["top"] = minutes_since_8am * (1 / 6)

        if appo.get("beginLesuur"):
            if appo.get("eindLesuur"):
                appo["lesson_hours"] = f"{appo['beginLesuur']}e" if appo["beginLesuur"] == appo["eindLesuur"] else f"{appo['beginLesuur']}e - {appo['eindLesuur']}e"
            else:
                appo["lesson_hours"] = f"{appo['beginLesuur']}e"
        appo["start_time"] = dt_start.strftime("%H:%M")
        appo["end_time"] = dt_end.strftime("%H:%M")
        appo["type"] = appo["afspraakItemType"].lower()
        appo["date"] = dt_start.strftime("%a %d %b")

        schedule_data[dt_start.weekday()].append(appo)

    # This is very broken, but i dont want to fix

    for daydata in schedule_data:
        daydata = sorted(daydata, key=lambda x: x["dt_start"])

        def overlaps(a, b):
            return not (a["dt_end"] <= b["dt_start"] or a["dt_start"] >= b["dt_end"])

        for i, appo in enumerate(daydata):
            appo["column"] = 0
            used_columns = set()

            for j, other in enumerate(daydata):
                if i == j:
                    continue
                if overlaps(appo, other):
                    if "column" in other:
                        used_columns.add(other["column"])

            col = 0
            while col in used_columns:
                col += 1
            appo["column"] = col

        max_column = max((appo.get("column", 0) for appo in daydata if "column" in appo), default=0) + 1
        for appo in daydata:
            appo["width"] = 100 / max_column
            appo["right"] = appo["column"] * appo["width"]

    zipped_data = get_zipped_data_with_dates(year, weeknum, schedule_data, request.args.get("days"))

    return render_template("islands/schedule-island.html", zipped_data=zipped_data)
