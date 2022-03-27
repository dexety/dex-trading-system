import logging

FORMAT = "%(asctime)s %(levelname)s:: %(message)-50s"
LEVEL = logging.DEBUG

Logger_debug = logging.getLogger("Logger for debug")
Logger_trades = logging.getLogger("Logger for trades")

Logger_trades.setLevel(logging.INFO)
Logger_debug.setLevel(logging.DEBUG)

trades_handler = logging.FileHandler("logs/trades.log")
trades_handler.setLevel(logging.INFO)
trades_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03dZ,%(message)s', "%Y-%m-%dT%H:%M:%S"))

debug_handler = logging.FileHandler("logs/trader_debug.log")
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter(FORMAT))

Logger_trades.addHandler(trades_handler)
Logger_debug.addHandler(debug_handler)
