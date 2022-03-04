import sys
import os
from datetime import datetime, timedelta
from dydx3.helpers.request_helpers import generate_now_iso
import websockets
import json
import asyncio
import os
from web3 import Web3

from dydx3 import Client
from dydx3 import private_key_to_public_key_pair_hex
from dydx3.constants import API_HOST_MAINNET, API_HOST_ROPSTEN
from dydx3.constants import NETWORK_ID_MAINNET, NETWORK_ID_ROPSTEN

from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY

sys.path.append("../../")

from connectors.dydx.connector import DydxConnector, safe_execute

ETH_KEY = ""
ETH_PRIVATE_KEY = ""
# INFURA_NODE = os.getenv("INFURA_NODE")



client = Client(
    network_id=NETWORK_ID_ROPSTEN,
    host=API_HOST_ROPSTEN,
    default_ethereum_address=ETH_KEY,
    eth_private_key=ETH_PRIVATE_KEY,
    web3=Web3(Web3.HTTPProvider("http://localhost:8545")),

)

print(client.api_key_credentials["passphrase"])


stark_private_key = client.onboarding.derive_stark_key()
client.stark_private_key = stark_private_key
public_x, public_y = private_key_to_public_key_pair_hex(stark_private_key)




now_iso_string = generate_now_iso()
signature = client.private.sign(
    request_path="/ws/accounts",
    method="GET",
    iso_timestamp=now_iso_string,
    data={},
)
req = {
    "type": "subscribe",
    "channel": "v3_accounts",
    "accountNumber": "0",
    "apiKey": client.api_key_credentials["key"],
    "passphrase": client.api_key_credentials[
                "passphrase"
    ],
    "timestamp": now_iso_string,
    "signature": signature,
}

socket_dydx = f"wss://api.stage.dydx.exchange/v3/ws"


async def get_our_trades():
    async with websockets.connect(socket_dydx) as sock:
        await sock.send(json.dumps(req))
        # await sock.recv()  # trash response
        # await sock.recv()  # trash response
        while True:
            data = await sock.recv()
            json_data = json.loads(data)
            print(json_data)

loop = asyncio.get_event_loop()
loop.run_until_complete(get_our_trades())
