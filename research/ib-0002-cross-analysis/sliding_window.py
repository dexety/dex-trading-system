from collections import deque
from datetime import datetime


class SlidingWindow:
    def __init__(self):
        self.trades_timestamps = deque()
        self.mins = deque()
        self.maxs = deque()
        self.window_size = 1000

    def clear(self):
        self.trades_timestamps.clear()
        self.mins.clear()
        self.maxs.clear()

    def get_timestamp_of_min(self) -> int:
        if len(self.mins) == 0:
            return -1
        return self.mins[0][1]

    def get_timestamp_of_max(self):
        if len(self.maxs) == 0:
            return -1
        return self.maxs[0][1]

    def get_min(self) -> float:
        if len(self.mins) == 0:
            return 10 ** 8
        return self.mins[0][0]

    def get_max(self) -> float:
        if len(self.maxs) == 0:
            return -(10 ** 8)
        return self.maxs[0][0]

    def get_last_trade(self) -> int:
        if len(self.trades_timestamps) == 0:
            return 0  # some small timestamp
        return self.trades_timestamps[-1]

    def get_first_trade(self) -> int:
        if len(self.trades_timestamps) == 0:
            return 2239499954238  # some big timestamp
        return self.trades_timestamps[0]

    def push_back(
        self, price: float, timestamp: int
    ) -> bool:  # returns true if min or max is changed
        changes = False
        if timestamp < self.get_last_trade():
            return changes

        while timestamp - self.get_first_trade() > self.window_size:
            first_trade = self.trades_timestamps.popleft()
            if first_trade == self.get_timestamp_of_min():
                self.mins.popleft()
                changes = True
            if first_trade == self.get_timestamp_of_max():
                self.maxs.popleft()
                changes = True
        self.trades_timestamps.append(timestamp)

        old_min = self.get_min()
        while len(self.mins) != 0 and self.mins[-1][0] >= price:
            self.mins.pop()
        self.mins.append((price, timestamp))
        if old_min != self.get_min():
            changes = True

        old_max = self.get_max()
        while len(self.maxs) != 0 and self.maxs[-1][0] <= price:
            self.maxs.pop()
        self.maxs.append((price, timestamp))
        if old_max != self.get_max():
            changes = True
        return changes
