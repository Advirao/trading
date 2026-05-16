"""
core/account.py — Account introspection utilities.

Provides simple functions to read account state from Alpaca:
  - equity, cash, buying power, day P&L
  - all open stock and options positions

Run directly to print a live account snapshot:
    uv run python core/account.py
"""

import sys                                # sys.path so this file runs standalone
from pathlib import Path                  # resolve project root from __file__
# Add the project root so "from core.xxx" works whether run directly or imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import trading_client   # authenticated Alpaca trading client


def get_account():
    """Return the full Alpaca Account object.

    Contains equity, cash, buying power, margin, status, options level, etc.
    """
    return trading_client.get_account()


def get_positions():
    """Return a list of all currently open positions (stocks and options).

    Each position object includes symbol, qty, avg_entry_price,
    market_value, unrealized_pl, and side (long/short).
    """
    return trading_client.get_all_positions()


def get_buying_power() -> float:
    """Return available buying power as a plain float (USD).

    For a margin account this is typically 2× the cash balance.
    For a cash account it equals cash.
    """
    return float(get_account().buying_power)


def print_summary():
    """Print a human-readable account + position snapshot to stdout."""
    account   = get_account()
    positions = get_positions()

    # Day P&L = current equity minus equity recorded at the previous market close
    day_pnl = float(account.equity) - float(account.last_equity)

    print("=== Account Summary ===")
    print(f"Equity:        ${float(account.equity):,.2f}")      # total portfolio value
    print(f"Cash:          ${float(account.cash):,.2f}")         # uninvested cash
    print(f"Buying Power:  ${float(account.buying_power):,.2f}") # available to trade
    print(f"Day P&L:       ${day_pnl:+,.2f}")                    # + green / - red
    print(f"Status:        {account.status}")                     # ACTIVE, RESTRICTED, etc.
    print()

    if positions:
        print("=== Open Positions ===")
        for p in positions:
            # Show key per-position metrics on one line for easy scanning
            print(
                f"  {p.symbol:6s}"
                f"  qty={p.qty:>8s}"
                f"  avg_entry=${float(p.avg_entry_price):,.2f}"
                f"  mkt_val=${float(p.market_value):,.2f}"
                f"  P&L=${float(p.unrealized_pl):+,.2f}"
            )
    else:
        print("No open positions.")


if __name__ == "__main__":
    print_summary()
