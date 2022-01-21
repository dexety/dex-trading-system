import json
import csv
import sys
from collections import deque
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm


class Indicators:
    @staticmethod
    def get_all_indicators():
        return {
            "trade-volume": lambda window: Indicators.trade_volume(window),
            "moving-average": lambda window: Indicators.moving_average(window),
            "weighted-moving-average": (
                lambda window: Indicators.weighted_moving_average(window)
            ),
            "exp-moving-average": (
                lambda window: Indicators.exp_moving_average(window)
            ),
            "stochastic-oscillator": (
                lambda window: Indicators.stochastic_oscillator(window)
            ),
        }

    @staticmethod
    def exp_moving_average(window, alpha=0.5) -> float:
        if not window:
            return 0
        ema = float(window[0]["price"])
        for i in range(1, len(window)):
            ema = ema + alpha * (float(window[i]["price"]) - ema)
        return ema

    @staticmethod
    def trade_volume(window) -> float:
        if not window:
            return 0
        return sum(map(lambda trade: float(trade["size"]), window))

    @staticmethod
    def moving_average(window) -> float:
        if not window:
            return 0
        return sum(map(lambda trade: float(trade["price"]), window)) / len(
            window
        )

    @staticmethod
    def weighted_moving_average(window) -> float:
        if not window:
            return 0
        return (
            sum(
                map(
                    lambda trade: float(trade["price"]) * float(trade["size"]),
                    window,
                )
            )
            / sum(map(lambda trade: float(trade["size"]), window))
        )

    @staticmethod
    def stochastic_oscillator(window) -> float:
        if not window:
            return 0
        return (
            float(window[-1]["price"])
            - float(
                min(window, key=lambda trade: float(trade["price"]))["price"]
            )
        ) / (
            max(
                1,
                float(
                    max(window, key=lambda trade: float(trade["price"]))[
                        "price"
                    ]
                )
                - float(
                    min(window, key=lambda trade: float(trade["price"]))[
                        "price"
                    ]
                ),
            )
        )


