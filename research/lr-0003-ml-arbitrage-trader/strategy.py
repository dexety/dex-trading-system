import os
from random import randint
import json
import sys
import time
import argparse
from functools import wraps
from collections import deque
from threading import Thread, Lock
from datetime import datetime, timedelta

from dydx3.errors import DydxApiError
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY, ORDER_SIDE_SELL

sys.path.append("../../")

from connectors.dydx.connector import DydxConnector, safe_execute
from indicator_funcs import Indicators
from connectors.dydx.order_book_cache import OrderBookCache
from base.logger import Logger


class MLArbitrage:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")

    update_interval_sec = 60
    window_parts = 10
    eth_trading_budget = 0.01
    slippage = 0.02
    symbol = MARKET_ETH_USD

    indicator_funcs = Indicators.get_all_indicators()
    indicator_data = {}
    trade_window = deque()
    recieved_trades = []
    latest_prices = {}

    eth_current_balance = 0
    usd_current_balance = 20

    trading_lock = Lock()

    def __init__(self) -> None:
        self.connector = DydxConnector(
            self.ETH_ADDRESS,
            self.ETH_PRIVATE_KEY,
            [self.symbol],
            self.INFURA_NODE,
        )
        self.connector.add_trade_listener(self.trade_listener)
        self.connector.add_trade_subscription(self.symbol)
        self.connector.add_account_listener(self.account_listener)
        self.connector.add_account_subscription()

    def run(self) -> None:
        Logger.debug("Initiating trading...")

        listener_thread = Thread(target=self.connector.start)
        trade_maker_thread = Thread(target=self.trade_maker)

        listener_thread.start()
        trade_maker_thread.start()

        Logger.debug("Trading started")

        listener_thread.join()
        trade_maker_thread.join()

    def trade_maker(self) -> None:
        while True:
            time.sleep(1)
            if len(self.recieved_trades) == 0:
                continue

            for trade in self.recieved_trades:
                self.trade_window.append(trade)
                self.latest_prices[trade["side"]] = trade["price"]

            self.recieved_trades.clear()

            self.correct_trade_window()
            self.count_indicators()

            prediction = self.predict()

            if prediction == 0:
                continue
            elif prediction == 1:
                self.buy()
            elif prediction == -1:
                self.sell()

    def count_indicators(self) -> None:
        for sec in range(
            self.update_interval_sec // self.window_parts,
            self.update_interval_sec + 1,
            self.update_interval_sec // self.window_parts,
        ):
            filtered_window = list(
                filter(
                    lambda trade: self.get_datetime(
                        self.trade_window[-1]["createdAt"]
                    )
                    - self.get_datetime(trade["createdAt"])
                    <= timedelta(seconds=sec),
                    self.trade_window,
                )
            )

            for indicator in self.indicator_funcs:
                self.indicator_data[
                    indicator + "-" + str(sec)
                ] = self.indicator_funcs[indicator](filtered_window)

    def correct_trade_window(self) -> None:
        last_trade_time = self.get_datetime(self.trade_window[-1]["createdAt"])
        while (
            self.get_datetime(self.trade_window[0]["createdAt"])
            + timedelta(seconds=self.update_interval_sec)
            < last_trade_time
        ):
            self.trade_window.popleft()
        

    def predict(self) -> int:
        # TODO
        # indicators -- self.indicator_data
        #
        # this function predicts, if the price of ETH in USD wil go up (returns 1),
        # down (-1) or will roughly remain the same (0)

        print(json.dumps(self.indicator_data, indent=4))
        return randint(-1, 1)

    def lock_trade(self, function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            self.trading_lock.acquire()
            function(*args, **kwargs)
            self.trading_lock.release() 
        
        return wrapper

    def buy(self) -> None:
        self.connector.send_fok_order(
            symbol=self.symbol,
            side=ORDER_SIDE_BUY,
            price=self.latest_prices["BUY"] * (1 + self.slippage / 100),
            quantity=self.eth_trading_budget,
        )
        Logger.debug("Bought")

    def sell(self) -> None:
        self.connector.send_fok_order(
            symbol=self.symbol,
            side=ORDER_SIDE_SELL,
            price=self.latest_prices["SELL"] * (1 - self.slippage / 100),
            quantity=self.eth_trading_budget,
        )
        Logger.debug("Sold")

    def trade_listener(self, trade) -> None:
        self.recieved_trades.append(trade)
    
    def account_listener(self, update) -> None:
        # TODO
        pass
        
    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def main():
    ml_arbitrage = MLArbitrage()
    ml_arbitrage.run()


if __name__ == "__main__":
    main()
