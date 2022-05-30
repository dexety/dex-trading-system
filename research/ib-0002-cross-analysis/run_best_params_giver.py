from signals_giver import SignalsGiver
from best_params_giver import BestParamsGiver
import json

SG = SignalsGiver(mode="file", filename="/Users/ivanbondyrev/Downloads/dex-data/binance/trades/BTCUSD_PERP-trades-2022-03-28.csv")
signals = SG.get_signals()
SG.dump_signals("new_signals_2022-03-28.csv")
SG.dump_stats("stats_2022-03-28.json")


BP = BestParamsGiver(signals, filename="/Users/ivanbondyrev/Downloads/dex-data/dydx/ETH-USD_dydx_2022-03-28.csv")
trades = BP.get_trades()
print(BP.total_usd)
with open("trades_with_best_params_2022-03.json", "w+") as file:
    json.dump(trades, file, indent=4)
