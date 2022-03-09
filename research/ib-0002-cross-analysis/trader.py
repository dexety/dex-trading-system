import asyncio
import csv

import websockets
import json
from datetime import datetime
from datetime import timedelta
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY
from dydx3.helpers.request_helpers import generate_now_iso


def string_to_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


log_file = "trader_log.csv"
f = open(log_file, "a+")
csv_writer = csv.writer(f)
ETH_KEY = "0x5e1F56e732C6e0C465B67a59fC96E862172D192B"
ETH_PRIVATE_KEY = "c559757ab5c49310a44f57a958de1f8e4af64588dd6e809322bd75683bab501a"
dydx_connector = DydxConnector(
    ETH_KEY,
    ETH_PRIVATE_KEY,
    [MARKET_ETH_USD],
)

symbol_binance = "btcusd_perp"
socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"
flag_1 = False
flag_2 = False
side = ""
dispatch_time = datetime.now()
trailing_percent = 0.14
quantity = 0.02
profit_threshold = 0.002
sliding_window = SlidingWindow()
market = MARKET_ETH_USD


async def catch_signal_send_market_order():
    global flag_1, dispatch_time, side
    async with websockets.connect(socket_binance) as sock:
        while True:
            data = await sock.recv()
            json_data = json.loads(data)
            if not flag_1 and not flag_2 and not json_data["m"]:
                if sliding_window.push_back(float(json_data["p"]), json_data["T"]):
                    max_in_window = sliding_window.get_max()
                    max_timestamp = sliding_window.get_max_timestamp()
                    min_in_window = sliding_window.get_min()
                    min_timestamp = sliding_window.get_min_timestamp()
                    if max_in_window / min_in_window >= 1.0021:
                        if max_timestamp > min_timestamp:
                            side = "BUY"
                        elif max_timestamp < min_timestamp:
                            side = "SELL"
                        now = datetime.now()
                        dispatch_time = now
                        csv_writer.writerow(["M", "Signal", side,
                                             now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # M = Market
                        dydx_connector.send_market_order(
                            symbol=market,
                            side=side,
                            price=1 if side == "SELL" else 10 ** 8,
                            quantity=quantity,
                        )
                        flag_1 = True
                        await asyncio.sleep(20)
                        sliding_window.clear()

now_iso_string = generate_now_iso()
signature = dydx_connector.get_client().private.sign(
    request_path="/ws/accounts",
    method="GET",
    iso_timestamp=now_iso_string,
    data={},
)
req = {
    "type": "subscribe",
    "channel": "v3_accounts",
    "accountNumber": "0",
    "apiKey": dydx_connector.get_client().api_key_credentials["key"],
    "passphrase": dydx_connector.get_client().api_key_credentials[
                "passphrase"
    ],
    "timestamp": now_iso_string,
    "signature": signature,
}
socket_dydx = f"wss://api.stage.dydx.exchange/v3/ws"


async def close_positions():
    while True:
        if flag_1 and flag_2:
            if datetime.now() >= (dispatch_time + timedelta(seconds=20)):
                now = datetime.now()
                csv_writer.writerow(["C", "TimeOut", now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # C = Cancel
                dydx_connector.cancel_all_orders(market=market)
                csv_writer.writerow(["M", "Close", side, now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # M = Market
                dydx_connector.send_market_order(
                    symbol=market,
                    side="BUY" if side == "SELL" else "SELL",
                    price=1 if side == "SELL" else 10**8,
                    quantity=quantity,
                )
        await asyncio.sleep(1/100)


async def catch_trades_send_limit_order():
    global flag_1, side, flag_2
    async with websockets.connect(socket_dydx) as sock:
        await sock.send(json.dumps(req))
        await sock.recv()  # trash response
        await sock.recv()  # trash response
        while True:
            data = await sock.recv()
            if flag_1:
                json_data = json.loads(data)
                if not flag_2:
                    if "fills" in json_data["contents"] and json_data["contents"]["fills"]:
                        flag_2 = True
                        now = datetime.now()
                        csv_writer.writerow(["T", side, str(trailing_percent),
                                             now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # T = Trailing
                        dydx_connector.send_trailing_stop_order(
                            symbol=market,
                            side=side,
                            price=1 if side == "SELL" else 10**8,
                            quantity=quantity,
                            trailing_percent=trailing_percent if side == "BUY" else 0 - trailing_percent,
                        )
                        price = float(json_data["contents"]["fills"][0]["price"]) * (1 + profit_threshold)
                        csv_writer.writerow(["L", side, str(price), now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # L = Limit
                        dydx_connector.send_limit_order(
                            symbol=market,
                            side="BUY" if side == "SELL" else "SELL",
                            price=price - (price % 0.1),
                            quantity=quantity,
                        )
                else:
                    if "fills" in json_data["contents"] and json_data["contents"]["fills"]:
                        now = datetime.now()
                        csv_writer.writerow(["C", "Filled", now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")])  # C = Cancel,
                        dydx_connector.cancel_all_orders(market=market)
                        flag_2 = False
                        flag_1 = False


loop = asyncio.get_event_loop()
asyncio.ensure_future(catch_signal_send_market_order())
asyncio.ensure_future(catch_trades_send_limit_order())
asyncio.ensure_future(close_positions())
loop.run_forever()


