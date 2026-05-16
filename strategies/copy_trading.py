"""
strategies/copy_trading.py — Level 3a: Congressional Copy Trading Bot.

Data source: Quiver Quantitative (https://quiverquant.com) — free, no API key needed.
Returns the 1,000 most recent congressional stock disclosures from both chambers.

Strategy logic:
  1. Fetch the latest congressional trades from Quiver Quantitative.
  2. Filter by target politician name (case-insensitive substring match).
  3. For each unseen trade:
       - "Purchase" → buy the same ticker on Alpaca
       - "Sale"     → sell the same ticker on Alpaca
  4. Store seen trade IDs in SQLite to prevent duplicates across polls.

Usage:
    uv run python strategies/copy_trading.py --recent
    uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1 --dry-run
    uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1

Use /level3 in Claude Code to let Claude pick the best politician automatically.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import is_trade_seen, mark_trade_seen
from core.trade import buy_market, sell_market

QUIVER_URL  = "https://api.quiverquant.com/beta/live/congresstrading"
QUIVER_HEADERS = {"Accept": "application/json"}

BUY_KEYWORDS  = {"purchase", "buy"}
SELL_KEYWORDS = {"sale", "sell", "sale_full", "sale_partial", "exchange"}


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_all_trades() -> list[dict]:
    """Fetch the 1,000 most recent congressional trades from Quiver Quantitative.

    Returns an empty list on network error. No API key required.
    """
    try:
        resp = requests.get(QUIVER_URL, headers=QUIVER_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] Quiver API request failed: {e}")
        return []


def fetch_trades_for_politician(politician: str, chamber: str = "both") -> list[dict]:
    """Return trades matching the politician name, optionally filtered by chamber.

    Chamber values from Quiver: "Senate" or "Representatives".
    Uses case-insensitive substring match so "Pelosi" matches "Nancy Pelosi".
    """
    all_trades = fetch_all_trades()
    results = []

    for trade in all_trades:
        name = (trade.get("Representative") or "").lower()
        if politician.lower() not in name:
            continue
        # Chamber filter
        quiver_chamber = (trade.get("House") or "").lower()
        if chamber == "senate" and "senate" not in quiver_chamber:
            continue
        if chamber == "house" and "representative" not in quiver_chamber:
            continue
        results.append(trade)

    return results


# ── Trade classification ──────────────────────────────────────────────────────

def classify_trade(transaction: str) -> str | None:
    """Map Quiver's Transaction field to 'buy', 'sell', or None (skip)."""
    tt = transaction.lower().replace(" ", "_").replace("(", "").replace(")", "")
    if any(k in tt for k in BUY_KEYWORDS):
        return "buy"
    if any(k in tt for k in SELL_KEYWORDS):
        return "sell"
    return None


# ── Trade processing ──────────────────────────────────────────────────────────

def process_trade(trade: dict, qty: float, dry_run: bool):
    """Mirror a single congressional trade on Alpaca if not already seen."""
    name        = trade.get("Representative") or "unknown"
    ticker      = (trade.get("Ticker") or "").upper().strip()
    transaction = trade.get("Transaction") or ""
    amount      = trade.get("Range") or trade.get("Amount") or "unknown"
    traded_at   = trade.get("TransactionDate") or ""
    chamber     = trade.get("House") or ""

    # Skip options, warrants, mutual funds — only mirror stocks
    if trade.get("TickerType") not in ("ST", None, ""):
        return

    # Skip blank or non-tradable tickers
    if not ticker or ticker in ("--", "N/A", ""):
        return

    trade_id = f"{name}|{ticker}|{traded_at}|{transaction}"

    if is_trade_seen(trade_id):
        return

    action = classify_trade(transaction)
    if action is None:
        print(f"  [SKIP] {name}: unrecognised type '{transaction}' for {ticker}")
        mark_trade_seen(trade_id, name, ticker, transaction, str(amount), traded_at)
        return

    print(f"\n[NEW TRADE] {name} ({chamber})  {action.upper()} {ticker}  amount={amount}  date={traded_at}")

    if dry_run:
        print(f"  [DRY RUN] Would {action} {qty} share(s) of {ticker}")
    else:
        try:
            if action == "buy":
                buy_market(ticker, qty)
            else:
                sell_market(ticker, qty)
        except Exception as e:
            print(f"  [ORDER ERROR] {e}")

    mark_trade_seen(trade_id, name, ticker, transaction, str(amount), traded_at)


