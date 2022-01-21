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

# dydx_connector.add_trade_listener(trade_listener)
# dydx_connector.add_trade_subscription(MARKET_BTC_USD)

# dydx_connector.start()

now_iso_string = generate_now_iso()
signature = client.private.sign(
    request_path='/ws/accounts',
    method='GET',
    iso_timestamp=now_iso_string,
    data={},
)
req = {
    'type': 'subscribe',
    'channel': 'v3_accounts',
    'accountNumber': '0',
    'apiKey': client.api_key_credentials['key'],
    'passphrase': client.api_key_credentials['passphrase'],
    'timestamp': now_iso_string,
    'signature': signature,
}


async def main():
    # Note: This doesn't work with Python 3.9.
    async with websockets.connect(WS_HOST_MAINNET) as websocket:

        await websocket.send(json.dumps(req))
        # print(f'> {req}')

        while True:
            res = await websocket.recv()
            print(json.dumps(json.loads(res), indent=4))

asyncio.get_event_loop().run_until_complete(main())

order = dydx_connector.send_fok_order(
    symbol=MARKET_ETH_USD,
    side=ORDER_SIDE_BUY,
    price=1,
    quantity=0.01,
)

# print(json.dumps(order, indent=4))

# time.sleep(1)

# print(dydx_connector.get_client().private.get_order_by_id(order["order"]["id"]))
