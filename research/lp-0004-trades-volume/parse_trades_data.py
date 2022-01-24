import json
import csv
import sys
from collections import deque
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm


class WindowIndicators:
    @staticmethod
    def get_all_indicators():
        return {
            "trade-amount": lambda window: WindowIndicators.trade_amount(
                window
            ),
            "trade-volume": lambda window: WindowIndicators.trade_volume(
                window
            ),
            "open-close-diff": lambda window: WindowIndicators.open_close_diff(
                window
            ),
            "moving-average": lambda window: WindowIndicators.moving_average(
                window
            ),
            "weighted-moving-average": (
                lambda window: WindowIndicators.weighted_moving_average(window)
            ),
            "exp-moving-average": (
                lambda window: WindowIndicators.exp_moving_average(window)
            ),
            "stochastic-oscillator": (
                lambda window: WindowIndicators.stochastic_oscillator(window)
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
    def trade_amount(window) -> float:
        return len(window)

    @staticmethod
    def trade_volume(window) -> float:
        if not window:
            return 0
        return sum(map(lambda trade: float(trade["size"]), window))

    @staticmethod
    def open_close_diff(window) -> float:
        if not window:
            return 0
        return float(window[-1]["price"]) / float(window[0]["price"])

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
    punch_threashold = 0.0002
    trades_window_slices_sec = [600, 60, 30, 10, 5, 1]
    trades_window_sec = 600
    punch_window_sec = 30
    random_data_pc = 0.005
    SIDES = ["BUY", "SELL"]
    indicator_functions = WindowIndicators.get_all_indicators()

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

    def reset_windows_after_punch(self) -> None:
        punch_window_head_time = self.get_min_item_time_from_window(
            self.punch_window
        )
        while self.get_min_item_time_from_window(
            self.punch_window
        ) - punch_window_head_time < timedelta(seconds=self.punch_window_sec):
            self.update_punch_window()

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def get_new_trade(self) -> dict:
        self.progress_bar.update()
        if self.data_it < self.data_it_max:
            trade = self.data[self.data_it]
            self.data_it += 1
            return trade
        return None

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

    def is_window_empty(self, window: dict) -> bool:
        return not (
            self.get_max_item_time_from_window(window)
            or self.get_max_item_time_from_window(window)
        )

    def set_trades_window(self) -> None:
        while self.is_window_empty(
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
        while self.is_window_empty(
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
        while self.data_it < self.data_it_max and (
            self.is_window_empty(self.punch_window)
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

    def get_max_price(self, window: dict, side: str) -> float:
        return float(
            max(
                window[side],
                key=lambda trade: trade["price"],
            )["price"]
        )

    def add_result(self) -> None:
        if not self.trades_window['BUY'] or not self.trades_window['SELL']:
            return
        
        update = dict()
        max_punch = 0

        current_trade_dt = self.get_datetime(
            self.data[self.data_it]["createdAt"]
        )

    def get_min_price(self, window: dict, side: str) -> float:
        return float(
            min(
                window[side],
                key=lambda trade: trade["price"],
            )["price"]
        )

    def calculate_indicators(self, update: dict) -> None:
        for side in self.SIDES:
            for n_trades_ago in [1, 10, 50, 100, 1000]:
                diff = (
                    self.get_datetime(self.data[self.data_it]["createdAt"])
                    - self.get_datetime(
                        self.data[max(0, self.data_it - n_trades_ago)][
                            "createdAt"
                        ]
                    )
                ).total_seconds()
                update[
                    "seconds-since-" + str(n_trades_ago) + "-trades-ago-" + side
                ] = diff
            for window_slice_sec in self.trades_window_slices_sec:
                window_slice = list(
                    filter(
                        lambda trade: self.get_datetime(
                            self.trades_window[side][-1]["createdAt"]
                        )
                        - self.get_datetime(trade["createdAt"])
                        <= timedelta(seconds=window_slice_sec),
                        self.trades_window[side],
                    )
                )

                for indicator_name in self.indicator_functions:
                    column_name = (
                        indicator_name
                        + "-"
                        + side
                        + "-"
                        + str(window_slice_sec)
                        + "-sec"
                    )
                    update[column_name] = self.indicator_functions[
                        indicator_name
                    ](window_slice)

    def calculate_punches(self, update, side) -> None:
        if side == "BUY" and self.punch_window["SELL"]:
            update[
                "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
            ] = max(
                0,
                1
                - self.get_max_price(self.punch_window, "SELL")
                / float(self.trades_window["BUY"][-1]["price"]),
            )
        elif side == "SELL" and self.punch_window["BUY"]:
            update[
                "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
            ] = min(
                0,
                1
                - self.get_min_price(self.punch_window, "BUY")
                / float(self.trades_window["SELL"][-1]["price"]),
            )
        else:
            update[
                "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
            ] = 0

    def add_result(self) -> None:
        if not self.trades_window["BUY"] or not self.trades_window["SELL"]:
            return

        update = {}
        max_punch = 0

        for side in self.SIDES:
            self.calculate_punches(update, side)
            max_punch = max(
                max_punch,
                update[
                    "punch-" + side + "-" + str(self.punch_window_sec) + "-sec"
                ],
                key=abs,
            )

        if (
            abs(max_punch) > self.punch_threashold
            or np.random.random() < self.random_data_pc
        ):

            current_trade_dt = self.get_datetime(
                self.data[self.data_it]["createdAt"]
            )
            midnight = current_trade_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            update["seconds-since-midnight"] = (current_trade_dt - midnight).seconds

            for side in self.SIDES:
                for n_trades_ago in [1, 10, 50, 100, 1000]:
                    diff = (
                        self.get_datetime(self.data[self.data_it]["createdAt"])
                        - self.get_datetime(
                            self.data[max(0, self.data_it - n_trades_ago)][
                                "createdAt"
                            ]
                        )
                    ).total_seconds()
                    update[
                        "seconds-since-" + str(n_trades_ago) + "-trades-ago-" + side
                    ] = diff
                for window_slice_sec in self.trades_window_slices_sec:
                    window_slice = list(
                        filter(
                            lambda trade: self.get_datetime(
                                self.trades_window[side][-1]["createdAt"]
                            )
                            - self.get_datetime(trade["createdAt"])
                            <= timedelta(seconds=window_slice_sec),
                            self.trades_window[side],
                        )
                    )

                    for indicator_name in self.indicator_functions:
                        column_name = (
                            indicator_name
                            + "-"
                            + side
                            + "-"
                            + str(window_slice_sec)
                            + "-sec"
                        )
                        update[column_name] = self.indicator_functions[
                            indicator_name
                        ](window_slice)

            current_trade_dt = self.get_datetime(
                self.data[self.data_it]["createdAt"]
            )
            midnight = current_trade_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            update["seconds-since-midnight"] = (
                current_trade_dt - midnight
            ).seconds

            self.calculate_indicators(update)

            current_trade_dt = self.get_datetime(
                self.data[self.data_it]["createdAt"]
            )
            self.output_data.append(update)
            self.reset_windows_after_punch()

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
    args = []
    if len(sys.argv) != 3:
        args = [0, 0, 1]
    else:
        args = sys.argv
    input_path = (
        "../../data/trades/raw/trades-2021_8_1_0_0_0-2022_1_22_0_0_0.json"
    )
    output_path = f"trades-df-2021_8_1_0_0_0-2022_1_22_0_0_0-{args[1]}.csv"
    dp = DataParser(input_path, output_path, int(args[1]), int(args[2]))
    dp.run_and_write()


if __name__ == "__main__":
    main()
