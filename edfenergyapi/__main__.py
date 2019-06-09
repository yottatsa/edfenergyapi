#!/usr/bin/python3
import os
import json

from .api import EDF


AUTH_FILE = ".edf.json"


def print_readings(edf, p="year"):
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


if __name__ == "__main__" and os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, "r") as f:
        auth = json.load(f)
    edf = EDF(**auth)
    print_readings(edf)
    print_readings(edf, "month")
    edf.save()
