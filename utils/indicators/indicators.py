import sys

sys.path.append("../../")

from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.helpful_scripts import string_to_datetime


class Indicators:
    @staticmethod
    def fill_punches_values(
        indicators_values: dict, queue: BuySellQueue
    ) -> float:
        """returns max punch"""
        buy_column_name = f"punch-BUY-{str(queue.window_interval_td)}-sec"
        sell_column_name = f"punch-SELL-{str(queue.window_interval_td)}-sec"

        indicators_values[buy_column_name] = (
            max(
                0,
                queue.get_side_queue_max_price("SELL") /
                float(queue["BUY"][-1]["price"])
                - 1,
            )
            if queue["BUY"]
            else 0
        )

        indicators_values[sell_column_name] = (
            min(
                0,
                queue.get_side_queue_min_price("BUY")
                / float(queue["SELL"][-1]["price"])
                - 1,
            )
            if queue["SELL"]
            else 0
        )

        max_punch = max(
            indicators_values[buy_column_name],
            indicators_values[sell_column_name],
            key=abs,
        )

        return max_punch

    @staticmethod
    def fill_features_values(
        indicators_punch_values: dict,
        queue: BuySellQueue,
        slices_lengths: list,
        n_trades_ago_list: list,
    ) -> None:
        WI_dict = {}
        for name, indicator in Indicators.__dict__.items():
            if name[:2] == "WI":
                WI_dict[name] = indicator.__func__

        indicators_punch_values[
            "seconds-since-midnight"
        ] = Indicators.seconds_since_midnight(queue.common_queue[-1])

        for side in ["BUY", "SELL"]:
            for n_trades_ago in n_trades_ago_list:
                Indicators.seconds_since_n_trades_ago(
                    indicators_punch_values, queue[side], n_trades_ago, side
                )
            for window_slice_sec in slices_lengths:
                window_slice = queue.get_side_queue_slice(
                    side, window_slice_sec
                )

                for WI_name, WI_function in WI_dict.items():
                    column_name = (
                        WI_name + "-" + str(window_slice_sec) + "-sec-" + side
                    )
                    WI_function(
                        indicators_punch_values, window_slice, column_name
                    )

    @staticmethod
    def seconds_since_n_trades_ago(
        indicators_values: dict, window, n_trades_ago: int, side: str
    ) -> None:
        column_name = (
            "seconds-since-" + str(n_trades_ago) + "-trades-ago-" + side
        )
        if not window:
            indicators_values[column_name] = 0
            return
        diff = (
            string_to_datetime(window[-1]["createdAt"])
            - string_to_datetime(
                window[
                    max(
                        0,
                        len(window) - n_trades_ago - 1,
                    )
                ]["createdAt"]
            )
        ).total_seconds()
        indicators_values[column_name] = diff

    @staticmethod
    def seconds_since_midnight(trade) -> int:
        current_trade_dt = string_to_datetime(trade["createdAt"])
        midnight = current_trade_dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (current_trade_dt - midnight).seconds

    @staticmethod
    def WI_exp_moving_average(
        indicators_values: dict, window: list, WI_column_name: str, alpha=0.5
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 0
            return
        ema = float(window[0]["price"])
        for i in range(1, len(window)):
            ema = ema + alpha * (float(window[i]["price"]) - ema)
        indicators_values[WI_column_name] = ema / (sum(
            map(lambda trade: float(trade["price"]), window)
        ) / len(window))

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
            indicators_values[WI_column_name] = 0
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
        ) / (sum(
            map(lambda trade: float(trade["price"]), window)
        ) / len(window))

    @staticmethod
    def WI_stochastic_oscillator(
        indicators_values: dict, window: list, WI_column_name: str
    ) -> None:
        if not window:
            indicators_values[WI_column_name] = 0
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
