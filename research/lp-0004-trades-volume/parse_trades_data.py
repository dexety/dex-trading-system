import json
import csv
import sys
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm

sys.path.append("../../")

from utils.indicators.indicators import Indicators
from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.helpful_scripts import string_to_datetime


class DataParser:
    stop_profit = 0.002
    stop_loss = 0.001
    trade_window_slices_sec = [600, 60, 30, 10, 5]
    n_trades_ago_list = [1000, 100, 50, 10, 1]
    trade_window_td = timedelta(seconds=600)
    punch_window_td = timedelta(seconds=30)
    random_data_pc = 0.03
    SIDES = ["BUY", "SELL"]

    def __init__(self, input_path: str, output_path: str) -> None:
        self.data = json.load(open(input_path, "r", encoding="utf8"))
        self.data_it = 0
        self.input_path = input_path
        self.output_path = output_path
        self.progress_bar = tqdm(range(len(self.data)))
        self.output_data = []

        self.trade_window = None
        self.init_windows()

    def init_windows(self) -> None:
        first_trade_dt = string_to_datetime(
            self.data[self.data_it]["createdAt"]
        )
        self.trade_window = BuySellQueue(window_interval_td=self.trade_window_td, min_side_queue_length=max(self.n_trades_ago_list))
        self.punch_window = BuySellQueue(self.punch_window_td)
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
        self.move_from_punch_window_to_trade_window()
        self.clean_trade_window()

    def get_new_trade(self) -> dict:
        self.progress_bar.update()
        trade = self.data[self.data_it]
        self.data_it += 1
        return trade

    def clean_trade_window(self) -> None:
        while (
            self.trade_window.size()
            and not self.trade_window.is_trade_inside(
                self.trade_window.common_queue[0]
            ) and self.trade_window.needs_pop_front()
        ):
            self.trade_window.pop_front()

    def fill_trade_window(self) -> None:
        while self.data_it < len(
            self.data
        ) and self.trade_window.is_trade_inside(self.data[self.data_it]):
            self.trade_window.push_back(self.get_new_trade())

    def move_from_punch_window_to_trade_window(self) -> None:
        while (
            self.punch_window.size()
            and not self.punch_window.is_trade_inside(
                self.punch_window.common_queue[0]
            )
        ):
            trade_to_move = self.punch_window.pop_front()
            if trade_to_move != {}:
                self.trade_window.push_back(trade_to_move)

    def fill_punch_window(self) -> None:
        while self.data_it < len(
            self.data
        ) and self.punch_window.is_trade_inside(self.data[self.data_it]):
            self.punch_window.push_back(self.get_new_trade())

    def update_windows_no_punch(self) -> None:
        new_trade = self.get_new_trade()
        self.set_window_borders(
            string_to_datetime(new_trade["createdAt"])
            - self.punch_window_td
            - self.trade_window_td
        )
        self.punch_window.push_back(new_trade)
        self.move_from_punch_window_to_trade_window()
        self.clean_trade_window()

    def add_result(self) -> None:
        if (
            not self.punch_window["SELL"]
            or not self.punch_window["BUY"]
            or not self.trade_window["SELL"]
            or not self.trade_window["BUY"]
        ):
            self.update_windows_no_punch()
            return

        indicators_values = {}
        Indicators.fill_target_values(
            indicators_values, self.trade_window, self.punch_window, self.stop_profit, self.stop_loss
        )

        if (
            indicators_values["target"]
            or np.random.random() < self.random_data_pc
        ):
            Indicators.fill_features_values(
                indicators_values,
                self.trade_window,
                self.trade_window_slices_sec,
                self.n_trades_ago_list,
            )
            self.output_data.append(indicators_values)
            self.update_windows_after_punch()
        else:
            self.update_windows_no_punch()

    def write_data(self) -> None:
        field_names = list(self.output_data[0].keys())
        with open(self.output_path, "w") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(self.output_data)

    def run_and_write(self) -> None:
        while self.data_it < len(self.data):
            self.add_result()
        self.write_data()


def main():
    input_path = "../../data/trades/raw/trades_01-08-2021_22-01-2022.json"
    output_path = (
        "../../data/trades/processed/indicators_01-08-2021_22-01-2022.csv"
    )
    dp = DataParser(input_path, output_path)
    dp.run_and_write()


if __name__ == "__main__":
    main()
