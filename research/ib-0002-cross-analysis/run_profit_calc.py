from profit_calculator import ProfitCalculator

pc = ProfitCalculator(signal_filename="/home/ivan/dex-data/binance/trades/BTCUSD_PERP-trades-2022-03.csv",
                      predict_filename="/home/ivan/dex-data/dydx/ETH-USD_dydx_2022-03.csv") #, mode="sig_dump", signals_dump="/home/ivan/dex-data/binance/signals/2022-03/signals_2000_0.004.csv")

total_profit, profits = pc.get_profit()
pc.dump_signals(f"/home/ivan/dex-data/binance/signals/2022-03/signals_{pc.window}_{pc.signal_threshold}_{pc.latency_signal_us}.csv")
print(total_profit)


