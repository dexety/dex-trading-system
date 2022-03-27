import asyncio
import websockets
import json
import math
from datetime import datetime
from datetime import timedelta
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY
from dydx3.helpers.request_helpers import generate_now_iso
from utils.logger.trader_logger import Logger_debug, Logger_trades


def string_to_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def custom_exception_handler(loop, context):
    loop.default_exception_handler(context)
    exception = context.get('exception')
    if isinstance(exception, Exception):
        loop.stop()
        loop.close()


def handle_task_result(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as error:
        Logger_debug.exception('Exception raised by task = %r', task)
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
    socket_dydx = f"wss://api.stage.dydx.exchange/v3/ws"
    connector = DydxConnector(
        [MARKET_ETH_USD],
    )
    loop = asyncio.get_event_loop()

    def __init__(self,
                 trailing_percent: float = 0.14,
                 quantity: float = 0.02,
                 profit_threshold: float = 0.1,
                 sec_to_wait: float = 20,
                 sec_after_trade: float = 0,
                 signal_threshold: float = 0.0001,
                 market=MARKET_ETH_USD):
        self.trailing_percent = trailing_percent
        self.quantity = quantity
        self.profit_threshold = profit_threshold
        self.market = market
        self.sec_to_wait = sec_to_wait
        self.sec_after_trade = sec_after_trade
        self.signal_threshold = signal_threshold

    def get_trailing_percent(self):
        return self.trailing_percent if self.opp_side == "BUY" else 0 - self.trailing_percent

    def get_price(self, opposite: bool):
        if opposite:
            return 1 if self.opp_side == "SELL" else 10 ** 8
        return 1 if self.side == "SELL" else 10 ** 8

    async def _listen_binance(self):
        async with websockets.connect(self.socket_binance, ping_interval=None) as sock:
            while True:
                data = await sock.recv()
                json_data = json.loads(data)
                if not self.is_market_sent and not self.is_limit_sent and not json_data["m"]:
                    if self.sliding_window.push_back(float(json_data["p"]), json_data["T"]):
                        max_in_window = self.sliding_window.get_max()
                        max_timestamp = self.sliding_window.get_max_timestamp()
                        min_in_window = self.sliding_window.get_min()
                        min_timestamp = self.sliding_window.get_min_timestamp()
                        if max_in_window / min_in_window >= (1 + self.signal_threshold):
                            if max_timestamp > min_timestamp:
                                self.side = "BUY"
                                self.opp_side = "SELL"
                            elif max_timestamp < min_timestamp:
                                self.side = "SELL"
                                self.opp_side = "BUY"
                            now = datetime.now()
                            self.dispatch_time = now
                            Logger_trades.info(f"Market,Signal,{self.side}")
                            self.connector.send_market_order(
                                symbol=self.market,
                                side=self.side,
                                price=self.get_price(opposite=False),
                                quantity=self.quantity,
                            )
                            self.is_market_sent = True
                            await asyncio.sleep(self.sec_to_wait)
                            self.sliding_window.clear()

    async def _close_positions(self):
        while True:
            if self.is_market_sent and self.is_limit_sent:
                if datetime.now() >= (self.dispatch_time + timedelta(seconds=20)):
                    Logger_trades.info("Cancel,TimeOut")
                    self.connector.cancel_all_orders(market=self.market)
                    Logger_trades.info(f"Market,Close,{self.opp_side}")
                    self.connector.send_market_order(
                        symbol=self.market,
                        side=self.opp_side,
                        price=self.get_price(opposite=True),
                        quantity=self.quantity,
                    )
                    self.is_market_sent = False
                    self.is_limit_sent = False
            await asyncio.sleep(1 / 100)

    async def _listen_our_trades(self):
        async with websockets.connect(self.socket_dydx, ping_interval=None) as sock:
            await sock.send(json.dumps(self.req))
            await sock.recv()  # trash response
            await sock.recv()  # trash response
            while True:
                data = await sock.recv()
                if self.is_market_sent:
                    json_data = json.loads(data)
                    if not self.is_limit_sent:
                        if "fills" in json_data["contents"] and json_data["contents"]["fills"]:
                            self.is_limit_sent = True
                            Logger_trades.info(f"Trailing,{self.opp_side},{str(self.trailing_percent)}")
                            self.connector.send_trailing_stop_order(
                                symbol=self.market,
                                side=self.opp_side,
                                price=self.get_price(opposite=True),
                                quantity=self.quantity,
                                trailing_percent=self.get_trailing_percent()
                            )
                            price = float(json_data["contents"]["fills"][0]["price"]) * (1 + self.profit_threshold)
                            Logger_trades.info(f"Limit,{self.opp_side},{str(price)}")
                            self.connector.send_limit_order(
                                symbol=self.market,
                                side=self.opp_side,
                                price=math.ceil(price * 10) / 10,
                                quantity=self.quantity,
                            )
                    else:
                        if "fills" in json_data["contents"] and json_data["contents"]["fills"]:
                            Logger_trades.info("Cancel,Filled")
                            self.connector.cancel_all_orders(market=self.market)
                            self.is_limit_sent = False
                            self.is_market_sent = False

    def _fill_signature_and_req(self):
        now_iso_string = generate_now_iso()

        self.signature = self.connector.get_client().private.sign(
            request_path="/ws/accounts",
            method="GET",
            iso_timestamp=now_iso_string,
            data={},
        )

        self.req = {
            "type": "subscribe",
            "channel": "v3_accounts",
            "accountNumber": "0",
            "apiKey": self.connector.get_client().api_key_credentials["key"],
            "passphrase": self.connector.get_client().api_key_credentials[
                "passphrase"
            ],
            "timestamp": now_iso_string,
            "signature": self.signature,
        }

    def _setup(self):
        self.loop.set_exception_handler(custom_exception_handler)
        tasks = [self.loop.create_task(self._listen_binance(), name="listen binance"),
                 self.loop.create_task(self._listen_our_trades(), name="listen our trades"),
                 self.loop.create_task(self._close_positions(), name="close positions")]
        for task in tasks:
            task.add_done_callback(handle_task_result)

    def run(self):
        self._setup()
        self._fill_signature_and_req()
        self.loop.run_forever()
