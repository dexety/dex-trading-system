import json
import plotly.graph_objs as go
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
pos_open_milliseconds = 10000
jump_signal_threshold = 0.0021
jump_trade_threshold = 0.0018
loss_threshold = 0.0009
signal_coin = "BTC_B"
signal_side = "BUY"
predicted_coin = "ETH_D"
latency_u_d = 500  # from us(u) to dydx(d)
latency_b_u = 200  # from binance(b) to us(u)


def main():
    data_btc_binance = open('../../../dex_data/trades_binance/data/futures/csv/'
                            'BTCUSD_PERP-trades-2021-12-17_2021-12-27.json', 'r', encoding='utf8')
    # data_eth_binance = open('../../../../dex_data/trades_binance/data/spot/daily/trades/ETHUSDT/'
    #                        '2021-12-16_2021-12-27/json/ETHUSDT-trades-2021-12-17.json', 'r', encoding='utf8')
    # data_btc_future_dydx = open('../../../../dex_data/trades_dydx/trades_BTC-USD_4_60k.json', 'r', encoding='utf8')
    # data_eth_future_dydx = open('../../../dex_data/trades_dydx/trades_ETH-USD_4.json', 'r', encoding='utf8')

    trades = dict()
    scaled_trades = dict()
    stats = dict()
    for coin in ["BTC_B"]:
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
    # data_eth_future_dydx = data_eth_future_dydx.readlines()
    data_btc_binance = data_btc_binance.readlines()
    # data_eth_binance = data_eth_binance.readlines()
    pairs = [("BTC_B", data_btc_binance)]
    coin = "BTC_B"
    for i, line in enumerate(tqdm(data_btc_binance, desc="read file")):
        update = list(line.split(','))
        time = datetime.fromtimestamp(int(update[4])/1000)
        time += timedelta(milliseconds=latency_b_u)
        # if not (get_datetime("2021-12-17T17:36:00.000000Z") <= time <= get_datetime("2021-12-17T17:39:00.238000Z")):
        #    if time > get_datetime("2021-12-17T17:39:00.238000Z"):
        #        break
        #    continue
        price = float(update[1])
        side = "SELL" if update[-1] == "true\n" else "BUY"
        trades[coin][side]["price"].append(price)
        trades[coin][side]["time"].append(time)
        stats[coin][side]["min_price"] = min(price, stats[coin][side]["min_price"])
        stats[coin][side]["max_price"] = max(price, stats[coin][side]["max_price"])

    '''
    for coin in tqdm(["ETH_D", "BTC_B"]):
        for side in tqdm(["SELL", "BUY"]):
            scaled_trades[coin][side]["price"][:] = list(map(lambda x: x - stats[coin][side]["min_price"],
                                                             trades[coin][side]["price"]))
            delta = stats[coin][side]["max_price"] - stats[coin][side]["min_price"]
            scaled_trades[coin][side]["price"][:] = list(map(lambda x: x / delta,
                                                             scaled_trades[coin][side]["price"]))
    '''

    colors = ["red", "blue", "green", "black", "purple", "yellow", "brown", "orange"]
    i = 0
    fig_trades = go.Figure()
    fig_trades.update_layout(title_text=f"Signal: {signal_coin}_{signal_side} | Predict: {predicted_coin}")
    for coin in ["BTC_B"]:
        for side in ["BUY", "SELL"]:
            fig_trades.add_trace(go.Scatter(name=side + "_" + coin, x=trades[coin][side]["time"],
                                            y=trades[coin][side]["price"], marker_color=colors[i]))
            i += 1

    pbar = tqdm(desc="find jumps", total=len(trades[signal_coin][signal_side]["price"]))
    i = 0
    good_jumps_ends = []
    good_jumps_begins = []
    while i < len(trades[signal_coin][signal_side]["price"]):
        tmp = i
        window = []
        good_jump = False
        up = False
        while tmp < len(trades[signal_coin][signal_side]["price"]) and \
                (trades[signal_coin][signal_side]["time"][tmp] -
                 trades[signal_coin][signal_side]["time"][i]).total_seconds() * (10 ** 6) < \
                (window_milliseconds_signal * (10 ** 3)):
            cur_price = trades[signal_coin][signal_side]["price"][tmp]
            window.append(trades[signal_coin][signal_side]["time"][tmp])
            jump = abs(1 - (trades[signal_coin][signal_side]["price"][i] / cur_price))
            if jump > jump_signal_threshold:
                if (1 - (trades[signal_coin][signal_side]["price"][i] / cur_price)) > 0:
                    up = True
                good_jump = True
                break
            else:
                if good_jump:
                    break
            tmp += 1
        if good_jump:
            good_jumps_ends.append((window[-1], up))
            good_jumps_begins.append(window[0])

            fig_trades.add_vrect(x0=window[0], x1=window[-1], row="all", col=1,
                                 annotation_text="",
                                 annotation_position="top left",
                                 fillcolor="orange", opacity=0.5, line_width=1)

            i += len(window) - 1
            pbar.update(len(window) - 1)
        else:
            i += 1
            pbar.update(1)
    pbar.close()

    with open("signal-jumps.txt", mode="w") as f:
        for i in range(len(good_jumps_begins)):
            string = f"{good_jumps_begins[i].strftime('%Y-%m-%dT%H:%M:%S.%fZ')}" \
                     f" {good_jumps_ends[i][0].strftime('%Y-%m-%dT%H:%M:%S.%fZ')}" \
                     f" {good_jumps_ends[i][1]}\n"
            f.write(string)

    fig_trades.show()

    '''
    positions = []
    usd = 100
    last_completion_time = get_datetime("2020-12-31T03:00:00.238000Z")
    sell_ts_ind = 0
    buy_ts_ind = 0
    for ts, up in tqdm(good_jumps_ends):
        if up:
            buy_ts_ind = bisect.bisect_left(trades[predicted_coin]["BUY"]["time"],
                                            ts + timedelta(milliseconds=latency_u_d),
                                            lo=buy_ts_ind)
            if buy_ts_ind >= len(trades[predicted_coin]["BUY"]["price"]):
                continue
            if last_completion_time + timedelta(milliseconds=2000) >= trades[predicted_coin]["BUY"]["time"][buy_ts_ind]:
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
                                     timedelta(milliseconds=10))
            while tmp < len(trades[predicted_coin]["SELL"]["time"]) and \
                    ((trades[predicted_coin]["SELL"]["time"][tmp]
                      - trades[predicted_coin]["BUY"]["time"][buy_ts_ind]).total_seconds() * (10 ** 6)) \
                    <= (window_milliseconds_trades * (10 ** 3)):
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
                        <= (window_milliseconds_trades * (10 ** 3)):
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
            if last_completion_time + timedelta(milliseconds=2000) >= trades[predicted_coin]["SELL"]["time"][sell_ts_ind]:
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
                                     timedelta(milliseconds=10))
            while tmp < len(trades[predicted_coin]["BUY"]["time"]) and \
                    ((trades[predicted_coin]["BUY"]["time"][tmp]
                      - trades[predicted_coin]["SELL"]["time"][sell_ts_ind]).total_seconds() * (10 ** 6)) \
                    <= (window_milliseconds_trades * (10 ** 3)):
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
                        == (window_milliseconds_trades * (10 ** 3)):
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
    print(usd)

    for position in positions:
        if position["SELL"][-1] < position["BUY"][-1]:
            print(f"SHORT | SELL : {position['SELL'][-0]}; BUY : {position['BUY'][-0]}")
            fig_trades.add_vrect(x0=position["SELL"][-1], x1=position["BUY"][-1], row="all", col=1,
                                 annotation_text="",
                                 annotation_position="top left",
                                 fillcolor="red", opacity=0.5, line_width=1)
        else:
            print(f"LONG | BUY : {position['BUY'][-0]}; SELL : {position['SELL'][-0]}")
            fig_trades.add_vrect(x0=position["BUY"][-1], x1=position["SELL"][-1], row="all", col=1,
                                 annotation_text="",
                                 annotation_position="top left",
                                 fillcolor="green", opacity=0.5, line_width=1)

    fig_trades.show()


    sell_ts_ind = 0
    buy_ts_ind = 0
    match_cnt = 0
    for ts, up in good_jumps_ends:
        if up:
            buy_ts_ind = bisect.bisect_left(trades[predicted_coin]["BUY"]["time"],
                                            ts + timedelta(milliseconds=latency_u_d),
                                            lo=buy_ts_ind)
            if buy_ts_ind >= len(trades[predicted_coin]["BUY"]["price"]):
                continue
            buy_price = trades[predicted_coin]["BUY"]["price"][buy_ts_ind]
            begin_sell_ts_ind = bisect.bisect_left(trades[predicted_coin]["SELL"]["time"],
                                                   trades[predicted_coin]["BUY"]["time"][buy_ts_ind] +
                                                   timedelta(milliseconds=10))
            while begin_sell_ts_ind < len(trades[predicted_coin]["SELL"]["time"]) and \
                    ((trades[predicted_coin]["SELL"]["time"][begin_sell_ts_ind]
                      - trades[predicted_coin]["BUY"]["time"][buy_ts_ind]).total_seconds() * (10 ** 6)) \
                    < (window_milliseconds_trades * (10 ** 3)):
                cur_sell_price = trades[predicted_coin]["SELL"]["price"][begin_sell_ts_ind]
                jump = (1 - (buy_price / cur_sell_price))
                if jump > 0 and jump > jump_trade_threshold:
                    match_cnt += 1
                    fig_trades.add_vrect(x0=trades[predicted_coin]["BUY"]["time"][buy_ts_ind],
                                         x1=trades[predicted_coin]["SELL"]["time"][begin_sell_ts_ind], row="all", col=1,
                                         annotation_text="",
                                         annotation_position="top left",
                                         fillcolor="green", opacity=0.5, line_width=1)
                    break
                begin_sell_ts_ind += 1
        else:
            sell_ts_ind = bisect.bisect_left(trades[predicted_coin]["SELL"]["time"],
                                             ts + timedelta(milliseconds=latency_u_d),
                                             lo=sell_ts_ind)
            if sell_ts_ind >= len(trades[predicted_coin]["BUY"]["price"]):
                continue
            sell_price = trades[predicted_coin]["SELL"]["price"][sell_ts_ind]
            begin_buy_ts_ind = bisect.bisect_left(trades[predicted_coin]["BUY"]["time"],
                                                  trades[predicted_coin]["SELL"]["time"][sell_ts_ind] +
                                                  timedelta(milliseconds=10))
            while begin_buy_ts_ind < len(trades[predicted_coin]["BUY"]["time"]) and \
                    ((trades[predicted_coin]["BUY"]["time"][begin_buy_ts_ind]
                      - trades[predicted_coin]["SELL"]["time"][sell_ts_ind]).total_seconds() * (10 ** 6)) \
                    < (window_milliseconds_trades * (10 ** 3)):
                cur_buy_price = trades[predicted_coin]["BUY"]["price"][begin_buy_ts_ind]
                jump = (1 - (sell_price / cur_buy_price))
                if jump < 0 and abs(jump) > jump_trade_threshold:
                    match_cnt += 1
                    fig_trades.add_vrect(x0=trades[predicted_coin]["SELL"]["time"][sell_ts_ind],
                                         x1=trades[predicted_coin]["BUY"]["time"][begin_buy_ts_ind], row="all", col=1,
                                         annotation_text="",
                                         annotation_position="top left",
                                         fillcolor="green", opacity=0.5, line_width=1)
                    break
                begin_buy_ts_ind += 1

    '''

if __name__ == '__main__':
    main()
