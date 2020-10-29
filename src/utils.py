import csv
import datetime
import json
import sqlite3
import time
import unicodedata
from functools import wraps

import requests
from decouple import config
from flask import jsonify, request, Response
from flask_limiter.util import get_remote_address

AUTHORIZATION = config("Authorization")

APIFY_URL = "https://api.apify.com/v2/key-value-stores/SmuuI0oebnTWjRTUh/records/LATEST?disableRedirect=true"
CSV_CONFIRMED = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"
CSV_DEATHS = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_global.csv"
CSV_RECOVERED = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_recovered_global.csv"

CSV_CONFIRMED_US = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_US.csv"
CSV_DEATHS_US = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_US.csv"

CSV_CONFIRMED_FPATH_US = "csv_confirmed_us.csv"
CSV_DEATHS_FPATH_US = "csv_deaths_us.csv"

CSV_CONFIRMED_FPATH = "csv_confirmed.csv"
CSV_DEATHS_FPATH = "csv_deaths.csv"
CSV_RECOVERD_FPATH = "csv_recovered.csv"

CSV_POPULATIONS = "data/populations.csv"
populations = {}

WORLD_POPULATION = 7800000000

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
    dl_csv(CSV_CONFIRMED, CSV_CONFIRMED_FPATH)
    dl_csv(CSV_DEATHS, CSV_DEATHS_FPATH)
    dl_csv(CSV_RECOVERED, CSV_RECOVERD_FPATH)
    dl_csv(CSV_CONFIRMED_US, CSV_CONFIRMED_FPATH_US)
    dl_csv(CSV_DEATHS_US, CSV_DEATHS_FPATH_US)
    csv_to_json(CSV_CONFIRMED_FPATH)
    csv_to_json(CSV_DEATHS_FPATH)
    csv_to_json(CSV_RECOVERD_FPATH)
    region_csv_to_json(CSV_CONFIRMED_FPATH)
    region_csv_to_json(CSV_DEATHS_FPATH)
    region_csv_to_json(CSV_RECOVERD_FPATH)
    region_csv_to_json(CSV_CONFIRMED_FPATH_US, is_us=True)
    region_csv_to_json(CSV_DEATHS_FPATH_US, is_us=True)
    store_data()

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

def region_csv_to_json(csv_fpath, is_us=False):
    csv_json = {}
    if is_us:
        province_key = "Province_State"
        country_key = "Country_Region"
        key_start = 12
    else:
        province_key = "Province/State"
        country_key = "Country/Region"
        key_start = 4
    with open("iso-3166.json", "r") as isof:
        iso_data = json.load(isof)
    with open(csv_fpath, "r") as csv_file:
        data = csv.DictReader(csv_file)
        for row in data:
            if not len(row[province_key]):
                continue
            if row[country_key] in SPECIAL_CASES:
                country = SPECIAL_CASES[row[country_key]]["name"]
            else:
                country = row[country_key]
            if (country not in csv_json):

                csv_json[country] = {"regions": {}}
                province = row[province_key]
                for key in list(row.keys())[key_start:]:
                    new_k = datetime.datetime.strptime(key, "%m/%d/%y").strftime("%m/%d/%y")
                    if province not in csv_json[country]["regions"]:
                        csv_json[country]["regions"][province] = {
                            "history": {}
                        }
                    csv_json[country]["regions"][province]["history"][new_k] = int(float(row[key]))
            else:
                province = row[province_key]
                for key in list(row.keys())[key_start:]:
                    new_k = datetime.datetime.strptime(key, "%m/%d/%y").strftime("%m/%d/%y")
                    if province not in csv_json[country]["regions"]:
                        csv_json[country]["regions"][province] = {
                            "history": {}
                        }
                    if is_us and csv_json[country]["regions"][province]["history"].get(new_k):
                        csv_json[country]["regions"][province]["history"][new_k] += int(float(row[key]))
                    else:
                        csv_json[country]["regions"][province]["history"][new_k] = int(float(row[key]))


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

        with open(csv_fpath.replace(".csv", "_region.json"), "w+") as f:
            f.write(str(json.dumps(csv_json)))

def csv_to_dict(csv_fpath):
    with open(csv_fpath, "r") as csv_file:
        dict_out = {}
        for line in csv_file:
            line = line.strip('\n')
            l = line.split(',')
            dict_out[l[0]] = l[1]
        return dict_out

def find_val_replace_null(country, data, base):
    try:
        return list(data[country]["history"].values())[-1]
    except KeyError:
        if base is None:
            return 0
    return base

def replace_null_value(dataset: list):
    new_dataset = []
    data_c = read_json(CSV_CONFIRMED_FPATH.replace(".csv", ".json"))
    data_r = read_json(CSV_RECOVERD_FPATH.replace(".csv", ".json"))
    data_d = read_json(CSV_DEATHS_FPATH.replace(".csv", ".json"))
    for kv_replace in dataset:
        tmp = kv_replace
        confirmed = find_val_replace_null(tmp["country"], data_c, tmp["totalCases"])
        recovered = find_val_replace_null(tmp["country"], data_r, tmp["totalRecovered"])
        deaths = find_val_replace_null(tmp["country"], data_d, tmp["totalDeaths"])
        if tmp["totalCases"] is None:
            tmp["totalCases"] = confirmed
        if tmp["activeCases"] is None:
            tmp["activeCases"] = confirmed - (recovered + deaths)
        if tmp["newCases"] is None:
            tmp["newCases"] = 0
        if tmp["totalDeaths"] is None:
            tmp["totalDeaths"] = deaths
        if tmp["totalRecovered"] is None:
            tmp["totalRecovered"] = recovered
        new_dataset.append(tmp)
    return new_dataset


def store_data():
    timestamp_update = int(time.time())
    r = requests.get(APIFY_URL)
    apify_data = r.json()
    with open("iso-3166.json", "r") as isof:
        iso_data = json.load(isof)
    merged_data = []
    for apify in apify_data["regionData"]:
        if apify["country"] == "Total:":
            continue
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
        if not iso_found:
            apify["iso2"] = ""
            apify["iso3"] = ""
        apify["lastUpdate"] = timestamp_update
        merged_data.append(apify)

    merged_data = replace_null_value(merged_data)
    with open("data.json", "w+") as fd:
        dumps = json.dumps(merged_data)
        fd.write(str(dumps))

def read_json(fpath: str):
    with open(fpath, "r") as f:
        data = json.load(f)
    return data

def pattern_match(to_match, *patterns):
    return to_match.lower() in map(lambda x: x.lower(), patterns)

def insert_user(ip, user_agent):
    with sqlite3.connect("user_list.db") as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO `users`(`ip`, `user_agent`) VALUES(?, ?)""", (ip, user_agent, ))
        conn.commit()
        c.close()

def require_appkey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        # try:
        #     ip = get_remote_address()
        #     insert_user(str(ip), request.headers.get("User-Agent"))
        # except Exception as exc:
        #     pass
        if request.headers.get('Authorization') and \
            request.headers.get('Authorization') == AUTHORIZATION:
            return view_function(*args, **kwargs)
        else:
            return jsonify({"status": 401, "description": "This app requires an API KEY if you would like to get one come over to my discord https://discord.gg/wTxbQYb and ask Taki#0853"})
    return decorated_function

def no_limit_owner():
    return request.headers.get("Authorization") and request.headers.get("Authorization") == config("Authorization")

def response_error(status=500, message="Internal server error"):
    return Response(response=message, status=status)

if __name__ == "__main__":
    update() # crontab
