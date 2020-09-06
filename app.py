import json
import sqlite3
import sys
import threading
import time

from decouple import config
from flask import Blueprint, Flask, Response, abort, jsonify, request
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# from flask_restful import Api, Resource
# from flask_restful_swagger import swagger

import src.utils as util
from src.errors import RegionNotFound

app = Flask(__name__)
app.url_map.strict_slashes = False
limiter = Limiter(
    app,
    get_remote_address,
    default_limits=["3/second", "60/minute", "1000/hour"]

)
cache = Cache(
    app,
    config={
        "CACHE_TYPE": "simple",
        "CACHE_DEFAULT_TIMEOUT": 30 * 60 # 30 minutes caching
    }
)

API_VERSION = "v1"
BASE_PATH = config("BASE_PATH")
ROUTES = [
    f"{BASE_PATH}/api/{API_VERSION}/all/",
    f"{BASE_PATH}/api/{API_VERSION}/all/<country>",
    f"{BASE_PATH}/api/{API_VERSION}/history/<data_type>",
    f"{BASE_PATH}/api/{API_VERSION}/history/<data_type>/total",
    f"{BASE_PATH}/api/{API_VERSION}/history/<data_type>/<country>",
    f"{BASE_PATH}/api/{API_VERSION}/history/<data_type>/<country>/regions",
    f"{BASE_PATH}/api/{API_VERSION}/history/<data_type>/<country>/<region_name>"
]
SOURCES = [
    "https://github.com/CSSEGISandData/COVID-19",
    "https://www.worldometers.info/coronavirus/"
]


@app.route(f"/api/{API_VERSION}/all/", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def tracker():
    try:
        data = util.read_json("data.json")
        return jsonify(data)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/all/<country>/", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def tracker_country(country):
    try:
        data = util.read_json("data.json")
        for region in data:
            if util.pattern_match(
                country,
                region["country"],
                region["iso2"],
                region["iso3"]):
                return jsonify(region)
        raise RegionNotFound("This region cannot be found. Please try again.")
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def history(data_type):
    try:
        data = util.read_json(f"csv_{data_type}.json")
        return jsonify(data)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/<country>/", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def history_country(data_type, country):
    try:
        data = util.read_json(f"csv_{data_type}.json")
        for region in list(data.keys()):
            if util.pattern_match(
                country,
                region,
                data[region]["iso2"],
                data[region]["iso3"]):
                return jsonify(data[region])
        raise RegionNotFound("This region cannot be found. Please try again.")
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/<country>/<region_name>", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def history_region(data_type, country, region_name):
    try:
        if country.lower() in ("us", "united states", "usa"):
            data = util.read_json(f"csv_{data_type}_us_region.json")
        else:
            data = util.read_json(f"csv_{data_type}_region.json")
        for inner_country in list(data.keys()):
            if util.pattern_match(
                country,
                inner_country,
                data[inner_country]["iso2"],
                data[inner_country]["iso3"]):
                for region in data[inner_country]["regions"]:
                    if region.lower() == region_name.lower():
                        return jsonify(data[inner_country]["regions"][region])
        raise RegionNotFound("This region cannot be found. Please try again.")
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/<country>/regions", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def history_region_all(data_type, country):
    try:
        if country.lower() in ("us", "united states", "usa"):
            data = util.read_json(f"csv_{data_type}_us_region.json")
        else:
            data = util.read_json(f"csv_{data_type}_region.json")
        for inner_country in list(data.keys()):
            if util.pattern_match(
                country,
                inner_country,
                data[inner_country]["iso2"],
                data[inner_country]["iso3"]):
                return jsonify(data[inner_country]["regions"])
        raise RegionNotFound("This region cannot be found. Please try again.")
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route(f"/api/{API_VERSION}/history/<data_type>/total", methods=["GET"])
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
# @util.require_appkey
@cache.cached()
def history_region_world(data_type):
    try:

        data = util.read_json(f"csv_{data_type}.json")
        ret = {"history" : {}}
        for d in data.keys():
            for h in data[d]["history"].keys():
                if h not in ret["history"]:
                    ret["history"][h] = int(data[d]["history"][h])
                else:
                    ret["history"][h] += int(data[d]["history"][h])
        return jsonify(ret)
    except Exception as e:
        return util.response_error(message=f"{type(e).__name__} : {e}")

@app.route("/")
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
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
@limiter.limit("3/second;60/minute;2000/hour", exempt_when=util.no_limit_owner)
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
    try:
        thread1 = threading.Thread(target=util.update)
        thread1.start()
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        with app.app_context():
            cache.clear()
        exit(0)
    except Exception as e:
        print(type(e).__name__, e)
        with app.app_context():
            cache.clear()
        exit(1)
