from sliding_window import SlidingWindow
import plotly.graph_objs as go
import csv
from datetime import datetime, timedelta
from tqdm import tqdm
from utils.helpful_scripts import string_to_datetime


class BestParamsGiver:
    dydx_commission = 0.0005

    def __init__(self, signals, filename):
        self.signals = signals
        self.filename = filename
        self.predict_csv_line_handler = self._dydx_csv_line_handler
        self.latency_us_predict = 600
        self.graph = go.Figure()
        self.total_usd = 0
        self.trades = []

    @staticmethod
    def _dydx_csv_line_handler(line: list):
        time = string_to_datetime(line[-1])
        time += timedelta(hours=3)
        price = float(line[2])
        side = "SELL" if line[0] == "SELL" else "BUY"
        return price, time, side

    def get_trades(self):
        f = open(self.filename, "r")
        raw_trades = f.readlines()
        f.close()

        usd = 100

        i = 0
        sig_num = 0
        while i < len(raw_trades) and sig_num < len(self.signals):
            price, time, side = self.predict_csv_line_handler(raw_trades[i].strip("\n").split(','))
            while time <= self.signals[sig_num]["time"] + timedelta(milliseconds=self.latency_us_predict) or \
                    side != self.signals[sig_num]["direction"]:
                i += 1
                price, time, side = self.predict_csv_line_handler(raw_trades[i].strip("\n").split(','))
            open_trade = {"time": time, "side": side, "price": price}
            i += 1
            tmp = i
            while time <= open_trade["time"] + timedelta(milliseconds=300):
                tmp += 1
                price, time, side = self.predict_csv_line_handler(raw_trades[tmp].strip("\n").split(','))

            top_buy = {"price": -1, "time": datetime.now()}
            low_buy = {"price": 10 ** 9, "time": datetime.now()}
            top_sell = {"price": -1, "time": datetime.now()}
            low_sell = {"price": 10 ** 9, "time": datetime.now()}
            while time <= open_trade["time"] + timedelta(seconds=20) or top_sell["price"] == -1 or top_buy["price"] == -1:
                if side == "BUY":
                    if top_buy["price"] < price:
                        top_buy["price"] = price
                        top_buy["time"] = time
                    if low_buy["price"] > price:
                        low_buy["price"] = price
                        low_buy["time"] = time
                else:
                    if top_sell["price"] < price:
                        top_sell["price"] = price
                        top_sell["time"] = time
                    if low_sell["price"] > price:
                        low_sell["price"] = price
                        low_sell["time"] = time
                tmp += 1
                price, time, side = self.predict_csv_line_handler(raw_trades[tmp].strip("\n").split(','))

            best_params = {"profit_threshold": -1, "loss_threshold": -1, "has_profit": 0, "profit": 0}
            close_trade = {"time": datetime.now(), "side": "", "price": -1}
            if open_trade["side"] == "BUY":
                jmp_up = top_sell["price"] / open_trade["price"]
                jmp_down = low_sell["price"] / open_trade["price"]
                if jmp_up * (1 - self.dydx_commission) ** 2 > 1:
                    best_params["has_profit"] = 1

                print(f"top sell : {top_sell['price']}")
                print(f"jmp_up : {jmp_up}")
                usd *= jmp_up * (1 - self.dydx_commission) ** 2
                print(f"usd : {usd}")
                best_params["profit"] = jmp_up * (1 - self.dydx_commission) ** 2 - 1

                if jmp_up > 1 and jmp_down > 1:
                    best_params["profit_threshold"] = jmp_up - 1
                    best_params["loss_threshold"] = 0.001
                elif jmp_up > 1 and jmp_down < 1:
                    best_params["profit_threshold"] = jmp_up - 1
                    best_params["loss_threshold"] = 1 - jmp_down
                elif jmp_up <= 1 and jmp_down <= 1:
                    best_params["profit_threshold"] = 0
                    best_params["loss_threshold"] = 1 - jmp_up

                close_trade["time"] = top_sell["time"]
                close_trade["price"] = top_sell["price"]
                close_trade["side"] = "SELL"
            else:
                jmp_up = open_trade["price"] / low_buy["price"]
                jmp_down = open_trade["price"] / top_buy["price"]
                if jmp_up * (1 - self.dydx_commission) ** 2 > 1:
                    best_params["has_profit"] = 1

                print(f"low buy : {low_buy['price']}")
                print(f"jmp_up : {jmp_up}")
                usd *= jmp_up * (1 - self.dydx_commission) ** 2
                print(f"usd : {usd}")

                best_params["profit"] = jmp_up * (1 - self.dydx_commission) ** 2 - 1

                if jmp_up > 1 and jmp_down > 1:
                    best_params["profit_threshold"] = jmp_up - 1
                    best_params["loss_threshold"] = 0.001
                elif jmp_up > 1 and jmp_down < 1:
                    best_params["profit_threshold"] = jmp_up - 1
                    best_params["loss_threshold"] = 1 - jmp_down
                elif jmp_up <= 1 and jmp_down <= 1:
                    best_params["profit_threshold"] = 0
                    best_params["loss_threshold"] = 1 - jmp_up

                close_trade["time"] = low_buy["time"]
                close_trade["price"] = low_buy["price"]
                close_trade["side"] = "BUY"

            open_trade["time"] = open_trade["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            close_trade["time"] = close_trade["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            trade = {"open_trade": open_trade, "close_trade": close_trade, "best_params": best_params}
            self.trades.append(trade)
            sig_num += 1

        self.total_usd = usd
        return self.trades

    def show_trades(self):
        self.graph.data = []
        if len(self.trades) == 0:
            self.get_trades()

        all_trades = dict()
        for side in ["BUY", "SELL"]:
            all_trades[side] = dict()
            for kek in ["price", "time"]:
                all_trades[side][kek] = []

        with open(self.filename, "r", encoding="utf-8") as predict_file:
            csv_reader = csv.reader(predict_file, delimiter=",")
            for line in tqdm(csv_reader, desc="reading file to show trades"):
                price, time, side = self.predict_csv_line_handler(line)
                all_trades[side]["time"].append(time)
                all_trades[side]["price"].append(price)

        for side in ["BUY", "SELL"]:
            self.graph.add_trace(
                go.Scatter(
                    name=side,
                    x=all_trades[side]["time"],
                    y=all_trades[side]["price"],
                    marker_color="blue" if side == "BUY" else "red",
                )
            )

        # total_profit, profits = self.get_profit()
        #
        # self.graph.update_layout(title_text=f"Signal trades | Amount of trades : {len(self.trades)} |"
        #                                     f" Total profit : {total_profit:.6f}")

        for i in tqdm(range(0, len(self.trades)), desc="draw trades"):
            self.graph.add_vrect(
                x0=self.trades[i]["open_trade"]["time"],
                x1=self.trades[i]["close_trade"]["time"],
                row="all",
                col=1,
                annotation_text=f"Open price = {self.trades[i]['open_trade']['price']}<br>"
                                f"Close price = {self.trades[i]['close_trade']['price']}<br>"
                                f"Profit = {self.trades[i]['best_params']['profit']}<br>"
                                f"Loss threshold = {self.trades[i]['best_params']['loss_threshold']}<br>"
                                f"Profit threshold = {self.trades[i]['best_params']['profit_threshold']}<br>",
                annotation_position="top left",
                fillcolor="green" if self.trades[i]["open_trade"]["side"] == "BUY" else "red",
                opacity=0.5,
                line_width=1,
            )

        for signal in self.signals:
            self.graph.add_vline(x=signal["time"], line_width=3,
                                 line_color="green" if signal["direction"] == "BUY" else "red",
                                 opacity=0.5)
        self.graph.show()
