import sys
sys.path.append("../../")

from utils.helpful_scripts import string_to_datetime

class Indicators:
    @staticmethod
    def get_all_indicators():
        indicators = dict()
        for name in Indicators.__dict__.keys():
            if name[:2] != "__" and name != "get_all_indicators":
                indicators[name] = Indicators.__dict__[name]
        return indicators

    @staticmethod
    def seconds_since_midnight(window) -> int:
        current_trade_dt = string_to_datetime(
            window[-1]["createdAt"]
        )
        midnight = current_trade_dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (current_trade_dt - midnight).seconds

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
