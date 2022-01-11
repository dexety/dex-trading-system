import os
import sys
import json
from datetime import datetime

sys.path.append("../")

from connectors.dydx.connector import DydxConnector


def get_trades_from_dydx_api(
    symbol: str, start_dt: datetime, end_dt: datetime, debug_info=False
) -> dict:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")
    dydx_connector_trades = DydxConnector(
        ETH_ADDRESS,
        ETH_PRIVATE_KEY,
        [symbol],
        INFURA_NODE,
    )
    return dydx_connector_trades.get_historical_trades(
        symbol, start_dt, end_dt, debug_info
    )


def get_formated_dt(dt: datetime) -> str:
    return f"{dt.year}_{dt.month}_{dt.day}_{dt.hour}_{dt.minute}_{dt.second}"


def main():
    print("collection of trades begin")
    print("it may takes a lot of time")
    start_dt = datetime(2021, 11, 1)
    end_dt = datetime(2021, 11, 7)
    trades_data = get_trades_from_dydx_api("ETH-USD", start_dt, end_dt, True)
    with open(
        f"../data/trades/trades-{get_formated_dt(start_dt)}-{get_formated_dt(end_dt)}.json",
        "w",
        encoding="utf8",
    ) as file:
        json.dump(trades_data, file)


if __name__ == "__main__":
    main()
