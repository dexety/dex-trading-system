import plotly.graph_objs as go
from trades_handler import TradesHandler
import csv
from datetime import datetime, timedelta
from tqdm import tqdm
import json


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

        self.signal_side = "BUY"
        self.latency_signal_us = 300

        self.trades_handler = TradesHandler()
        self.graph = go.Figure()

        self.signal_csv_line_handler: callable = self._binance_csv_line_handler

    @staticmethod
    def _binance_csv_line_handler(line: list):
        time = datetime.fromtimestamp(int(line[4]) / 1000)
        price = float(line[1])
        quantity = float(line[2])
        side = "SELL" if line[-1] == "true" else "BUY"
        return time, price, quantity, side

    def _get_signals_from_iterable(self, iterable: iter):
        for line in tqdm(iterable, desc="get signals"):
            time, price, quantity, side = self.signal_csv_line_handler(line)
            time += timedelta(milliseconds=self.latency_signal_us)
            if side == self.signal_side:
                self.trades_handler.handle(time, price, quantity)
        return self.trades_handler.signals

    def get_signals(self):
        if self.mode == "file":
            with open(self.trades_file, "r", encoding="utf-8") as signal_file:
                csv_reader = csv.reader(signal_file, delimiter=",")
                return self._get_signals_from_iterable(csv_reader)
        elif self.mode == "list":
            return self._get_signals_from_iterable(self.trades_list)

    def show_signals(self):
        self.graph.data = []
        if len(self.trades_handler.signals) == 0:
            self.get_signals()

        self.graph.update_layout(
            title_text=f"Signals, side = {self.signal_side}"
        )
        prices = []
        times = []
        with open(self.trades_file, "r", encoding="utf-8") as signal_file:
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
        for signal in self.trades_handler.signals:
            self.graph.add_vline(x=signal["time"], line_width=3,
                                 line_color="green" if signal["direction"] == "BUY" else "red",
                                 opacity=0.5)
        self.graph.show()

    def dump_signals(self, filename: str):
        if len(self.trades_handler.signals) == 0:
            self.get_signals()

        with open(filename, "w+", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            for signal in tqdm(self.trades_handler.signals, desc="dump signals", total=len(self.trades_handler.signals)):
                csv_writer.writerow([signal["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"), signal["direction"]])

    def dump_stats(self, filename: str):
        if len(self.trades_handler.signals) == 0:
            self.get_signals()

        with open(filename, "w+", encoding="utf-8") as file:
            json.dump(self.trades_handler.stats, file, indent=4)



