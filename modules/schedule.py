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

    zipped_data = get_zipped_data_with_dates(year, weeknum, schedule_data, request.args.get("days"))

    return render_template("islands/schedule-island.html", zipped_data=zipped_data)
