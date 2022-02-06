import json
import os
import asyncio
import websockets
from telebot import TeleBot
from dydx3.constants import WS_HOST_MAINNET
from dydx3.helpers.request_helpers import generate_now_iso
from connectors.dydx.connector import DydxConnector


class Sender:
    TOKEN = os.getenv("LLV_DYDX")
    ETH_ADDRESS = os.getenv("ETH_ADDRESS")
    ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")

    def __init__(self) -> None:
        self.bot = TeleBot(self.TOKEN)
        self.dydx_connector = DydxConnector(
            self.ETH_ADDRESS,
            self.ETH_PRIVATE_KEY,
            [],
            self.INFURA_NODE,
        )
        self.set_null_account()

    def set_null_account(self) -> None:
        self.account = {
            "balance": 0,
            "open_orders": [],
            "open_positions": [],
        }

    async def run(self) -> None:
        now_iso_string = generate_now_iso()
        signature = self.dydx_connector.sync_client.private.sign(
            request_path="/ws/accounts",
            method="GET",
            iso_timestamp=now_iso_string,
            data={},
        )
        subscribe_request = {
            "type": "subscribe",
            "channel": "v3_accounts",
            "accountNumber": "0",
            "apiKey": self.dydx_connector.sync_client.api_key_credentials[
                "key"
            ],
            "passphrase": self.dydx_connector.sync_client.api_key_credentials[
                "passphrase"
            ],
            "timestamp": now_iso_string,
            "signature": signature,
        }
        async with websockets.connect(WS_HOST_MAINNET) as websocket:
            await websocket.send(json.dumps(subscribe_request))
            update = json.loads(await websocket.recv())
            if update["type"] != "connected":
                raise Exception("Error when connecting to the Dydx")
            update = json.loads(await websocket.recv())
            if update["type"] != "subscribed":
                raise Exception("Error when subscribing to the Dydx")
            self.account["balance"] = update["contents"]["account"]["equity"]

            while True:
                update = json.loads(await websocket.recv())
                self.add_orders(update["contents"])
                self.add_positions(update["contents"])
                self.bot_send_info()

    def add_orders(self, update: dict) -> None:
        if "orders" not in update:
            return
        for order in update["orders"]:
            if order["status"] == "OPEN":
                self.add_order(order)
            elif order["status"] == "CANCELED":
                self.remove_order(order)

    def add_positions(self, update: dict) -> None:
        if "positions" not in update:
            return
        for position in update["positions"]:
            if position["status"] == "OPEN":
                self.add_position(position)
            elif position["status"] == "CANCELED":
                self.remove_position(position)

    def add_order(self, order) -> None:
        self.account["open_orders"].append(
            {
                "side": order["side"],
                "price": order["price"],
                "size": order["size"],
                "market": order["market"],
            }
        )

    def remove_order(self, order) -> None:
        item = {
            "side": order["side"],
            "price": order["price"],
            "size": order["size"],
            "market": order["market"],
        }
        if item in self.account["open_orders"]:
            self.account["open_orders"].remove(item)

    def add_position(self, position) -> None:
        self.remove_position(position)
        self.account["open_positions"].append(
            {
                "side": position["side"],
                "entry_price": position["entryPrice"],
                "size": position["size"],
                "market": position["market"],
            }
        )

    def remove_position(self, position) -> None:
        item = {
            "side": position["side"],
            "price": position["price"],
            "size": position["size"],
            "market": position["market"],
        }
        if item in self.account["open_positions"]:
            self.account["open_positions"].remove(item)

    def bot_send_info(self) -> None:
        with open("users.json", "r", encoding="utf8") as file:
            try:
                data = json.load(file)
            except BaseException:
                return
            if "users" not in data or len(data["users"]) == 0:
                return
            for user_id, user_info in data["users"].items():
                if (
                    "subscriptions" in user_info
                    and "account" in user_info["subscriptions"]
                ):
                    self.bot.send_message(
                        user_id, json.dumps(self.account, indent=2)
                    )


def run_sender():
    sender = Sender()
    while True:
        try:
            asyncio.run(sender.run())
        except Exception:
            pass
