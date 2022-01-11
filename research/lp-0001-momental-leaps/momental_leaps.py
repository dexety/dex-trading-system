import json
import plotly.graph_objs as go
from datetime import datetime, timedelta
from collections import deque


def get_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def main():
    milliseconds_delta = 300
    jump_threshold = 0.001
    data = open("../../data/trades/trades_ETH-USD_4.json", "r", encoding="utf8")
    jumps_scale = []
    times = []
    trades_sell = []
    trades_buy = []
    times_sell = []
    times_buy = []
    times_big_jumps = []
    trades_window = deque()

    while True:
        update = json.loads(data.readline())["update"]
        time = get_datetime(update["recieveTime"])

        if update["side"] == "SELL":
            trades_sell.append(update["price"])
            times_sell.append(time)
        elif update["side"] == "BUY":
            trades_buy.append(update["price"])
            times_buy.append(time)

        if len(trades_window) == 0 or trades_window[0]["time"] + timedelta(
            milliseconds=milliseconds_delta
        ) > get_datetime(update["recieveTime"]):
            trades_window.append(
                {
                    "time": time,
                    "price": update["price"],
                }
            )
        else:
            break

    data = data.readlines()
    for update in data:
        update = json.loads(update)["update"]
        time = get_datetime(update["recieveTime"])

        if update["side"] == "SELL":
            trades_sell.append(update["price"])
            times_sell.append(time)
        elif update["side"] == "BUY":
            trades_buy.append(update["price"])
            times_buy.append(time)

        while (
            len(trades_window) > 0
            and trades_window[0]["time"]
            + timedelta(milliseconds=milliseconds_delta)
            < time
        ):
            trades_window.popleft()

        trades_window.append(
            {
                "time": get_datetime(update["recieveTime"]),
                "price": update["price"],
            }
        )

        trades_delta = (
            trades_window[-1]["price"] / trades_window[0]["price"] - 1
        )
        jumps_scale.append(trades_delta)
        times.append(time)
        if abs(trades_delta) > jump_threshold and (
            len(times_big_jumps) == 0
            or trades_window[0]["time"] > times_big_jumps[-1][-1]["time"]
        ):
            times_big_jumps.append([trades_window[0], trades_window[-1]])

    fig_distributuion = go.Figure()
    fig_distributuion.add_trace(
        go.Bar(
            name="jumps",
            x=list(range(len(jumps_scale))),
            y=sorted(jumps_scale),
            marker={"color": "red"},
        )
    )
    fig_distributuion.update_layout(
        barmode="group",
        bargap=0,
        bargroupgap=0,
        title="Trades jumps in window distribution. Delta = "
        + str(milliseconds_delta)
        + "ms",
        xaxis_title="time from " + str(times[0]) + " up to " + str(times[-1]),
        yaxis_title="ratio of last trade in window and first",
    )
    fig_distributuion.show()

    fig_trades = go.Figure()
    #
    # Too slow plot view with the markers
    #
    # fig_trades.add_trace(go.Scatter(name='SELL', x=times_sell, y = trades_sell, mode='lines+markers', marker_size=4, marker_color='green'))
    # fig_trades.add_trace(go.Scatter(name='BUY', x=times_buy, y = trades_buy, mode='lines+markers', marker_size=4, marker_color='red'))
    #
    fig_trades.add_trace(
        go.Scatter(
            name="SELL", x=times_sell, y=trades_sell, marker_color="green"
        )
    )
    fig_trades.add_trace(
        go.Scatter(name="BUY", x=times_buy, y=trades_buy, marker_color="red")
    )
    for time_big_jump in times_big_jumps:
        fig_trades.add_vrect(
            x0=time_big_jump[0]["time"],
            x1=time_big_jump[-1]["time"],
            row="all",
            col=1,
            annotation_text=str(
                1 - time_big_jump[-1]["price"] / time_big_jump[0]["price"]
            ),
            annotation_position="top left",
            fillcolor="green",
            opacity=0.5,
            line_width=1,
        )
    fig_trades.update_layout(
        title="Trades on dydx", xaxis_title="time", yaxis_title="price"
    )
    fig_trades.show()


if __name__ == "__main__":
    main()
