import plotly.graph_objs as go
import sys
from datetime import datetime, timedelta
from tqdm import tqdm

sys.path.append("../../../")


def get_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


# Constants
commission = 0.0005
window_milliseconds_signal = 1000
jump_signal_threshold = 0.0021
signal_coin = "BTC_B"
signal_side = "BUY"
predicted_coin = "ETH_D"
latency_u_d = 500  # from us(u) to dydx(d)
latency_b_u = 200  # from binance(b) to us(u)


def main():
    data_btc_binance = open("binance_trades.cvs", "r", encoding="utf8")

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

    data_btc_binance = data_btc_binance.readlines()
    coin = "BTC_B"
    for i, line in enumerate(tqdm(data_btc_binance, desc="read file")):
        update = list(line.split(","))
        time = datetime.fromtimestamp(int(update[4]) / 1000)
        time += timedelta(milliseconds=latency_b_u)
        # if not (get_datetime("2021-12-17T17:36:00.000000Z") <= time <= get_datetime("2021-12-17T17:39:00.238000Z")):
        #    if time > get_datetime("2021-12-17T17:39:00.238000Z"):
        #        break
        #    continue
        price = float(update[1])
        side = "SELL" if update[-1] == "true\n" else "BUY"
        trades[coin][side]["price"].append(price)
        trades[coin][side]["time"].append(time)
        stats[coin][side]["min_price"] = min(
            price, stats[coin][side]["min_price"]
        )
        stats[coin][side]["max_price"] = max(
            price, stats[coin][side]["max_price"]
        )

    colors = [
        "red",
        "blue",
        "green",
        "black",
        "purple",
        "yellow",
        "brown",
        "orange",
    ]
    i = 0
    fig_trades = go.Figure()
    fig_trades.update_layout(
        title_text=f"Signal: {signal_coin}_{signal_side} | Predict: {predicted_coin}"
    )
    for coin in ["BTC_B"]:
        for side in ["BUY", "SELL"]:
            fig_trades.add_trace(
                go.Scatter(
                    name=side + "_" + coin,
                    x=trades[coin][side]["time"],
                    y=trades[coin][side]["price"],
                    marker_color=colors[i],
                )
            )
            i += 1

    pbar = tqdm(
        desc="find jumps", total=len(trades[signal_coin][signal_side]["price"])
    )
    i = 0
    good_jumps_ends = []
    good_jumps_begins = []
    while i < len(trades[signal_coin][signal_side]["price"]):
        tmp = i
        window = []
        good_jump = False
        up = False
        while tmp < len(trades[signal_coin][signal_side]["price"]) and (
            trades[signal_coin][signal_side]["time"][tmp]
            - trades[signal_coin][signal_side]["time"][i]
        ).total_seconds() * (10 ** 6) < (
            window_milliseconds_signal * (10 ** 3)
        ):
            cur_price = trades[signal_coin][signal_side]["price"][tmp]
            window.append(trades[signal_coin][signal_side]["time"][tmp])
            jump = abs(
                1 - (trades[signal_coin][signal_side]["price"][i] / cur_price)
            )
            if jump > jump_signal_threshold:
                if (
                    1
                    - (trades[signal_coin][signal_side]["price"][i] / cur_price)
                ) > 0:
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

            fig_trades.add_vrect(
                x0=window[0],
                x1=window[-1],
                row="all",
                col=1,
                annotation_text="",
                annotation_position="top left",
                fillcolor="orange",
                opacity=0.5,
                line_width=1,
            )

            i += len(window) - 1
            pbar.update(len(window) - 1)
        else:
            i += 1
            pbar.update(1)
    pbar.close()

    with open("signal-jumps.txt", mode="w") as f:
        for i in range(len(good_jumps_begins)):
            string = (
                f"{good_jumps_begins[i].strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
                f" {good_jumps_ends[i][0].strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
                f" {good_jumps_ends[i][1]}\n"
            )
            f.write(string)

    fig_trades.show()


if __name__ == "__main__":
    main()
