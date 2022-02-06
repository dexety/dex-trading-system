import json
from collections import deque
from datetime import datetime, timedelta
import numpy as np
from connectors.dydx.order_book_cache import OrderBookCache

symbol = "ETH-USD"
commision = 0.0003
decision_threshold_number = 30
request_delay_seconds = 0.5
cancel_time_seconds = 30
max_order_book_depth = 20
# profit_threshold = [commision * i for i in range(5, 5 + 1)]
profit_threshold = commision * 3

file = open(
    "../../data/order_book/order_book_" + symbol + "_10.json",
    "r",
    encoding="utf8",
).readlines()[:4000]
data = [[0] * (max_order_book_depth * decision_threshold_number)]
y_jumps = []
order_book = OrderBookCache(symbol)
bids_price_window = deque()
asks_price_window = deque()


def str_to_datetime(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def get_balance_measure(bids: list, asks: list, depth: int) -> float:
    bids_volume = 0
    asks_volume = 0
    size_bids = list(map(lambda bid: float(bids[bid]["size"]), bids))
    size_asks = list(map(lambda ask: float(asks[ask]["size"]), asks))
    for i in range(depth):
        bids_volume += size_bids[-i - 1]
        asks_volume += size_asks[i]
    return (bids_volume - asks_volume) / (bids_volume + asks_volume)


def get_strategy_and_price() -> dict:
    price_bids = list(map(lambda x: float(x), bids.keys()))
    asks_bids = list(map(lambda x: float(x), asks.keys()))
    current_price = price_bids[-1]
    for ask in bids_price_window:
        if ask["price"] / current_price < 1 - profit_threshold:
            return {"jump": current_price / ask["price"], "strategy": -1}
    for bid in bids_price_window:
        if bid["price"] / current_price > 1 + profit_threshold:
            return {"jump": -bid["price"] / current_price, "strategy": 1}

    if (
        asks_price_window[-1]["price"] + bids_price_window[-1]["price"]
    ) / 2 > current_price:
        return {
            "jump": asks_price_window[-1]["price"] / current_price,
            "strategy": 0,
        }
    else:
        return {
            "jump": -current_price / bids_price_window[-1]["price"],
            "strategy": 0,
        }


last_offer_line = 0


def add_next_offeres() -> None:
    global last_offer_line
    order_book_copy = order_book
    while (
        len(bids_price_window) == 0
        or str_to_datetime(bids_price_window[-1]["time"])
        < str_to_datetime(bids_price_window[0]["time"])
        + timedelta(seconds=cancel_time_seconds)
        and len(asks_price_window) == 0
        or str_to_datetime(asks_price_window[-1]["time"])
        < str_to_datetime(asks_price_window[0]["time"])
        + timedelta(seconds=cancel_time_seconds)
    ):
        if last_offer_line >= len(file):
            break
        update = file[last_offer_line]
        update = json.loads(update)
        time = update["time"]
        if update["update"]["type"] == "subscribed":
            is_first_request = True
        elif update["update"]["type"] == "channel_data":
            is_first_request = False
        order_boook_update = update["update"]["contents"]
        order_book_copy.update_orders(
            order_boook_update, is_first_request=is_first_request
        )

        bids = order_book_copy.bids
        price_bids = list(map(lambda x: float(x), bids.keys()))
        bids_price_window.append({"price": price_bids[-1], "time": time})

        asks = order_book_copy.asks
        price_asks = list(map(lambda x: float(x), asks.keys()))
        asks_price_window.append({"price": price_asks[0], "time": time})

        last_offer_line += 1


def clean_and_add_odders(time: str):
    while len(bids_price_window) and str_to_datetime(
        bids_price_window[0]["time"]
    ) < str_to_datetime(time) + timedelta(seconds=request_delay_seconds):
        bids_price_window.popleft()
    while len(asks_price_window) and str_to_datetime(
        asks_price_window[0]["time"]
    ) < str_to_datetime(time) + timedelta(seconds=request_delay_seconds):
        asks_price_window.popleft()

    add_next_offeres()


add_next_offeres()

for i in range(decision_threshold_number):
    update = file[i]
    update = json.loads(update)
    time = update["time"]
    if update["update"]["type"] == "subscribed":
        is_first_request = True
    elif update["update"]["type"] == "channel_data":
        is_first_request = False
    order_boook_update = update["update"]["contents"]
    order_book.update_orders(
        order_boook_update, is_first_request=is_first_request
    )

    bids = order_book.bids
    asks = order_book.asks

    price_bids = list(map(lambda x: float(x), bids.keys()))
    price_asks = list(map(lambda x: float(x), asks.keys()))

    clean_and_add_odders(time)

    for depth in range(1, max_order_book_depth + 1):
        balance_measure = get_balance_measure(bids, asks, depth)
        data[0][
            (depth - 1) * decision_threshold_number
            + decision_threshold_number
            - 1
            - i
        ] = balance_measure

strategy_and_price = get_strategy_and_price()
next_price = strategy_and_price["jump"]
y_jumps.append(next_price)

for i in range(decision_threshold_number, len(file)):
    if i % 1000 == 0:
        print(i, "of", len(file))
    update = file[i]
    update = json.loads(update)
    time = update["time"]
    is_first_request = False

    order_boook_update = update["update"]["contents"]
    order_book.update_orders(
        order_boook_update, is_first_request=is_first_request
    )

    bids = order_book.bids
    asks = order_book.asks

    if last_offer_line >= len(file):
        break

    data.append(data[-1])
    for j in range(max_order_book_depth):
        data[-1][len(data[0]) - 1 - j] = data[-1][
            len(data[0]) - 1 - j - max_order_book_depth
        ]
    for depth in range(1, max_order_book_depth + 1):
        balance_measure = get_balance_measure(bids, asks, depth)
        data[-1][depth - 1] = balance_measure

    clean_and_add_odders(time)

    strategy_and_price = get_strategy_and_price()
    next_price = strategy_and_price["jump"]
    y_jumps.append(next_price)

import torch
import torch.nn as nn


def main():
    # global y_jumps
    # parameters = []
    # with open('parameters.json', 'r', encoding='utf8') as file:
    #     parameters = json.load(file)
    #     parameters = np.asarray(parameters['parameters'])
    # X_test = np.array(data)
    # y_jumps = np.array(y_jumps)
    # y_jumps.reshape((y_jumps.shape[0], 1))
    # print(X_test.shape, parameters.shape, y_jumps.shape)
    # y_test_result = X_test.dot(parameters)
    # print('Profit', y_test_result.T.dot(y_jumps))
    # # print()
    # # print(y_test_result.tolist()[:100])
    # # print()
    # # print(y_jumps.tolist()[:100])

    global y_jumps
    X_test = np.array(data)


if __name__ == "__main__":
    main()
