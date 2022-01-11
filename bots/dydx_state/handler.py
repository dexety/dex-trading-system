import os
import sys
import json
import asyncio
from telebot import TeleBot
from telebot.types import Message

sys.path.append("../../")

from connectors.dydx.connector import DydxConnector

TOKEN = os.getenv("LLV_DYDX")
ETH_ADDRESS = os.getenv("ETH_ADDRESS")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
INFURA_NODE = os.getenv("INFURA_NODE")

bot = TeleBot(TOKEN, parse_mode=None)

dydx_connector = DydxConnector(
    ETH_ADDRESS,
    ETH_PRIVATE_KEY,
    [],
    INFURA_NODE,
)


class CommandsQueue:
    commands_queue = []

    def add(self, command: str) -> None:
        if command in self.commands_queue:
            self.commands_queue.remove(command)
        self.commands_queue.append(command)

    def remove(self, command: str) -> None:
        if command in self.commands_queue:
            self.commands_queue.remove(command)

    def contains(self, command: str) -> bool:
        return command in self.commands_queue


commands_queue = CommandsQueue()


def is_login(user: int) -> bool:
    user = str(user)
    data = get_users_data()
    if user in data["users"]:
        return True
    return False


def login_required(function):
    def check_auth(message: Message):
        if is_login(int(message.chat.id)):
            return function(message)
        bot.reply_to(message, "You are not log in!")
        return None

    return check_auth


@bot.message_handler(commands=["subscribe"])
@login_required
def run_account_subscription(message: Message) -> None:
    add_subscription(message.chat.id, "account")
    bot.send_message(message.chat.id, "You have been successfully subscribed")
    bot.send_message(message.chat.id, "Waiting for new trades")


@bot.message_handler(commands=["unsubscribe"])
def stop_account_subscription(message: Message) -> None:
    bot.send_message(message.chat.id, "You have been successfully unsubscribed")
    remove_subscription(message.chat.id, "account")


@bot.message_handler(commands=["positions"])
@login_required
def get_our_positions_command(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        get_positions(),
    )


def get_positions() -> dict:
    positions = []
    for position in dydx_connector.get_our_positions()["positions"]:
        positions.append(
            {
                "market": position["market"],
                "size": position["size"],
                "side": position["side"],
                "entryPrice": position["entryPrice"],
                "unrealizedPnl": position["unrealizedPnl"],
                "realizedPnl": position["realizedPnl"],
            }
        )
    return json.dumps(positions, indent=2)


@bot.message_handler(commands=["orders"])
@login_required
def get_our_orders_command(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        get_orders(),
    )


def get_orders() -> dict:
    orders = []
    for order in dydx_connector.get_our_orders()["orders"]:
        orders.append(
            {
                "market": order["market"],
                "size": order["size"],
                "side": order["side"],
                "price": order["price"],
            }
        )
    return json.dumps(orders, indent=2)


@bot.message_handler(commands=["balance"])
@login_required
def get_our_balance_command(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        dydx_connector.get_our_accounts()["accounts"][0]["equity"] + "$",
    )


@bot.message_handler(commands=["login"])
def login_command(message: Message) -> None:
    if is_login(message.chat.id):
        bot.send_message(message.chat.id, "You are already logged in")
    else:
        commands_queue.add("login")
        bot.send_message(message.chat.id, "Write your password below")


@bot.message_handler(func=lambda m: True)
def get_message(message: Message) -> None:
    if commands_queue.contains("login"):
        login(message)
        commands_queue.remove("login")
    else:
        bot.send_message(message.chat.id, "Excuse me?")


def login(message: Message) -> None:
    PASSWORD = os.getenv("LLV_DYDX_PASSWORD")
    if message.text == PASSWORD:
        bot.send_message(message.chat.id, "You are welcome!")
        add_new_user(int(message.chat.id))
    else:
        bot.send_message(message.chat.id, "Wrong password!")


def get_users_data() -> dict:
    with open("users.json", "r", encoding="utf-8") as file:
        return json.load(file)


def update_users_data(data: dict) -> None:
    with open("users.json", "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def add_subscription(user: int, subscription_type: str) -> None:
    user = str(user)
    data = get_users_data()
    data["users"][user]["subscriptions"].append(subscription_type)
    update_users_data(data)


def remove_subscription(user: int, subscription_type: str) -> None:
    user = str(user)
    data = get_users_data()
    data["users"][user]["subscriptions"].remove(subscription_type)
    update_users_data(data)


def add_new_user(user: int) -> None:
    user = str(user)
    data = get_users_data()
    if user not in data["users"]:
        data["users"][user] = {}
        data["users"][user]["subscriptions"] = []
    update_users_data(data)


def remove_user(message: Message) -> None:
    data = get_users_data()
    if message.chat.id in data["users"]:
        del data["users"][message.chat.id]
    update_users_data(data)


def run_handler():
    while True:
        try:
            asyncio.run(bot.polling())
        except Exception:
            pass
