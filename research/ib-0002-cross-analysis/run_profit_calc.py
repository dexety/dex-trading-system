from profit_calculator import ProfitCalculator

pc = ProfitCalculator(signal_filename="/home/ivan/dex-data/binance/BTCUSD_PERP-trades-2022-03-28.csv",
                      predict_filename="/home/ivan/dex-data/dydx/ETH-USD_dydx_2022-03-28.csv")
pc.show_trades()

