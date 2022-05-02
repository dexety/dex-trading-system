from sliding_window import SlidingWindow
import plotly.graph_objs as go
import csv
from datetime import datetime, timedelta
from tqdm import tqdm
from utils.helpful_scripts import string_to_datetime


class SignalsGiver:
    def __init__(self,
                 signal_threshold: float = 0.0021,
                 window_millisec: int = 1000,
                 side: str = "BUY",
                 latency_millisec: int = 300,
                 mode: str = "file",
                 **kwargs):

        self.mode = mode
        self.trades_file: str = ""
        self.trades_list: list = []
        if mode == "file":
            self.trades_file = kwargs["filename"]
        elif mode == "list":
            self.trades_list = kwargs["trades_list"]
        else:
            raise KeyError("Bad mode")

        self.signal_threshold = 0.0021
        self.window = 1000  # all time in millisecs
        self.signal_side = "BUY"
        self.latency_us_predict = 0
        self.latency_signal_us = 300
        self.after_signal = 20000
        self.recover_time = 3000

        self.signals: list = []
        self.signals_stats: list = []

        self.slide = SlidingWindow(self.window)
        self.graph = go.Figure()

        self.signal_csv_line_handler: callable = self._binance_csv_line_handler

    @staticmethod
    def _binance_csv_line_handler(line: list):
        time = datetime.fromtimestamp(int(line[4]) / 1000)
        price = float(line[1])
        side = "SELL" if line[-1] == "true" else "BUY"
        return price, time, side

    def _update_window(self, price, time) -> str:
        if self.slide.push_back(
                price, time.timestamp() * 1000
        ):
            max_in_window = self.slide.get_max()
            max_timestamp = self.slide.get_max_timestamp()
            min_in_window = self.slide.get_min()
            min_timestamp = self.slide.get_min_timestamp()
            if max_in_window / min_in_window >= (
                    1 + self.signal_threshold
            ):
                if max_timestamp > min_timestamp:
                    return "BUY"
                elif max_timestamp < min_timestamp:
                    return "SELL"
        return ""

    def _get_signals_from_iterable(self, iterable: iter):
        for line in tqdm(iterable, desc="get signals"):
            price, time, side = self.signal_csv_line_handler(line)
            time += timedelta(milliseconds=self.latency_signal_us)
            if side == self.signal_side:
                direction = self._update_window(price, time)
                if direction == "":
                    continue
                self.signals_stats.append(None)  # TODO : collect stats
                self.signals.append({"time": time, "direction": direction})
                self.slide.clear()
        return self.signals

    def get_signals(self):
        if self.mode == "file":
            with open(self.trades_file, "r", encoding="utf-8") as signal_file:
                csv_reader = csv.reader(signal_file, delimiter=",")
                return self._get_signals_from_iterable(csv_reader)
        elif self.mode == "list":
            return self._get_signals_from_iterable(self.trades_list)

    def show_signals(self):
        self.graph.data = []
        if len(self.signals) == 0:
            self.get_signals()

        self.graph.update_layout(
            title_text=f"Signals, side = {self.signal_side}"
        )
        prices = []
        times = []
        with open(self.trades_file, "r", encoding="utf-8") as signal_file:
            csv_reader = csv.reader(signal_file, delimiter=",")
            for line in csv_reader:
                price, time, side = self.signal_csv_line_handler(list(line))
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

    def dump_signals(self, filename: str):
        if len(self.signals) == 0:
            self.get_signals()

        with open(filename, "w+", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            for signal in tqdm(self.signals, desc="dump signals", total=len(self.signals)):
                csv_writer.writerow([signal["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"), signal["direction"]])
