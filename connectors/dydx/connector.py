import json
from datetime import datetime
import asyncio
from typing import Callable
from functools import wraps
import websockets
from web3 import Web3
from tqdm import tqdm

from dydx3 import Client
from dydx3.constants import API_HOST_MAINNET, TIME_IN_FORCE_IOC, API_HOST_ROPSTEN
from dydx3.constants import NETWORK_ID_MAINNET, WS_HOST_MAINNET, NETWORK_ID_ROPSTEN, WS_HOST_ROPSTEN
from dydx3.constants import POSITION_STATUS_OPEN
from dydx3.constants import POSITION_STATUS_CLOSED
from dydx3.constants import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, ORDER_TYPE_TRAILING_STOP
from dydx3.constants import TIME_IN_FORCE_GTT
from dydx3.constants import ORDER_STATUS_OPEN
from dydx3.errors import DydxApiError

from connectors.dydx.order_book_cache import OrderBookCache


def safe_execute(f: Callable):
    @wraps(f)
    def wrapper(*args, **kwargs):
        num_of_connection_attempts = 50
        for _ in range(num_of_connection_attempts):
            try:
                return f(*args, **kwargs)
            except DydxApiError as error:
                raise error
            except Exception as error:
                print(
                    "Basic exception while executing function",
                    f.__name__,
                    ":",
                    error,
                )
        raise Exception("DydxConnecotor error")

    return wrapper


