#!/usr/bin/python3
import datetime
import os
import json

from .api import EDF


AUTH_FILE = ".edf.json"


def print_readings(edf, p="year", json=None):
    if json:
        readings = edf.session.get(json).json()[0]["result"]["readings"]
    else:
        readings = edf.request("myaccount/energygraph/{}".format(p))["data"][0]["result"]["readings"]
    if isinstance(readings, dict):
        readings = readings.values()
    p = lambda v: v['periodStart']
    c = lambda v: v['periodConsumption']
    total = 0
    for v in sorted(filter(c, readings), key=p):
        print(p(v), c(v))
        total += c(v)
    print(total)
    return p(v), total


if __name__ == "__main__" and os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, "r") as f:
        auth = json.load(f)
    edf = EDF(**auth)
    _, total = print_readings(edf)
    last_day, month_total = print_readings(edf, "month")
    next_day = datetime.datetime.strptime(last_day, '%Y-%m-%d').date() + datetime.timedelta(days=1)
    _, next_day_total = print_readings(edf, json="https://my.edfenergy.com/smartdata/{}/day/0".format(next_day))
    print(total + month_total + next_day_total)
    edf.save()
