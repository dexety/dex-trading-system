import asyncio
import websockets
import json
import contextlib
from datetime import datetime
from mmqueue import MMQueue
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_ETH_USD
from utils.logger.trader_logger import DebugLogger, TradeLogger


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
        DebugLogger.exception("Exception raised by task = %r", task)
        raise error


class Trader:
    maker_comission = 0.0002
    taker_comission = 0.0005

    symbol_binance = "btcusd_perp"
    socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"
    network = "ropsten"
    symbol = MARKET_ETH_USD

    time_measurements = [
        "from_last_trade_to_jump_detected",
        "from_jump_detected_to_market_sending",
        "from_market_sending_to_market_sent",
        "from_market_sent_to_market_processed",
        "from_market_processed_to_limit_sending",
        "from_limit_sending_to_limit_sent",
        "from_limit_sent_to_trailing_sending",
        "from_trailing_sending_to_trailing_sent",
    ]

    def __init__(
        self,
        trailing_percent: float = 0.14,
        quantity: float = 0.01,
        profit_threshold: float = 0.0007,
        sec_to_wait: float = 20,
        sec_after_trade: float = 0,
        signal_threshold: float = 0.0003,
        round_digits: int = 1,
        symbol=MARKET_ETH_USD,
    ):
        self.trailing_percent = trailing_percent
        self.quantity = quantity
        self.profit_threshold = profit_threshold
        self.symbol = symbol
        self.sec_to_wait = sec_to_wait
        self.sec_after_trade = sec_after_trade
        self.signal_threshold = signal_threshold
        self.round_digits = round_digits

        self.cycle_counter = 0

        self.start_time = datetime.now()
        self.dispatch_time = datetime.now()
        self.sliding_window = SlidingWindow()

        self.market_filled_or_canceled = asyncio.Event()
        self.limit_filled_or_canceled = asyncio.Event()
        self.trailing_filled_or_canceled = asyncio.Event()
        self.mirror_filled = asyncio.Event()
        self.position_closed = asyncio.Event()

        self.is_market_filled = False
        self.is_limit_filled = False
        self.is_trailing_filled = False

        self.is_limit_opened = False
        self.is_trailing_opened = False

        self.openeng_fill = dict()
        self.closing_fill = dict()

        self.dydx_connector = DydxConnector(
            symbols=[self.symbol],
            network=self.network,
        )
        TradeLogger.info(f"Trader initiated. {self.network} {self.symbol}.")

        self.current_measurement = list(
            [0 for _ in range(len(self.time_measurements))]
        )

        with open("logs/time_measurements.log", "w") as out:
            print(*self.time_measurements, file=out, sep=",")

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

    def _get_worst_price(self, side: str) -> str:
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
        if self.sliding_window.push_back(
                price, time
        ):
            max_in_window = self.sliding_window.get_max()
            max_timestamp = self.sliding_window.get_max_timestamp()
            min_in_window = self.sliding_window.get_min()
            min_timestamp = self.sliding_window.get_min_timestamp()
            if max_in_window / min_in_window >= (
                    1 + self.signal_threshold
            ):
                if max_timestamp > min_timestamp:
                    self.side = "BUY"
                    self.opp_side = "SELL"
                elif max_timestamp < min_timestamp:
                    self.side = "SELL"
                    self.opp_side = "BUY"
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

                    if (
                        self._update_window(float(trade["p"]), int(trade["T"]))
                    ):
                        jump_detected = datetime.now()
                        last_binance_trade = datetime.fromtimestamp(
                            trade["T"] / 1000
                        )
                        self.current_measurement[0] = (
                            jump_detected - last_binance_trade
                        )
                        TradeLogger.info(
                            "--------------------------------------------------------------"
                        )
                        self.cycle_counter += 1

                        self.dispatch_time = datetime.now()
                        market_sending = datetime.now()
                        self.current_measurement[1] = (
                            market_sending - jump_detected
                        )
                        self._send_market()
                        market_sent = datetime.now()
                        self.current_measurement[2] = (
                            market_sent - market_sending
                        )
                        TradeLogger.info(
                            f"cycle {self.cycle_counter} | market sent | side: {self.side}"
                        )

                        await self.market_filled_or_canceled.wait()
                        market_processed = datetime.now()
                        self.current_measurement[3] = (
                            market_processed - market_sent
                        )
                        if not self.is_market_filled:
                            self._reset()
                            continue

                        limit_price = self._get_limit_price(
                            self.openeng_fill["price"]
                        )

                        limit_sending = datetime.now()
                        self.current_measurement[4] = (
                            limit_sending - market_processed
                        )
                        self._send_limit(limit_price)
                        limit_sent = datetime.now()
                        self.current_measurement[5] = limit_sent - limit_sending
                        # await self.limit_opened_or_canceled()
                        # TODO: нужно будет обработать вариант, когда лимитка по какой то причине не поставилась. В таком случае закрываем позицию.
                        TradeLogger.info(
                            f"cycle {self.cycle_counter} | limit sent | {self.opp_side} | price: {limit_price}"
                        )

                        trailing_sending = datetime.now()
                        self.current_measurement[6] = (
                            trailing_sending - limit_sent
                        )
                        self._send_trailing()
                        trailing_sent = datetime.now()
                        self.current_measurement[7] = (
                            trailing_sent - trailing_sending
                        )
                        # await self.trailing_opened_or_canceled()
                        # TODO: то же самое, но еще нужно будет отменить limit
                        TradeLogger.info(
                            f"cycle {self.cycle_counter} | trailing sent | {self.opp_side} | percent: {self.trailing_percent}"
                        )

                        with contextlib.suppress(asyncio.TimeoutError):
                            await asyncio.wait_for(
                                self.mirror_filled.wait(), self.sec_to_wait
                            )

                        if self.mirror_filled.is_set():
                            if self.is_limit_filled:
                                TradeLogger.info(
                                    f"cycle {self.cycle_counter} | limit filled | price: {self.closing_fill['price']} | profit: {self._get_profit(closed_by_limit=True)}"
                                )
                            elif self.is_trailing_filled:
                                TradeLogger.info(
                                    f"cycle {self.cycle_counter} | trailing filled | price: {self.closing_fill['price']} | profit: {self._get_profit()}"
                                )
                            self._cancel_orders()
                        else:
                            TradeLogger.info(
                                f"cycle {self.cycle_counter} | timeout reached | cancelling all orders"
                            )
                            self._cancel_orders()

                            if self.is_limit_opened:
                                await self.limit_filled_or_canceled.wait()
                                if self.is_limit_filled:
                                    TradeLogger.info(
                                        f"cycle {self.cycle_counter} | limit filled | price: {self.closing_fill['price']} | profit: {self._get_profit(closed_by_limit=True)}"
                                    )
                                    self._reset()
                                    continue

                            if self.is_trailing_opened:
                                await self.trailing_filled_or_canceled.wait()
                                if self.is_trailing_filled:
                                    TradeLogger.info(
                                        f"cycle {self.cycle_counter} | trailing filled | price: {self.closing_fill['price']} | profit: {self._get_profit()}"
                                    )
                                    self._reset()
                                    continue

                            TradeLogger.info(
                                f"cycle {self.cycle_counter} | orders canceled, closing position | {self.opp_side}"
                            )
                            self._close_position()
                            await self.position_closed.wait()
                            TradeLogger.info(
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

        with open("logs/time_measurements.log", "a") as out:
            print(*self.current_measurement, file=out, sep=",")

        self.current_measurement = list(
            [0 for _ in range(len(self.time_measurements))]
        )

    def _send_market(self):
        self.dydx_connector.send_market_order(
            symbol=self.symbol,
            side=self.side,
            price=self._get_worst_price(side=self.side),
            quantity=str(self.quantity),
            client_id=f"mk-{self.side}-{self.cycle_counter}-{self.start_time}",  # MarKet
        )

    def _send_trailing(self):
        self.dydx_connector.send_trailing_stop_order(
            symbol=self.symbol,
            side=self.opp_side,
            price=self._get_worst_price(side=self.opp_side),
            quantity=str(self.quantity),
            trailing_percent=self._get_trailing_percent(),
            client_id=f"ts-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # Trailing Stop
        )

    def _send_limit(self, limit_price):
        self.dydx_connector.send_limit_order(
            symbol=self.symbol,
            side=self.opp_side,
            price=limit_price,
            quantity=str(self.quantity),
            client_id=f"lm-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # LiMit
        )

    def _close_position(self):
        self.dydx_connector.send_market_order(
            symbol=self.symbol,
            side=self.opp_side,
            price=self._get_worst_price(side=self.opp_side),
            quantity=str(self.quantity),
            client_id=f"cp-{self.opp_side}-{self.cycle_counter}-{self.start_time}",  # Close Position
        )

    def _cancel_orders(self):
        self.dydx_connector.cancel_all_orders(symbol=self.symbol)

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
                TradeLogger.info(
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
