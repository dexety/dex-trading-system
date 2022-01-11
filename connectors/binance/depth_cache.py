from operator import itemgetter


class DepthCache:
    def __init__(self, symbol, conv_type=float):
        self.symbol = symbol
        self._bids = {}
        self._asks = {}
        self.timestamp = None
        self.conv_type = conv_type

    def add_bid(self, bid):
        self._bids[bid[0]] = self.conv_type(bid[1])
        if bid[1] == "0.00000000":
            del self._bids[bid[0]]

    def add_ask(self, ask):
        self._asks[ask[0]] = self.conv_type(ask[1])
        if ask[1] == "0.00000000":
            del self._asks[ask[0]]

    def get_bids(self):
        return DepthCache.sort_depth(
            self._bids, reverse=True, conv_type=self.conv_type
        )

    def get_asks(self):
        return DepthCache.sort_depth(
            self._asks, reverse=False, conv_type=self.conv_type
        )

    def apply_orders(self, msg):
        self.timestamp = msg["E"]
        for bid in msg.get("b", []) + msg.get("bids", []):
            self.add_bid(bid)
        for ask in msg.get("a", []) + msg.get("asks", []):
            self.add_ask(ask)

    def apply_trade(self, trade):
        self.timestamp = trade["E"]
        if trade["aggressor_side"] == "BUY":
            to_delete = []
            for price, _ in self._asks.items():
                if float(price) < trade["price"]:
                    to_delete.append(price)

            for price in to_delete:
                del self._asks[price]

            if trade["p"] not in self._asks:
                self._asks[trade["p"]] = trade["qty"]
        else:
            to_delete = []
            for price, _ in self._bids.items():
                if float(price) > trade["price"]:
                    to_delete.append(price)

            for price in to_delete:
                del self._bids[price]

            if trade["p"] not in self._bids:
                self._bids[trade["p"]] = trade["qty"]

    @staticmethod
    def sort_depth(vals, reverse=False, conv_type=float):
        lst = [[conv_type(price), quantity] for price, quantity in vals.items()]
        lst = sorted(lst, key=itemgetter(0), reverse=reverse)
        return lst
