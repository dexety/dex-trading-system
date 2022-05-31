from connectors.dydx.connector import Network
import strategy.arbitrage.trader as trader
from dydx3.constants import MARKET_ETH_USD

if __name__ == "__main__":
    trader_settings = trader.Settings(
        trailing_percent=0.005,
        quantity=0.01,
        profit_threshold=0.0015,
        sec_to_wait=30,
        sec_after_trade=0,
        signal_threshold=0.00015,
        dydx_symbol=MARKET_ETH_USD,
        dydx_network=Network.ropsten,
        round_digits=1
    )
    trader_old = trader.Trader(settings=trader_settings)
    trader_old.run()
