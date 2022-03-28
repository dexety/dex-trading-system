import sys
import os
from datetime import datetime, timedelta

from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY

sys.path.append("../../")

from connectors.dydx.connector import DydxConnector, safe_execute

ETH_KEY = ""
ETH_PRIVATE_KEY = ""
# INFURA_NODE = os.getenv("INFURA_NODE")

dydx_connector = DydxConnector(
    ETH_KEY,
    ETH_PRIVATE_KEY,
    [MARKET_ETH_USD],
)

order = dydx_connector.send_trailing_stop_order(
    symbol=MARKET_ETH_USD,
    side="BUY",
    price=10 ** 8,
    quantity=0.02,
    trailing_percent=0.14,
)
