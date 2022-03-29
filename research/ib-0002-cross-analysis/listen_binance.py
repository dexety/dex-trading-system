import asyncio
import websockets
import json

symbol_binance = "btcusd_perp"
socket_binance = f"wss://dstream.binance.com/ws/{symbol_binance}@trade"

async def _listen_binance():
    async with websockets.connect(
        socket_binance, ping_interval=None
    ) as sock:
        while True:
            data = await sock.recv()
            json_data = json.loads(data)
            print(json.dumps(json_data, indent=4))

def _setup():
    loop.create_task(
        _listen_binance(), name="listen binance"
    )

loop = asyncio.get_event_loop()

_setup()
loop.run_forever()