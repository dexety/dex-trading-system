from dydx3.constants import MARKET_ETH_USD, ORDER_SIDE_BUY
from connectors.dydx.connector import DydxConnector
from speed_measure_class import SpeedMeasure

if __name__ == "__main__":
    dydx_connector = DydxConnector(MARKET_ETH_USD)

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
