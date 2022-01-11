import logging

FORMAT = "%(asctime)s %(levelname)-6s %(module)-10s:: %(message)-50s"
LEVEL = logging.DEBUG

logging.basicConfig(format=FORMAT)

Logger = logging.getLogger("dex_trading_system")
Logger.setLevel(LEVEL)

Logger.addHandler(logging.FileHandler("dex_trading_system/debug.log"))
# Logger.propagate = False
