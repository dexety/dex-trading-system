from asyncio.runners import run
import json
import asyncio
from connectors.dydx.connector import DydxConnector
from utils.logger.logger import Logger
from my_queue import Queue
from connectors.binance.connector import BinanceConnector
from datetime import datetime


class FindLeaps:
    def __init__(
        self, binance_connector: BinanceConnector, dydx_connector: DydxConnector
    ) -> None:
        self.binance_connector = binance_connector
        self.dydx_connector = dydx_connector

        self.time_interval = 1
        self.leap = 0.3

        self.binance_connector.add_trade_listener(self.on_binance_trade)
        self.dydx_connector.add_trade_listener(self.on_dydx_trade)

        self.binance_current_buys = Queue(
            lambda a, b: a if a["price"] > b["price"] else b
        )
        self.binance_current_sells = Queue(
            lambda a, b: a if a["price"] < b["price"] else b
        )
        self.dydx_current_buys = Queue(
            lambda a, b: a if a["price"] > b["price"] else b
        )
        self.dydx_current_sells = Queue(
            lambda a, b: a if a["price"] < b["price"] else b
        )

        self.binance_recorded_buys = []
        self.binance_recorded_sells = []
        self.dydx_recorded_buys = []
        self.dydx_recorded_sells = []

        self.binance_buy_leaps = []
        self.binance_sell_leaps = []
        self.dydx_buy_leaps = []
        self.dydx_sell_leaps = []

        Logger.info(
            f"inited template strategy. balances: {binance_connector.get_all_balances()}"
        )

    async def _async_start(self, run_duration):
        task1 = asyncio.create_task(self.dydx_connector.start(run_duration))
        task2 = asyncio.create_task(self.binance_connector.start(run_duration))
        await task1
        await task2

    def start(self, run_duration, out):
        self.output = out
        self.output.write("[\n")
        asyncio.run(self._async_start(run_duration))

    def on_order_book(self, order_book):
        Logger.info(
            f"{order_book.symbol} :: received order_book: bids: {order_book.get_bids()} asks: {order_book.get_asks()}"
        )

    def str_to_timestamp(self, str):
        return datetime.strptime(str, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

    def process_trade(self, trade, queue, found_leaps, recorded_trades):
        self.output.write(json.dumps(trade, indent=4))
        self.output.write(",\n")
        # queue.push(trade)
        # recorded_trades.append(trade)
        # while self.str_to_timestamp(queue.back()['createdAt']) + self.time_interval < self.str_to_timestamp(trade['createdAt']):
        #     queue.pop()

        # price_leap = abs(trade['price'] / queue.best()['price'] - 1) * 100
        # if price_leap > self.leap:
        #     found_leaps.append(trade)
        #     while queue.size() > 0:
        #         queue.pop()

    def on_binance_trade(self, trade):
        # Logger.info(f"{trade['symbol']} :: received binance trade: {trade}")

        if trade["side"] == "BUY":
            self.process_trade(
                trade,
                self.binance_current_buys,
                self.binance_buy_leaps,
                self.binance_recorded_buys,
            )
        else:
            self.process_trade(
                trade,
                self.binance_current_sells,
                self.binance_sell_leaps,
                self.binance_recorded_sells,
            )

    def on_dydx_trade(self, trade):
        # Logger.info(f"{trade['symbol']} :: received dydx trade: {trade}")

        if trade["side"] == "BUY":
            self.process_trade(
                trade,
                self.dydx_current_buys,
                self.dydx_buy_leaps,
                self.dydx_recorded_buys,
            )
        else:
            self.process_trade(
                trade,
                self.dydx_current_sells,
                self.dydx_sell_leaps,
                self.dydx_recorded_sells,
            )
