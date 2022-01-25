from collections import deque
from datetime import datetime, timedelta

class BuySellQueue:
    buy_queue = deque()
    sell_queue = deque()

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def reset(self) -> None:
        self.buy_queue = deque()
        self.sell_queue = deque()

    def add_
