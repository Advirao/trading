"""
core/market_data.py — Real-time quotes and historical price bars.

Wraps the Alpaca market data API for:
  - Latest bid/ask quote for any ticker
  - Daily OHLCV bars for the past N days

Uses the IEX data feed (free, no subscription required).

Run directly to inspect a symbol:
    uv run python core/market_data.py AAPL
    uv run python core/market_data.py TSLA 10
"""

import sys                                               # argv for CLI and sys.path
from pathlib import Path                                 # resolve project root
# Add project root so "from core.xxx" works when run directly or imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone       # date range for bars

from alpaca.data.requests import (
    StockLatestQuoteRequest,   # request object for a single latest quote
    StockBarsRequest,          # request object for historical daily bars
)
from alpaca.data.timeframe import TimeFrame              # bar granularity (Day, Hour, etc.)
from alpaca.data.enums import DataFeed                   # IEX = free feed, SIP = paid feed

from core.config import data_client                      # authenticated Alpaca data client


def get_quote(symbol: str):
    """Return the latest bid/ask Quote object for the given ticker.

    Fields include: ask_price, bid_price, ask_size, bid_size, timestamp.
    """
    req    = StockLatestQuoteRequest(symbol_or_symbols=symbol)  # wrap symbol in request
    quotes = data_client.get_stock_latest_quote(req)            # returns dict[symbol -> Quote]
    return quotes[symbol]                                        # extract the single quote


def get_latest_price(symbol: str) -> float:
    """Return a single float representing the current market price.

    Uses ask_price as the primary source; falls back to bid_price if ask is zero.
    This is good enough for stop calculations — use a full order book for precise fills.
    """
    quote = get_quote(symbol)
    # ask_price is None or 0 outside market hours — fall back to bid in that case
    return float(quote.ask_price or quote.bid_price)


def get_bars(symbol: str, days: int = 5):
    """Return a list of daily OHLCV Bar objects for the last `days` calendar days.

    Args:
        symbol: Ticker, e.g. "AAPL"
        days:   Number of calendar days to look back (default 5, ~1 trading week)

    Returns:
        List of Bar objects with .open, .high, .low, .close, .volume, .timestamp
    """
    end   = datetime.now(timezone.utc)            # end = now (UTC required by Alpaca)
    start = end - timedelta(days=days)            # start = N days ago

    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,                  # one bar per trading day
        start=start,
        end=end,
        feed=DataFeed.IEX,                        # IEX = free feed, no subscription needed
    )

    bars = data_client.get_stock_bars(req)        # returns dict[symbol -> list[Bar]]
    return bars[symbol]                            # extract bars for this symbol


def get_bars_multi(symbols: list, days: int = 45) -> dict:
    """Return a dict of {symbol -> list[Bar]} for all symbols in one batched SDK call.

    Uses 45 calendar days by default to guarantee 20+ trading days for RSI(14)/SMA(20).
    Symbols with no data (new listings, gaps) map to an empty list.
    """
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )

    result = data_client.get_stock_bars(req)
    # BarSet uses dict-style key access; missing symbols raise KeyError so we catch them
    out = {}
    for sym in symbols:
        try:
            out[sym] = list(result[sym])
        except (KeyError, TypeError):
            out[sym] = []
    return out


def print_quote(symbol: str):
    """Print a one-line bid/ask summary for the given symbol."""
    q = get_quote(symbol)
    print(f"{symbol}  bid=${q.bid_price}  ask=${q.ask_price}  size={q.ask_size}")


if __name__ == "__main__":
    # Allow: python core/market_data.py AAPL [days]
    _symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
    _days   = int(sys.argv[2])    if len(sys.argv) > 2 else 5

    print_quote(_symbol)

    _bars = get_bars(_symbol, days=_days)
    print(f"\nLast {len(_bars)} daily bars for {_symbol}:")
    for b in _bars:
        # Print standard OHLCV columns aligned for easy reading
        print(
            f"  {b.timestamp.date()}"
            f"  O={b.open:.2f}"
            f"  H={b.high:.2f}"
            f"  L={b.low:.2f}"
            f"  C={b.close:.2f}"
            f"  V={int(b.volume):,}"
        )
