import os
import sys

from dydx3.constants import MARKET_ETH_USD, ORDER_SIDE_BUY

sys.path.append("../../")
from connectors.dydx.connector import DydxConnector
from speed_measure_class import SpeedMeasure

ETH_KEY = os.getenv("ETH_ADDRESS")
ETH_SECRET = os.getenv("ETH_PRIVATE_KEY")
INFURA_NODE = os.getenv("INFURA_NODE")

if __name__ == "__main__":
    dydx_connector = DydxConnector(
        ETH_KEY, ETH_SECRET, MARKET_ETH_USD, INFURA_NODE
    )

    speed_measure = SpeedMeasure(dydx_connector)

    speed_measure.get_connector_funcs_exec_times(
        MARKET_ETH_USD,
        ORDER_SIDE_BUY,
        iters_num=10,
        filename="connector_funcs_exec_times.json",
    )

    speed_measure.get_orders_processing_delays(
        MARKET_ETH_USD,
        ORDER_SIDE_BUY,
        orders_num=10,
        filename="orders_processing_delays.json",
    )
