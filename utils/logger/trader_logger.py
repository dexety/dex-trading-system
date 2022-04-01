from datetime import datetime
import logging

FORMAT = "%(asctime)s %(levelname)s:: %(message)-50s"
LEVEL = logging.DEBUG

DebugLogger = logging.getLogger("Logger for debug")
TradeLogger = logging.getLogger("Logger for trades")

TradeLogger.setLevel(logging.INFO)
DebugLogger.setLevel(logging.DEBUG)

TradesHandler = logging.FileHandler(
    f"logs/trades-{datetime.now():%Y_%m_%dT%H_%M_%S}.log"
)
TradesHandler.setLevel(logging.INFO)
TradesHandler.setFormatter(
    logging.Formatter(
        "%(asctime)s.%(msecs)03dZ,%(message)s", "%Y-%m-%dT%H:%M:%S"
    )
)

DebugHandler = logging.FileHandler("logs/trader_debug.log")
DebugHandler.setLevel(logging.DEBUG)
DebugHandler.setFormatter(logging.Formatter(FORMAT))

TradeLogger.addHandler(TradesHandler)
DebugLogger.addHandler(DebugHandler)
