import sys
import json
from collections import deque
from datetime import datetime, timedelta
import numpy as np

# from sklearn.linear_model import LinearRegression
# from sklearn.linear_model import Ridge
# from sklearn.linear_model import ElasticNet

sys.path.append("../../")
from ...connectors.dydx.order_book_cache import OrderBookCache

symbol = "ETH-USD"
commision = 0.0004
decision_threshold_number = 500
request_delay_seconds = 0.5
cancel_time_seconds = 30
max_order_book_depth = 20
# profit_threshold = [commision * i for i in range(5, 5 + 1)]
profit_threshold = commision * 2

file = open(
    "../../data/order_book/order_book_" + symbol + ".json", "r", encoding="utf8"
).readlines()
data = [[0] * (max_order_book_depth * decision_threshold_number)]
y_desicions = []
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
            return {"jump": bid["price"] / current_price, "strategy": 1}

    return {"jump": 0, "strategy": 0}


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
strategy = strategy_and_price["strategy"]

y_jumps.append(next_price)
y_desicions.append(strategy)

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
    strategy = strategy_and_price["strategy"]
    y_jumps.append(next_price)
    y_desicions.append(strategy)

import torch
import torch.nn as nn


def main():
    X_train = np.array(data)
    X_train = X_train.astype("float32")
    y_train = np.array(y_desicions)
    y_train += 1
    y_train = y_train.reshape((y_train.shape[0], 1))
    y_train = y_train.astype("int")
    # reg = LinearRegression()
    # reg.fit(X_train, y_train)
    # with open('parameters.json', 'w', encoding='utf8') as file:
    # json.dump({'parameters': reg.coef_.T.tolist()}, file)
    # clf = Ridge(alpha=10**-25, max_iter=10000000)
    # clf.fit(X_train, y_train)
    # print(clf.coef_)
    # with open('parameters.json', 'w', encoding='utf8') as file:
    # json.dump({'parameters': clf.coef_.T.tolist()}, file)
    # regr = ElasticNet(random_state=0, alpha=1, max_iter=1000000)
    # regr.fit(X_train, y_train)
    # print(regr.coef_)
    # with open('parameters.json', 'w', encoding='utf8') as file:
    #     json.dump({'parameters': regr.coef_.T.tolist()}, file)

    input_size = max_order_book_depth * decision_threshold_number
    num_classes = 3
    num_epochs = 100
    learning_rate = 0.001
    # Logistic regression model
    model = nn.Linear(input_size, num_classes)
    nn.CrossEntropyLoss()
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)

    for epoch in range(num_epochs):
        inputs = torch.from_numpy(X_train)
        targets = torch.from_numpy(y_train.ravel())
        targets = targets.type(torch.LongTensor)
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 100 == 0:
            print(
                "Epoch [{}/{}], Loss: {:.4f}".format(
                    epoch + 1, num_epochs, loss.item()
                )
            )

    # Test the model
    with torch.no_grad():
        inputs = torch.from_numpy(X_train)
        targets = torch.from_numpy(y_train)
        correct = 0
        total = 0
        outputs = model(inputs)
        _, predicted = torch.max(outputs.data, 1)
        print(y_train.tolist())
        print(predicted.numpy().tolist())
        total = targets.size(0)
        correct = np.sum(predicted.numpy().ravel() == targets.numpy().ravel())
        print("Accuracy of the model : {} %".format(100 * correct / total))

    # Save the model checkpoint
    torch.save(model.state_dict(), "model.ckpt")


if __name__ == "__main__":
    main()
