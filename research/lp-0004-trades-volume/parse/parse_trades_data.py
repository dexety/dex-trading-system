import sys
import os
import csv
from datetime import datetime, timedelta
import numpy as np
from tqdm import tqdm
from utils.indicators.indicators import Indicators
from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.helpful_scripts import string_to_datetime, memory
from utils.logger.logger import Logger

# Logger.disabled = True

class DataParser:
    stop_profit = 0.0015
    stop_loss = 0.001
    trade_window_slices_sec = [600, 60, 30, 10, 5]
    n_trades_ago_list = [1000, 100, 50, 10, 1]
    trade_window_td = timedelta(seconds=600)
    punch_window_td = timedelta(seconds=30)
    random_data_pc = 0.02
    SIDES = ["BUY", "SELL"]

    def __init__(self, input_path: str, output_path: str) -> None:
        Logger.debug("__init__")
        with open(input_path, "r", encoding="utf8") as input_file:
            self.data = list(csv.DictReader(input_file))
        self.data_it = 0

        self.output_path = output_path
        self.output_data = []

        self.progress_bar = tqdm(range(len(self.data)))

        Indicators.fill_WI_dict()

        self.init_windows()

    def init_windows(self) -> None:
        Logger.debug("init windows")
        first_trade_dt = string_to_datetime(
            self.data[self.data_it]["createdAt"]
        )
        self.trade_window = BuySellQueue(
            window_interval_td=self.trade_window_td,
            min_side_queue_length=max(self.n_trades_ago_list),
        )
        self.punch_window = BuySellQueue(self.punch_window_td)
        self.set_window_borders(first_trade_dt)
        self.fill_trade_window()
        self.fill_punch_window()

    def set_window_borders(self, trade_window_from_dt: datetime) -> None:
        # Logger.debug("set window borders")
        self.trade_window.set_window_borders(trade_window_from_dt)
        self.punch_window.set_window_borders(
            trade_window_from_dt + self.trade_window_td
        )

    def update_windows_after_punch(self) -> None:
        # Logger.debug("update windows ap")
        self.set_window_borders(
            self.trade_window.from_dt + self.update_interval
        )
        self.fill_punch_window()
        self.move_from_punch_window_to_trade_window()
        self.clean_trade_window()

    def get_new_trade(self) -> dict:
        # Logger.debug("get new trade")
        self.progress_bar.update()
        trade = self.data[self.data_it]
        self.data_it += 1
        return trade

    def clean_trade_window(self) -> None:
        # Logger.debug("clean tw")
        while (
            self.trade_window.size()
            and not self.trade_window.is_trade_inside(
                self.trade_window.common_queue[0]
            )
            and self.trade_window.needs_pop_front()
        ):
            self.trade_window.pop_front()

    def fill_trade_window(self) -> None:
        # Logger.debug("fill tw")
        while self.data_it < len(
            self.data
        ) and self.trade_window.is_trade_inside(self.data[self.data_it]):
            self.trade_window.push_back(self.get_new_trade())

    def move_from_punch_window_to_trade_window(self) -> None:
        # Logger.debug("move from pw to tw")
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
        # Logger.debug("fill pw")
        are_trades_added = False
        while self.data_it < len(
            self.data
        ) and self.punch_window.is_trade_inside(self.data[self.data_it]):
            self.punch_window.push_back(self.get_new_trade())
            are_trades_added = True

        if not are_trades_added and not self.data_it == len(self.data):
            self.set_window_borders(self.trade_window.from_dt + (string_to_datetime(self.data[self.data_it]["createdAt"]) - self.punch_window.to_dt))
            self.punch_window.push_back(self.get_new_trade())

    def update_windows_no_punch(self) -> None:
        # Logger.debug("update windows np")
        new_trade = self.get_new_trade()
        self.set_window_borders(
            string_to_datetime(new_trade["createdAt"])
            - self.punch_window_td
            - self.trade_window_td
        )
        self.punch_window.push_back(new_trade)
        self.move_from_punch_window_to_trade_window()
        self.clean_trade_window()

    def add_result(self) -> bool:
        # Logger.debug("add result")
        """returns true if stoploss or stopprofit reached, false otherwise (no punch or not enough trades in queue)"""
        if (
            not self.punch_window["SELL"]
            or not self.punch_window["BUY"]
            or len(self.trade_window["SELL"])
            < self.trade_window.min_side_queue_length
            or len(self.trade_window["BUY"])
            < self.trade_window.min_side_queue_length
        ):
            return False

        indicators_values = {}
        self.update_interval = Indicators.fill_target_values(
            indicators_values,
            self.punch_window,
            self.stop_profit,
            self.stop_loss,
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
            return indicators_values["target"]

        return False

    def write_data(self) -> None:
        field_names = list(self.output_data[0].keys())
        with open(self.output_path, "w") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(self.output_data)

    def run_and_write(self) -> None:
        while self.data_it < len(self.data):
            if self.add_result():
                self.update_windows_after_punch()
            else:
                self.update_windows_no_punch()
        self.write_data()

@memory(percentage=0.5)
def main():
    date_borders = "01-08-2021_22-01-2022"
    if len(sys.argv) != 2:
        input_path = f"../../data/trades/raw/trades_{date_borders}.csv"
        output_path = (
            f"../../data/trades/processed/indicators_{date_borders}.csv"
        )
    else:
        raw_parts_dir_path = f"../../data/trades/raw/parts_{date_borders}"
        processed_parts_dir_path = (
            f"../../data/trades/processed/parts_{date_borders}"
        )

        if not os.path.isdir(processed_parts_dir_path):
            os.makedirs(processed_parts_dir_path)

        input_path = f"{raw_parts_dir_path}/{int(sys.argv[1])}.csv"
        output_path = f"{processed_parts_dir_path}/{int(sys.argv[1])}.csv"

    dp = DataParser(input_path, output_path)
    dp.run_and_write()


if __name__ == "__main__":
    main()
