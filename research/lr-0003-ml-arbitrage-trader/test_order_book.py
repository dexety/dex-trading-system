import json

from dydx3.constants import MARKET_BTC_USD
from connectors.dydx.connector import DydxConnector

dydx_connector = DydxConnector(
    MARKET_BTC_USD,
)
client = dydx_connector.get_client()


def trade_listener(trade):
    print(json.dumps(trade, indent=4))


# dydx_connector.add_orderbook_listener(ob_listener)
# dydx_connector.add_orderbook_subscription(MARKET_BTC_USD)

# dydx_connector.add_trade_listener(trade_listener)
# dydx_connector.add_trade_subscription(MARKET_BTC_USD)
dydx_connector.add_account_listener(trade_listener)
dydx_connector.add_account_subscription()

dydx_connector.start()
