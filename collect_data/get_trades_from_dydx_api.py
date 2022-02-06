import os
import sys
import csv
import json
from datetime import datetime, timedelta

sys.path.append("../")

from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_ETH_USD
from utils.helpful_scripts import string_to_datetime


def clean_data(data: list) -> list:
    cleaned_data = []
    cur_dt = string_to_datetime(data[0]["createdAt"])
    for new_trade in data:
        new_dt = string_to_datetime(new_trade["createdAt"])
        if new_dt >= cur_dt:
            cleaned_data.append(new_trade)
    return cleaned_data


def get_trades_from_dydx_api(
    symbol: str, start_dt: datetime, end_dt: datetime
) -> list:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")
    dydx_connector_trades = DydxConnector(
        ETH_ADDRESS,
        ETH_PRIVATE_KEY,
        [symbol],
        INFURA_NODE,
    )
    return clean_data(
        dydx_connector_trades.get_historical_trades(symbol, start_dt, end_dt)
    )


def get_formated_dt(dt: datetime) -> str:
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year}"


def main():
    print("collection of trades begin")
    print("it may takes a lot of time")
    start_dt = datetime(2022, 1, 22)
    end_dt = datetime.utcnow()
    trades_data = get_trades_from_dydx_api(MARKET_ETH_USD, start_dt, end_dt)
    with open(
        f"../data/trades/raw/trades_{get_formated_dt(start_dt)}_{get_formated_dt(end_dt)}.csv",
        "w",
        encoding="utf8",
    ) as csvfile:
        field_names = trades_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(trades_data)


if __name__ == "__main__":
    main()
