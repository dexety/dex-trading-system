import asyncio
import websockets
import json
from datetime import datetime
from datetime import timedelta
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY
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
    side: str = ""
    opp_side: str = ""
    dispatch_time: datetime = datetime.now()
    sliding_window: SlidingWindow = SlidingWindow()
    is_market_sent: bool = False
    is_limit_sent: bool = False
    symbol_binance = "btcusd_perp"
    socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"

    dydx_connector = DydxConnector(
        symbols=[MARKET_ETH_USD],
    )

    loop = asyncio.get_event_loop()

    def __init__(
        self,
        trailing_percent: float = 0.14,
        quantity: float = 0.02,
        profit_threshold: float = 0.00001,
        sec_to_wait: float = 20,
        sec_after_trade: float = 0,
        signal_threshold: float = 0.000015,
        round_digits: int = 1,
        market=MARKET_ETH_USD,
    ):
        self.trailing_percent = trailing_percent
        self.quantity = str(quantity)
        self.profit_threshold = profit_threshold
        self.market = market
        self.sec_to_wait = sec_to_wait
        self.sec_after_trade = sec_after_trade
        self.signal_threshold = signal_threshold
        self.round_digits = round_digits
        self.cycle_counter = 0
        self.start_time = datetime.now()

    def _get_limit_price(self, price: str) -> str:
        (multiplier, add_for_round) = ( 
            (1 + self.profit_threshold, 0.5 / (10 ** self.round_digits))
            if self.opp_side == "SELL" 
            else (1 - self.profit_threshold, -0.5 / (10 ** self.round_digits))
        )
        limit_price = round(float(price) * multiplier + add_for_round, self.round_digits)
        return str(limit_price)

    def _get_trailing_percent(self) -> str:
        return str(
            self.trailing_percent
            if self.opp_side == "BUY"
            else -self.trailing_percent
        )

    def _get_worst_price(self, side: str) -> str:
        return str(1 if side == "SELL" else 10 ** 8)

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
                    not self.is_market_sent
                    and not self.is_limit_sent
                    and not trade["m"]
                    and trade["T"] / 1000 > self.dispatch_time.second + self.sec_to_wait + 0.5
                ):
                    if self.sliding_window.push_back(
                        float(trade["p"]), trade["T"]
                    ):
                        max_in_window = self.sliding_window.get_max()
                        max_timestamp = self.sliding_window.get_max_timestamp()
                        min_in_window = self.sliding_window.get_min()
                        min_timestamp = self.sliding_window.get_min_timestamp()
                        if max_in_window / min_in_window >= 1 + self.signal_threshold:
                            if max_timestamp > min_timestamp:
                                self.side = "BUY"
                                self.opp_side = "SELL"
                            elif max_timestamp < min_timestamp:
                                self.side = "SELL"
                                self.opp_side = "BUY"
                            
                            self.dispatch_time = datetime.now()
                            TradeLogger.info(f"cycle {self.cycle_counter} | market sent | side: {self.side}")
                            self.dydx_connector.send_market_order(
                                symbol=self.market,
                                side=self.side,
                                price=self._get_worst_price(side=self.side),
                                quantity=self.quantity,
                                client_id=f"mk-{self.side}-{self.cycle_counter}-{self.start_time}"
                            )
                            self.is_market_sent = True
                            timeout = asyncio.Event()
                            close_positions_task = asyncio.create_task(self._close_positions(timeout))
                            await asyncio.sleep(self.sec_to_wait)
                            timeout.set()
                            await close_positions_task
                            self.cycle_counter += 1
                            self.sliding_window.clear()

    async def _close_positions(self, timeout: asyncio.Event):
        await timeout.wait()
        if self.is_market_sent and self.is_limit_sent:
            TradeLogger.info(f"cycle {self.cycle_counter} | timeout reached | cancelling all orders")
            self.dydx_connector.cancel_all_orders(market=self.market)
            TradeLogger.info(f"cycle {self.cycle_counter} | closing position | {self.opp_side}")
            self.dydx_connector.send_market_order(
                symbol=self.market,
                side=self.opp_side,
                price=self._get_worst_price(side=self.opp_side),
                quantity=self.quantity,
                client_id=f"cp-{self.side}-{self.cycle_counter}-{self.start_time}"
            )
            self.is_market_sent = False
            self.is_limit_sent = False

    def _account_listener(self, account_update):
        for order in account_update["contents"]["orders"]:
            TradeLogger.info(f"UPDATE | {order['clientId']} {order['status']} | {order['cancelReason']}")
        
        if "fills" not in account_update["contents"]:
            return

        for fill in account_update["contents"]["fills"]:
            if fill["orderClientId"].startswith("mk"):
                self._market_fill_listener(fill)
            elif fill["orderClientId"].startswith("lm"):
                self._limit_fill_listener(fill)
            elif fill["orderClientId"].startswith("ts"):
                self._trailing_fill_listener(fill)
        

    def _market_fill_listener(self, fill):
        self.market_price = float(fill["price"])
        limit_price = self._get_limit_price(self.market_price)

        self.dydx_connector.send_trailing_stop_order(
            symbol=self.market,
            side=self.opp_side,
            price=self._get_worst_price(side=self.opp_side),
            quantity=self.quantity,
            trailing_percent=self._get_trailing_percent(),
            client_id=f"ts-{self.side}-{self.cycle_counter}-{self.start_time}"
        )
        TradeLogger.info(f"cycle {self.cycle_counter} | trailing sent | {self.opp_side} | percent: {self.trailing_percent}")

        self.dydx_connector.send_limit_order(
            symbol=self.market,
            side=self.opp_side,
            price=limit_price,
            quantity=self.quantity,
            client_id=f"lm-{self.side}-{self.cycle_counter}-{self.start_time}"
        )
        TradeLogger.info(f"cycle {self.cycle_counter} | limit sent | {self.opp_side} | price: {limit_price}")

        self.is_limit_sent = True

    def _limit_fill_listener(self, fill):
        if not self.is_limit_sent:
            return
        if not self.is_market_sent:
            return

        TradeLogger.info(f"cycle {self.cycle_counter} | limit filled | price: {fill['price']} | profit: {abs(float(fill['price']) - self.market_price)}")
        self.dydx_connector.cancel_all_orders(market=self.market)
        self.is_limit_sent = False
        self.is_market_sent = False

    def _trailing_fill_listener(self, fill):
        if not self.is_limit_sent:
            return
        if not self.is_market_sent:
            return

        TradeLogger.info(f"cycle {self.cycle_counter}| trailing filled | price: {fill['price']} | loss: {abs(self.market_price - float(fill['price']))}")
        self.dydx_connector.cancel_all_orders(market=self.market)
        self.is_limit_sent = False
        self.is_market_sent = False

    def _setup(self):
        self.loop.set_exception_handler(custom_exception_handler)
        tasks = [
            self.loop.create_task(
                self._listen_binance(), name="listen binance"
            ),
            self.loop.create_task(
                self.dydx_connector.async_start(), name="dydx connector async start"
            ),
        ]
        for task in tasks:
            task.add_done_callback(handle_task_result)

    def run(self):
        self.dydx_connector.add_account_subscription()
        self.dydx_connector.add_account_listener(self._account_listener)
        self._setup()
        self.loop.run_forever()
