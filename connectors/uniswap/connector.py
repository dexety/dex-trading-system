import os
from uniswap import Uniswap


class L1PoolConnector:
    def __init__(self, eth_address: str, eth_private_key: str) -> None:
        INFURA_NODE = os.getenv("INFURA_NODE")
        self.uniswap = Uniswap(
            address=eth_address,
            private_key=eth_private_key,
            version=3,
            provider=INFURA_NODE,
        )

    def get_uniswap_price_input(
        self, from_token: str, to_token: str, from_token_amount: str
    ) -> int:
        return self.uniswap.get_price_input(
            from_token, to_token, from_token_amount
        )
