import os
import json
import argparse
from datetime import datetime
from connectors.dydx.connector import DydxConnector, Network

ETH_ADDRESS = os.getenv("ETH_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")

parser = argparse.ArgumentParser(description="Ping script")
parser.add_argument("--symbol", dest="symbol", required=True)
args = parser.parse_args()
symbol = args.symbol
symbols = [symbol]

file_index = 1
while os.path.exists(
    f"../data/trades/raw/trades_{symbol}_{str(file_index)}.json"
):
    file_index += 1

DATA_PATH = f"../data/trades/raw/trades_{symbol}_{str(file_index)}.json"


def on_trade_update(update):
    trade = {
        "update": update,
        "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }

    with open(DATA_PATH, "a", encoding="utf8") as file:
        json.dump(trade, file)
        file.write("\n")


def main():
    dydx_connector = DydxConnector(symbols, Network.mainnet)
    dydx_connector.add_trade_listener(on_trade_update)
    dydx_connector.start()


if __name__ == "__main__":
    main()
