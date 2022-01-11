import os
from web3 import Web3

from dydx3 import Client
from dydx3 import private_key_to_public_key_pair_hex
from dydx3.constants import API_HOST_MAINNET
from dydx3.constants import NETWORK_ID_MAINNET


ETHEREUM_ADDRESS = os.getenv("ETH_ADDRESS")
ETHEREUM_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
WEB_PROVIDER_URL = "http://localhost:8545"

client = Client(
    network_id=NETWORK_ID_MAINNET,
    host=API_HOST_MAINNET,
    default_ethereum_address=ETHEREUM_ADDRESS,
    eth_private_key=ETHEREUM_PRIVATE_KEY,
    web3=Web3(Web3.HTTPProvider(WEB_PROVIDER_URL)),
)

stark_private_key = client.onboarding.derive_stark_key()
client.stark_private_key = stark_private_key
public_x, public_y = private_key_to_public_key_pair_hex(stark_private_key)

onboarding_response = client.onboarding.create_user(
    stark_public_key=public_x,
    stark_public_key_y_coordinate=public_y,
)
print("onboarding_response", onboarding_response)
