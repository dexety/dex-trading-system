import os
import sys

sys.path.append("../")

from connectors.uniswap.connector import L1PoolConnector

ETH_KEY = os.getenv("ETH_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")

ETH = "0x0000000000000000000000000000000000000000"
BAT = "0x0D8775F648430679A709E98d2b0Cb6250d2887EF"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

connector = L1PoolConnector(ETH_KEY, ETH_PRIVATE_KEY)


def test_get_price() -> None:
    price = connector.get_uniswap_price_input(BAT, ETH, 10 ** 18)
    assert price != 0
