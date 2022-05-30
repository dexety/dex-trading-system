from sliding_window import SlidingWindow
import plotly.graph_objs as go
import csv
from datetime import datetime, timedelta
from tqdm import tqdm
from utils.helpful_scripts import string_to_datetime


class ProfitCalculator:
    dydx_commission = 0.0005

    def __init__(self, signal_filename: str, predict_filename: str = "", mode: str = "", signals_dump: str = ""):
        self.signal_filename = signal_filename
        self.predict_filename = predict_filename
        self.signal_threshold = 0.0025
        self.window = 1000  # all time in millisecs
        self.signal_side = "BUY"
        self.latency_us_predict = 500
        self.latency_signal_us = 300
        self.after_signal = 3000
        self.loss_threshold = 0.0015
        self.profit_threshold = 0.0021
        self.after_last_trade = 3000
        self.pos_open = 20000
        self.recover_time = 3000
        self.trades = []
        self.signals = []
        self.signals_stats = []
        self.price_slide = SlidingWindow(self.window)
        self.quantity_slide = SlidingWindow(self.window)
        self.graph = go.Figure()
        self.signal_csv_line_handler = self._binance_csv_line_handler
        self.predict_csv_line_handler = self._dydx_csv_line_handler
        self.mode = mode
        self.signals_dump = signals_dump

    @staticmethod
    def _dydx_csv_line_handler(line: list):
        time = string_to_datetime(line[-1])
        time += timedelta(hours=3)
        price = float(line[2])
        side = "SELL" if line[0] == "SELL" else "BUY"
        return price, time, side

    @staticmethod
    def _binance_csv_line_handler(line: list):
        time = datetime.fromtimestamp(int(line[4]) / 1000)
        price = float(line[1])
        quantity = float(line[2])
        side = "SELL" if line[-1] == "true" else "BUY"
        return time, price, quantity, side

    def _update_window(self, price, quantity, time) -> str:
        self.quantity_slide.push_back(
            quantity, time.timestamp() * 1000
        )
        if self.price_slide.push_back(
                price, time.timestamp() * 1000
        ):
            max_in_window = self.price_slide.get_max()
            max_timestamp = self.price_slide.get_max_timestamp()
            min_in_window = self.price_slide.get_min()
            min_timestamp = self.price_slide.get_min_timestamp()
            if max_in_window / min_in_window >= (
                    1 + self.signal_threshold
            ):
                if max_timestamp > min_timestamp:
                    return "BUY"
                elif max_timestamp < min_timestamp:
                    return "SELL"
        return ""

    def set_signal_params(self,
                          signal_threshold: float = 0.0021,
                          signal_side: str = "BUY",
                          latency_signal_us_millsec: float = 200,
                          ):
        self.signal_threshold = signal_threshold
        self.signal_side = signal_side
        self.latency_signal_us = latency_signal_us_millsec

    def set_signal_csv_line_handler(self, handler: callable):
        self.signal_csv_line_handler = handler

    def get_signals(self):
        with open(self.signal_filename, "r", encoding="utf-8") as signal_file:
            csv_reader = csv.reader(signal_file, delimiter=",")
            try:
                for line in tqdm(csv_reader, desc="get signals"):
                    time, price, quantity, side = self.signal_csv_line_handler(line)
                    time += timedelta(milliseconds=self.latency_signal_us)
                    if side == self.signal_side:
                        direction = self._update_window(price, quantity, time)
                        if direction == "":
                            continue
                        stat = {"max_quantity": self.quantity_slide.get_max(),
                                "jump_time_length":
                                    self.quantity_slide.get_last_trade() - self.quantity_slide.get_first_trade()}
                        self.signals_stats.append(stat)  # TODO : collect stats
                        self.signals.append({"time": time, "direction": direction})
                        self.price_slide.clear()
                        self.quantity_slide.clear()
            except Exception as e:
                return self.signals

        return self.signals

    def show_signals(self):
        self.graph.data = []
        if len(self.signals) == 0:
            self.get_signals()

        self.graph.update_layout(
            title_text=f"Signals, side = {self.signal_side}"
        )
        prices = []
        times = []
        with open(self.signal_filename, "r", encoding="utf-8") as signal_file:
            csv_reader = csv.reader(signal_file, delimiter=",")
            for line in csv_reader:
                time, price, quantity, side = self.signal_csv_line_handler(list(line))
                if side == self.signal_side:
                    prices.append(price)
                    times.append(time)
        self.graph.add_trace(
            go.Scatter(
                name=self.signal_side,
                x=times,
                y=prices,
                marker_color="blue" if self.signal_side == "BUY" else "red",
            )
        )
        for signal in self.signals:
            self.graph.add_vline(x=signal["time"], line_width=3,
                                 line_color="green" if signal["direction"] == "BUY" else "red",
                                 opacity=0.5)
        self.graph.show()

    def _set_trade_params(self, loss_threshold, profit_threshold, pos_open_milsec):
        self.loss_threshold = loss_threshold
        self.profit_threshold = profit_threshold
        self.pos_open = pos_open_milsec

    @staticmethod
    def _get_trade_params(signal_stats: dict, predict_model: callable):
        return predict_model(signal_stats)

    def _stupid_model(signal_stats: dict):
        # a = random.choice([0.0008, 0.001, 0.0012])
        # b = random.choice([0.0018, 0.002, 0.0022, 0.0024])
        # c = random.choice([10000, 15000, 20000])
        return 0.0011, 0.0013, 20000

    def set_predict_csv_line_handler(self, handler: callable):
        self.predict_csv_line_handler = handler

    def _detect_threshold(self, open_price: float, close_price: float, side: str):
        jmp = close_price / open_price if side == "BUY" else open_price / close_price
        if jmp >= 1 + self.profit_threshold:
            return "profit"
        if jmp <= 1 - self.loss_threshold:
            return "loss"
        return ""

    def _check_trades(self):
        for i in range(0, len(self.trades), 2):
            if self.trades[i]["side"] == self.trades[i + 1]["side"]:
                raise RuntimeError("Trade search algorithm is not working correctly, call the person who did it")

    @staticmethod
    def _opp_side(side: str):
        return "SELL" if side == "BUY" else "BUY"

    def load_signals(self):
        with open(self.signals_dump, "r", encoding="utf-8") as file:
            csv_reader = csv.reader(file)
            for line in tqdm(csv_reader, desc="load signals from file", total=len(self.signals)):
                time = string_to_datetime(line[0])
                direction = line[1]
                self.signals.append({"time": time, "direction": direction})
                self.signals_stats.append(None)  # TODO : collect stats

    def get_trades(self, predict_model: callable = _stupid_model):
        if len(self.signals) == 0:
            if self.mode == "sig_dump":
                self.load_signals()
            else:
                self.get_signals()

        with open(self.predict_filename, "r") as predict_file:
            csv_reader = csv.reader(predict_file, delimiter=",")
            sig_num = 0

            for line in tqdm(csv_reader, desc="get trades"):
                # while self.signals_stats[sig_num]["max_quantity"] >= 1200 \
                #         or self.signals_stats[sig_num]["jump_time_length"] <= 100:
                #     sig_num += 1
                #     if sig_num >= len(self.signals):
                #         self._check_trades()
                #         return self.trades
                price, time, side = self.predict_csv_line_handler(line)
                while side != self.signals[sig_num]["direction"] or\
                        time <= self.signals[sig_num]["time"] + timedelta(milliseconds=self.latency_us_predict):
                    try:
                        price, time, side = self.predict_csv_line_handler(next(csv_reader))
                    except StopIteration:
                        self._check_trades()
                        return self.trades
                self._set_trade_params(*self._get_trade_params(self.signals_stats[0], predict_model))
                open_trade = {"time": time, "side": side, "price": price}
                detector = self._detect_threshold(open_trade["price"], price, open_trade["side"])
                while (detector == "" or time <= open_trade["time"] + timedelta(milliseconds=300)) \
                        or side != self._opp_side(open_trade["side"]):
                    try:
                        price, time, side = self.predict_csv_line_handler(next(csv_reader))
                    except StopIteration:
                        self._check_trades()
                        return self.trades
                    detector = self._detect_threshold(open_trade["price"], price, open_trade["side"])
                    if time >= open_trade["time"] + timedelta(milliseconds=self.pos_open):
                        while side != self._opp_side(open_trade["side"]):
                            try:
                                price, time, side = self.predict_csv_line_handler(next(csv_reader))
                            except StopIteration:
                                self._check_trades()
                                return self.trades
                        detector = "timeout"
                        break
                open_trade["reason"] = detector
                close_trade = {"time": time, "side": side, "price": price, "reason": detector}
                self.trades.append(open_trade)
                self.trades.append(close_trade)

                last_trade_time = close_trade["time"]
                sig_num += 1
                if sig_num >= len(self.signals):
                    break
                while self.signals[sig_num]["time"] < last_trade_time + timedelta(milliseconds=self.recover_time):
                    sig_num += 1
                    if sig_num >= len(self.signals):
                        self._check_trades()
                        return self.trades

        self._check_trades()
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

        with open(self.predict_filename, "r", encoding="utf-8") as predict_file:
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

        total_profit, profits = self.get_profit()

        self.graph.update_layout(title_text=f"Signal trades | Amount of trades : {len(self.trades)} |"
                                            f" Total profit : {total_profit:.6f}")

        for i in tqdm(range(0, len(self.trades), 2), desc="draw trades"):
            self.graph.add_vrect(
                x0=self.trades[i]["time"],
                x1=self.trades[i + 1]["time"],
                row="all",
                col=1,
                annotation_text="Profit = " + "{:.6f}<br>".format(profits[i // 2]) +
                                f"Open price = {self.trades[i]['price']}<br>"
                                f"Close price = {self.trades[i + 1]['price']}<br>"
                                f"Close reason : {self.trades[i + 1]['reason']}",
                annotation_position="top left",
                fillcolor="green" if self.trades[i]["side"] == "BUY" else "red",
                opacity=0.5,
                line_width=1,
            )

        for signal in self.signals:
            self.graph.add_vline(x=signal["time"], line_width=3,
                                 line_color="green" if signal["direction"] == "BUY" else "red",
                                 opacity=0.5)
        self.graph.show()

    def get_profit(self):
        if len(self.trades) == 0:
            self.get_trades()

        profits = []
        usd = 100
        for i in tqdm(range(0, len(self.trades), 2), desc="calculate profit"):
            new_usd = usd * (1 - self.dydx_commission) ** 2
            if self.trades[i]["side"] == "BUY":
                jmp = self.trades[i + 1]["price"] / self.trades[i]["price"]
            else:
                jmp = self.trades[i]["price"] / self.trades[i + 1]["price"]
            new_usd *= jmp
            profits.append((new_usd / usd - 1) * 100)
            usd = new_usd

        total_profit = usd - 100

        return total_profit, profits

    def reset(self, new_signal_filename: str, new_predict_filename: str):
        self.signal_filename = new_signal_filename
        self.predict_filename = new_predict_filename
        self.trades.clear()
        self.signals.clear()
        self.signals_stats.clear()
        self.price_slide.clear()
        self.graph.data = []

    def dump_signals(self, filename: str):
        if len(self.signals) == 0:
            self.get_signals()

        with open(filename, "w+", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            for signal in tqdm(self.signals, desc="dump signals", total=len(self.signals)):
                csv_writer.writerow([signal["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"), signal["direction"]])

    def dump_trades(self, filename: str):
        if len(self.trades) == 0:
            self.get_trades()

        with open(filename, "w+", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            for trade in tqdm(self.trades, desc="dump trades", total=len(self.trades)):
                csv_writer.writerow([trade["side"], trade["price"],
                                     trade["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"), trade["reason"]])
