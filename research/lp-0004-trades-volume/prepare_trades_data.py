import json
import csv
from collections import deque
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm


class DataParser:
    punch_threashold = 0.0002
    trades_window_sec = 30
    trades_window_timestamps_num = 3
    punch_window_sec = 30
    punch_window_timestamps_num = 3
    punch_round = 4
    data_it = 0
    trades_window = {"BUY": deque(), "SELL": deque()}
    punch_window = {"BUY": deque(), "SELL": deque()}
    output_data = []
    SIDES = ["BUY", "SELL"]

    def __init__(self, input_path: str, output_path: str) -> None:
        self.data = json.load(open(input_path, "r", encoding="utf8"))
        self.input_path = input_path
        self.progress_bar = tqdm(range(len(self.data)))
        self.output_path = output_path
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
        return self.data_it < len(self.data)

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

    def run(self) -> None:
        while self.data_it < len(self.data):
            self.update_windows()
            if len(self.punch_window) >= 2:
                self.add_result()

    def add_result(self) -> None:
        punch_window_price = {
            "BUY": list(
                map(
                    lambda trade: float(trade["price"]),
                    self.punch_window["BUY"],
                )
            ),
            "SELL": list(
                map(
                    lambda trade: float(trade["price"]),
                    self.punch_window["SELL"],
                )
            ),
        }
        punch_pc = {
            "BUY": round(
                (
                    (
                        max(punch_window_price["BUY"])
                        / min(punch_window_price["BUY"])
                        - 1
                    )
                    if punch_window_price["BUY"]
                    else 0
                ),
                self.punch_round,
            ),
            "SELL": round(
                (
                    (
                        1
                        - max(punch_window_price["SELL"])
                        / min(punch_window_price["SELL"])
                    )
                    if punch_window_price["SELL"]
                    else 0
                ),
                self.punch_round,
            ),
        }

        update = dict()

        for window_sec in range(
            self.trades_window_sec // self.trades_window_timestamps_num,
            self.trades_window_sec + 1,
            self.trades_window_sec // self.trades_window_timestamps_num,
        ):
            for side in self.SIDES:
                update["trades-" + side + "-" + str(window_sec) + "-sec"] = (
                    sum(
                        map(
                            lambda trade: float(trade["size"]),
                            filter(
                                lambda trade: self.get_datetime(
                                    self.trades_window[side][-1]["createdAt"]
                                )
                                - self.get_datetime(trade["createdAt"])
                                <= timedelta(seconds=window_sec),
                                self.trades_window[side],
                            ),
                        )
                    )
                    if self.trades_window[side]
                    else 0
                )
                if self.punch_window[side]:
                    update["punch-" + side + "-" + str(window_sec) + "-sec"] = (
                        round(
                            1
                            - max(punch_window_price[side])
                            / min(punch_window_price[side]),
                            self.punch_round,
                        )
                        if side == "SELL"
                        else round(
                            max(punch_window_price[side])
                            / min(punch_window_price[side])
                            - 1,
                            self.punch_round,
                        )
                    )
                else:
                    update["punch-" + side + "-" + str(window_sec) + "-sec"] = 0

        if (
            max(
                map(
                    lambda elem: abs(elem[1]),
                    dict(
                        filter(lambda elem: "punch" in elem[0], update.items())
                    ).items(),
                )
            )
            > self.punch_threashold
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


def main():
    input_path = (
        "../../data/trades/raw/trades-2021_11_1_0_0_0-2021_12_21_0_0_0.json"
    )
    output_path = "trades-df-2021_11_1_0_0_0-2021_12_21_0_0_0.csv"
    dp = DataParser(input_path, output_path)
    dp.run()
    dp.write_data()
    df = pd.read_csv(output_path)
    print(df)


if __name__ == "__main__":
    main()
