class Indicators:
    @staticmethod
    def get_all_indicators():
        return {
            "trade_volume": lambda window: Indicators.trade_volume(window),
            "moving_average_price": lambda window: Indicators.moving_average(window),
            "weighted_moving_average_price": (
                lambda window: Indicators.weighted_moving_average(window)
            ),
            "exp_moving_average_price": (
                lambda window: Indicators.exp_moving_average(window)
            ),
            "stochastic_oscillator": (
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
