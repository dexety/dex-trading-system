import os
<<<<<<< HEAD
import sys
import pandas as pd
=======
import csv
import json
>>>>>>> main
from datetime import datetime
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_ETH_USD
from utils.helpful_scripts import string_to_datetime
<<<<<<< HEAD
=======


def clean_data(data: list) -> list:
    cleaned_data = []
    cur_dt = string_to_datetime(data[0]["createdAt"])
    for new_trade in data:
        new_dt = string_to_datetime(new_trade["createdAt"])
        if new_dt >= cur_dt:
            cleaned_data.append(new_trade)
        cur_dt = new_dt
    return cleaned_data
>>>>>>> main


def get_trades_from_dydx_api(
    symbol: str, start_dt: datetime, end_dt: datetime
<<<<<<< HEAD
) -> pd.DataFrame:
=======
) -> list:
>>>>>>> main
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")
    dydx_connector_trades = DydxConnector(
        ETH_ADDRESS,
        ETH_PRIVATE_KEY,
        [symbol],
        INFURA_NODE,
    )
<<<<<<< HEAD

    return pd.DataFrame(
=======
    return clean_data(
>>>>>>> main
        dydx_connector_trades.get_historical_trades(symbol, start_dt, end_dt)
    )


def get_formated_dt(dt: datetime) -> str:
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year}"


def main():
<<<<<<< HEAD
    print("Collection of trades initiated...")
    print("***It may take a lot of time***")
    start_dt = datetime(2022, 2, 7, 15)
    end_dt = datetime.utcnow()
    trades: pd.DataFrame = get_trades_from_dydx_api(
        MARKET_ETH_USD, start_dt, end_dt
    )

    print("Trades collected.")
    print("Cleaning initiated...")
    trades_to_drop = []
    cur_dt = string_to_datetime(trades.iloc[0, 3])
    for i in range(trades.shape[0]):
        new_dt = string_to_datetime(trades.iloc[i, 3])
        if new_dt < cur_dt:
            trades_to_drop.append(i)
        else:
            cur_dt = new_dt
        if i % 100000 == 0:
            print(
                f"\r{str(i * 100 / trades.shape[0])}% cleaned. {len(trades_to_drop)} redundant trades found",
                end="",
            )

    trades = trades.drop(axis=0, index=trades_to_drop)

    print("Trades cleaned. Writing to output file...")

=======
    print("collection of trades begin")
    print("it may takes a lot of time")
    start_dt = datetime(2022, 1, 22)
    end_dt = datetime.utcnow()
    trades_data = get_trades_from_dydx_api(MARKET_ETH_USD, start_dt, end_dt)
>>>>>>> main
    with open(
        f"../data/trades/raw/trades_{get_formated_dt(start_dt)}_{get_formated_dt(end_dt)}.csv",
        "w",
        encoding="utf8",
    ) as csvfile:
<<<<<<< HEAD
        trades.to_csv(csvfile, index=False)
    print("Done")
=======
        field_names = trades_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(trades_data)
>>>>>>> main


if __name__ == "__main__":
    main()
