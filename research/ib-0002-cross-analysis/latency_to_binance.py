import asyncio
import websockets, json
from datetime import datetime

symbol = "btcusd_perp"
socket = f"wss://dstream.binance.com/ws/{symbol}@trade"

stats = dict()
stats["max"] = -1
stats["min"] = 10 ** 3


async def get_trades():
    async with websockets.connect(socket) as sock:
        for i in range(0, 100):
            data = await sock.recv()
            recv_time = datetime.now()
            json_data = json.loads(data)
            print(json_data)
            delta = recv_time - datetime.fromtimestamp(json_data["E"] / 1000)
            stats["max"] = max(delta.total_seconds(), stats["max"])
            stats["min"] = min(delta.total_seconds(), stats["min"])


loop = asyncio.get_event_loop()
loop.run_until_complete(get_trades())

print(f"MAX: {stats['max']}\n" f"MIN: {stats['min']}\n")
