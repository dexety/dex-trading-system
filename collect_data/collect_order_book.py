import os
import json
import argparse
from datetime import datetime
from connectors.dydx.connector import DydxConnector

ETH_ADDRESS = os.getenv("ETH_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")

parser = argparse.ArgumentParser(description="Ping script")
parser.add_argument("--symbol", dest="symbol", required=True)
args = parser.parse_args()
symbol = args.symbol
symbols = [symbol]


def on_order_book_update(update):
    oreder_book = {
        "update": update,
        "time": str(datetime.now()),
    }

    with open(
        "../data/order_book/order_book_" + symbol + ".json",
        "a",
        encoding="utf8",
    ) as file:
        json.dump(oreder_book, file)
        file.write("\n")


def main():
    dydx_connector = DydxConnector(symbols)
    dydx_connector.add_orderbook_listener(on_order_book_update)
    dydx_connector.start()


if __name__ == "__main__":
    main()
