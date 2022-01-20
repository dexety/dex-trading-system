import os
import sys
from datetime import datetime
import json
import time
import asyncio
import threading
import websockets

from dydx3.constants import MARKET_ETH_USD
from dydx3.constants import ORDER_SIDE_BUY
from dydx3.constants import WS_HOST_MAINNET
from dydx3.helpers.request_helpers import generate_now_iso

sys.path.append("../../")
from connectors.dydx.connector import DydxConnector


class SpeedMeasure:
    ETH_KEY = os.getenv("ETH_ADDRESS")
    ETH_SECRET = os.getenv("ETH_PRIVATE_KEY")
    INFURA_NODE = os.getenv("INFURA_NODE")
    connector = DydxConnector(ETH_KEY, ETH_SECRET, MARKET_ETH_USD, INFURA_NODE)
    orders_info = {}
    connector_funcs_speed_info = {}
    iters_num = 0
    orders_num = 0

    def _speed_test(self, func, **kwargs):
        start_time = datetime.utcnow().timestamp()
        result = func(**kwargs)
        delta_time = datetime.utcnow().timestamp() - start_time
        if func.__name__ not in self.connector_funcs_speed_info:
            self.connector_funcs_speed_info[func.__name__] = {}
            self.connector_funcs_speed_info[func.__name__][
                "average"
            ] = delta_time
            self.connector_funcs_speed_info[func.__name__][
                "fastest"
            ] = delta_time
            self.connector_funcs_speed_info[func.__name__][
                "slowest"
            ] = delta_time
        else:
            self.connector_funcs_speed_info[func.__name__][
                "average"
            ] += delta_time
            self.connector_funcs_speed_info[func.__name__]["fastest"] = min(
                delta_time,
                self.connector_funcs_speed_info[func.__name__]["fastest"],
            )
            self.connector_funcs_speed_info[func.__name__]["slowest"] = max(
                delta_time,
                self.connector_funcs_speed_info[func.__name__]["slowest"],
            )
        return result

    def _connector_funcs_exec_time(self, symbol, side):
        for _ in range(self.iters_num):
            self._speed_test(self.connector.get_user)
            self._speed_test(self.connector.get_our_accounts)
            self._speed_test(self.connector.get_symbol_info, symbol=symbol)
            self._speed_test(self.connector.get_order_book, symbol=symbol)
            self._speed_test(self.connector.get_our_positions)
            self._speed_test(self.connector.get_our_positions, opened=False)
            self._speed_test(self.connector.get_our_orders)
            order = self._speed_test(
                self.connector.send_limit_order,
                symbol=symbol,
                side=side,
                price=1,
                quantity=0.01,
            )
            time.sleep(2)
            self._speed_test(
                self.connector.cancel_order,
                order_id=order["order"]["id"],
            )
        for _, value in self.connector_funcs_speed_info.items():
            value["average"] /= self.iters_num

    async def _websocket_request(self, request, orders_info):
        async with websockets.connect(WS_HOST_MAINNET) as websocket:
            await websocket.send(json.dumps(request))

            for _ in range(2 + self.orders_num * 3):
                update = json.loads(await websocket.recv())
                if update["type"] == "channel_data":
                    orders_info.setdefault(
                        update["contents"]["orders"][0]["id"], {}
                    )
                    update_datetime = update["contents"]["orders"][0][
                        "updatedAt"
                    ]
                    format_string = "%Y-%m-%dT%H:%M:%S.%fZ"
                    update_datetime = datetime.strptime(
                        update_datetime, format_string
                    )
                    update_timestamp = update_datetime.timestamp()
                    if update["contents"]["orders"][0]["status"] == "PENDING":
                        orders_info[update["contents"]["orders"][0]["id"]][
                            "pending_time"
                        ] = update_timestamp
                    elif update["contents"]["orders"][0]["status"] == "OPEN":
                        orders_info[update["contents"]["orders"][0]["id"]][
                            "open_time"
                        ] = update_timestamp
                    elif (
                        update["contents"]["orders"][0]["status"] == "CANCELED"
                    ):
                        orders_info[update["contents"]["orders"][0]["id"]][
                            "server_cancel_time"
                        ] = update_timestamp

    def _catch_orders_updates(self, orders_info):
        now_iso_string = generate_now_iso()
        signature = self.connector.get_client().private.sign(
            request_path="/ws/accounts",
            method="GET",
            iso_timestamp=now_iso_string,
            data={},
        )
        request = {
            "type": "subscribe",
            "channel": "v3_accounts",
            "accountNumber": "0",
            "apiKey": self.connector.get_client().api_key_credentials["key"],
            "passphrase": self.connector.get_client().api_key_credentials[
                "passphrase"
            ],
            "timestamp": now_iso_string,
            "signature": signature,
        }
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._websocket_request(request, orders_info))

    def _send_and_cancel_orders(self, symbol, side):
        thread_orders_info = {}
        catch_updates_thread = threading.Thread(
            target=self._catch_orders_updates, args=(thread_orders_info,)
        )
        catch_updates_thread.start()
        time.sleep(2)
        for _ in range(self.orders_num):
            send_time = datetime.utcnow().timestamp()
            order = self.connector.send_limit_order(
                symbol=symbol, side=side, price=1, quantity=0.01
            )
            self.orders_info[order["order"]["id"]] = {}
            self.orders_info[order["order"]["id"]]["send_time"] = send_time
            time.sleep(2)
            cancel_time = datetime.utcnow().timestamp()
            self.connector.cancel_order(order_id=order["order"]["id"])
            self.orders_info[order["order"]["id"]][
                "our_cancel_time"
            ] = cancel_time
        catch_updates_thread.join()

        for order_hash, value in thread_orders_info.items():
            self.orders_info[order_hash]["pending_time"] = value["pending_time"]
            self.orders_info[order_hash]["open_time"] = value["open_time"]
            self.orders_info[order_hash]["server_cancel_time"] = value[
                "server_cancel_time"
            ]

    @staticmethod
    def _append_json_to_file(data, filename):
        if not os.path.isfile(filename) or os.path.getsize(filename) == 0:
            with open(filename, mode="w", encoding="utf-8") as f:
                json.dump([], f)
        with open(filename, mode="r+", encoding="utf-8") as f:
            cur_data = json.load(f)
            cur_data.append(data)
            f.seek(0)
            json.dump(cur_data, f, indent=4)

    def get_orders_processing_delays(self, symbol, side, orders_num, filename):
        self.orders_info.clear()
        self.orders_num = orders_num
        self._send_and_cancel_orders(symbol, side)

        delays = {}
        delay_types = [
            "from_send_to_pending",
            "from_pending_to_open",
            "from_our_cancel_to_serv_cancel",
        ]
        option_types = ["average", "slowest", "fastest"]

        for delay_type in delay_types:
            delays[delay_type] = {}
            for option_type in option_types:
                if option_type == "fastest":
                    delays[delay_type][option_type] = 100
                    continue
                delays[delay_type][option_type] = 0

        for _, order in self.orders_info.items():
            from_send_to_pending = order["pending_time"] - order["send_time"]
            from_pending_to_open = order["open_time"] - order["pending_time"]
            from_our_cancel_to_serv_cancel = (
                order["server_cancel_time"] - order["our_cancel_time"]
            )
            diffs = [
                from_send_to_pending,
                from_pending_to_open,
                from_our_cancel_to_serv_cancel,
            ]
            for i in range(3):
                delay_type = delay_types[i]
                diff = diffs[i]
                for option_type in option_types:
                    if option_type == "fastest":
                        delays[delay_type][option_type] = min(
                            diff, delays[delay_type][option_type]
                        )
                    elif option_type == "slowest":
                        delays[delay_type][option_type] = max(
                            diff, delays[delay_type][option_type]
                        )
                    elif option_type == "average":
                        delays[delay_type][option_type] += (
                            diff / self.orders_num
                        )

        aggregate_info = {
            "meta": {
                "datetime": str(datetime.utcnow()),
                "symbol": symbol,
                "side": side,
                "orders_num": orders_num,
            },
            "results": delays,
        }
        self._append_json_to_file(aggregate_info, filename)

    def get_connector_funcs_exec_times(self, symbol, side, iters_num, filename):
        self.iters_num = iters_num
        self.connector_funcs_speed_info.clear()
        self._connector_funcs_exec_time(symbol, side)
        aggregate_info = {
            "meta": {
                "datetime": str(datetime.utcnow()),
                "symbol": symbol,
                "side": side,
                "iters_num": iters_num,
            },
            "results": self.connector_funcs_speed_info,
        }
        self._append_json_to_file(aggregate_info, filename)

    def run_measurer(self):
        self.get_connector_funcs_exec_times(
            MARKET_ETH_USD,
            ORDER_SIDE_BUY,
            iters_num=10,
            filename="connector_funcs_exec_times.json",
        )

        self.get_orders_processing_delays(
            MARKET_ETH_USD,
            ORDER_SIDE_BUY,
            orders_num=10,
            filename="orders_processing_delays.json",
        )


def main():
    speed_measure = SpeedMeasure()
    speed_measure.run_measurer()


if __name__ == "__main__":
    main()
