import trader
from dydx3.constants import MARKET_BTC_USD

if __name__ == "__main__":
    trader_settings = trader.Settings(
        trailing_percent=0.005,
        quantity=0.001,
        profit_threshold=0.0015,
        sec_to_wait=30,
        sec_after_trade=0,
        signal_threshold=0.003,
        dydx_market=MARKET_BTC_USD,
        binance_market="BTCUSD_PERP",
    )
    trader = trader.Trader(trader_settings)
    trader.run()
