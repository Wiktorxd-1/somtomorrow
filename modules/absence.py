from flask import Blueprint, render_template, session
from datetime import datetime
import requests
import re

from .utils import use_session_data

absence_bp = Blueprint("absence", __name__)


@absence_bp.route("/absentie")
@use_session_data
def absence_main():
    return render_template("pages/main/absence.html")


@absence_bp.route("/api/islands/registrations")
@use_session_data
def registrations_island():
    token = session["token"]
    student_id = session["student_id"]

    api_url = f"https://api.somtoday.nl/rest/v1/leerlingen/{student_id}/registratieOverzicht?periode=SCHOOLJAAR"

    api_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    response = requests.get(api_url, headers=api_headers)
    api_data = response.json()

    data = []

    for type, entries in api_data.items():
        if not isinstance(entries, list):
            # Boilerplate API stuff from som that isn't data
            continue

        type_name_formatted = " ".join(re.findall(r".[^A-Z]*", type)).capitalize()

        entries_data = []

        for entry in entries:
            dt_start = datetime.strptime(entry["begin"], "%Y-%m-%dT%H:%M:%S.%f%z")
            dt_end = datetime.strptime(entry["eind"], "%Y-%m-%dT%H:%M:%S.%f%z")
            entry["datetime"] = f"{dt_start.strftime('%a %d %b')}, {dt_start.strftime('%H:%M:%S')} tot {dt_end.strftime('%H:%M:%S')}" if dt_start.date() == dt_end.date() else f"{dt_start.strftime('%a %d %b %Y %H:%M')} tot {dt_end.strftime('%a %d %b %Y %H:%M')}"
            entries_data.append(entry)

        data.append({"type": type_name_formatted, "entries": entries_data})

    return render_template("islands/absence/registrations-island.html", registrationsdata=data)

