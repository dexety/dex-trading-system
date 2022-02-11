from datetime import datetime
from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.helpful_scripts import string_to_datetime


class Indicators:
    static_WI_dict = {}

    @staticmethod
    def fill_WI_dict():
        for name, indicator in Indicators.__dict__.items():
            if name[:2] == "WI":
                Indicators.static_WI_dict[name] = indicator.__func__

    @staticmethod
    def fill_target_values(
        indicators_values: dict,
        punch_window: BuySellQueue,
        stop_profit: float,
        stop_loss: float,
    ) -> datetime:
        column_name = "target"
        buy_price = float(punch_window["SELL"][0]["price"])
        max_sell_price = 0

        for trade in punch_window["SELL"]:
            sell_price = float(trade["price"])
            if sell_price > max_sell_price:
                if sell_price > buy_price * (1 + stop_profit):
                    indicators_values[column_name] = 1
                    return (
                        string_to_datetime(trade["createdAt"])
                        - punch_window.from_dt
                    )
                max_sell_price = sell_price
            else:
                if sell_price < max_sell_price * (1 - stop_loss):
                    indicators_values[column_name] = -1
                    return (
                        string_to_datetime(trade["createdAt"])
                        - punch_window.from_dt
                    )

        indicators_values[column_name] = 0
        return (
            string_to_datetime(punch_window.common_queue[-1]["createdAt"])
            - punch_window.from_dt
        )

    @staticmethod
    def fill_features_values(
        indicators_punch_values: dict,
        queue: BuySellQueue,
        slices_lengths: list,
        n_trades_ago_list: list,
    ) -> None:

        indicators_punch_values["seconds-since-midnight"] = int(
            (
                queue.to_dt
                - queue.to_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            ).total_seconds()
        )
        indicators_punch_values["date"] = string_to_datetime(
            queue.common_queue[-1]["createdAt"]
        ).date()

        for side in ["BUY", "SELL"]:
            for n_trades_ago in n_trades_ago_list:
                Indicators.seconds_since_n_trades_ago(
                    indicators_punch_values, queue, n_trades_ago, side
                )
            for window_slice_sec in slices_lengths:
                window_slice = queue.get_side_queue_slice(
                    side, window_slice_sec
                )

                for WI_name, WI_function in Indicators.static_WI_dict.items():
                    column_name = (
                        WI_name + "-" + str(window_slice_sec) + "_sec-" + side
                    )
                    WI_function(
                        indicators_punch_values, window_slice, column_name
                    )

    @staticmethod
    def seconds_since_n_trades_ago(
        indicators_values: dict,
        queue: BuySellQueue,
        n_trades_ago: int,
        side: str,
    ) -> None:
        column_name = (
            "seconds_since-" + str(n_trades_ago) + "-trades_ago-" + side
        )
        if not queue[side]:
            indicators_values[column_name] = 0
            return
        diff = (
            queue.to_dt
            - string_to_datetime(queue[side][-n_trades_ago]["createdAt"])
        ).total_seconds()
        indicators_values[column_name] = diff

    @staticmethod
    def WI_exp_moving_average(
        indicators_values: dict, window: list, WI_column_name: str, alpha=0.5
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 1
            return
        ema = float(window[0]["price"])
        for i in range(1, len(window)):
            ema = ema + alpha * (float(window[i]["price"]) - ema)
        indicators_values[WI_column_name] = ema / (
            sum(map(lambda trade: float(trade["price"]), window)) / len(window)
        )

    @staticmethod
    def WI_trade_amount(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        indicators_values[WI_column_name] = len(window)

    @staticmethod
    def WI_trade_volume(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 0
            return
        indicators_values[WI_column_name] = sum(
            map(lambda trade: float(trade["size"]), window)
        )

    @staticmethod
    def WI_open_close_diff(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 1
            return
        indicators_values[WI_column_name] = float(window[-1]["price"]) / float(
            window[0]["price"]
        )

    @staticmethod
    def WI_weighted_moving_average(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 1
            return
        indicators_values[WI_column_name] = (
            sum(
                map(
                    lambda trade: float(trade["price"]) * float(trade["size"]),
                    window,
                )
            )
            / sum(map(lambda trade: float(trade["size"]), window))
        ) / (
            sum(map(lambda trade: float(trade["price"]), window)) / len(window)
        )

    @staticmethod
    def WI_stochastic_oscillator(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 0.5
            return
        indicators_values[WI_column_name] = (
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
