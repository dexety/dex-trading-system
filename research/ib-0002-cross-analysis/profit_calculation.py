import json
import plotly.graph_objs as go
import numpy as np
import sys
import bisect
from datetime import datetime, timedelta
from tqdm import tqdm

sys.path.append('../../../')


def get_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, '%Y-%m-%dT%H:%M:%S.%fZ')


# Constants
commission = 0.0005
window_milliseconds_signal = 1000
pos_open_milliseconds = 20000
# jump_signal_threshold = 0.0021
millisec_after_last_trade = 2900
jump_trade_threshold = 0.0024
loss_threshold = 0.0014
signal_coin = "BTC_B"
signal_side = "BUY"
predicted_coin = "ETH_D"
latency_u_d = 500  # from us(u) to dydx(d)
latency_b_u = 200  # from binance(b) to us(u)


def main():
    # data_btc_binance = open('../../../dex_data/trades_binance/data/futures/json/'
                            #'BTCUSD_PERP-trades-2021-12-17_2021-12-27.json', 'r', encoding='utf8')
    # data_eth_binance = open('../../../../dex_data/trades_binance/data/spot/daily/trades/ETHUSDT/'
    #                        '2021-12-16_2021-12-27/json/ETHUSDT-trades-2021-12-17.json', 'r', encoding='utf8')
    # data_btc_future_dydx = open('../../../../dex_data/trades_dydx/trades_BTC-USD_4_60k.json', 'r', encoding='utf8')
    data_eth_future_dydx = open('ETH-USD_dydx_2022-01-01_2022-02-01.csv', 'r', encoding='utf8')

    trades = dict()
    scaled_trades = dict()
    stats = dict()
    for coin in ["ETH_D"]:
        scaled_trades[coin] = dict()
        trades[coin] = dict()
        stats[coin] = dict()
        for side in ["SELL", "BUY"]:
            stats[coin][side] = dict()
            stats[coin][side]["max_price"] = -1
            stats[coin][side]["min_price"] = 10000000

            trades[coin][side] = dict()
            trades[coin][side]["price"] = []
            trades[coin][side]["time"] = []

            scaled_trades[coin][side] = dict()
            scaled_trades[coin][side]["price"] = []

    # data_btc_future_dydx = data_btc_future_dydx.readlines()
    data_eth_future_dydx = data_eth_future_dydx.readlines()
    # data_btc_binance = data_btc_binance.readlines()
    # data_eth_binance = data_eth_binance.readlines()
    #pairs = [("ETH_D", data_eth_future_dydx)]

    coin = "ETH_D"
    for i, line in enumerate(tqdm(data_eth_future_dydx, desc="read file")):
        update = list(line.split(','))
        time = get_datetime(update[-1][0:len(update[-1])-1])
        time += timedelta(hours=3)
        # if not (get_datetime("2021-12-17T17:36:00.000000Z") <= time <= get_datetime("2021-12-17T17:39:00.238000Z")):
        #    if time > get_datetime("2021-12-17T17:39:00.238000Z"):
        #        break
        #    continue
        price = float(update[2])
        side = "SELL" if update[0] == "SELL" else "BUY"
        trades[coin][side]["price"].append(price)
        trades[coin][side]["time"].append(time)
        stats[coin][side]["min_price"] = min(price, stats[coin][side]["min_price"])
        stats[coin][side]["max_price"] = max(price, stats[coin][side]["max_price"])

    colors = ["red", "blue", "green", "black", "purple", "yellow", "brown", "orange"]
    i = 0
    fig_trades = go.Figure()
    fig_trades.update_layout(title_text=f"Signal: {signal_coin}_{signal_side} | Predict: {predicted_coin}")
    for coin in ["ETH_D"]:
        for side in ["BUY", "SELL"]:
            fig_trades.add_trace(go.Scatter(name=side + "_" + coin, x=trades[coin][side]["time"],
                                            y=trades[coin][side]["price"], marker_color=colors[i]))
            i += 1

    good_jumps_ends = []
    with open("signal-jumps_BTC_PERP_2022-01.txt") as f:
        for line in f.readlines():
            line = list(line.split())
            jump_begin = get_datetime(line[0])
            jump_end = get_datetime(line[1])
            up = True if line[-1] == "True" else False
            good_jumps_ends.append((jump_end, up))

    '''
    best_positions = []
    max_usd = -1
    best_wt = -1
    best_tth = -1
    best_lth = -1
    best_alt = -1
    for window_milliseconds_trades in tqdm(range(10000, 20500, 500), desc="1 loop"):
        for millisec_after_last_trade in tqdm(range(1000, 3000, 100), desc="2 loop", leave=False):
            for jump_trade_threshold in tqdm(np.arange(0.001, 0.0025, 0.0001), desc="3 loop", leave=False):
                for loss_threshold in tqdm(np.arange(0.0001, 0.0015, 0.0001), desc="3 loop", leave=False):
    '''

    positions = []
    usd = 100
    last_completion_time = get_datetime("2019-12-31T03:00:00.238000Z")
    sell_ts_ind = 0
    buy_ts_ind = 0
    for ts, up in good_jumps_ends:
        if up:
            buy_ts_ind = bisect.bisect_left(trades[predicted_coin]["BUY"]["time"],
                                            ts + timedelta(milliseconds=latency_u_d),
                                            lo=buy_ts_ind)
            if buy_ts_ind >= len(trades[predicted_coin]["BUY"]["price"]):
                continue
            if last_completion_time + timedelta(milliseconds=millisec_after_last_trade) >= trades[predicted_coin]["BUY"]["time"][buy_ts_ind]:
                continue
            buy_price = trades[predicted_coin]["BUY"]["price"][buy_ts_ind]
            position = dict()
            position["BUY"] = list()
            position["SELL"] = list()
            position["BUY"].append(buy_price)
            position["BUY"].append(trades[predicted_coin]["BUY"]["time"][buy_ts_ind])
            sell_price = -1
            usd *= (1 - commission) ** 2
            tmp = bisect.bisect_left(trades[predicted_coin]["SELL"]["time"],
                                     trades[predicted_coin]["BUY"]["time"][buy_ts_ind] +
                                     timedelta(milliseconds=150))
            while tmp < len(trades[predicted_coin]["SELL"]["time"]) and \
                    ((trades[predicted_coin]["SELL"]["time"][tmp]
                      - trades[predicted_coin]["BUY"]["time"][buy_ts_ind]).total_seconds() * (10 ** 6)) \
                    <= (pos_open_milliseconds * (10 ** 3)):
                jump = trades[predicted_coin]["SELL"]["price"][tmp] / buy_price
                if jump > 1 + jump_trade_threshold:
                    sell_price = trades[predicted_coin]["SELL"]["price"][tmp]
                    last_completion_time = trades[predicted_coin]["SELL"]["time"][tmp]
                    usd *= jump
                    position["SELL"].append(sell_price)
                    position["SELL"].append(trades[predicted_coin]["SELL"]["time"][tmp])
                    positions.append(position)
                    break
                elif jump < 1 - loss_threshold:
                    sell_price = trades[predicted_coin]["SELL"]["price"][tmp]
                    last_completion_time = trades[predicted_coin]["SELL"]["time"][tmp]
                    usd *= jump
                    position["SELL"].append(sell_price)
                    position["SELL"].append(trades[predicted_coin]["SELL"]["time"][tmp])
                    positions.append(position)
                    break
                tmp += 1
            else:
                if tmp >= len(trades[predicted_coin]["SELL"]["time"]):
                    sell_price = trades[predicted_coin]["SELL"]["price"][-1]
                    last_completion_time = trades[predicted_coin]["SELL"]["time"][-1]
                    jump = sell_price / buy_price
                    usd *= jump
                    position["SELL"].append(sell_price)
                    position["SELL"].append(trades[predicted_coin]["SELL"]["time"][-1])
                    positions.append(position)
                    continue
                if tmp == 0:
                    continue
                if ((trades[predicted_coin]["SELL"]["time"][tmp]
                     - trades[predicted_coin]["BUY"]["time"][buy_ts_ind]).total_seconds() * (10 ** 6)) \
                        <= (pos_open_milliseconds * (10 ** 3)):
                    sell_price = trades[predicted_coin]["SELL"]["price"][
                        tmp]
                    jump = sell_price / buy_price
                    usd *= jump
                    last_completion_time = trades[predicted_coin]["SELL"]["time"][tmp]
                    position["SELL"].append(sell_price)
                    position["SELL"].append(trades[predicted_coin]["SELL"]["time"][tmp])
                    positions.append(position)
                    continue
                sell_price = trades[predicted_coin]["SELL"]["price"][tmp - 1] + trades[predicted_coin]["SELL"]["price"][tmp]
                sell_price /= 2
                jump = sell_price / buy_price
                usd *= jump
                last_completion_time = trades[predicted_coin]["SELL"]["time"][tmp]
                position["SELL"].append(sell_price)
                position["SELL"].append(trades[predicted_coin]["SELL"]["time"][tmp])
                positions.append(position)
        else:
            sell_ts_ind = bisect.bisect_left(trades[predicted_coin]["SELL"]["time"],
                                             ts + timedelta(milliseconds=latency_u_d),
                                             lo=sell_ts_ind)
            if sell_ts_ind >= len(trades[predicted_coin]["SELL"]["time"]):
                continue
            if last_completion_time + timedelta(milliseconds=millisec_after_last_trade) >= trades[predicted_coin]["SELL"]["time"][sell_ts_ind]:
                continue
            sell_price = trades[predicted_coin]["SELL"]["price"][sell_ts_ind]
            position = dict()
            position["BUY"] = list()
            position["SELL"] = list()
            position["SELL"].append(sell_price)
            position["SELL"].append(trades[predicted_coin]["SELL"]["time"][sell_ts_ind])
            buy_price = -1
            usd *= (1 - commission) ** 2
            tmp = bisect.bisect_left(trades[predicted_coin]["BUY"]["time"],
                                     trades[predicted_coin]["SELL"]["time"][sell_ts_ind] +
                                     timedelta(milliseconds=150))
            while tmp < len(trades[predicted_coin]["BUY"]["time"]) and \
                    ((trades[predicted_coin]["BUY"]["time"][tmp]
                      - trades[predicted_coin]["SELL"]["time"][sell_ts_ind]).total_seconds() * (10 ** 6)) \
                    <= (pos_open_milliseconds * (10 ** 3)):
                jump = sell_price / trades[predicted_coin]["BUY"]["price"][tmp]
                if jump > 1 + jump_trade_threshold:
                    buy_price = trades[predicted_coin]["BUY"]["price"][tmp]
                    last_completion_time = trades[predicted_coin]["BUY"]["time"][tmp]
                    usd *= jump
                    position["BUY"].append(buy_price)
                    position["BUY"].append(last_completion_time)
                    positions.append(position)
                    break
                elif jump < 1 - loss_threshold:
                    buy_price = trades[predicted_coin]["BUY"]["price"][tmp]
                    last_completion_time = trades[predicted_coin]["BUY"]["time"][tmp]
                    usd *= jump
                    position["BUY"].append(buy_price)
                    position["BUY"].append(last_completion_time)
                    positions.append(position)
                    break
                tmp += 1
            else:
                if tmp >= len(trades[predicted_coin]["BUY"]["time"]):
                    buy_price = trades[predicted_coin]["BUY"]["price"][-1]
                    last_completion_time = trades[predicted_coin]["BUY"]["time"][-1]
                    jump = sell_price / buy_price
                    usd *= jump
                    position["BUY"].append(buy_price)
                    position["BUY"].append(last_completion_time)
                    positions.append(position)
                    continue
                if tmp == 0:
                    continue
                if ((trades[predicted_coin]["BUY"]["time"][tmp]
                     - trades[predicted_coin]["SELL"]["time"][sell_ts_ind]).total_seconds() * (10 ** 6)) \
                        == (pos_open_milliseconds * (10 ** 3)):
                    buy_price = trades[predicted_coin]["BUY"]["price"][tmp]
                    jump = sell_price / buy_price
                    usd *= jump
                    last_completion_time = trades[predicted_coin]["BUY"]["time"][tmp]
                    position["BUY"].append(buy_price)
                    position["BUY"].append(last_completion_time)
                    positions.append(position)
                    continue
                buy_price = trades[predicted_coin]["BUY"]["price"][tmp - 1] + trades[predicted_coin]["BUY"]["price"][tmp]
                buy_price /= 2
                jump = sell_price / buy_price
                usd *= jump
                last_completion_time = trades[predicted_coin]["BUY"]["time"][tmp]
                position["BUY"].append(buy_price)
                position["BUY"].append(last_completion_time)
                positions.append(position)

    '''
    if usd > max_usd:
        best_positions = positions
        best_wt = window_milliseconds_trades
        best_alt = millisec_after_last_trade
        best_lth = loss_threshold
        best_tth = jump_trade_threshold
        usd = max_usd
        print(f"LOSS_TH: {best_lth}\tTRADE_TH: {best_tth}\tAFTER_TRADE: {best_alt}\tPOS_OPEN: {best_wt}")
    '''

    print(f"PROFIT : {usd - 100}")
    with open("trades.txt", "w") as f:
        for position in tqdm(positions, desc="draw trades"):
            if position["SELL"][-1] < position["BUY"][-1]:
                f.write(f"SHORT | SELL : {position['SELL'][-0]}; BUY : {position['BUY'][-0]}\n")
                fig_trades.add_vrect(x0=position["SELL"][-1], x1=position["BUY"][-1], row="all", col=1,
                                     annotation_text="",
                                     annotation_position="top left",
                                     fillcolor="red", opacity=0.5, line_width=1)
            else:
                f.write(f"LONG | BUY : {position['BUY'][-0]}; SELL : {position['SELL'][-0]}\n")
                fig_trades.add_vrect(x0=position["BUY"][-1], x1=position["SELL"][-1], row="all", col=1,
                                     annotation_text="",
                                     annotation_position="top left",
                                     fillcolor="green", opacity=0.5, line_width=1)

    fig_trades.show()


if __name__ == '__main__':
    main()
