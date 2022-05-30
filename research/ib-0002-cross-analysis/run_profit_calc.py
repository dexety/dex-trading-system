from profit_calculator import ProfitCalculator

pc = ProfitCalculator(signal_filename="/Users/ivanbondyrev/Downloads/dex-data/binance/trades/BTCUSD_PERP-trades-2022-03-28.csv",
                      predict_filename="/Users/ivanbondyrev/Downloads/dex-data/dydx/ETH-USD_dydx_2022-03-28.csv") #, mode="sig_dump", signals_dump="signals_2022-01.csv")

pc.show_signals()
pc.show_trades()
total_profit, profits = pc.get_profit()
print(total_profit)



