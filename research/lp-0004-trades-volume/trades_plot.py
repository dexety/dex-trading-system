import json
import plotly.graph_objs as go
from plotly.subplots import make_subplots


def main():
    data = json.load(
        open(
            "../../data/trades/trades-2021_12_1_0_0_0-2021_12_21_0_0_0.json",
            "r",
            encoding="utf8",
        )
    )[:100000]

    # Trade update
    # {
    #     "side": "SELL",
    #     "size": 0.065,
    #     "price": 4063.2,
    #     "createdAt": "2021-12-06T07:22:55.249Z",
    #     "exchange": "dydx",
    #     "symbol": "ETH-USD",
    #     "recieveTime": "2021-12-06T07:22:56.038579Z",
    # }

    trades_sell = list(filter(lambda trade: trade["side"] == "SELL", data))
    trades_buy = list(filter(lambda trade: trade["side"] == "BUY", data))

    trades = {
        "SELL": {
            "price": list(
                map(lambda trade: float(trade["price"]), trades_sell)
            ),
            "size": list(map(lambda trade: -float(trade["size"]), trades_sell)),
            "time": list(map(lambda trade: trade["createdAt"], trades_sell)),
        },
        "BUY": {
            "price": list(map(lambda trade: float(trade["price"]), trades_buy)),
            "size": list(map(lambda trade: float(trade["size"]), trades_buy)),
            "time": list(map(lambda trade: trade["createdAt"], trades_buy)),
        },
    }

    fig_trades = make_subplots(specs=[[{"secondary_y": True}]])

    fig_trades.add_trace(
        go.Scatter(
            name="price sell",
            x=trades["SELL"]["time"],
            y=trades["SELL"]["price"],
            marker_color="red",
        ),
        secondary_y=False,
    )
    fig_trades.add_trace(
        go.Scatter(
            name="size sell",
            x=trades["SELL"]["time"],
            y=trades["SELL"]["size"],
            marker_color="blue",
        ),
        secondary_y=True,
    )
    fig_trades.add_trace(
        go.Scatter(
            name="price buy",
            x=trades["BUY"]["time"],
            y=trades["BUY"]["price"],
            marker_color="green",
        ),
        secondary_y=False,
    )
    fig_trades.add_trace(
        go.Scatter(
            name="size buy",
            x=trades["BUY"]["time"],
            y=trades["BUY"]["size"],
            marker_color="orange",
        ),
        secondary_y=True,
    )
    fig_trades.update_layout(
        title="Trades on dydx", xaxis_title="time", yaxis_title="price"
    )
    fig_trades.show()


if __name__ == "__main__":
    main()
