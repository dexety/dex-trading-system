import time

import requests
import csv
from datetime import datetime


def get_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


filename = "ETH-USD_dydx_2021-12_reverse.csv"
begin = get_datetime("2021-12-01T00:00:00.000Z")
end = get_datetime("2021-12-03T18:58:53.157Z")
day = end.day
trade_template = {"side": "", "size": "", "price": "", "createdAt": ""}


with open(filename, "a") as file:
    csv_writer = csv.DictWriter(file, list(trade_template.keys()))
    while end >= begin:
        try:
            req = requests.get(
                "https://api.dydx.exchange/v3/trades/ETH-USD?startingBeforeOrAt="
                + end.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                + "&limit=100"
            )
        except Exception as e:
            print(e)
            print("Exception")
            time.sleep(60)
            continue
        trades = req.json()["trades"]
        end = get_datetime(trades[-1]["createdAt"])
        for trade in trades:
            csv_writer.writerow(trade)
        if end.day != day:
            print(f"Done with {day}")
            day = end.day