class DydxConnector:
    order_book = {}
    symbols_info = {}
    subscriptions = []

    orderbook_listeners = []
    account_listeners = []
    trades_listeners = []
    num_of_connection_attempts = 50

    def __init__(
        self,
        eth_address: str,
        eth_private_key: str,
        symbols: list,
        eth_node_url="http://localhost:8545",
    ) -> None:
        self.eth_address = eth_address
        self.eth_private_key = eth_private_key
        self.eth_node_url = eth_node_url
        self.sync_client = Client(
            network_id=NETWORK_ID_ROPSTEN,
            host=API_HOST_ROPSTEN,
            default_ethereum_address=self.eth_address,
            eth_private_key=self.eth_private_key,
            web3=Web3(Web3.HTTPProvider(self.eth_node_url)),
        )
        self.sync_client.stark_private_key = (
            self.sync_client.onboarding.derive_stark_key()
        )
        self.symbols = symbols
        for symbol in symbols:
            self.order_book[symbol] = OrderBookCache(symbol)

    @safe_execute
    def get_user(self):
        user = self.sync_client.private.get_user()
        return user

    def get_client(self):
        return self.sync_client

    @safe_execute
    def get_our_accounts(self):
        account = self.sync_client.private.get_accounts()
        return account

    @safe_execute
    def get_symbol_info(self, symbol, cached=True):
        if symbol not in self.symbols_info or not cached:
            self.symbols_info[symbol] = self.sync_client.public.get_markets(
                market=symbol
            )
            return self.symbols_info[symbol]
        return self.symbols_info[symbol]

    @safe_execute
    def get_order_book(self, symbol):
        order_book = self.sync_client.public.get_orderbook(market=symbol)
        return order_book

    @safe_execute
    def get_our_orders(self, *, opened=True):
        if opened:
            return self.sync_client.private.get_orders(status=ORDER_STATUS_OPEN)
        return self.sync_client.private.get_orders()

    @safe_execute
    def get_our_positions(self, *, opened=True, symbol=None):
        if opened:
            status = POSITION_STATUS_OPEN
        else:
            status = POSITION_STATUS_CLOSED

        if not symbol:
            positions = self.sync_client.private.get_positions(
                market=symbol, status=status
            )
        else:
            positions = self.sync_client.private.get_positions(status=status)
        return positions

    def get_historical_trades(self, symbol, start_dt, end_dt, debug_info=False):
        trades = []
        while end_dt > start_dt:
            trades.extend(
                self.sync_client.public.get_trades(symbol, end_dt)["trades"]
            )
            end_dt = datetime.strptime(
                trades[-1]["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            if debug_info:
                print(end_dt, "->", start_dt)

        trades.reverse()
        return trades

    @safe_execute
    def send_limit_order(
        self, *, symbol, side, price, quantity, cancel_id=None
    ):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            order_type=ORDER_TYPE_LIMIT,
            post_only=False,
            size=str(quantity),
            price=str(price),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_GTT,
            expiration_epoch_seconds=10613988637,
            cancel_id=None if (not cancel_id) else str(cancel_id),
        )

    @safe_execute
    def send_trailing_stop_order(
            self, *, symbol, side, price, quantity, trailing_percent, cancel_id=None
    ):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            order_type=ORDER_TYPE_TRAILING_STOP,
            post_only=False,
            size=str(quantity),
            price=str(price),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_GTT,
            expiration_epoch_seconds=10613988637,
            cancel_id=None if (not cancel_id) else str(cancel_id),
            trailing_percent=trailing_percent
        )

    @safe_execute
    def send_ioc_order(self, *, symbol, side, price, quantity, our_id=None):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            order_type=ORDER_TYPE_MARKET,
            post_only=False,
            size=str(quantity),
            price=str(price),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_FOK,
            expiration_epoch_seconds=10613988637,
            client_id=our_id,
        )

    @safe_execute
    def send_market_order(self, *, symbol, side, price, quantity, our_id=None):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            order_type=ORDER_TYPE_MARKET,
            post_only=False,
            size=str(quantity),
            price=str(price),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_IOC,
            expiration_epoch_seconds=10613988637,
            client_id=None if (not our_id) else str(our_id),
        )

    @safe_execute
    def cancel_order(self, order_id) -> None:
        return self.sync_client.private.cancel_order(order_id=str(order_id))

    @safe_execute
    def cancel_all_orders(self, market) -> None:
        return self.sync_client.private.cancel_all_orders(market=market)

    async def subscribe_and_recieve(self) -> None:
        async with websockets.connect(WS_HOST_ROPSTEN) as websocket:
            for request in self.subscriptions:
                await websocket.send(json.dumps(request))

            while True:
                update = json.loads(await websocket.recv())
                now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                if "channel" in update:
                    if update["channel"] == "v3_orderbook":
                        self._call_orderbook_listeners(update)
                    elif update["channel"] == "v3_trades":
                        if "trades" in update["contents"]:
                            for trade in update["contents"]["trades"]:
                                trade["exchange"] = "dydx"
                                trade["symbol"] = update["id"]
                                trade["price"] = float(trade["price"])
                                trade["size"] = float(trade["size"])
                                trade["recieveTime"] = now
                                self._call_trade_listeners(trade)
                    elif update["channel"] == "v3_accounts":
                        self._call_account_listeners(update)

    def add_orderbook_listener(self, listener) -> None:
        self.orderbook_listeners.append(listener)

    def add_account_listener(self, listener) -> None:
        self.account_listeners.append(listener)

    def add_trade_listener(self, listener) -> None:
        self.trades_listeners.append(listener)

    def add_orderbook_subscription(self, symbol: str) -> None:
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_orderbook",
                "id": symbol,
                "includeOffsets": True,
            }
        )

    def add_account_subscription(self) -> None:
        now_iso_string = generate_now_iso()
        signature = self.get_client().private.sign(
            request_path="/ws/accounts",
            method="GET",
            iso_timestamp=now_iso_string,
            data={},
        )
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_accounts",
                "accountNumber": "0",
                "apiKey": self.get_client.api_key_credentials["key"],
                "passphrase": self.get_client.api_key_credentials["passphrase"],
                "timestamp": now_iso_string,
                "signature": signature,
            }
        )

    def add_trade_subscription(self, symbol: str) -> None:
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_trades",
                "id": symbol,
            }
        )

    def _call_orderbook_listeners(self, update) -> None:
        symbol = update["id"]
        if update["type"] == "subscribed":
            is_first_request = True
        elif update["type"] == "channel_data":
            is_first_request = False
        self.order_book[symbol].update_orders(
            update["contents"], is_first_request=is_first_request
        )
        for listener in self.orderbook_listeners:
            listener(update)

    def _call_account_listeners(self, update) -> None:
        for listener in self.account_listeners:
            listener(update)

    def _call_trade_listeners(self, update) -> None:
        for listener in self.trades_listeners:
            listener(update)

    async def async_start(self) -> None:
        while True:
            try:
                await self.subscribe_and_recieve()
            except Exception as error:
                print("Error in DydxConnector.asyc_start:", error)

    def start(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            try:
                loop.run_until_complete(self.subscribe_and_recieve())
            except Exception as error:
                print("Error in DydxConnector.start:", error)
