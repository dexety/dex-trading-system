import pandas as pd
from datetime import datetime
from connectors.dydx.connector import DydxConnector, Network
from dydx3.constants import MARKET_ETH_USD
from utils.helpful_scripts import string_to_datetime


def get_trades_from_dydx_api(
    symbol: str, start_dt: datetime, end_dt: datetime
) -> pd.DataFrame:
    dydx_connector_trades = DydxConnector(
        [symbol],
        Network.mainnet,
    )

    return pd.DataFrame(
        dydx_connector_trades.get_historical_trades(symbol, start_dt, end_dt)
    )


def get_formated_dt(dt: datetime) -> str:
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year}"


def main():
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
    cur_dt = string_to_datetime(trades.iloc[0].createdAt)
    for i in range(trades.shape[0]):
        new_dt = string_to_datetime(trades.iloc[i].createdAt)
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

    with open(
        f"../data/trades/raw/trades_{get_formated_dt(start_dt)}_{get_formated_dt(end_dt)}.csv",
        "w",
        encoding="utf8",
    ) as csvfile:
        trades.to_csv(csvfile, index=False)
    print("Done")


if __name__ == "__main__":
    main()
