import json
from datetime import datetime, timedelta


class MarkerMaking:
    stock_delay_ms = 400
    commision = 0.0005
    spread_pc = 4 * commision
    buying_power = 0.01
    currency_balance = 0
    profit = 0
    expire_time_sec = 60
    update_num = 0

    def __init__(self, path: str) -> None:
        self.data = json.loads(open(path, "r", encoding="utf8").read())
        self.set_first_orders()
        self.set_trades_window()

    def get_new_update(self) -> dict:
        update = self.data[self.update_num]
        update["price"] = float(update["price"])
        update["size"] = float(update["size"])
        self.update_num += 1
        return update

    def set_trades_window(self) -> bool:
        read_lines = 0
        self.set_null_trades_window()
        while self.update_num < len(self.data):
            update = self.get_new_update()
            time = self.get_datetime(update["createdAt"])
            if time < max(
                self.our_orders["BUY"]["time"], self.our_orders["SELL"]["time"]
            ):
                self.current_time = time
                continue
            read_lines += 1
            self.trades_window[update["side"]].append(
                {
                    "price": update["price"],
                    "time": time,
                }
            )
            if time > self.current_time + timedelta(
                milliseconds=self.stock_delay_ms
            ):
                break
        self.current_time = self.get_max_time()
        if read_lines != 0:
            return True
        return False

    def set_first_orders(self) -> None:
        self.set_null_our_orders()
        while self.update_num < len(self.data):
            update = self.get_new_update()
            if update["side"] == "SELL":
                time = self.get_datetime(update["createdAt"])
                self.current_time = time
                self.our_orders["SELL"]["time"] = time + timedelta(
                    milliseconds=self.stock_delay_ms
                )
                self.our_orders["SELL"]["price"] = update["price"] * (
                    1 + self.spread_pc
                )
                break

        while self.update_num < len(self.data):
            update = self.get_new_update()
            if update["side"] == "BUY":
                time = self.get_datetime(update["createdAt"])
                self.current_time = time
                self.our_orders["BUY"]["time"] = time + timedelta(
                    milliseconds=self.stock_delay_ms
                )
                self.our_orders["BUY"]["price"] = update["price"] * (
                    1 - self.spread_pc
                )
                self.current_time = time
                break

    @staticmethod
    def get_datetime(string_time: str) -> datetime:
        return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    def set_null_trades_window(self) -> None:
        self.trades_window = {
            "BUY": [],
            "SELL": [],
        }

    def get_max_time(self, side=None) -> datetime:
        if side != None:
            if len(self.trades_window[side]) > 0:
                return max(map(lambda x: x["time"], self.trades_window[side]))
            else:
                return None
        else:
            if (
                len(self.trades_window["BUY"]) > 0
                and len(self.trades_window["SELL"]) > 0
            ):
                return max(
                    max(map(lambda x: x["time"], self.trades_window["SELL"])),
                    max(map(lambda x: x["time"], self.trades_window["BUY"])),
                )
            elif len(self.trades_window["BUY"]) > 0:
                return max(map(lambda x: x["time"], self.trades_window["BUY"]))
            elif len(self.trades_window["SELL"]) > 0:
                return max(map(lambda x: x["time"], self.trades_window["SELL"]))
            else:
                return None

    def set_null_our_orders(self) -> None:
        self.our_orders = {
            "BUY": {
                "price": -1e12,
                "prev_price": -1e12,
                "time": None,
            },
            "SELL": {
                "price": 1e12,
                "prev_price": 1e12,
                "time": None,
            },
        }

    def update_our_orders(self) -> None:
        if len(self.trades_window["BUY"]) != 0:
            if self.currency_balance != 1:
                self.our_orders["BUY"]["prev_price"] = self.our_orders["BUY"][
                    "price"
                ]
                self.our_orders["BUY"]["price"] = self.trades_window["BUY"][-1][
                    "price"
                ] * (1 - self.spread_pc)
                self.our_orders["BUY"]["time"] = self.current_time + timedelta(
                    milliseconds=self.stock_delay_ms
                )
            if self.currency_balance == 0:
                self.our_orders["SELL"]["prev_price"] = self.our_orders["SELL"][
                    "price"
                ]
                self.our_orders["SELL"]["price"] = self.our_orders["BUY"][
                    "price"
                ] * (1 + self.spread_pc)
                self.our_orders["SELL"]["time"] = self.current_time + timedelta(
                    milliseconds=self.stock_delay_ms
                )
        if len(self.trades_window["SELL"]) != 0:
            if self.currency_balance != -1:
                self.our_orders["SELL"]["prev_price"] = self.our_orders["SELL"][
                    "price"
                ]
                self.our_orders["SELL"]["price"] = self.trades_window["SELL"][
                    -1
                ]["price"] * (1 + self.spread_pc)
                self.our_orders["SELL"]["time"] = self.current_time + timedelta(
                    milliseconds=self.stock_delay_ms
                )
            if self.currency_balance == 0:
                self.our_orders["BUY"]["prev_price"] = self.our_orders["BUY"][
                    "price"
                ]
                self.our_orders["BUY"]["price"] = self.our_orders["SELL"][
                    "price"
                ] * (1 - self.spread_pc)
                self.our_orders["BUY"]["time"] = self.current_time + timedelta(
                    milliseconds=self.stock_delay_ms
                )

    def is_punch(self, side: str) -> bool:
        # print('WIN', self.trades_window)
        # print('OUR', self.our_orders)
        # print()
        for trade in self.trades_window[side]:
            if (
                side == "SELL"
                and trade["price"] >= self.our_orders["SELL"]["price"]
            ):
                return True
            elif (
                side == "BUY"
                and trade["price"] <= self.our_orders["BUY"]["price"]
            ):
                return True
        return False

    def check_punches(self) -> None:
        if self.is_punch("SELL"):
            if self.currency_balance == 0:
                self.our_orders["SELL"]["prev_price"] = self.our_orders["SELL"][
                    "price"
                ]
                self.our_orders["SELL"]["price"] = 1e12
                self.currency_balance = -1
            elif self.currency_balance == 1:
                self.currency_balance = 0
                self.add_profit()
        elif self.is_punch("BUY"):
            if self.currency_balance == 0:
                self.our_orders["BUY"]["prev_price"] = self.our_orders["BUY"][
                    "price"
                ]
                self.our_orders["BUY"]["price"] = -1e12
                self.currency_balance = 1
            elif self.currency_balance == -1:
                self.currency_balance = 0
                self.add_profit()

    def check_expire(self) -> None:
        if self.currency_balance == 1:
            if self.our_orders["SELL"]["time"] >= self.our_orders["BUY"][
                "time"
            ] + timedelta(seconds=self.expire_time_sec):
                self.our_orders["SELL"]["prev_price"] = self.our_orders["SELL"][
                    "price"
                ]
                self.our_orders["SELL"]["price"] = 1e12
                self.add_profit()
                self.currency_balance = 0
        elif self.currency_balance == -1:
            if self.our_orders["BUY"]["time"] >= self.our_orders["SELL"][
                "time"
            ] + timedelta(seconds=self.expire_time_sec):
                self.our_orders["BUY"]["prev_price"] = self.our_orders["BUY"][
                    "price"
                ]
                self.our_orders["BUY"]["price"] = -1e12
                self.add_profit()
                self.currency_balance = 0

    def add_profit(self) -> None:
        print(self.our_orders)
        if (
            self.our_orders["SELL"]["price"] == 1e12
            and self.our_orders["BUY"]["price"] == -1e12
        ):
            self.profit += (
                self.our_orders["SELL"]["prev_price"]
                - self.our_orders["BUY"]["prev_price"]
                + 2 * self.commision
            ) * self.buying_power
        elif self.our_orders["SELL"]["price"] == 1e12:
            self.profit += (
                self.our_orders["SELL"]["prev_price"]
                - self.our_orders["BUY"]["price"]
                + 2 * self.commision
            ) * self.buying_power
        elif self.our_orders["BUY"]["price"] == -1e12:
            self.profit += (
                self.our_orders["SELL"]["price"]
                - self.our_orders["BUY"]["prev_price"]
                + 2 * self.commision
            ) * self.buying_power

    def print_profit(self) -> None:
        print(
            "Your profit is",
            self.profit,
            "$ using market-making strategy with",
            self.buying_power,
            "ETH",
        )

    def run(self) -> None:
        while True:
            self.update_our_orders()
            self.check_punches()
            self.check_expire()
            if not self.set_trades_window():
                break
        self.print_profit()


def main():
    mm = MarkerMaking(
        "../../data/trades/trades-2021_11_1_0_0_0-2021_11_7_0_0_0.json"
    )
    mm.run()


if __name__ == "__main__":
    main()
