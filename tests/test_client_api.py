from datetime import datetime, timedelta
from dydx3.constants import MARKET_BTC_USD, MARKET_ETH_USD, ORDER_SIDE_BUY
from connectors.dydx.connector import DydxConnector, safe_execute

dydx_connector = DydxConnector(MARKET_BTC_USD)


def test_get_user():
    result = dydx_connector.get_user()
    assert result != {}


def test_get_our_accounts():
    result = dydx_connector.get_our_accounts()
    assert result != {}


def test_get_symbol_info():
    result = dydx_connector.get_symbol_info(MARKET_BTC_USD)
    assert result != {}

    result = dydx_connector.get_symbol_info(MARKET_ETH_USD)
    assert result != {}


def test_get_our_positions():
    result = dydx_connector.get_our_positions()
    assert result != {}

    result = dydx_connector.get_our_positions(opened=False)
    assert result != {}

    result = dydx_connector.get_our_positions(
        opened=True, symbol=MARKET_ETH_USD
    )
    assert result != {}

    result = dydx_connector.get_our_positions(
        opened=False, symbol=MARKET_ETH_USD
    )
    assert result != {}


def test_get_our_orders():
    result = dydx_connector.get_our_orders()
    assert result != {}

    result = dydx_connector.get_our_orders(opened=False)
    assert result != {}


def test_get_historical_trades():
    result = dydx_connector.get_historical_trades(
        MARKET_BTC_USD,
        datetime.now() - timedelta(minutes=5),
        datetime.now(),
    )
    assert result != {}


def test_get_order_book():
    result = dydx_connector.get_order_book(MARKET_BTC_USD)
    assert result != {}

    result = dydx_connector.get_order_book(MARKET_ETH_USD)
    assert result != {}


@safe_execute
def test_send_and_cancel_limit_order():
    order = dydx_connector.send_limit_order(
        symbol=MARKET_ETH_USD, side=ORDER_SIDE_BUY, price="1", quantity="0.1"
    )
    assert order != {}
    cancel_order = dydx_connector.cancel_order(order["order"]["id"])
    assert cancel_order != {}
