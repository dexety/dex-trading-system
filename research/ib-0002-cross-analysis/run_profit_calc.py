from profit_calculator import ProfitCalculator

pc = ProfitCalculator(signal_filename="/home/ivan/dex-data/binance/BTCUSD_PERP-trades-2022-01.csv",
                      predict_filename="/home/ivan/dex-data/dydx/ETH-USD_dydx_2022-01-01_2022-02-01.csv", mode="sig_dump", signals_dump="signals.csv")
total_profit, for_each_trade = pc.get_profit()
print(total_profit)
# pc.dump_signals("signals.csv")
# pc.dump_trades("trades.csv")

