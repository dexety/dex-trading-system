import sys
import os
import time
import asyncio
from datetime import datetime, timedelta
import json
import websockets

from dydx3.helpers.request_helpers import generate_now_iso
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

# dydx_connector.add_orderbook_listener(ob_listener)
# dydx_connector.add_orderbook_subscription(MARKET_BTC_USD)

dydx_connector.add_trade_listener(trade_listener)
dydx_connector.add_trade_subscription(MARKET_BTC_USD)

dydx_connector.start()
