import csv
import datetime
import json
import sqlite3
import time
import unicodedata
from functools import wraps

import requests
from decouple import config
from flask import jsonify, request
from flask_limiter.util import get_remote_address

APIFY_URL = "https://api.apify.com/v2/key-value-stores/SmuuI0oebnTWjRTUh/records/LATEST?disableRedirect=true"
CSV_CONFIRMED = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"
CSV_DEATHS = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_global.csv"
CSV_RECOVERED = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_recovered_global.csv"

CSV_CONFIRMED_FPATH = "csv_confirmed.csv"
CSV_DEATHS_FPATH = "csv_deaths.csv"
CSV_RECOVERD_FPATH = "csv_recovered.csv"

SPECIAL_CASES = {
    "US": {
        "name": "United States",
        "iso2": "US",
        "iso3": "USA"
    },
    "Taiwan*": {
        "name": "Taiwan",
        "iso2": "TW",
        "iso3": "TWN"
    },
    "United Kingdom": {
        "name": "United Kingdom",
        "iso2": "GB",
        "iso3": "GBR"
    },
    "Syria": {
        "name": "Syria",
        "iso2": "SY",
        "iso3": "SYR"
    },
    "USA": {
        "name": "United States",
        "iso2": "US",
        "iso3": "USA"
    },
    "UK": {
        "name": "United Kingdom",
        "iso2": "GB",
        "iso3": "GBR"
    }
}

def update():
    while True:
        dl_csv(CSV_CONFIRMED, CSV_CONFIRMED_FPATH)
        dl_csv(CSV_DEATHS, CSV_DEATHS_FPATH)
        dl_csv(CSV_RECOVERED, CSV_RECOVERD_FPATH)
        csv_to_json(CSV_CONFIRMED_FPATH)
        csv_to_json(CSV_DEATHS_FPATH)
        csv_to_json(CSV_RECOVERD_FPATH)
        store_data()
        time.sleep(30 * 60)

def dl_csv(csv_type, fpath):
    r = requests.get(csv_type)
    with open(fpath, "w+") as f:
        f.write(r.text)

def csv_to_json(csv_fpath):
    csv_json = {}
    with open("iso-3166.json", "r") as isof:
        iso_data = json.load(isof)
    with open(csv_fpath, "r") as csv_file:
        data = csv.DictReader(csv_file)
        for row in data:
            if row["Country/Region"] not in csv_json:
                if row["Country/Region"] in SPECIAL_CASES:
                    country = SPECIAL_CASES[row["Country/Region"]]["name"]
                else:
                    country = row["Country/Region"]
                csv_json[country] = {"history": {}}
                for key in list(row.keys())[4:]:
                    new_k = datetime.datetime.strptime(key, "%m/%d/%y").strftime("%m/%d/%y")
                    csv_json[country]["history"][new_k] = int(row[key])
            else:
                for key in list(row.keys())[4:]:
                    new_k = datetime.datetime.strptime(key, "%m/%d/%y").strftime("%m/%d/%y")
                    csv_json[country]["history"][new_k] += int(row[key])

        for k in csv_json.keys():
            for iso in iso_data:
                if k.lower() == iso["name"].lower():
                    csv_json[k]["iso2"] = iso["iso2"]
                    csv_json[k]["iso3"] = iso["iso3"]
            if k in SPECIAL_CASES:
                csv_json[SPECIAL_CASES[k]["name"]]["iso2"] = SPECIAL_CASES[k]["iso2"]
                csv_json[SPECIAL_CASES[k]["name"]]["iso3"] = SPECIAL_CASES[k]["iso3"]
                continue
            if not csv_json[k].get("iso2"):
                csv_json[k]["iso2"] = ""
                csv_json[k]["iso3"] = ""

        with open(csv_fpath.replace(".csv", ".json"), "w+") as f:
            f.write(str(json.dumps(csv_json)))

def store_data():
    timestamp_update = int(time.time())
    r = requests.get(APIFY_URL)
    apify_data = r.json()
    with open("iso-3166.json", "r") as isof:
        iso_data = json.load(isof)
    merged_data = []
    for apify in apify_data["regionData"]:
        iso_found = False
        apify_normalized = unicodedata.normalize('NFKD', apify["country"]).encode('ascii', 'ignore').decode("utf-8")
        if apify_normalized in SPECIAL_CASES:
            apify_normalized = SPECIAL_CASES[apify_normalized]["name"]
            apify["country"] = apify_normalized
        for iso in iso_data:
            if apify_normalized.lower() == iso["name"].lower():
                apify["iso2"] = iso["iso2"]
                apify["iso3"] = iso["iso3"]
                iso_found = True
                break
        if not iso_found and apify["country"] != "Total:":
            apify["iso2"] = ""
            apify["iso3"] = ""
        apify["lastUpdate"] = timestamp_update
        merged_data.append(apify)

    with open("data.json", "w+") as fd:
        dumps = json.dumps(merged_data)
        fd.write(str(dumps))

def read_json(fpath: str):
    with open(fpath, "r") as f:
        data = json.load(f)
    return data

def insert_user(ip, user_agent):
    with sqlite3.connect("user_list.db") as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO `users`(`ip`, `user_agent`) VALUES(?, ?)""", (ip, user_agent, ))
        conn.commit()
        c.close()

def require_appkey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        try:
            ip = get_remote_address()
            insert_user(str(ip), request.headers.get("User-Agent"))
        except Exception as exc:
            pass
        if request.headers.get('Authorization') and request.headers.get('Authorization') == config("Authorization"):
            return view_function(*args, **kwargs)
        else:
            return jsonify({"status": 401, "description": "This app required an API KEY if you would like to have one come over my discord https://discord.gg/wTxbQYb and ask to Taki#0853"})
    return decorated_function

def response_error(status=500, message="Internal server error"):
    return jsonify({
        "status": status,
        "message": message
    })