import sys
import os
import json

from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY, WS_HOST_MAINNET

sys.path.append("../")

from connectors.dydx.connector import DydxConnector, safe_execute

ETH_KEY = os.getenv("ETH_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
INFURA_NODE = os.getenv("INFURA_NODE")

dydx_connector = DydxConnector(
    ETH_KEY,
    ETH_PRIVATE_KEY,
    [MARKET_BTC_USD],
    INFURA_NODE,
)
client = dydx_connector.get_client()

def trade_listener(trade):
    print(json.dumps(trade, indent=4))

order = dydx_connector.send_fok_order(
    symbol=MARKET_ETH_USD,
    side=ORDER_SIDE_BUY,
    price=2000,
    quantity=0.01,
)

print(json.dumps(order, indent=4))
