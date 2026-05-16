"""
core/trade.py — Order placement and management.

Provides thin wrappers around the Alpaca orders API for:
  - Market buy / sell
  - Listing open or historical orders
  - Cancelling all open orders
  - Closing all open positions

Run directly to inspect or manage live orders:
    uv run python core/trade.py                       # list open orders
    uv run python core/trade.py buy  AAPL 1           # buy 1 share at market
    uv run python core/trade.py sell AAPL 1           # sell 1 share at market
    uv run python core/trade.py cancel                # cancel all open orders
    uv run python core/trade.py close                 # close all positions
"""

import sys                                            # argv for CLI dispatch and sys.path
from pathlib import Path                              # resolve project root
# Add project root so "from core.xxx" works when run directly or imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpaca.trading.requests import (
    MarketOrderRequest,   # parameters for a market order
    GetOrdersRequest,     # filter parameters when listing orders
)
from alpaca.trading.enums import (
    OrderSide,          # BUY or SELL
    TimeInForce,        # DAY = expires at market close, GTC = good till cancelled
    QueryOrderStatus,   # OPEN / CLOSED / ALL — filter for get_orders
)

from core.config import trading_client               # authenticated Alpaca trading client


def buy_market(symbol: str, qty: float):
    """Submit a market BUY order for `qty` shares of `symbol`.

    Market orders fill immediately at the best available ask price.
    Time-in-force DAY means the order expires if the market is closed
    and it doesn't fill by end of the next session.

    Returns the submitted Order object (with .id and .status).
    """
    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,          # we are buying
        time_in_force=TimeInForce.DAY,  # cancel at end of day if unfilled
    )
    order = trading_client.submit_order(req)
    print(f"BUY  {qty} {symbol}  order_id={order.id}  status={order.status}")
    return order


def sell_market(symbol: str, qty: float):
    """Submit a market SELL order for `qty` shares of `symbol`.

    Requires that you already hold at least `qty` shares.
    Selling more than you own will be rejected by the broker.

    Returns the submitted Order object.
    """
    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.SELL,          # we are selling
        time_in_force=TimeInForce.DAY,
    )
    order = trading_client.submit_order(req)
    print(f"SELL {qty} {symbol}  order_id={order.id}  status={order.status}")
    return order


def get_orders(status: str = "open") -> list:
    """Return a list of orders filtered by status.

    Args:
        status: "open" (default), "closed", or "all"

    Returns:
        List of Order objects ordered by submission time (newest first).
    """
    # Map friendly strings to the SDK enum values
    status_map = {
        "open":   QueryOrderStatus.OPEN,
        "closed": QueryOrderStatus.CLOSED,
        "all":    QueryOrderStatus.ALL,
    }
    req    = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.OPEN))
    return trading_client.get_orders(req)


def cancel_all_orders() -> list:
    """Cancel every open order on the account.

    Returns a list of CancelOrderResponse objects (one per cancelled order).
    Safe to call even when there are no open orders — returns an empty list.
    """
    cancelled = trading_client.cancel_orders()
    print(f"Cancelled {len(cancelled)} order(s).")
    return cancelled


def close_all_positions():
    """Close every open position at market price and cancel any open orders.

    This is a nuclear option — use it to flatten the book entirely.
    cancel_orders=True ensures no resting orders interfere with the closes.
    """
    trading_client.close_all_positions(cancel_orders=True)
    print("All positions closed.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "orders"

    if cmd == "buy" and len(sys.argv) == 4:
        # Usage: trade.py buy AAPL 1
        buy_market(sys.argv[2].upper(), float(sys.argv[3]))

    elif cmd == "sell" and len(sys.argv) == 4:
        # Usage: trade.py sell AAPL 1
        sell_market(sys.argv[2].upper(), float(sys.argv[3]))

    elif cmd == "cancel":
        cancel_all_orders()

    elif cmd == "close":
        close_all_positions()

    else:
        # Default: print all open orders
        orders = get_orders("open")
        if orders:
            print("Open orders:")
            for o in orders:
                print(f"  {o.id}  {o.side.value:4s} {o.qty} {o.symbol}  {o.status}")
        else:
            print("No open orders.")
