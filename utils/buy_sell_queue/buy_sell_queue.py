from collections import deque
from datetime import datetime, timedelta

from utils.helpful_scripts import string_to_datetime


class BuySellQueue:
    def __init__(self, window_interval_td: timedelta) -> None:
        self.buy_queue = deque()
        self.sell_queue = deque()
        self.common_queue = deque()
        self.from_dt = datetime.utcnow()
        self.to_dt = datetime.utcnow()
        self.window_interval_td = window_interval_td

    def __getitem__(self, side: str) -> deque:
        return self.buy_queue if side == "BUY" else self.sell_queue

    def set_window_borders(self, from_dt: datetime) -> None:
        self.from_dt = from_dt
        self.to_dt = self.from_dt + self.window_interval_td

    def get_last_to_first_td(self) -> timedelta:
        return string_to_datetime(self.common_queue[-1]) - string_to_datetime(
            self.common_queue[0]
        )

    def size(self) -> int:
        return len(self.common_queue)

    def is_trade_inside(self, trade: dict) -> bool:
        trade_time = string_to_datetime(trade["createdAt"])
        return self.to_dt >= trade_time >= self.from_dt

    def pop_front(self) -> dict:
        if self.size():
            first_trade = self.common_queue.popleft()
            self[first_trade["side"]].popleft()
            return first_trade
        return {}

    def push_back(self, trade: dict) -> None:
        self.common_queue.append(trade)
        self[trade["side"]].append(trade)

    def get_side_queue_slice(self, side: str, seconds: int) -> list:
        if seconds >= self.window_interval_td.seconds:
            return self[side]

        queue_slice = []
        i = 1
        while i <= len(self[side]) and string_to_datetime(
            self[side][-i]["createdAt"]
        ) >= self.to_dt - timedelta(seconds=seconds):
            queue_slice.append(self[side][-i])
            i += 1

        return queue_slice

    def get_side_queue_max_price(self, side: str) -> float:
        return float(
            max(
                self[side],
                key=lambda trade: float(trade["price"]),
            )["price"]
        )

    def get_side_queue_min_price(self, side: str) -> float:
        return float(
            min(
                self[side],
                key=lambda trade: float(trade["price"]),
            )["price"]
        )
