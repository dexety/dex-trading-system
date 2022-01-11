import json
import plotly.express as px
import plotly.graph_objects as go

from datetime import timedelta
import datetime

# {'size': 0.001, 'side': 'SELL', 'price': 61729.0, 'createdAt': '2021-10-28T20:45:42.374Z',
# 'exchange': 'dydx', 'symbol': 'BTC-USD', 'recieveTime': '2021-10-28T20:45:42.455387Z'}

# {'side': 'BUY', 'size': 1.0, 'price': 198.685, 'createdAt': '2021-10-28T23:45:43.273000Z',
# 'exchange': 'binance', 'symbol': 'SOLUSDT', 'recieveTime': '2021-10-28T23:45:43.419046Z'}

dydx_df = {"x1": [], "x2": [], "y": []}

binance_df = {"x1": [], "x2": [], "y": []}

file = open("archive_trades", "r", encoding="utf8")

for line in file:
    line = json.loads(line.replace("'", '"'))
    if line["exchange"] == "dydx":
        dydx_df["x1"].append(line["recieveTime"])
        dydx_df["x2"].append(
            datetime.datetime.strptime(
                line["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            + timedelta(hours=3)
        )
        dydx_df["y"].append(line["price"])
    elif line["exchange"] == "binance":
        binance_df["x1"].append(line["recieveTime"])
        binance_df["x2"].append(line["createdAt"])
        binance_df["y"].append(line["price"])

fig1 = go.Figure()
fig1.add_trace(
    go.Scatter(x=binance_df["x1"], y=binance_df["y"], name="binance")
)
fig1.add_trace(go.Scatter(x=dydx_df["x2"], y=dydx_df["y"], name="dydx"))
fig1.update_layout(title="BTC/USDT", xaxis_title="Date", yaxis_title="Price")
fig1.show()

# fig2 = go.Figure()
# fig2.add_trace(go.Scatter(x=binance_df['x2'], y=binance_df['y'], name='binance'))
# fig2.add_trace(go.Scatter(x=dydx_df['x2'], y=dydx_df['y'], name='dydx'))
# fig2.update_layout(title="BTC/USDT", xaxis_title="Date", yaxis_title="Price")
# fig2.show()
