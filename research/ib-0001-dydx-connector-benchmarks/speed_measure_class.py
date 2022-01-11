import datetime
import json
import time
import asyncio
import os
import websockets
import threading

from dydx3.helpers.request_helpers import generate_now_iso
from dydx3.constants import WS_HOST_MAINNET


class SpeedMeasure:
    def __init__(self, connector):
        self.connector = connector
        self.orders_info = dict()
        self.connector_funcs_speed_info = dict()
        self.iters_num = 1
        self.orders_num = 3

    def set_iters_num(self, num):
        self.iters_num = num

    def get_iters_num(self):
        return self.iters_num

    def _speed_test(self, func, args=None):
        if args is None:
            args = dict()
        start_time = time.time()
        res = func(**args)
        delta_time = time.time() - start_time
        if func.__name__ not in self.connector_funcs_speed_info:
            self.connector_funcs_speed_info[func.__name__] = dict()
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
        return res

    def _connector_funcs_exec_time(self, symbol, side):
        for i in range(self.iters_num):
            self._speed_test(self.connector.get_user)
            self._speed_test(self.connector.get_our_accounts)
            self._speed_test(self.connector.get_symbol_info, {"symbol": symbol})
            self._speed_test(self.connector.get_order_book, {"symbol": symbol})
            self._speed_test(self.connector.get_our_positions)
            self._speed_test(
                self.connector.get_our_positions, {"opened": False}
            )
            self._speed_test(self.connector.get_our_orders)
            order = self._speed_test(
                self.connector.send_limit_order,
                {"symbol": symbol, "side": side, "price": 1, "quantity": 0.01},
            )
            time.sleep(1)
            self._speed_test(
                self.connector.cancel_order,
                {"order_id": order["order"]["id"]},
            )
        for func in self.connector_funcs_speed_info:
            self.connector_funcs_speed_info[func]["average"] /= self.iters_num

    async def _websocket_request(self, req, orders_info):
        async with websockets.connect(WS_HOST_MAINNET) as websocket:
            await websocket.send(json.dumps(req))

            for i in range(2 + self.orders_num * 3):
                update = json.loads(await websocket.recv())
                if update["type"] == "channel_data":
                    orders_info.setdefault(
                        update["contents"]["orders"][0]["id"], {}
                    )
                    update_datetime = update["contents"]["orders"][0][
                        "updatedAt"
                    ]
                    format_string = "%Y-%m-%dT%H:%M:%S.%fZ"
                    update_datetime = datetime.datetime.strptime(
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
        req = {
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
        loop.run_until_complete(self._websocket_request(req, orders_info))

    def _send_and_cancel_orders(self, symbol, side):
        thread_orders_info = dict()
        catch_updates_thread = threading.Thread(
            target=self._catch_orders_updates, args=(thread_orders_info,)
        )
        catch_updates_thread.start()
        time.sleep(2)
        for i in range(self.orders_num):
            send_time = time.time()
            order = self.connector.send_limit_order(
                symbol=symbol, side=side, price=1, quantity=0.01
            )
            self.orders_info[order["order"]["id"]] = dict()
            self.orders_info[order["order"]["id"]]["send_time"] = send_time
            time.sleep(2)
            cancel_time = time.time()
            self.connector.cancel_order(order_id=order["order"]["id"])
            self.orders_info[order["order"]["id"]][
                "our_cancel_time"
            ] = cancel_time
        catch_updates_thread.join()

        for order_hash in thread_orders_info:
            self.orders_info[order_hash]["pending_time"] = thread_orders_info[
                order_hash
            ]["pending_time"]
            self.orders_info[order_hash]["open_time"] = thread_orders_info[
                order_hash
            ]["open_time"]
            self.orders_info[order_hash][
                "server_cancel_time"
            ] = thread_orders_info[order_hash]["server_cancel_time"]

    @staticmethod
    def _append_json_to_file(self, data, filename):
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

        delays = dict(dict())
        delay_types = [
            "from_send_to_pending",
            "from_pending_to_open",
            "from_our_cancel_to_serv_cancel",
        ]
        option_types = ["average", "slowest", "fastest"]

        for delay_type in delay_types:
            delays[delay_type] = dict()
            for option_type in option_types:
                if option_type == "fastest":
                    delays[delay_type][option_type] = 100
                    continue
                delays[delay_type][option_type] = 0

        for order_hash in self.orders_info:
            from_send_to_pending = (
                self.orders_info[order_hash]["pending_time"]
                - self.orders_info[order_hash]["send_time"]
            )
            from_pending_to_open = (
                self.orders_info[order_hash]["open_time"]
                - self.orders_info[order_hash]["pending_time"]
            )
            from_our_cancel_to_serv_cancel = (
                self.orders_info[order_hash]["server_cancel_time"]
                - self.orders_info[order_hash]["our_cancel_time"]
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
                "datetime": str(datetime.datetime.utcnow()),
                "symbol": symbol,
                "side": side,
                "orders_num": orders_num,
            },
            "results": delays,
        }
        self._append_json_to_file(self, aggregate_info, filename)

    def get_connector_funcs_exec_times(self, symbol, side, iters_num, filename):
        self.iters_num = iters_num
        self.connector_funcs_speed_info.clear()
        self._connector_funcs_exec_time(symbol, side)
        aggregate_info = {
            "meta": {
                "datetime": str(datetime.datetime.utcnow()),
                "symbol": symbol,
                "side": side,
                "iters_num": iters_num,
            },
            "results": self.connector_funcs_speed_info,
        }
        self._append_json_to_file(self, aggregate_info, filename)
