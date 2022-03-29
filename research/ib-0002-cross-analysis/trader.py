import asyncio
import websockets
import json
from datetime import datetime
from datetime import timedelta
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY
from utils.logger.trader_logger import Logger_debug, Logger_trades


def string_to_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


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
        Logger_debug.exception("Exception raised by task = %r", task)
        raise error


class Trader:
    side: str = ""
    opp_side: str = ""
    dispatch_time: datetime = datetime.now()
    sliding_window: SlidingWindow = SlidingWindow()
    is_market_sent: bool = False
    is_limit_sent: bool = False
    signature = None
    req = None
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
        profit_threshold: float = 0.1,
        sec_to_wait: float = 20,
        sec_after_trade: float = 0,
        signal_threshold: float = 0.0015,
        market=MARKET_ETH_USD,
    ):
        self.trailing_percent = trailing_percent
        self.quantity = quantity
        self.profit_threshold = profit_threshold
        self.market = market
        self.sec_to_wait = sec_to_wait
        self.sec_after_trade = sec_after_trade
        self.signal_threshold = signal_threshold
        self.cycle_counter = 0
        self.start_time = datetime.now()

    def get_limit_price(self, price: str):
        return float(price) * (1 + (
                self.profit_threshold 
                if self.opp_side == "SELL" 
                else (-self.profit_threshold)
            ) / 100
        )

    def get_trailing_percent(self):
        return (
            self.trailing_percent
            if self.opp_side == "BUY"
            else 0 - self.trailing_percent
        )

    def get_worst_price(self, opposite: bool):
        if opposite:
            return 1 if self.opp_side == "SELL" else 10 ** 8
        return 1 if self.side == "SELL" else 10 ** 8

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
                    and trade["T"] / 1000 > self.dispatch_time.second + self.sec_to_wait + 2
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
                            Logger_trades.info(f"r{self.cycle_counter}| market sent, side: {self.side}")
                            self.dydx_connector.send_market_order(
                                symbol=self.market,
                                side=self.side,
                                price=self.get_worst_price(opposite=False),
                                quantity=self.quantity,
                                client_id=f"mk-{self.side}-{self.cycle_counter}-{self.start_time}"
                            )
                            self.is_market_sent = True
                            await asyncio.sleep(self.sec_to_wait + 1)
                            self.cycle_counter += 1
                            self.sliding_window.clear()

    async def _close_positions(self):
        while True:
            if self.is_market_sent and self.is_limit_sent:
                if datetime.now() >= (
                    self.dispatch_time + timedelta(seconds=self.sec_to_wait)
                ):
                    Logger_trades.info(f"r{self.cycle_counter}| timeout reached, cancelling all orders")
                    self.dydx_connector.cancel_all_orders(market=self.market)
                    Logger_trades.info(f"r{self.cycle_counter}| closing position, {self.opp_side}")
                    self.dydx_connector.send_market_order(
                        symbol=self.market,
                        side=self.opp_side,
                        price=self.get_worst_price(opposite=True),
                        quantity=self.quantity,
                    )
                    self.is_market_sent = False
                    self.is_limit_sent = False
            await asyncio.sleep(1 / 100)
    
    def account_listener(self, account_update):
        for order_update in account_update["contents"]["orders"]:
            if order_update["status"] == "CANCELED":
                if order_update["clientId"].startswith("mk"):
                    Logger_trades.info(f"r{self.cycle_counter}| market cancelled, {order_update['cancelReason']}, clientId: {order_update['clientId']}")
                elif order_update["clientId"].startswith("lm"):
                    Logger_trades.info(f"r{self.cycle_counter}| limit cancelled, {order_update['cancelReason']}, clientId: {order_update['clientId']}")
                elif order_update["clientId"].startswith("ts"):
                    Logger_trades.info(f"r{self.cycle_counter}| trailing cancelled, {order_update['cancelReason']}, clientId: {order_update['clientId']}")
        
        if "fills" not in account_update["contents"]: return

        for fill in account_update["contents"]["fills"]:
            if fill["orderClientId"].startswith("mk"):
                self.market_fill_listener(fill)
            elif fill["orderClientId"].startswith("lm"):
                self.limit_fill_listener(fill)
            elif fill["orderClientId"].startswith("ts"):
                self.trailing_fill_listener(fill)
        

    def market_fill_listener(self, fill):
        self.market_price = float(fill["price"])
        limit_price = self.get_limit_price(self.market_price)

        self.dydx_connector.send_trailing_stop_order(
            symbol=self.market,
            side=self.opp_side,
            price=self.get_worst_price(opposite=True),
            quantity=self.quantity,
            trailing_percent=self.get_trailing_percent(),
            client_id=f"ts-{self.side}-{self.cycle_counter}-{self.start_time}"
        )
        Logger_trades.info(f"r{self.cycle_counter}| trailing sent, {self.opp_side}, percent: {self.trailing_percent}")

        self.dydx_connector.send_limit_order(
            symbol=self.market,
            side=self.opp_side,
            price=round(limit_price + 0.05, 1),
            quantity=self.quantity,
            client_id=f"lm-{self.side}-{self.cycle_counter}-{self.start_time}"
        )
        Logger_trades.info(f"r{self.cycle_counter}| limit sent, {self.opp_side}, price: {limit_price}")

        self.is_limit_sent = True

    def limit_fill_listener(self, fill):
        if not self.is_limit_sent: return
        if not self.is_limit_sent: return

        Logger_trades.info(f"r{self.cycle_counter}| limit filled, profit: {abs(float(fill['price']) - self.market_price)}")
        self.dydx_connector.cancel_all_orders(market=self.market)
        self.is_limit_sent = False
        self.is_market_sent = False

    def trailing_fill_listener(self, fill):
        if not self.is_limit_sent: return
        if not self.is_limit_sent: return

        Logger_trades.info(f"r{self.cycle_counter}| trailing filled, loss: {abs(self.market_price - float(fill['price']))}")
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
            self.loop.create_task(
                self._close_positions(), name="close positions"
            ),
        ]
        for task in tasks:
            task.add_done_callback(handle_task_result)

    def run(self):
        self.dydx_connector.add_account_subscription()
        self.dydx_connector.add_account_listener(self.account_listener)
        self._setup()
        self.loop.run_forever()
