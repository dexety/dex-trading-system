import asyncio
import traceback
from datetime import datetime

from binance import AsyncClient, Client, BinanceSocketManager
from binance.enums import TIME_IN_FORCE_GTC, TIME_IN_FORCE_IOC, ORDER_TYPE_LIMIT

from depth_cache import DepthCache
from utils.logger.logger import Logger


def dt_to_ms_timestamp(date_time: datetime):
    return int(date_time.timestamp()) * 1000


class BinanceConnector:
    # pylint: disable=logging-fstring-interpolation
    depth_caches = {}
    symbol_infos = {}
    run_duration = 0

    exchange_data_task = None
    user_data_task = None
    started = False

    order_book_listeners = []
    kline_listeners = []
    trade_listeners = []
    execution_report_listeners = []
    finish_listeners = []

    def __init__(self, api_key, api_secret, symbols):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbols = symbols

        self.sync_client = Client(self.api_key, self.api_secret)

        for symbol in self.symbols:
            self.get_cached_order_book(symbol)

        Logger.info("binance connector has been inited")

    @staticmethod
    def get_commission():
        return 0.001

    def add_order_book_listener(self, listener):
        if self.started:
            Logger.error("cannot add listener after start")
            return
        self.order_book_listeners.append(listener)
        Logger.info("added order_book listener")

    def add_trade_listener(self, listener):
        if self.started:
            Logger.error("cannot add listener after start")
            return
        self.trade_listeners.append(listener)
        Logger.info("added trade listener")

    def get_cached_symbol_info(self, symbol):
        if symbol not in self.symbol_infos:
            self.symbol_infos[symbol] = self.sync_client.get_symbol_info(symbol)
        return self.symbol_infos[symbol]

    def trunc_price(self, symbol, price):
        symbol_info = self.get_cached_symbol_info(symbol)
        tick_size = 0.01
        for symbol_filter in symbol_info["filters"]:
            if symbol_filter["filterType"] == "PRICE_FILTER":
                tick_size = symbol_filter["tick_size"]
        return self._trunc(price, float(tick_size))

    def trunc_quantity(self, symbol, quantity):
        symbol_info = self.get_cached_symbol_info(symbol)
        step_size = 0.01
        for symbol_filter in symbol_info["filters"]:
            if symbol_filter["filterType"] == "LOT_SIZE":
                step_size = symbol_filter["step_size"]
        return self._trunc(quantity, float(step_size))

    def get_cached_order_book(self, symbol):
        if symbol not in self.depth_caches:
            raw_order_book = self.sync_client.get_order_book(symbol=symbol)
            depth_cache = DepthCache(symbol)
            for ask in raw_order_book["asks"]:
                depth_cache.add_ask(ask)
            for bid in raw_order_book["bids"]:
                depth_cache.add_bid(bid)
            self.depth_caches[symbol] = depth_cache
        return self.depth_caches[symbol]

    def get_all_balances(self):
        account_info = self.sync_client.get_account()
        balances = {}
        for balance_info in account_info["balances"]:
            total = float(balance_info["free"]) + float(balance_info["locked"])
            if total > 0:
                balances[balance_info["asset"]] = total
        return balances

    def send_limit_order(self, *, symbol, side, price, quantity, our_id):
        Logger.debug(
            f"""send limit order:
                symbol: {symbol}
                side: {side}
                price: {str(price)}
                quantity: {str(quantity)}
                our_id: {str(our_id)}"""
        )
        self.sync_client.create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            price=price,
            quantity=quantity,
            newClientOrderId=our_id,
        )

    def send_ioc_order(self, *, symbol, side, price, quantity, our_id):
        Logger.debug(
            f"""send ioc order:
                symbol: {symbol}
                side: {side}
                price: {str(price)}
                quantity: {str(quantity)}
                our_id: {str(our_id)}"""
        )
        self.sync_client.create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_IOC,
            price=price,
            quantity=quantity,
            newClientOrderId=our_id,
        )

    def cancel_order(self, symbol, our_id):
        Logger.debug(f"canceled order: symbol: {symbol} our_id: {str(our_id)}")
        self.sync_client.cancel_order(
            symbol=symbol, origClientOrderId=str(our_id)
        )

    def get_historical_trades(self, symbol, from_id, limit):
        return self.sync_client.get_historical_trades(
            symbol=symbol,
            fromId=from_id,
            limit=limit,
        )

    def get_historical_aggregated_trades(self, symbol, start_dt, end_dt):
        trades = []
        current_start_timestamp = dt_to_ms_timestamp(start_dt)
        end_timestamp = dt_to_ms_timestamp(end_dt)
        while current_start_timestamp < end_timestamp:
            hour_delta = min(
                1000 * 60 * 60, end_timestamp - current_start_timestamp
            )
            trades.extend(
                self.sync_client.get_aggregate_trades(
                    symbol=symbol,
                    startTime=current_start_timestamp,
                    endTime=current_start_timestamp + hour_delta,
                )
            )
            current_start_timestamp += hour_delta + 1
        return trades

    def get_futures_historical_aggregated_trades(
        self, symbol, start_dt, end_dt
    ):
        trades = []
        time_bias = 3 * 60 * 60 * 1000
        current_start_timestamp = dt_to_ms_timestamp(start_dt) + time_bias
        end_timestamp = dt_to_ms_timestamp(end_dt) + time_bias
        while current_start_timestamp < end_timestamp:
            Logger.debug(
                f"""binance::get_historical_aggregated_trades
                    start timestamp: {str(current_start_timestamp)}
                    end timestamp: {str(end_timestamp)}"""
            )
            aggregated_trades = self.sync_client.futures_aggregate_trades(
                symbol=symbol,
                startTime=current_start_timestamp,
            )

            if len(aggregated_trades) > 0:
                first_id = aggregated_trades[0]["f"]
                last_id = aggregated_trades[-1]["l"]
                current_id = first_id
                while current_id < last_id:
                    trades.extend(
                        self.sync_client.futures_historical_trades(
                            symbol=symbol,
                            fromId=current_id,
                            limit=min(999, last_id - current_id),
                        )
                    )
                    current_id += 1000

            current_start_timestamp = trades[-1]["time"] + 1
        for trade in trades:
            trade["time"] -= time_bias
        return trades

    async def start(self, run_duration):
        if self.started:
            Logger.error("connector already started")
            return
        self.started = True
        self.run_duration = run_duration
        await self._async_start()
        Logger.info("binance connector has been started")

    def _call_order_book_listeners(self, depth_update):
        # self.depth_caches[depth_update['symbol']].apply_orders(depth_update)
        for listener in self.order_book_listeners:
            listener(self.depth_caches[depth_update["symbol"]])

    def _call_trade_listeners(self, trade):
        # self.depth_caches[trade['symbol']].apply_trade(trade)
        for listener in self.trade_listeners:
            listener(trade)

    def _call_execution_report_listeners(self, execution_report):
        for listener in self.execution_report_listeners:
            listener(execution_report)

    async def _async_start(self):
        self.exchange_data_task = asyncio.create_task(
            self._subscribe_exchange_data()
        )

        if self.exchange_data_task:
            await self.exchange_data_task
        if self.user_data_task:
            await self.user_data_task

    async def _subscribe_exchange_data(self):
        client = await AsyncClient.create()
        binance_manager = BinanceSocketManager(client)

        streams = []

        for symbol in self.symbols:
            lower_symbol = symbol.lower()
            streams.extend(
                [
                    lower_symbol + "@trade",
                    lower_symbol + "@depth",
                ]
            )

        Logger.info(f"subscribe for exchange data streams: {str(streams)}")

        multiplex_socket = binance_manager.futures_multiplex_socket(streams)

        stop_time = datetime.utcnow() + self.run_duration
        async with multiplex_socket as msm_socket:
            while datetime.utcnow() < stop_time:
                update = await msm_socket.recv()
                try:
                    stream = update["stream"]
                    if stream.endswith("trade"):
                        trade = {}
                        trade["size"] = float(update["data"]["q"])
                        trade["side"] = "BUY" if update["data"]["m"] else "SELL"
                        trade["price"] = float(update["data"]["p"])
                        trade["createdAt"] = (
                            datetime.fromtimestamp(update["data"]["E"] / 1000)
                        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                        trade["exchange"] = "binance"
                        trade["symbol"] = update["data"]["s"]
                        trade["recieveTime"] = (datetime.utcnow()).strftime(
                            "%Y-%m-%dT%H:%M:%S.%fZ"
                        )
                        self._call_trade_listeners(trade)
                    elif stream.endswith("depth"):
                        self._call_order_book_listeners(update["data"])
                    else:
                        Logger.error(f"unknown message: {update}")
                except Exception as error:
                    Logger.error(
                        f"exchange data exception: {str(error)} traceback: {traceback.format_exc()}"
                    )

    @staticmethod
    def _trunc(price, tick_size):
        # pylint: disable=consider-using-f-string
        num = 0
        while tick_size < 1:
            num += 1
            tick_size *= 10
        string = f"{price}"
        if "e" in string or "E" in string:
            return "{0:.{1}f}".format(price, num)
        iteration, _, dec = string.partition(".")
        return float(".".join([iteration, (dec + "0" * num)[:num]]))
