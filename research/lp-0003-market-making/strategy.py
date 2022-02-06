import os
import time
import argparse
from functools import wraps
from threading import Thread, Lock
from datetime import datetime, timedelta
from dydx3.errors import DydxApiError
from connectors.dydx.connector import DydxConnector, safe_execute
from connectors.dydx.order_book_cache import OrderBookCache
from utils.logger.logger import Logger


def too_many_requests_guard(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        while True:
            try:
                return function(*args, **kwargs)
            except DydxApiError as dydx_error:
                if dydx_error.status_code == 429:
                    Logger.debug(f"Too many requests error: {dydx_error}")
                    time.sleep(1)
                    continue
                raise dydx_error

    return wrapper


class MarketMakingStrategy:
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")

    update_processing_ms = 100
    order_expiration_time_sec = 30
    order_checker_period_sec = 0.3

    commision_pc = 0.0005
    half_spread_pc = 2 * commision_pc
    after_punch_spread_pc = 3 * commision_pc
    price_change_threshold = commision_pc / 7

    is_running = False

    trade_update_mutex = Lock()

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        if symbol == "ETH-USD":
            self.buying_power = 0.01
            self.tick_size_round = 1
        elif symbol == "BTC-USD":
            self.buying_power = 0.001
            self.tick_size_round = 0
        else:
            raise Exception("Unsupported symbol")
        self.dydx_connector_trades = DydxConnector(
            self.ETH_ADDRESS,
            self.ETH_PRIVATE_KEY,
            [symbol],
            self.INFURA_NODE,
        )
        self.dydx_connector_order_book = DydxConnector(
            self.ETH_ADDRESS,
            self.ETH_PRIVATE_KEY,
            [symbol],
            self.INFURA_NODE,
        )
        self.dydx_connector_trades.add_trade_listener(self.on_trade_update)
        self.dydx_connector_order_book.add_orderbook_listener(
            self.on_order_book_update
        )
        self.set_null_last_trades()
        self.set_null_open_orders()
        self.order_book = OrderBookCache(self.symbol)

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def set_null_last_trades(self) -> None:
        self.last_trades = {
            "BUY": {
                "time": None,
                "price": -1e12,
            },
            "SELL": {
                "time": None,
                "price": 1e12,
            },
        }

    def set_null_open_orders(self) -> None:
        self.open_orders = {
            "BUY": None,
            "SELL": None,
        }

    def is_update_expired(self, time: datetime) -> bool:
        return (
            time + timedelta(milliseconds=self.update_processing_ms)
            <= datetime.utcnow()
        )

    def on_trade_update(self, update: dict) -> None:
        if self.is_update_expired(self.get_datetime(update["createdAt"])):
            return
        if self.last_trades[update["side"]]["price"] == update["price"]:
            return
        if (
            self.get_new_price(update["side"])
            == self.open_orders[update["side"]]
        ):
            return
        self.last_trades[update["side"]]["price"] = update["price"]
        self.last_trades[update["side"]]["time"] = update["createdAt"]
        self.on_trade_update_notify()

    def on_trade_update_notify(self, update_time=None) -> None:
        if (
            not self.is_running
            or (update_time and self.is_update_expired(update_time))
            or self.trade_update_mutex.locked()
        ):
            return

        Logger.debug("Orders update")

        self.trade_update_mutex.acquire()
        start_time = time.time()

        self.threading_replace_mirror_orders()
        open_positions = self.get_open_positions_by_dydx_api()
        if len(open_positions) != 0:
            self.is_running = False
            self.cancel_all_orders()
            time.sleep(0.1)
            self.set_order_for_second_punch()
            self.process_second_punch()
            self.is_running = True

        Logger.debug(
            f"Spent time processing update {1000 * (time.time() - start_time)} ms"
        )
        self.trade_update_mutex.release()

    @safe_execute
    def cancel_all_orders(self) -> None:
        Logger.debug("Cancel all orders")
        self.dydx_connector_trades.cancel_all_orders()

    def wait_for_orders_set(self) -> None:
        while True:
            orders = self.get_our_orders_by_dydx_api()
            if (
                len(orders) == 2
                and orders[0]["status"] == orders[1]["status"] == "OPEN"
            ):
                break
            time.sleep(0.01)

    def orders_checker(self) -> None:
        while True:
            self.check_orders()
            time.sleep(self.order_checker_period_sec)

    def check_orders(self) -> None:
        if self.is_running and (
            self.need_to_update_our_orders()
            or len(self.get_our_orders_by_dydx_api()) == 0
        ):
            self.on_trade_update_notify(datetime.utcnow())

    def need_to_update_our_orders(self) -> bool:
        need_to_update = 0
        for side in ["BUY", "SELL"]:
            if (
                self.open_orders[side] is not None
                and abs(
                    1
                    - float(self.open_orders[side]["price"])
                    / self.get_new_price(side)
                )
                >= self.price_change_threshold
            ) or self.open_orders[side] is None:
                need_to_update += 1
        return need_to_update == 2

    def on_order_book_update(self, update: dict) -> None:
        if update["type"] == "subscribed":
            is_first_request = True
        elif update["type"] == "channel_data":
            is_first_request = False

        order_boook_update = update["contents"]
        self.order_book.update_orders(
            order_boook_update, is_first_request=is_first_request
        )

    def cancel_order(self, side: str) -> None:
        Logger.debug(f"Cancel {side}")
        if self.open_orders[side] is not None:
            try:
                cancel_order = self.dydx_connector_trades.cancel_order(
                    self.open_orders[side]["id"]
                )
            except DydxApiError as error:
                Logger.debug(f"Cancel error: {error}")

    def threading_replace_mirror_orders(self) -> None:
        if self.open_orders["BUY"]:
            thread_send_order_buy = Thread(
                target=self.send_limit_order,
                kwargs={
                    "side": "BUY",
                    "cancel_id": self.open_orders["BUY"]["id"],
                },
            )
        else:
            thread_send_order_buy = Thread(
                target=self.send_limit_order,
                kwargs={"side": "BUY"},
            )
        thread_send_order_buy.start()

        if self.open_orders["SELL"]:
            thread_send_order_sell = Thread(
                target=self.send_limit_order,
                kwargs={
                    "side": "SELL",
                    "cancel_id": self.open_orders["SELL"]["id"],
                },
            )
        else:
            thread_send_order_sell = Thread(
                target=self.send_limit_order,
                kwargs={
                    "side": "SELL",
                },
            )
        thread_send_order_sell.start()

        thread_send_order_buy.join()
        thread_send_order_sell.join()

    def set_order_for_second_punch(self) -> None:
        Logger.debug("Set orders for second punch")
        positions = self.get_open_positions_by_dydx_api()
        total_size = sum(
            map(lambda position: float(position["size"]), positions)
        )
        average_price = sum(
            map(lambda position: float(position["entryPrice"]), positions)
        ) / len(positions)
        Logger.debug(
            f"Size of opened positions: {total_size}, average price: {average_price}"
        )
        self.set_null_open_orders()
        if total_size > 0:
            self.send_limit_order(
                side="SELL",
                cancel_id=None,
                spread=None,
                price=average_price * (1 + self.after_punch_spread_pc),
                size=total_size,
            )
        elif total_size < 0:
            self.send_limit_order(
                side="BUY",
                cancel_id=None,
                spread=None,
                price=average_price * (1 - self.after_punch_spread_pc),
                size=-total_size,
            )

    @too_many_requests_guard
    def wait_for_second_punch(self, divider: int) -> None:
        if len(self.dydx_connector_trades.get_our_orders()["orders"]) != 0:
            time.sleep(self.order_expiration_time_sec / divider)

    @too_many_requests_guard
    def get_our_orders_by_dydx_api(self) -> dict:
        return self.dydx_connector_trades.get_our_orders()["orders"]

    @too_many_requests_guard
    def get_open_positions_by_dydx_api(self) -> dict:
        return self.dydx_connector_trades.get_our_positions()["positions"]

    def process_second_punch(self) -> None:
        Logger.debug("Waiting for second punch")
        iters_num = 10
        for _ in range(iters_num):
            self.wait_for_second_punch(iters_num)
        orders = self.get_our_orders_by_dydx_api()
        if len(orders) == 0:
            self.set_null_open_orders()
            return
        side = orders[0]["side"]
        size = orders[0]["size"]
        while True:
            orders = self.get_our_orders_by_dydx_api()
            if len(orders) == 0:
                break
            try:
                self.cancel_order(side)
            except DydxApiError:
                break
            Logger.debug("Re-order")
            if side == "BUY":
                self.send_limit_order(
                    side=side,
                    cancel_id=None,
                    spread=0,
                    price=self.get_max_bid() - 2 * self.get_price_tick(),
                    size=size,
                )
            elif side == "SELL":
                self.send_limit_order(
                    side=side,
                    cancel_id=None,
                    spread=0,
                    price=self.get_min_ask() + 2 * self.get_price_tick(),
                    size=size,
                )
            time.sleep(5)
        self.set_null_open_orders()

    def get_price_tick(self) -> float:
        return 10 ** (-self.tick_size_round)

    def get_max_bid(self) -> float:
        return list(map(lambda x: float(x), self.order_book.bids.keys()))[-1]

    def get_min_ask(self) -> float:
        return list(map(lambda x: float(x), self.order_book.asks.keys()))[0]

    def get_new_price(self, side: str, spread=None) -> float:
        if spread == None:
            spread = self.half_spread_pc
        if side == "BUY":
            return round(
                self.get_max_bid() - self.get_min_ask() * spread,
                self.tick_size_round,
            )
        elif side == "SELL":
            return round(
                self.get_min_ask() * (1 + spread), self.tick_size_round
            )

    @too_many_requests_guard
    def send_limit_order(
        self,
        *,
        side: str,
        cancel_id=None,
        spread=None,
        price=None,
        size=None,
    ) -> None:
        if spread == None:
            spread = self.half_spread_pc

        if size == None:
            size = self.buying_power

        if self.need_to_update_our_orders():
            Logger.debug(
                f"Send limit {side}, {self.get_new_price(side, spread)}$"
            )
            self.open_orders[
                side
            ] = self.dydx_connector_trades.send_limit_order(
                symbol=self.symbol,
                side=side,
                price=self.get_new_price(side, spread)
                if price == None
                else round(price, self.tick_size_round),
                quantity=size,
                cancel_id=cancel_id,
            )[
                "order"
            ]

    def run(self) -> None:
        self.order_book_update_thread = Thread(
            target=self.dydx_connector_order_book.start
        )
        self.order_book_update_thread.start()
        Logger.debug("STRATEGY PREPARATION")
        while len(self.order_book.asks) == 0 or len(self.order_book.bids) == 0:
            Logger.debug(
                "Waiting for order book update to understand the spread window"
            )
            time.sleep(2)
        self.trade_update_thread = Thread(
            target=self.dydx_connector_trades.start
        )
        self.trade_update_thread.start()
        self.orders_checker_thread = Thread(target=self.orders_checker)
        self.orders_checker_thread.start()
        time.sleep(5)  # needs to skip the first archive trades
        self.is_running = True
        Logger.debug("STRATEGY LAUNCH")
        Logger.debug("Waiting for trades")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", dest="symbol", required=True)
    args = parser.parse_args()
    symbol = args.symbol

    mms = MarketMakingStrategy(symbol)
    mms.run()


if __name__ == "__main__":
    main()
