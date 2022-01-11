from sortedcontainers import SortedDict


class OrderBookCache:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.bids = SortedDict()
        self.asks = SortedDict()

    def add_bid(self, *, price: str, size: str, offset: str) -> None:
        price = float(price)
        if (
            price in self.bids
            and int(self.bids[price]["offset"]) < int(offset)
            or price not in self.bids
        ):
            self.bids[price] = {"size": size, "offset": offset}
            while not self._is_order_book_stable():
                self._remove_first_ask()

        if price in self.bids and self.bids[price]["size"] == "0":
            del self.bids[price]

    def add_ask(self, *, price: str, size: str, offset: str) -> None:
        price = float(price)
        if (
            price in self.asks
            and int(self.asks[price]["offset"]) < int(offset)
            or price not in self.asks
        ):
            self.asks[price] = {"size": size, "offset": offset}
            while self._get_first_ask() < self._get_last_bid():
                self._remove_last_bid()

        if self.asks[price]["size"] == "0":
            del self.asks[price]

    def _is_order_book_stable(self) -> bool:
        if len(self.bids) and len(self.asks):
            return self._get_last_bid() < self._get_first_ask()

        return True

    def _get_last_bid(self) -> float:
        return self.bids.keys()[-1]

    def _get_first_ask(self) -> float:
        return self.asks.keys()[0]

    def _remove_last_bid(self) -> None:
        del self.bids[self._get_last_bid()]

    def _remove_first_ask(self) -> None:
        del self.asks[self._get_first_ask()]

    def update_orders(self, contents: dict, is_first_request=False) -> None:
        if not is_first_request:
            for bid in contents["bids"]:
                self.add_bid(
                    price=bid[0], size=bid[1], offset=contents["offset"]
                )
            for ask in contents["asks"]:
                self.add_ask(
                    price=ask[0], size=ask[1], offset=contents["offset"]
                )
        else:
            for bid in contents["bids"]:
                self.add_bid(
                    price=bid["price"], size=bid["size"], offset=bid["offset"]
                )
            for ask in contents["asks"]:
                self.add_ask(
                    price=ask["price"], size=ask["size"], offset=ask["offset"]
                )
