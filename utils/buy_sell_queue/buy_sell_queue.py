from collections import deque
from datetime import datetime, timedelta

from utils.helpful_scripts import string_to_datetime

class BuySellWindow:
    buy_queue = deque()
    sell_queue = deque()
    common_queue = deque()

    def __init__(self, window_interval_td: timedelta) -> None:
        self.window_interval_td = window_interval_td
    
    def __getitem__(self, side: str) -> deque:
        return self.buy_queue if side == "BUY" else self.sell_queue

    def set_window_borders(self, from_dt: datetime) -> None:
        self.from_dt = from_dt
        self.to_dt = self.from_dt + self.window_interval_td

    def get_last_to_first_td(self) -> timedelta:
        return string_to_datetime(self.common_queue[-1]) - string_to_datetime(self.common_queue[0])
    
    def trade_inside(self, trade: dict) -> bool:
        trade_time = string_to_datetime(trade["createdAt"])
        return trade_time >= self.from_dt and trade_time <= self.to_dt

    def pop_front(self) -> dict:
        first_trade = self.common_queue.popleft()
        self[first_trade["side"]].popleft()
        return first_trade

    def push_back(self, trade: dict) -> None:
        self.common_queue.append(trade)
        self[trade["side"]].append(trade)

    def get_side_queue_slice(self, side: str, seconds: int) -> list:
        if seconds == self.window_interval_td.seconds:
            return self[side]
        
        slice = []
        i = 1
        while i <= len(self[side]) and string_to_datetime(self[side][-i]["createdAt"]) >= self.to_dt - timedelta(seconds=seconds):
            slice.append(self[side][-i])
            i += 1
        
        return slice
    
    def get_side_queue_max_price(self, side: str) -> float:
        return float(
            max(
                self[side],
                key=lambda trade: trade["price"],
            )["price"]
        )

    def get_side_queue_min_price(self, side: str) -> float:
        return float(
            min(
                self[side],
                key=lambda trade: trade["price"],
            )["price"]
        )
