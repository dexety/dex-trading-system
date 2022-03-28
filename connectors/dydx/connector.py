import json
import os
import asyncio

from typing import Callable
from functools import wraps
from datetime import datetime
from dataclasses import dataclass
from web3 import Web3
from tqdm import tqdm

import websockets

from dydx3 import Client
from dydx3.helpers.request_helpers import generate_now_iso
from dydx3.constants import TIME_IN_FORCE_FOK
from dydx3.constants import TIME_IN_FORCE_GTT
from dydx3.constants import NETWORK_ID_MAINNET, NETWORK_ID_ROPSTEN
from dydx3.constants import API_HOST_MAINNET, API_HOST_ROPSTEN
from dydx3.constants import WS_HOST_MAINNET, WS_HOST_ROPSTEN
from dydx3.constants import POSITION_STATUS_OPEN, POSITION_STATUS_CLOSED
from dydx3.constants import ORDER_TYPE_LIMIT
from dydx3.constants import ORDER_TYPE_MARKET
from dydx3.constants import ORDER_TYPE_TAKE_PROFIT
from dydx3.constants import ORDER_TYPE_TRAILING_STOP
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


@dataclass
class Network:
    endpoint: str
    network_id: int
    api_host: str
    ws_host: str


networks = {
    "ropsten": Network(
        os.getenv("ROPSTEN_INFURA_NODE"),
        NETWORK_ID_ROPSTEN,
        API_HOST_ROPSTEN,
        WS_HOST_ROPSTEN,
    ),
    "mainnet": Network(
        os.getenv("INFURA_NODE"),
        NETWORK_ID_MAINNET,
        API_HOST_MAINNET,
        WS_HOST_MAINNET,
    ),
}


class DydxConnector:
    order_book = {}
    symbols_info = {}
    num_of_connection_attempts = 50

    def __init__(
        self,
        symbols: list = [],
        network: str = "ropsten",
    ) -> None:
        self.address = os.getenv("ETH_ADDRESS")
        self.private_key = os.getenv("ETH_PRIVATE_KEY")
        self.network = networks[network]
        self.sync_client = Client(
            network_id=self.network.network_id,
            host=self.network.api_host,
            default_ethereum_address=self.address,
            eth_private_key=self.private_key,
            web3=Web3(Web3.HTTPProvider(self.network.endpoint)),
        )
        self.sync_client.stark_private_key = (
            self.sync_client.onboarding.derive_stark_key()
        )
        self.symbols = symbols
        for symbol in symbols:
            self.order_book[symbol] = OrderBookCache(symbol)

        self.subscriptions = []
        self.orderbook_listeners = []
        self.account_listeners = []
        self.trades_listeners = []

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

    @safe_execute
    def send_limit_order(
        self,
        *,
        symbol: str,
        side: str,
        price: str,
        quantity: str,
        client_id: str = None,
        cancel_id: str = None,
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
            client_id=client_id,
            cancel_id=cancel_id,
        )

    @safe_execute
    def send_trailing_stop_order(
        self,
        *,
        symbol: str,
        side: str,
        price: str,
        quantity: str,
        trailing_percent: str,
        client_id: str = None,
    ):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            size=str(quantity),
            price=str(price),
            order_type=ORDER_TYPE_TRAILING_STOP,
            post_only=False,
            trailing_percent=str(trailing_percent),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_GTT,
            expiration_epoch_seconds=10613988637,
            client_id=client_id,
        )

    @safe_execute
    def send_take_profit_order(
        self,
        *,
        symbol: str,
        side: str,
        price: str,
        quantity: str,
        client_id: str = None,
    ):
        return self.sync_client.private.create_order(
            position_id=self.sync_client.private.get_account()["account"][
                "positionId"
            ],
            market=symbol,
            side=side,
            order_type=ORDER_TYPE_TAKE_PROFIT,
            post_only=False,
            size=str(quantity),
            price=str(price),
            trigger_price=str(price),
            limit_fee="0.015",
            time_in_force=TIME_IN_FORCE_GTT,
            expiration_epoch_seconds=10613988637,
            client_id=client_id,
        )

    @safe_execute
    def send_market_order(
        self,
        *,
        symbol: str,
        side: str,
        price: str,
        quantity: str,
        client_id: str = None,
    ):
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
            client_id=client_id,
        )

    @safe_execute
    def cancel_order(self, order_id) -> None:
        return self.sync_client.private.cancel_order(order_id=str(order_id))

    @safe_execute
    def cancel_all_orders(self, market) -> None:
        return self.sync_client.private.cancel_all_orders(market=market)

    async def subscribe_and_recieve(self) -> None:
        async with websockets.connect(self.network.ws_host) as websocket:
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
                "apiKey": self.get_client().api_key_credentials["key"],
                "passphrase": self.get_client().api_key_credentials[
                    "passphrase"
                ],
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
