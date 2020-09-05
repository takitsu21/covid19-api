import json
import sqlite3
import sys
import threading
import time

from flask import Flask, Response, abort, jsonify, request
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import src.utils as util

app = Flask(__name__)
limiter = Limiter(
    app,
    get_remote_address,
    default_limits=["3/second", "60/minute", "1000/hour"]

)
cache = Cache(
    app,
    config={
        "CACHE_TYPE": "simple",
        "CACHE_DEFAULT_TIMEMOUT": 30 * 60 # 30 minutes caching
    }
)

API_VERSION = "v1"
ROUTES = [
    f"/api/{API_VERSION}/all/",
    f"/{API_VERSION}/all/<country>",
    f"/{API_VERSION}/history/<data_type>",
    f"/{API_VERSION}/history/<data_type>/<country>"
]
SOURCES = [
    "https://github.com/CSSEGISandData/COVID-19",
    "https://www.worldometers.info/coronavirus/"
]



@app.route(f"/api/{API_VERSION}/all/", methods=["GET"])
@limiter.limit("3/second;60/minute", override_defaults=False)
# @util.require_appkey
@cache.cached()
def tracker():
    try:
        data = util.read_json("data.json")
        # for d in data:
        #     if not d.get("iso2"):
        #         print(d["country"])
        return jsonify(data)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/all/<country>/", methods=["GET"])
@limiter.limit("3/second;60/minute")
# @util.require_appkey
@cache.cached()
def tracker_country(country):
    try:
        data = util.read_json("data.json")
        for region in data:
            if country.lower() in \
                (region["country"].lower(), region["iso2"].lower(), region["iso3"].lower()):
                return jsonify(region)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/", methods=["GET"])
@limiter.limit("3/second;60/minute", override_defaults=False)
# @util.require_appkey
@cache.cached()
def history(data_type):
    try:
        data = util.read_json(f"csv_{data_type}.json")
        # for k, v in data.items():
        #     if not v.get("iso2"):
        #         print(k)
        return jsonify(data)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/<country>/", methods=["GET"])
@limiter.limit("3/second;60/minute", override_defaults=False)
# @util.require_appkey
@cache.cached()
def history_country(data_type, country):
    try:
        data = util.read_json(f"csv_{data_type}.json")
        for region in list(data.keys()):
            if country.lower() in \
                (region.lower(), data[region]["iso2"].lower(), data[region]["iso3"].lower()):
                return jsonify(data[region])
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route("/")
@limiter.exempt
def index():
    route_error = {
        "routes": ROUTES,
        "<data_type>": "confirmed | recovered | deaths",
        "Api version": API_VERSION,
        "discord": "https://discord.gg/wTxbQYb",
        "sources": SOURCES
        }
    return jsonify(route_error)

@app.route(f"/api/")
@limiter.exempt
def version_index():
    route_error = {
        "routes": ROUTES,
        "<data_type>": "confirmed | recovered | deaths",
        "Api version": API_VERSION,
        "discord": "https://discord.gg/wTxbQYb",
        "sources": SOURCES
        }
    return jsonify(route_error)

if __name__ == '__main__':
    thread1 = threading.Thread(target=util.update)
    thread1.start()
    app.run(host="0.0.0.0", port=11232)
