import json
import csv
import sys
from collections import deque
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm

sys.path.append("../../")

from utils.indicators.indicators import Indicators
from utils.buy_sell_queue.buy_sell_queue import BuySellWindow
from utils.helpful_scripts import string_to_datetime

class DataParser:
    punch_threashold = 0.0002
    trade_window_slices_sec = [600, 60, 30, 10, 5, 1]
    trade_window_td = timedelta(seconds=600)
    punch_window_td = timedelta(seconds=30)
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
        self.output_data = []
        self.progress_bar = tqdm(range(self.data_it_max - self.data_it))

        self.init_windows()

    def init_windows(self) -> None:
        first_trade_dt = string_to_datetime(
            self.data[self.data_it]["createdAt"]
        )
        self.trade_window = BuySellWindow(self.trade_window_td)
        self.punch_window = BuySellWindow(self.punch_window_td)
        self.set_window_borders(first_trade_dt)
        self.fill_trade_window()
        self.fill_punch_window()

    def set_window_borders(self, trade_window_from_dt: datetime) -> None:
        self.trade_window.set_window_borders(trade_window_from_dt)
        self.punch_window.set_window_borders(
            trade_window_from_dt + self.trade_window_td
        )

    def update_windows_after_punch(self) -> None:
        self.set_window_borders(
            self.trade_window.from_dt + self.punch_window_td
        )
        self.fill_punch_window()
        self.clean_trade_window()
        self.move_from_punch_window_to_trade_window()

    def get_new_trade(self) -> dict:
        self.progress_bar.update()
        trade = self.data[self.data_it]
        self.data_it += 1
        return trade

    def clean_trade_window(self) -> None:
        while not self.trade_window.trade_inside(
            self.trade_window.common_queue[0]
        ):
            self.trade_window.pop_front()

    def fill_trade_window(self) -> None:
        while self.trade_window.trade_inside(self.data[self.data_it]):
            self.trade_window.push_back(self.get_new_trade())

    def move_from_punch_window_to_trade_window(self) -> None:
        while not self.punch_window.trade_inside(
            self.punch_window.common_queue[0]
        ):
            self.trade_window.push_back(self.punch_window.pop_front())

    def fill_punch_window(self) -> None:
        while self.punch_window.trade_inside(self.data[self.data_it]):
            self.punch_window.push_back(self.get_new_trade())

    def update_windows_no_punch(self) -> None:
        new_trade = self.get_new_trade()
        self.set_window_borders(
            string_to_datetime(new_trade["createdAt"])
            - self.punch_window_td
            - self.trade_window_td
        )
        self.punch_window.push_back(new_trade)
        self.clean_trade_window()
        self.move_from_punch_window_to_trade_window()

    def get_max_price(self, window: dict, side: str) -> float:
        return float(
            max(
                window[side],
                key=lambda trade: trade["price"],
            )["price"]
        )

    def add_result(self) -> None:
        if not self.trades_window["BUY"] or not self.trades_window["SELL"]:
            return

        update = {}
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
                    string_to_datetime(
                        self.trade_window.side_queues[side][-1]["createdAt"]
                    )
                    - string_to_datetime(
                        self.trade_window.side_queues[side][
                            max(
                                0,
                                len(self.trade_window.common_queue)
                                - n_trades_ago
                                - 1,
                            )
                        ]["createdAt"]
                    )
                ).total_seconds()
                update[
                    "seconds-since-" + str(n_trades_ago) + "-trades-ago-" + side
                ] = diff
            for window_slice_sec in self.trade_window_slices_sec:
                window_slice = self.trade_window.get_side_queue_slice(side, window_slice_sec)

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
                "punch-" + side + "-" + str(self.punch_window_td) + "-sec"
            ] = max(
                0,
                1
                - self.get_max_price(self.punch_window, "SELL")
                / float(self.trade_window["BUY"][-1]["price"]),
            )
        elif side == "SELL" and self.punch_window["BUY"]:
            update[
                "punch-" + side + "-" + str(self.punch_window_td) + "-sec"
            ] = min(
                0,
                1
                - self.get_min_price(self.punch_window, "BUY")
                / float(self.trade_window["SELL"][-1]["price"]),
            )
        else:
            update[
                "punch-" + side + "-" + str(self.punch_window_td) + "-sec"
            ] = 0

    def add_result(self) -> None:
        if not self.trade_window["BUY"] or not self.trade_window["SELL"]:
            return

        update = {}
        max_punch = 0

        for side in self.SIDES:
            self.calculate_punches(update, side)
            max_punch = max(
                max_punch,
                update[
                    "punch-" + side + "-" + str(self.punch_window_td) + "-sec"
                ],
                key=abs,
            )

        if (
            abs(max_punch) > self.punch_threashold
            or np.random.random() < self.random_data_pc
        ):
            current_trade_dt = string_to_datetime(
                self.data[self.data_it]["createdAt"]
            )
            midnight = current_trade_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            update["seconds-since-midnight"] = (
                current_trade_dt - midnight
            ).seconds

            self.calculate_indicators(update)

            current_trade_dt = string_to_datetime(
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
            self.update_windows_after_punch()

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
