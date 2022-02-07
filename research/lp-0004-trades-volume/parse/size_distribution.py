import csv
from collections import deque
from datetime import datetime, timedelta
from sortedcontainers import SortedDict
import plotly.graph_objs as go


class TradesSize:
    trades_window_sec = 60
    punch_window_sec = 30
    punch_round = 5
    data_it = 0
    trades_window = deque()
    punch_window = deque()
    punch_plot = SortedDict()

    def __init__(self, path: str) -> None:
        self.data = list(csv.DictReader(open(path, "r", encoding="utf8")))[:100]
        self.set_trades_window()
        self.set_punch_window()

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def get_new_trade(self) -> dict:
        if self.is_data_left():
            trade = self.data[self.data_it]
            self.data_it += 1
            return trade
        return None

    def is_data_left(self) -> bool:
        return self.data_it < len(self.data)

    def set_trades_window(self) -> None:
        while len(self.trades_window) == 0 or self.get_datetime(
            self.trades_window[-1]["createdAt"]
        ) - self.get_datetime(self.trades_window[0]["createdAt"]) <= timedelta(
            seconds=self.trades_window_sec
        ):
            self.trades_window.append(self.get_new_trade())

    def set_punch_window(self) -> None:
        while len(self.punch_window) == 0 or self.get_datetime(
            self.punch_window[-1]["createdAt"]
        ) - self.get_datetime(self.punch_window[0]["createdAt"]) <= timedelta(
            seconds=self.punch_window_sec
        ):
            self.punch_window.append(self.get_new_trade())

    def update_punch_window(self) -> None:
        if len(self.punch_window):
            self.trades_window.append(self.punch_window[0])
            self.punch_window.popleft()
        while self.is_data_left() and (
            len(self.punch_window) == 0
            or (
                self.get_datetime(self.punch_window[-1]["createdAt"])
                - self.get_datetime(self.punch_window[0]["createdAt"])
            )
            < timedelta(seconds=self.punch_window_sec)
        ):
            self.punch_window.append(self.get_new_trade())

    def update_trades_window(self) -> None:
        while len(self.trades_window) > 0 and self.get_datetime(
            self.trades_window[-1]["createdAt"]
        ) - self.get_datetime(self.trades_window[0]["createdAt"]) > timedelta(
            seconds=self.trades_window_sec
        ):
            self.trades_window.popleft()

    def update_windows(self) -> None:
        self.update_punch_window()
        self.update_trades_window()

    def run(self) -> None:
        while self.data_it < len(self.data):
            self.update_windows()
            if len(self.punch_window) >= 2:
                self.add_result()

    def add_result(self) -> None:
        punch_window_price = list(
            map(lambda trade: float(trade["price"]), self.punch_window)
        )
        punch_pc = round(
            max(punch_window_price) / min(punch_window_price) - 1,
            self.punch_round,
        )
        trades_size = sum(
            map(lambda trade: float(trade["size"]), self.trades_window)
        )
        if punch_pc in self.punch_plot:
            self.punch_plot[punch_pc]["size"] = (
                self.punch_plot[punch_pc]["size"]
                * self.punch_plot[punch_pc]["count"]
                + trades_size
            ) / (self.punch_plot[punch_pc]["count"] + 1)
            self.punch_plot[punch_pc]["count"] += 1
        else:
            self.punch_plot[punch_pc] = {"size": trades_size, "count": 1}

    def plot(self) -> None:
        sizes = list(
            map(lambda x: float(x[1]["size"]), self.punch_plot.items())
        )
        punches = list(map(lambda x: float(x[0]), self.punch_plot.items()))
        plot_data = list(zip(sizes, punches))
        plot_data.sort()
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="punch",
                x=list(map(lambda x: str(x[0]), plot_data)),
                y=list(map(lambda x: float(x[1]), plot_data)),
                marker_color="blue",
            )
        )
        fig.update_layout(
            title=f"Trades distribution by size. Trades {self.trades_window_sec} sec, punches {self.punch_window_sec} sec",
            xaxis_title="size",
            yaxis_title="punch, pc",
        )
        fig.show()


def main():
    ts = TradesSize(
        "../../data/trades/raw/trades_01-08-2021_22-01-2022.csv"
    )
    ts.run()
    ts.plot()


if __name__ == "__main__":
    main()
