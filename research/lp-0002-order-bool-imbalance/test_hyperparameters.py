import argparse
import json
from collections import deque
from datetime import datetime, timedelta
from connectors.dydx.order_book_cache import OrderBookCache

parser = argparse.ArgumentParser(description="Ping script")
parser.add_argument(
    "--depth", dest="depth", help="order book depth", required=True
)
parser.add_argument(
    "--dicision_time",
    dest="dicision_time",
    help="dicision time in seconds",
    required=True,
)
parser.add_argument(
    "--dicision_threshold",
    dest="dicision_threshold",
    help="dicision threshold in percent",
    required=True,
)
parser.add_argument(
    "--cancel_time",
    dest="cancel_time",
    help="cancel time in seconds",
    required=True,
)
parser.add_argument(
    "--cancel_threshold",
    dest="cancel_threshold",
    help="cancel threshold in percent",
    required=True,
)
parser.add_argument(
    "--profit_threshold",
    dest="profit",
    help="profit threshold in percent. profit=1 is 2x profit",
    required=True,
)
parser.add_argument("--symbol", dest="symbol", help="symbol", required=True)
args = parser.parse_args()
order_book_depth = int(args.depth)
decision_time_seconds = int(args.dicision_time)
decision_threshold_percent = float(args.dicision_threshold)
cancel_time_seconds = int(args.cancel_time)
cancel_threshold_percent = float(args.cancel_threshold)
profit_threshold_percent = float(args.profit)
symbol = str(args.symbol)

commision = 0.001
data = []

with open(
    "../../data/order_book/order_book_" + symbol + "_1.json",
    "r",
    encoding="utf8",
) as file:
    order_book = OrderBookCache(symbol)

    for update in file:
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
        size_bids = list(map(lambda bid: float(bids[bid]["size"]), bids))
        price_asks = list(map(lambda x: float(x), asks.keys()))
        size_asks = list(map(lambda ask: float(asks[ask]["size"]), asks))

        bids_volume = 0
        asks_volume = 0
        for i in range(order_book_depth):
            bids_volume += size_bids[-i - 1]
            asks_volume += size_asks[i]

        balance_measure = (bids_volume - asks_volume) / (
            bids_volume + asks_volume
        )

        data.append(
            {
                "bids_volume": bids_volume,
                "asks_volume": asks_volume,
                "bids_price": price_bids[-1],
                "asks_price": price_asks[0],
                "balance_measure": balance_measure,
                "time": time,
            }
        )


def str_to_datetime(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def get_profit_from_signal(
    time: datetime, signal: str, data_index: int
) -> float:
    current_time = time
    profit = 0
    costs = 0
    if data_index >= len(data):
        return 0, 0
    if signal == "BUY":
        buy_price = data[data_index]["asks_price"]
        current_bid_price = data[data_index]["bids_price"]
        while (
            current_time < time + timedelta(seconds=cancel_time_seconds)
            and current_bid_price / buy_price < 1 + profit_threshold_percent
            and current_bid_price / buy_price > 1 - cancel_threshold_percent
        ):
            data_index += 1
            if data_index >= len(data):
                return 0, 0
            current_time = str_to_datetime(data[data_index]["time"])
            current_bid_price = data[data_index]["bids_price"]
        profit += current_bid_price - buy_price
        costs -= commision * (buy_price + current_bid_price)
    elif signal == "SELL":
        sell_price = data[data_index]["bids_price"]
        current_ask_price = data[data_index]["asks_price"]
        while (
            current_time < time + timedelta(seconds=cancel_time_seconds)
            and current_ask_price / sell_price < 1 + profit_threshold_percent
            and current_ask_price / sell_price > 1 - cancel_threshold_percent
        ):
            data_index += 1
            if data_index >= len(data):
                return 0, 0
            current_time = str_to_datetime(data[data_index]["time"])
            current_ask_price = data[data_index]["asks_price"]
        profit += sell_price - current_ask_price
        costs -= commision * (sell_price + current_ask_price)
    return profit, costs


data_begin_index = 0
data_end_index = 0
decision_window = deque()
window_balance_measure_sum = 0
profit = 0
costs = 0

with open("test_hyperparameters.json", "a", encoding="utf8") as file:
    file.write(f"order_book_depth = {order_book_depth}\n")
    file.write(f"decision_time_seconds = {decision_time_seconds}\n")
    file.write(f"decision_threshold_percent = {decision_threshold_percent}\n")
    file.write(f"cancel_time_seconds = {cancel_time_seconds}\n")
    file.write(f"cancel_threshold_percent = {cancel_threshold_percent}\n")
    file.write(f"profit_threshold_percent = {profit_threshold_percent}\n")
    file.write(f"symbol = {symbol}\n")

while data_begin_index < len(data) - 10 * len(decision_window):
    begin_time = str_to_datetime(data[data_begin_index]["time"])

    if len(decision_window):
        window_balance_measure_sum -= decision_window.popleft()[
            "balance_measure"
        ]
    while len(decision_window) == 0 or str_to_datetime(
        decision_window[-1]["time"]
    ) < begin_time + timedelta(seconds=decision_time_seconds):
        decision_window.append(data[data_end_index])
        window_balance_measure_sum += decision_window[-1]["balance_measure"]
        data_end_index += 1
    end_time = str_to_datetime(decision_window[-1]["time"])

    if (
        abs(window_balance_measure_sum / len(decision_window))
        > decision_threshold_percent
    ):
        if window_balance_measure_sum / len(decision_window) > 0:
            # print('BUY')
            current_profit, current_costs = get_profit_from_signal(
                end_time, "BUY", data_end_index
            )
            profit += current_profit
            costs += current_costs
        else:
            # print('SELL')
            current_profit, current_costs = get_profit_from_signal(
                end_time, "SELL", data_end_index
            )
            profit += current_profit
            costs += current_costs
        # print('balance', balance, '$')
        data_begin_index += len(decision_window)
        data_end_index = data_begin_index
        decision_window = deque()
        window_balance_measure_sum = 0

    data_begin_index += 1

with open("test_hyperparameters.json", "a", encoding="utf8") as file:
    file.write(
        "profit: "
        + str(profit)
        + " $, costs: "
        + str(costs)
        + " $, balance: "
        + str(profit + costs)
        + " $\n\n"
    )