# ── Display helpers ───────────────────────────────────────────────────────────

def show_recent(chamber: str = "both", limit: int = 25):
    """Print the most recent congressional trades from Quiver Quantitative."""
    all_trades = fetch_all_trades()

    if chamber == "senate":
        trades = [t for t in all_trades if "senate" in (t.get("House") or "").lower()]
    elif chamber == "house":
        trades = [t for t in all_trades if "representative" in (t.get("House") or "").lower()]
    else:
        trades = all_trades

    trades = trades[:limit]

    if not trades:
        print("No trades returned from Quiver Quantitative.")
        return

    print(f"\nRecent congressional trades (source: Quiver Quantitative):")
    print(f"{'Politician':<28} {'Chamber':<16} {'Ticker':<8} {'Transaction':<12} {'Amount':<22} {'Date'}")
    print("-" * 100)
    for t in trades:
        name    = (t.get("Representative") or "")[:26]
        chamber_str = (t.get("House") or "")[:14]
        ticker  = (t.get("Ticker") or "")[:6]
        txn     = (t.get("Transaction") or "")[:10]
        amount  = (t.get("Range") or str(t.get("Amount") or ""))[:20]
        date    = t.get("TransactionDate") or ""
        print(f"{name:<28} {chamber_str:<16} {ticker:<8} {txn:<12} {amount:<22} {date}")


# ── Main polling loop ─────────────────────────────────────────────────────────

def run(politician: str, qty: float, chamber: str, interval: int, dry_run: bool):
    """Poll Quiver Quantitative every `interval` seconds and mirror new trades."""
    print(f"Watching: {politician} ({chamber})")
    print(f"Mirror qty: {qty}  |  Poll every {interval}s  |  Source: Quiver Quantitative (no API key)")
    if dry_run:
        print("[DRY RUN — no orders will be placed]\n")

    while True:
        print(f"[{_ts()}] Polling congressional trades...")
        trades = fetch_trades_for_politician(politician, chamber)

        if not trades:
            print(f"  No new trades found for '{politician}'")
        else:
            for trade in trades:
                process_trade(trade, qty, dry_run)

        print(f"  Next poll in {interval}s")
        time.sleep(interval)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Congressional copy trading bot — mirrors politician stock disclosures. No API key needed."
    )
    parser.add_argument("--politician", default="",
                        help='Name to filter on, e.g. "Nancy Pelosi". Use /level3 in Claude Code to auto-pick.')
    parser.add_argument("--qty",        type=float, default=1,   help="Shares to mirror per trade (default 1)")
    parser.add_argument("--chamber",    choices=["senate", "house", "both"], default="both")
    parser.add_argument("--interval",   type=int,   default=900, help="Poll interval seconds (default 900 = 15 min)")
    parser.add_argument("--dry-run",    action="store_true",     help="Print actions without placing orders")
    parser.add_argument("--recent",     action="store_true",     help="Show recent trades table and exit")
    args = parser.parse_args()

    if args.recent:
        show_recent(args.chamber)
        sys.exit(0)

    if not args.politician:
        parser.error(
            "--politician is required. "
            "Use /level3 in Claude Code to let it browse trades and pick for you."
        )

    run(
        politician = args.politician,
        qty        = args.qty,
        chamber    = args.chamber,
        interval   = args.interval,
        dry_run    = args.dry_run,
    )
