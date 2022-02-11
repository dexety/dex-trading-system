import os
from random import randint
import json
import time
from threading import Thread, Lock, Condition
from datetime import datetime, timedelta

from dydx3.errors import DydxApiError
from dydx3.constants import (
    MARKET_BTC_USD,
    MARKET_ETH_USD,
    ORDER_SIDE_BUY,
    ORDER_SIDE_SELL,
)

from connectors.dydx.connector import DydxConnector
from utils.buy_sell_queue.buy_sell_queue import BuySellQueue
from utils.helpful_scripts import string_to_datetime
from utils.indicators.indicators import Indicators
from connectors.dydx.order_book_cache import OrderBookCache
from utils.logger.logger import Logger


class MLArbitrage:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")

    eth_trading_budget = 0.01
    take_profit = 0.003
    stop_loss = 0.001
    trade_window_slices_sec = [600, 60, 30, 10, 5]
    n_trades_ago_list = [1000, 100, 50, 10, 1]
    min_side_queue_length = max(n_trades_ago_list)
    trade_window_td = timedelta(seconds=600)
    punch_window_td = timedelta(seconds=30)
    start_timestamp = str(datetime.utcnow())

    order_cycles_counter = 0

    slippage = 0.0002
    symbol = MARKET_ETH_USD

    features_values = {}

    recieved_trades = []
    opener_order_update = {"updatedAt": "2020-01-01T00:00:00.000Z"}
    trading_lock = Lock()
    opened_position_cv = Condition()
    closed_position_cv = Condition()

    def __init__(self) -> None:
        self.trade_window = BuySellQueue(
            window_interval_td=self.trade_window_td,
            min_side_queue_length=self.min_side_queue_length,
        )
        self.connector = DydxConnector(
            self.symbol,
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

            if (
                len(self.trade_window["BUY"]) < self.min_side_queue_length
                or len(self.trade_window["SELL"]) < self.min_side_queue_length
            ):
                continue
            self.recieved_trades.clear()
            Indicators.fill_features_values(
                self.features_values,
                self.trade_window,
                self.trade_window_slices_sec,
                self.n_trades_ago_list,
            )
            prediction = self.predict()

            if prediction == 0:
                continue
            self.go_long()

    def predict(self) -> bool:
        # TODO
        # this function predicts, if the price of ETH in USD wil go up (True) or not (False)

        print(json.dumps(self.features_values, indent=4))
        return randint(-1, 1)

    def go_long(self) -> None:
        self.order_cycles_counter += 1
        price = self.trade_window.last_prices["BUY"] * (1 + self.slippage)
        order = self.connector.send_fok_market_order(
            symbol=self.symbol,
            side=ORDER_SIDE_BUY,
            price=price,
            quantity=self.eth_trading_budget,
            client_id=f"market long #{self.order_cycles_counter} {self.start_timestamp}",
        )

        self.opened_position_cv.wait_for(
            lambda: self.opener_order_update["status"] in ["CANCELED", "FILLED"]
        )
        if self.opener_order_update["status"] == "CANCELED":
            return "CANCELED"

        Logger.debug("Bought")

    def trade_listener(self, trade) -> None:
        self.recieved_trades.append(trade)

    def account_listener(self, update) -> None:
        # TODO
        recieved_opener_order_update = False
        recieved_closer_order_update = False
        for order_update in update["contents"]["orders"]:
            if order_update["clientId"] == "1" and string_to_datetime(
                order_update["updatedAt"]
            ) > string_to_datetime(self.opener_order_update["updatedAt"]):
                self.opener_order_update = order_update
                recieved_opener_order_update = True
            if order_update["clientId"] == "2" and string_to_datetime(
                order_update["updatedAt"]
            ) > string_to_datetime(self.opener_order_update["updatedAt"]):
                self.closer_order_update = order_update
                recieved_closer_order_update = True
        if recieved_opener_order_update:
            self.opened_position_cv.notify(1)
        if recieved_closer_order_update:
            self.closed_position_cv.notify(1)
        pass

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def main():
    ml_arbitrage = MLArbitrage()
    ml_arbitrage.run()


if __name__ == "__main__":
    main()
