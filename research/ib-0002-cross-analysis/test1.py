from signals_giver import SignalsGiver

SG = SignalsGiver(mode="file", filename="/home/ivan/dex-data/binance/trades/BTCUSD_PERP-trades-2022-03-28.csv")
SG.get_signals()
SG.show_signals()