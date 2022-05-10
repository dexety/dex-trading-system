import asyncio
import dataclasses
import math
import os
import random

from datetime import datetime
from datetime import timedelta

from binance.enums import FuturesType

from connectors.dydx.connector import DydxConnector, Network
from connectors.binance.connector import BinanceConnector
from utils.logger import LOGGER
from utils.sliding_window import SlidingWindow


def custom_exception_handler(loop, context):
    loop.default_exception_handler(context)
    exception = context.get("exception")
    if isinstance(exception, Exception):
        loop.stop()
        loop.close()


def handle_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as error:
        LOGGER.exception("Exception raised by task = %r", task)
        raise error


@dataclasses.dataclass
class Settings:
    trailing_percent: float
    quantity: float
    profit_threshold: float
    sec_to_wait: float
    sec_after_trade: float
    signal_threshold: float
    dydx_market: str
    binance_market: str


class Trader:
    side: str = ""
    opp_side: str = ""
    dispatch_time: datetime = datetime.now()
    sliding_window: SlidingWindow = SlidingWindow()
    is_market_sent: bool = False
    is_limit_sent: bool = False
    loop = asyncio.get_event_loop()

    # pylint: disable=too-many-arguments
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dydx_connector = DydxConnector(
            [settings.dydx_market],
            Network.mainnet,
        )
        self.binance_connector = BinanceConnector(
            os.getenv("BINANCE_API_KEY"),
            os.getenv("BINANCE_API_SECRET"),
            [settings.binance_market],
            FuturesType.COIN_M,
        )

    def get_trailing_percent(self):
        return (
            self.settings.trailing_percent
            if self.opp_side == "BUY"
            else 0 - self.settings.trailing_percent
        )

    def get_price(self, opposite: bool):
        if opposite:
            return 1 if self.opp_side == "SELL" else 10 ** 8
        return 1 if self.side == "SELL" else 10 ** 8

    def _binance_trade_listener(self, update: dict) -> None:
        if random.random() < 0.01:
            min_window_price = self.sliding_window.get_min_value()
            min_window_timestamp = self.sliding_window.get_timestamp_of_min()
            max_window_price = self.sliding_window.get_max_value()
            max_window_timestamp = self.sliding_window.get_timestamp_of_max()
            LOGGER.debug(
                f"Binance trade listener is still alive.\n"
                f"Current state:\n"
                f"Min price in window = {min_window_price}\n"
                f"Max price in window = {max_window_price}\n"
                f"Min time in window = {datetime.fromtimestamp(min_window_timestamp)}\n"
                f"Max time in window = {datetime.fromtimestamp(max_window_timestamp)}\n"
            )
        if (
            not self.is_market_sent
            and not self.is_limit_sent
            and update["side"] == "BUY"
        ):
            if self.sliding_window.push_back(
                float(update["price"]),
                datetime.fromisoformat(update["createdAt"]).timestamp(),
            ):
                min_window_price = self.sliding_window.get_min_value()
                min_window_timestamp = (
                    self.sliding_window.get_timestamp_of_min()
                )
                max_window_price = self.sliding_window.get_max_value()
                max_window_timestamp = (
                    self.sliding_window.get_timestamp_of_max()
                )
                if max_window_price / min_window_price >= (
                    1 + self.settings.signal_threshold
                ):
                    if max_window_timestamp > min_window_timestamp:
                        self.side = "BUY"
                        self.opp_side = "SELL"
                    elif max_window_timestamp < min_window_timestamp:
                        self.side = "SELL"
                        self.opp_side = "BUY"
                    now = datetime.now()
                    self.dispatch_time = now
                    LOGGER.info(
                        f"binance signal: "
                        f"min_in_window={min_window_price}, "
                        f"max_in_window={max_window_price}, "
                        f"min_timestamp={min_window_timestamp}, "
                        f"max_timestamp={max_window_timestamp}"
                    )
                    LOGGER.info(
                        f"Market {self.side} on dydx."
                        f"Price {self.get_price(opposite=False)}, "
                        f"quantity{self.settings.quantity}. "
                        f"Reason: binance signal"
                    )
                    self.dydx_connector.send_market_order(
                        symbol=self.settings.dydx_market,
                        side=self.side,
                        price=self.get_price(opposite=False),
                        quantity=self.settings.quantity,
                    )
                    self.is_market_sent = True
                    asyncio.sleep(self.settings.sec_to_wait)
                    self.sliding_window.clear()

    async def _listen_binance(self):
        self.binance_connector.add_trade_listener(self._binance_trade_listener)
        await self.binance_connector.start()

    async def _close_positions(self):
        while True:
            if self.is_market_sent and self.is_limit_sent:
                if datetime.now() >= (
                    self.dispatch_time + timedelta(seconds=20)
                ):
                    LOGGER.info("Cancel all orders on dydx. Reason: timeout")
                    self.dydx_connector.cancel_all_orders(
                        symbol=self.settings.dydx_market
                    )
                    LOGGER.info(
                        f"Market {self.opp_side} on dydx."
                        f"Price {self.get_price(opposite=False)}, "
                        f"quantity{self.settings.quantity}. "
                        f"Reason: close positions"
                    )
                    self.dydx_connector.send_market_order(
                        symbol=self.settings.dydx_market,
                        side=self.opp_side,
                        price=self.get_price(opposite=True),
                        quantity=self.settings.quantity,
                    )
                    self.is_market_sent = False
                    self.is_limit_sent = False
            await asyncio.sleep(1 / 100)

    def _accout_listener(self, update: dict) -> None:
        if self.is_market_sent:
            if not self.is_limit_sent:
                if (
                    "fills" in update["contents"]
                    and update["contents"]["fills"]
                ):
                    self.is_limit_sent = True
                    LOGGER.info(
                        f"Trailing {self.opp_side} on dydx."
                        f"Price {self.get_price(opposite=True)}, "
                        f"quantity{self.settings.quantity}. "
                        f"Reason: fills"
                    )
                    self.dydx_connector.send_trailing_stop_order(
                        symbol=self.settings.dydx_market,
                        side=self.opp_side,
                        price=self.get_price(opposite=True),
                        quantity=self.settings.quantity,
                        trailing_percent=self.get_trailing_percent(),
                    )
                    price = float(update["contents"]["fills"][0]["price"]) * (
                        1 + self.settings.profit_threshold
                    )
                    LOGGER.info(
                        f"Limit {self.opp_side} on dydx."
                        f"Price {math.ceil(price * 10) / 10}, "
                        f"quantity{self.settings.quantity}. "
                        f"Reason: fills"
                    )
                    self.dydx_connector.send_limit_order(
                        symbol=self.settings.dydx_market,
                        side=self.opp_side,
                        price=math.ceil(price * 10) / 10,
                        quantity=self.settings.quantity,
                    )
            else:
                if (
                    "fills" in update["contents"]
                    and update["contents"]["fills"]
                ):
                    LOGGER.info("Cancel all orders on dydx. Reason: filled")
                    self.dydx_connector.cancel_all_orders(
                        symbol=self.settings.dydx_market
                    )
                    self.is_limit_sent = False
                    self.is_market_sent = False

    async def _listen_our_trades(self):
        self.dydx_connector.add_account_subscription()
        self.dydx_connector.add_account_listener(self._accout_listener)
        await self.dydx_connector.async_start()

    def _setup(self):
        self.loop.set_exception_handler(custom_exception_handler)
        tasks = [
            self.loop.create_task(
                self._listen_binance(), name="listen binance"
            ),
            self.loop.create_task(
                self._listen_our_trades(), name="listen our trades"
            ),
            self.loop.create_task(
                self._close_positions(), name="close positions"
            ),
        ]
        for task in tasks:
            task.add_done_callback(handle_task_result)

    def run(self):
        self._setup()
        self.loop.run_forever()