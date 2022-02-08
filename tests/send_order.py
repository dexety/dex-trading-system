import sys
import os
import json
from datetime import datetime

from dydx3.constants import (
    MARKET_BTC_USD,
    MARKET_ETH_USD,
    ORDER_SIDE_BUY,
    ORDER_SIDE_SELL,
)

from connectors.dydx.connector import DydxConnector

ETH_KEY = os.getenv("ETH_TEST_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_TEST_PRIVATE_KEY")
INFURA_NODE = os.getenv("ROPSTEN_INFURA_NODE")

programm_start_time = str(datetime.utcnow())
dydx_connector = DydxConnector(
    [MARKET_BTC_USD],
    account="test",
    network="ropsten"
)
client = dydx_connector.get_client()

order_book = dydx_connector.get_order_book(MARKET_ETH_USD)
best_bid = float(order_book["bids"][0]["price"])
best_ask = float(order_book["asks"][0]["price"])
price = (best_bid + best_ask) / 2
print(f"best ask: {best_ask}")
print(f"best bid: {best_bid}")

def trade_listener(trade):
    print(json.dumps(trade, indent=4))

trades = dydx_connector.get_client().public.get_trades(MARKET_ETH_USD)["trades"][0]

try:
    go_long_order = dydx_connector.send_fok_market_order(
        symbol=MARKET_ETH_USD,
        side=ORDER_SIDE_BUY,
        price=str(best_ask),
        quantity="0.01",
        client_id="go_long " + programm_start_time,
    )

    take_profit_order = dydx_connector.send_take_profit_order(
        symbol=MARKET_ETH_USD,
        side=ORDER_SIDE_SELL,
        price=str(round(best_ask * 1.0005, 1)),
        quantity="0.01",
        client_id="take_profit " + programm_start_time,
    )

    stop_loss_order = dydx_connector.send_trailing_stop_order(
        symbol=MARKET_ETH_USD,
        side=ORDER_SIDE_SELL,
        price=str(best_ask),
        quantity="0.01",
        trailing_percent="-0.1",
        client_id="trailing_stop " + programm_start_time,
    )
except:
    dydx_connector.cancel_all_orders()
    raise

print(json.dumps([go_long_order, take_profit_order, stop_loss_order], indent=4))

# dydx_connector.cancel_all_orders()
