import asyncio
import websockets
import json
from datetime import datetime
from sliding_window import SlidingWindow
from connectors.dydx.connector import DydxConnector
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY


ETH_KEY = ""
ETH_PRIVATE_KEY = ""
dydx_connector = DydxConnector(
    ETH_KEY,
    ETH_PRIVATE_KEY,
    [MARKET_ETH_USD],
)
symbol_binance = "btcusd_perp"
socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"
flag = False
quantity = 0.02
sliding_window = SlidingWindow()


async def catch_signal_send_market_order():
    global flag
    async with websockets.connect(socket_binance) as sock:
        while True:
            data = await sock.recv()
            json_data = json.loads(data)
            if not flag and not json_data["m"]:
                if sliding_window.push_back(float(json_data["p"]), json_data["T"]):
                    max_in_window = sliding_window.get_max()
                    max_timestamp = sliding_window.get_max_timestamp()
                    min_in_window = sliding_window.get_min()
                    min_timestamp = sliding_window.get_min_timestamp()
                    if max_in_window / min_in_window >= 1.0021:
                        # now = datetime.now().timestamp() * 10 ** 3
                        side = ""
                        if max_timestamp > min_timestamp:
                            side = "BUY"
                        elif max_timestamp < min_timestamp:
                            side = "SELL"
                        dydx_connector.send_trailing_stop_order(
                            symbol=MARKET_ETH_USD,
                            side=side,
                            price=1 if side == "SELL" else 10**8,
                            quantity=quantity,
                            trailing_percent=0.14,
                        )
                        flag = True


symbol_dydx = "ETH-USD"
socket_dydx = f"wss://api.dydx.exchange/v3/ws"

req = {
    'type': 'subscribe',
    'channel': 'v3_trades',
    'id': symbol_dydx
}


async def catch_trade_send_limit_order():
    global flag
    async with websockets.connect(socket_dydx) as sock:
        await sock.send(json.dumps(req))
        await sock.recv()  # trash response
        await sock.recv()  # trash response
        while True:
            data = await sock.recv()
            if flag:
                json_data = json.loads(data)
                if # надо проверять на fill, чтобы посылать зеркальную лимитку





loop = asyncio.get_event_loop()
loop.run_until_complete(catch_signal_send_market_order())

