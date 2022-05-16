from collections import deque
import dataclasses
import typing


@dataclasses.dataclass
class SlidingWindowElem:
    price: float
    timestamp: int


class SlidingWindow:
    def __init__(self, window_millisec: int = 1000):
        self.trades_timestamps = deque()
        self.mins: typing.Deque[SlidingWindowElem] = deque()
        self.maxs: typing.Deque[SlidingWindowElem] = deque()
        self.window_size_millisec = window_millisec

    def clear(self):
        self.trades_timestamps.clear()
        self.mins.clear()
        self.maxs.clear()

    def get_timestamp_of_min(self) -> int:
        if len(self.mins) == 0:
            return -1
        return self.mins[0].timestamp

    def get_timestamp_of_max(self):
        if len(self.maxs) == 0:
            return -1
        return self.maxs[0].timestamp

    def get_min_value(self) -> float:
        if len(self.mins) == 0:
            return 10 ** 8
        return self.mins[0].price

    def get_max_value(self) -> float:
        if len(self.maxs) == 0:
            return -(10 ** 8)
        return self.maxs[0].price

    def get_last_trade_timestamp(self) -> int:
        if len(self.trades_timestamps) == 0:
            return 0
        return self.trades_timestamps[-1]

    def get_first_trade_timestamp(self) -> int:
        if len(self.trades_timestamps) == 0:
            return 2239499954238
        return self.trades_timestamps[0]

    def move_window(self, new_timestamp: int) -> bool:
        """Return value: True if min or max is changed"""
        minmax_was_changed: bool = False
        while (
            new_timestamp - self.get_first_trade_timestamp()
            > self.window_size_millisec
        ):
            first_trade = self.trades_timestamps.popleft()
            if first_trade == self.get_timestamp_of_min():
                self.mins.popleft()
                minmax_was_changed = True
            if first_trade == self.get_timestamp_of_max():
                self.maxs.popleft()
                minmax_was_changed = True
        return minmax_was_changed

    def push_back(self, price: float, timestamp: int) -> bool:
        """Return value: True if min or max is changed"""
        minmax_was_changed: bool = False
        if timestamp < self.get_last_trade_timestamp():
            return minmax_was_changed

        minmax_was_changed = self.move_window(timestamp)
        self.trades_timestamps.append(timestamp)

        old_min_value = self.get_min_value()
        while len(self.mins) != 0 and self.mins[-1].price >= price:
            self.mins.pop()
        self.mins.append(SlidingWindowElem(price, timestamp))
        if old_min_value != self.get_min_value():
            minmax_was_changed = True

        old_max_value = self.get_max_value()
        while len(self.maxs) != 0 and self.maxs[-1].price <= price:
            self.maxs.pop()
        self.maxs.append(SlidingWindowElem(price, timestamp))
        if old_max_value != self.get_max_value():
            minmax_was_changed = True

        return minmax_was_changed
