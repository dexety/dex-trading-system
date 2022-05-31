import asyncio
import contextlib
import dataclasses
import json
import random
from datetime import datetime
import websockets

from connectors.dydx.connector import DydxConnector
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
    dydx_symbol: str
    dydx_network: str
    round_digits: int


class Trader:
    # pylint: disable=line-too-long
    # pylint: disable=too-many-branches
    # pylint: disable=too-few-public-methods
    maker_comission = 0.0002
    taker_comission = 0.0005
    symbol_binance = "btcusd_perp"
    socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"

    def __init__(self, settings: Settings):
        self.trailing_percent = settings.trailing_percent
        self.quantity = settings.quantity
        self.profit_threshold = settings.profit_threshold
        self.sec_to_wait = settings.sec_to_wait
        self.sec_after_trade = settings.sec_after_trade
        self.signal_threshold = settings.signal_threshold
        self.dydx_symbol = settings.dydx_symbol
        self.dydx_network = settings.dydx_network
        self.round_digits = settings.round_digits

        self.cycle_counter = 0

        self.start_time = datetime.now()
        self.dispatch_time = datetime.now()
        self.sliding_window = SlidingWindow()

        self.market_filled_or_canceled = asyncio.Event()
        self.limit_filled_or_canceled = asyncio.Event()
        self.trailing_filled_or_canceled = asyncio.Event()
        self.mirror_filled = asyncio.Event()
        self.position_closed = asyncio.Event()

        self.side = "BUY"
        self.opp_side = "SELL"

        self.is_market_filled = False
        self.is_limit_filled = False
        self.is_trailing_filled = False
        self.is_closing_filled = False

        self.is_limit_opened = False
        self.is_trailing_opened = False

        self.openeng_fill = {}
        self.closing_fill = {}

        self.dydx_connector = DydxConnector(
            symbols=[self.dydx_symbol],
            network=self.dydx_network,
        )
        LOGGER.info(
            f"Trader initiated. {self.dydx_network} {self.dydx_symbol}."
        )

        self.loop = asyncio.get_event_loop()

    def _get_limit_price(self, price: str) -> str:
        (multiplier, add_for_round) = (
            (1 + self.profit_threshold, 0.5 / (10 ** self.round_digits))
            if self.opp_side == "SELL"
            else (1 - self.profit_threshold, -0.5 / (10 ** self.round_digits))
        )
        limit_price = round(
            float(price) * multiplier + add_for_round, self.round_digits
        )
        return str(limit_price)

    def _get_trailing_percent(self) -> str:
        return str(
            self.trailing_percent
            if self.opp_side == "BUY"
            else -self.trailing_percent
        )

    @staticmethod
    def _get_worst_price(side: str) -> str:
        return str(1 if side == "SELL" else 10 ** 8)

    def _get_profit(self, closed_by_limit=False):
        closing_price = float(self.closing_fill["price"])
        opening_price = float(self.openeng_fill["price"])
        closing_comission = (
            closing_price * self.quantity * self.maker_comission
            if closed_by_limit
            else self.taker_comission
        )
        opening_comission = opening_price * self.quantity * self.taker_comission
        return (
            (closing_price - opening_price)
            * self.quantity
            * (-1 if self.side == "SELL" else 1)
            - closing_comission
            - opening_comission
        )

    def _update_window(self, price: float, time: int) -> bool:
        if random.random() < 0.01:
            max_in_window = self.sliding_window.get_max_value()
            min_in_window = self.sliding_window.get_min_value()
            LOGGER.debug(
                f"Binance trade listener is still alive.\n"
                f"Current jump: {max_in_window / min_in_window}\n"
            )
        if self.sliding_window.push_back(price, time):
            max_in_window = self.sliding_window.get_max_value()
            min_in_window = self.sliding_window.get_min_value()
            if max_in_window / min_in_window >= (1 + self.signal_threshold):
                timestamp_of_max = self.sliding_window.get_timestamp_of_max()
                timestamp_of_min = self.sliding_window.get_timestamp_of_min()
                if timestamp_of_max > timestamp_of_min:
                    self.side = "BUY"
                    self.opp_side = "SELL"
                elif timestamp_of_max < timestamp_of_min:
                    self.side = "SELL"
                    self.opp_side = "BUY"
                else:
                    return False
                return True
        return False

    async def _listen_binance(self):
        async with websockets.connect(
            self.socket_binance, ping_interval=None
        ) as sock:
            while True:
                data = await sock.recv()
                trade = json.loads(data)
                # m -- side ("BUY" == 0, "SELL" == 1)
                # T -- milliseconds timestamp
                # p -- price
                if (
                    not trade["m"]
                    and trade["T"] / 1000
                    > self.dispatch_time.second + self.sec_to_wait + 0.5
                ):
                    if self._update_window(float(trade["p"]), int(trade["T"])):
                        await self._initiate_trade_cycle()

    async def _initiate_trade_cycle(self):
        LOGGER.info(
            "--------------------------------------------------------------"
        )
        self.cycle_counter += 1

        self.dispatch_time = datetime.now()
        self._send_market()
        LOGGER.info(
            f"cycle {self.cycle_counter} | market sent | side: {self.side}"
        )

        await self.market_filled_or_canceled.wait()
        if not self.is_market_filled:
            self._reset()
            return

        limit_price = self._get_limit_price(self.openeng_fill["price"])

        self._send_limit(limit_price)
        LOGGER.info(
            f"cycle {self.cycle_counter} | limit sent | {self.opp_side} | price: {limit_price}"
        )

        self._send_trailing()
        # await self.trailing_opened_or_canceled()
        # TODO: то же самое, но еще нужно будет отменить limit
        LOGGER.info(
            f"cycle {self.cycle_counter} | trailing sent | {self.opp_side} | percent: {self.trailing_percent}"
        )

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.mirror_filled.wait(), self.sec_to_wait)

        if self.mirror_filled.is_set():
            if self.is_limit_filled:
                LOGGER.info(
                    f"cycle {self.cycle_counter} | limit filled | price: {self.closing_fill['price']} | profit: {self._get_profit(closed_by_limit=True)}"
                )
            elif self.is_trailing_filled:
                LOGGER.info(
                    f"cycle {self.cycle_counter} | trailing filled | price: {self.closing_fill['price']} | profit: {self._get_profit()}"
                )
            self._cancel_orders()
        else:
            LOGGER.info(
                f"cycle {self.cycle_counter} | timeout reached | cancelling all orders"
            )
            self._cancel_orders()

            if self.is_limit_opened:
                await self.limit_filled_or_canceled.wait()
                if self.is_limit_filled:
                    LOGGER.info(
                        f"cycle {self.cycle_counter} | limit filled | price: {self.closing_fill['price']} | profit: {self._get_profit(closed_by_limit=True)}"
                    )
                    self._reset()
                    return

            if self.is_trailing_opened:
                await self.trailing_filled_or_canceled.wait()
                if self.is_trailing_filled:
                    LOGGER.info(
                        f"cycle {self.cycle_counter} | trailing filled | price: {self.closing_fill['price']} | profit: {self._get_profit()}"
                    )
                    self._reset()
                    return

            LOGGER.info(
                f"cycle {self.cycle_counter} | orders canceled, closing position | {self.opp_side}"
            )
            self._close_position()
            await self.position_closed.wait()
            LOGGER.info(
                f"cycle {self.cycle_counter} | position closed | price: {self.closing_fill['price']} | profit: {self._get_profit()}"
            )

        self._reset()

    def _reset(self):
        self.market_filled_or_canceled.clear()
        self.limit_filled_or_canceled.clear()
        self.trailing_filled_or_canceled.clear()
        self.mirror_filled.clear()
        self.position_closed.clear()
        self.sliding_window.clear()

        self.is_market_filled = False
        self.is_limit_filled = False
        self.is_trailing_filled = False

        self.is_limit_opened = False
        self.is_trailing_opened = False

    def _send_market(self):
        self.dydx_connector.send_market_order(
            symbol=self.dydx_symbol,
            side=self.side,
            price=Trader._get_worst_price(self.side),
            quantity=str(self.quantity),
            client_id=f"mk-{self.side}-{self.cycle_counter}-{self.start_time}",  # MarKet
        )

    def _send_trailing(self):
        self.dydx_connector.send_trailing_stop_order(
            symbol=self.dydx_symbol,
            side=self.opp_side,
            price=Trader._get_worst_price(self.opp_side),
            quantity=str(self.quantity),
            trailing_percent=self._get_trailing_percent(),
            client_id=f"ts-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # Trailing Stop
        )

    def _send_limit(self, limit_price):
        self.dydx_connector.send_limit_order(
            symbol=self.dydx_symbol,
            side=self.opp_side,
            price=limit_price,
            quantity=str(self.quantity),
            client_id=f"lm-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # LiMit
        )

    def _close_position(self):
        self.dydx_connector.send_market_order(
            symbol=self.dydx_symbol,
            side=self.opp_side,
            price=Trader._get_worst_price(self.opp_side),
            quantity=str(self.quantity),
            client_id=f"cp-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # Close Position
        )

    def _cancel_orders(self):
        self.dydx_connector.cancel_all_orders(symbol=self.dydx_symbol)

    def _account_listener(self, account_update):
        if "contents" not in account_update:
            return

        if "fills" in account_update["contents"]:
            for fill in account_update["contents"]["fills"]:
                if fill["orderClientId"].startswith("mk"):
                    self.is_market_filled = True
                    self.openeng_fill = fill
                elif fill["orderClientId"].startswith("lm"):
                    self.is_limit_filled = True
                    self.closing_fill = fill
                elif fill["orderClientId"].startswith("ts"):
                    self.is_trailing_filled = True
                    self.closing_fill = fill
                elif fill["orderClientId"].startswith("cp"):
                    self.is_closing_filled = True
                    self.closing_fill = fill

        if "orders" in account_update["contents"]:
            for order in account_update["contents"]["orders"]:
                LOGGER.info(
                    f"UPDATE | {order['clientId']} {order['status']} | {order['cancelReason']}"
                )

                if order["status"] == "CANCELED":
                    if order["clientId"].startswith("mk"):
                        self.market_filled_or_canceled.set()
                    elif order["clientId"].startswith("lm"):
                        self.limit_filled_or_canceled.set()
                    elif order["clientId"].startswith("ts"):
                        self.trailing_filled_or_canceled.set()

                elif order["status"] == "FILLED":
                    if order["clientId"].startswith("mk"):
                        self.market_filled_or_canceled.set()
                    elif order["clientId"].startswith("lm"):
                        self.limit_filled_or_canceled.set()
                        self.mirror_filled.set()
                    elif order["clientId"].startswith("ts"):
                        self.trailing_filled_or_canceled.set()
                        self.mirror_filled.set()
                    elif order["clientId"].startswith("cp"):
                        self.position_closed.set()

                elif order["status"] == "OPEN":
                    if order["clientId"].startswith("lm"):
                        self.is_limit_opened = True

                elif order["status"] == "UNTRIGGERED":
                    if order["clientId"].startswith("ts"):
                        self.is_trailing_opened = True

    def _setup(self):
        self.loop.set_exception_handler(custom_exception_handler)
        tasks = [
            self.loop.create_task(
                self._listen_binance(), name="listen binance"
            ),
            self.loop.create_task(
                self.dydx_connector.async_start(),
                name="dydx connector async start",
            ),
        ]
        for task in tasks:
            task.add_done_callback(handle_task_result)

    def run(self):
        self.dydx_connector.add_account_subscription()
        self.dydx_connector.add_account_listener(self._account_listener)
        self._setup()
        self.loop.run_forever()
