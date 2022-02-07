import os
from random import randint
import json
import sys
import time
from functools import wraps
from collections import deque
from threading import Thread, Lock
from datetime import datetime, timedelta

from dydx3.errors import DydxApiError
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY, ORDER_SIDE_SELL

from connectors.dydx.connector import DydxConnector
from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.indicators.indicators import Indicators
from connectors.dydx.order_book_cache import OrderBookCache
from utils.logger.logger import Logger


class MLArbitrage:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")

    eth_trading_budget = 0.01
    trade_window_slices_sec = [600, 60, 30, 10, 5]
    n_trades_ago_list = [1000, 100, 50, 10, 1]
    min_side_queue_length = max(n_trades_ago_list)
    trade_window_td = timedelta(seconds=600)
    punch_window_td = timedelta(seconds=30)

    slippage = 0.02
    symbol = MARKET_ETH_USD

    features_values = {}

    recieved_trades = []
    trading_lock = Lock()

    def __init__(self) -> None:
        self.trade_window = BuySellQueue(
            window_interval_td=self.trade_window_td,
            min_side_queue_length=self.min_side_queue_length
        )
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
                self.trade_window.push_back(trade)
            
            if len(self.trade_window["BUY"]) < self.min_side_queue_length or \
                len(self.trade_window["SELL"]) < self.min_side_queue_length:
                continue

            self.recieved_trades.clear()

            Indicators.fill_features_values(self.features_values, self.trade_window, self.trade_window_slices_sec, self.n_trades_ago_list)

            prediction = self.predict()

            if prediction == 0:
                continue
            elif prediction == 1:
                self.buy()


    def predict(self) -> int:
        # TODO
        # indicators -- self.indicator_data
        #
        # this function predicts, if the price of ETH in USD wil go up (returns 1),
        # down (-1) or will roughly remain the same (0)

        print(json.dumps(self.features_values, indent=4))
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
