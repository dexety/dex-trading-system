import json
from datetime import datetime
import asyncio
from typing import Callable
from functools import wraps
import websockets
from web3 import Web3
from tqdm import tqdm

from dydx3 import Client
from dydx3.constants import API_HOST_MAINNET, TIME_IN_FORCE_IOC
from dydx3.constants import NETWORK_ID_MAINNET, WS_HOST_MAINNET
from dydx3.constants import POSITION_STATUS_OPEN
from dydx3.constants import POSITION_STATUS_CLOSED
from dydx3.constants import ORDER_TYPE_LIMIT
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
            network_id=NETWORK_ID_MAINNET,
            host=API_HOST_MAINNET,
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
    def send_ioc_order(self, *, symbol, side, price, quantity, our_id=None):
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
            time_in_force=TIME_IN_FORCE_IOC,
            expiration_epoch_seconds=10613988637,
            client_id=None if (not our_id) else str(our_id),
        )

    @safe_execute
    def cancel_order(self, order_id) -> None:
        return self.sync_client.private.cancel_order(order_id=str(order_id))

    @safe_execute
    def cancel_all_orders(self) -> None:
        return self.sync_client.private.cancel_all_orders()

    def add_orderbook_subscription(self, symbol: str) -> None:
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_orderbook",
                "id": symbol,
                "includeOffsets": True,
            }
        )

    @safe_execute
    def get_historical_trades(
        self, symbol: str, start_dt: datetime, end_dt: datetime
    ) -> list:
        diff_seconds = int((end_dt - start_dt).total_seconds())
        period_end_dt = end_dt
        period_start_dt = end_dt
        progress_bar = tqdm(range(diff_seconds))
        trades = []
        while period_end_dt > start_dt:
            trades.extend(
                self.sync_client.public.get_trades(symbol, period_end_dt)[
                    "trades"
                ]
            )
            period_start_dt = datetime.strptime(
                trades[-1]["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            progress_bar.update(
                int((period_end_dt - period_start_dt).total_seconds())
            )
            period_end_dt = period_start_dt

        trades.reverse()
        return trades

    def add_trade_subscription(self, symbol: str) -> None:
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_trades",
                "id": symbol,
            }
        )

    def add_symbols_subscription(self):
        self.subscriptions.append(
            {
                "type": "subscribe",
                "channel": "v3_markets",
            }
        )

    async def subscribe_and_recieve(self) -> None:
        async with websockets.connect(WS_HOST_MAINNET) as websocket:
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

    def add_orderbook_listener(self, listener) -> None:
        self.orderbook_listeners.append(listener)
        for symbol in self.symbols:
            self.add_orderbook_subscription(symbol)

    def add_trade_listener(self, listener) -> None:
        self.trades_listeners.append(listener)
        for symbol in self.symbols:
            self.add_trade_subscription(symbol)

    def _call_orderbook_listeners(self, orderbook_update) -> None:
        symbol = orderbook_update["id"]
        if orderbook_update["type"] == "subscribed":
            is_first_request = True
        elif orderbook_update["type"] == "channel_data":
            is_first_request = False
        self.order_book[symbol].update_orders(
            orderbook_update["contents"], is_first_request=is_first_request
        )
        for listener in self.orderbook_listeners:
            listener(orderbook_update)

    def _call_trade_listeners(self, trade_update) -> None:
        for listener in self.trades_listeners:
            listener(trade_update)

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
