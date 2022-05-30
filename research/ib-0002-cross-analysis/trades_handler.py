from sliding_window import SlidingWindow
import statistics


class TradesHandler:
    def __init__(self):
        self.second_price_slide = SlidingWindow(1000)
        self.second_quantity_slide = SlidingWindow(1000)
        self.minute_quantity_slide = SlidingWindow(60000)
        self.minute_price_slide = SlidingWindow(60000)

        self.stats = []
        self.signals = []

        self.jump_value = 0
        self.jump_time_length = 0

        self.signal_threshold = 0.0021
        self.minmax_window = 1000  # all time in millisecs
        self.signal_side = "BUY"
        self.max_amount = -1

    def _update_windows(self, timestamp_millsec, price, quantity) -> str:  # TODO make a lagging window window
        #self.minute_quantity_slide.push_back(quantity, timestamp_millsec)
        self.second_quantity_slide.push_back(quantity, timestamp_millsec)
        #self.minute_price_slide.push_back(price, timestamp_millsec)
        if self.second_price_slide.push_back(
                price, timestamp_millsec
        ):
            max_in_window = self.second_price_slide.get_max()
            max_timestamp = self.second_price_slide.get_max_timestamp()
            min_in_window = self.second_price_slide.get_min()
            min_timestamp = self.second_price_slide.get_min_timestamp()
            if max_in_window / min_in_window >= (
                    1 + self.signal_threshold
            ):
                if max_timestamp > min_timestamp:
                    self.jump_value = max_in_window / min_in_window
                    self.jump_time_length = max_timestamp - min_timestamp
                    return "BUY"
                elif max_timestamp < min_timestamp:
                    self.jump_value = max_in_window / min_in_window
                    self.jump_time_length = min_timestamp - max_timestamp
                    return "SELL"
        return ""

    def _clear(self):
        self.second_price_slide.clear()
        self.minute_price_slide.clear()
        self.minute_price_slide.clear()
        self.second_quantity_slide.clear()

    def handle(self, time, price, quantity):
        direction = self._update_windows(time.timestamp() * 1000, price, quantity)
        if direction == "":
            return
        stat = dict()
        # stat["minute"] = dict()
        stat["second"] = dict()

        # stat["minute"]["average_price"] = statistics.mean(self.minute_price_slide.target_params)
        # stat["minute"]["average_quantity"] = statistics.mean(self.minute_quantity_slide.target_params)
        # stat["minute"]["max_quantity"] = self.minute_quantity_slide.get_max()
        # stat["minute"]["stdev_price"] = statistics.stdev(self.minute_price_slide.target_params)
        # stat["minute"]["stdev_quantity"] = statistics.stdev(self.minute_quantity_slide.target_params)
        # stat["minute"]["trades_frequency"] = len(self.minute_price_slide.trades_timestamps) / 60

        seconds_from_first_to_last = (self.second_price_slide.get_last_trade()
                                      - self.second_price_slide.get_first_trade()) / 1000

        stat["second"]["average_price"] = statistics.mean(self.second_price_slide.target_params)
        stat["second"]["average_quantity"] = statistics.mean(self.second_quantity_slide.target_params)
        stat["second"]["max_quantity"] = self.second_quantity_slide.get_max()
        stat["second"]["stdev_price"] = statistics.stdev(self.second_price_slide.target_params)
        stat["second"]["stdev_quantity"] = statistics.stdev(self.second_quantity_slide.target_params)
        stat["second"]["trades_frequency"] = len(self.second_price_slide.trades_timestamps) / seconds_from_first_to_last
        stat["second"]["jump_value"] = self.jump_value
        stat["second"]["jump_time_length"] = self.jump_time_length

        self.stats.append(stat)
        self.signals.append({"time": time, "direction": direction})
        self._clear()





