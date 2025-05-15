from flask import session, g
from datetime import datetime, timezone, timedelta
from functools import wraps
import re
import json


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


def use_session_data(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        for key in session.keys():
            setattr(g, key, session[key])
            g.capit = capit
        return f(*args, **kwargs)

    return wrapper


def clean_somdata(data):
    if isinstance(data, list):
        return [clean_somdata(item) for item in data]
    elif isinstance(data, dict):
        return {key: clean_somdata(value) for key, value in data.items() if key not in ["links", "permissions", "UUID"]}
    else:
        return data


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


def get_zipped_data_with_dates(year, weeknum, data, days_to_include):
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

    if days_to_include == "today":
        if any(current_day_class):
            today_index = current_day_class.index("today")
            zipped_data = [list(zipped_data)[today_index]]
        else:
            zipped_data = [list(zipped_data)[0]]

    return zipped_data