class DataParser:
    punch_threashold = 0.0001
    trades_window_sec = 60
    trades_window_timestamps_num = 10
    punch_window_sec = 30
    random_data_pc = 0.005
    SIDES = ["BUY", "SELL"]

    indicator_functions = Indicators.get_all_indicators()

    def __init__(
        self,
        input_path: str,
        output_path: str,
        current_thread_num: int,
        max_thread_num: int,
    ) -> None:
        self.data = json.load(open(input_path, "r", encoding="utf8"))
        self.data_it = len(self.data) // max_thread_num * current_thread_num
        self.data_it_max = (
            len(self.data) // max_thread_num * (current_thread_num + 1)
        )
        self.input_path = input_path
        self.output_path = output_path
        self.trades_window = {"BUY": deque(), "SELL": deque()}
        self.punch_window = {"BUY": deque(), "SELL": deque()}
        self.output_data = []
        self.progress_bar = tqdm(range(self.data_it_max - self.data_it))

        self.init_windows()

    def init_windows(self) -> None:
        self.set_trades_window()
        self.set_punch_window()

    def reset_windows(self) -> None:
        self.trades_window = {"BUY": deque(), "SELL": deque()}
        self.punch_window = {"BUY": deque(), "SELL": deque()}

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def get_new_trade(self) -> dict:
        self.progress_bar.update()
        if self.is_data_left():
            trade = self.data[self.data_it]
            self.data_it += 1
            return trade
        return None

    def is_data_left(self) -> bool:
        return self.data_it < self.data_it_max

    def get_max_item_from_window(self, window: dict) -> dict:
        if window["BUY"] and window["SELL"]:
            if self.get_datetime(
                window["BUY"][-1]["createdAt"]
            ) > self.get_datetime(window["SELL"][-1]["createdAt"]):
                return window["BUY"][-1]
            else:
                return window["SELL"][-1]
        if window["BUY"]:
            return window["BUY"][-1]
        if window["SELL"]:
            return window["SELL"][-1]
        return None

    def get_max_item_time_from_window(self, window: dict) -> datetime:
        trade = self.get_max_item_from_window(window)
        if trade:
            return self.get_datetime(trade["createdAt"])
        return None

    def get_min_item_from_window(self, window: dict) -> dict:
        if window["BUY"] and window["SELL"]:
            if self.get_datetime(
                window["BUY"][0]["createdAt"]
            ) < self.get_datetime(window["SELL"][0]["createdAt"]):
                return window["BUY"][0]
            else:
                return window["SELL"][0]
        if window["BUY"]:
            return window["BUY"][0]
        if window["SELL"]:
            return window["SELL"][0]
        return None

    def get_min_item_time_from_window(self, window: dict) -> datetime:
        trade = self.get_min_item_from_window(window)
        if trade:
            return self.get_datetime(trade["createdAt"])
        return None

    def non_empty_window(self, window: dict) -> bool:
        return self.get_max_item_time_from_window(
            window
        ) or self.get_max_item_time_from_window(window)

    def set_trades_window(self) -> None:
        while not self.non_empty_window(
            self.trades_window
        ) or self.get_max_item_time_from_window(
            self.trades_window
        ) - self.get_min_item_time_from_window(
            self.trades_window
        ) <= timedelta(
            seconds=self.trades_window_sec
        ):
            new_trade = self.get_new_trade()
            if not new_trade:
                return
            self.trades_window[new_trade["side"]].append(new_trade)

    def set_punch_window(self) -> None:
        while not self.non_empty_window(
            self.punch_window
        ) or self.get_max_item_time_from_window(
            self.punch_window
        ) - self.get_min_item_time_from_window(
            self.punch_window
        ) <= timedelta(
            seconds=self.punch_window_sec
        ):
            new_trade = self.get_new_trade()
            if not new_trade:
                return
            self.punch_window[new_trade["side"]].append(new_trade)

    def update_punch_window(self) -> None:
        if self.get_min_item_from_window(self.punch_window):
            self.trades_window[
                self.get_min_item_from_window(self.punch_window)["side"]
            ].append(self.get_min_item_from_window(self.punch_window))
            self.punch_window[
                self.get_min_item_from_window(self.punch_window)["side"]
            ].popleft()
        while self.is_data_left() and (
            not self.non_empty_window(self.punch_window)
            or (
                self.get_max_item_time_from_window(self.punch_window)
                - self.get_min_item_time_from_window(self.punch_window)
            )
            < timedelta(seconds=self.punch_window_sec)
        ):
            new_trade = self.get_new_trade()
            if not new_trade:
                return
            self.punch_window[new_trade["side"]].append(new_trade)

    def update_trades_window(self) -> None:
        for side in self.SIDES:
            while (self.trades_window[side]) and self.get_datetime(
                self.trades_window[side][-1]["createdAt"]
            ) - self.get_datetime(
                self.trades_window[side][0]["createdAt"]
            ) > timedelta(
                seconds=self.trades_window_sec
            ):
                self.trades_window[side].popleft()

    def update_windows(self) -> None:
        self.update_punch_window()
        self.update_trades_window()

    def add_result(self) -> None:
        update = dict()
        max_punch = 0

        for side in self.SIDES:
            for window_sec in range(
                self.trades_window_sec // self.trades_window_timestamps_num,
                self.trades_window_sec + 1,
                self.trades_window_sec // self.trades_window_timestamps_num,
            ):
                window_slice = list(
                    filter(
                        lambda trade: self.get_datetime(
                            self.trades_window[side][-1]["createdAt"]
                        )
                        - self.get_datetime(trade["createdAt"])
                        <= timedelta(seconds=window_sec),
                        self.trades_window[side],
                    )
                )

                for indicator_name in self.indicator_functions:
                    column_name = (
                        indicator_name
                        + "-"
                        + side
                        + "-"
                        + str(window_sec)
                        + "-sec"
                    )
                    update[column_name] = self.indicator_functions[
                        indicator_name
                    ](window_slice)

            update[
                "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
            ] = (
                (
                    (
                        1
                        - float(
                            max(
                                self.punch_window[side],
                                key=lambda trade: trade["price"],
                            )["price"]
                        )
                        / float(
                            min(
                                self.punch_window[side],
                                key=lambda trade: trade["price"],
                            )["price"]
                        )
                    )
                    * (1 if side == "SELL" else -1)
                )
                if self.punch_window[side]
                else 0
            )
            max_punch = max(
                max_punch,
                update[
                    "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
                ],
            )

        if (
            max_punch > self.punch_threashold
            or np.random.random() < self.random_data_pc
        ):
            self.output_data.append(update)
            self.reset_windows()
            self.init_windows()

    def write_data(self) -> None:
        field_names = list(self.output_data[0].keys())
        with open(self.output_path, "w") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(self.output_data)

    def run_and_write(self) -> None:
        while self.data_it < self.data_it_max:
            self.update_windows()
            if len(self.punch_window) >= 2:
                self.add_result()
        self.write_data()


def main():
    input_path = (
        "../../data/trades/raw/trades-2021_11_1_0_0_0-2021_12_21_0_0_0.json"
    )
    output_path = (
        f"trades-df-2021_11_1_0_0_0-2021_12_21_0_0_0-{sys.argv[1]}.csv"
    )
    dp = DataParser(input_path, output_path, int(sys.argv[1]), int(sys.argv[2]))
    dp.run_and_write()


if __name__ == "__main__":
    main()
