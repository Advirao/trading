"""
strategies/wheel.py — Level 3b: Wheel Strategy Options Bot (pure Python execution).

This script handles ORDER EXECUTION only. All reasoning about when to close, roll,
and what strike/expiry to pick is done by Claude Code via the /level3 slash command
using your Claude subscription — no API key required.

The wheel is a two-stage, repeating options income strategy:

  Stage 1 — Sell a cash-secured put (CSP):
    • Receive premium upfront.
    • If the stock stays above the strike → put expires worthless; keep the premium.
    • If the stock falls below the strike → assigned 100 shares at the strike price.

  Stage 2 — Sell a covered call (CC) on the assigned shares:
    • If stock stays below call strike → call expires; keep shares + premium.
    • If stock rises above call strike → shares called away; restart at Stage 1.

Requirements:
  • Options approval on your account (your paper account is Level 3 ✓).
  • Each contract = 100 shares → need $strike × 100 in buying power for a CSP.

Usage:
    # Claude Code suggests strike/expiry via /level3, then calls this script:
    uv run python strategies/wheel.py --symbol AAPL --dry-run
    uv run python strategies/wheel.py --symbol AAPL --strike 270 --expiry 2025-06-20 --dry-run
    uv run python strategies/wheel.py --symbol AAPL --strike 295 --expiry 2025-06-20 --stage call
    uv run python strategies/wheel.py --status
    uv run python strategies/wheel.py --monitor --dry-run
"""

import argparse
import sys
import time
from datetime import datetime, date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config      import API_KEY, SECRET_KEY
from core.market_data import get_latest_price
from db import open_wheel_leg, close_wheel_leg, get_open_wheel_legs


# ── Pure-Python strike/expiry helpers (no LLM needed — just math) ─────────────

def _suggest_strike(current_price: float, option_type: str) -> float:
    """Return a strike 10% OTM rounded to the nearest dollar."""
    if option_type == "put":
        return round(current_price * 0.90)   # 10% below — OTM put
    return round(current_price * 1.10)        # 10% above — OTM call


def _suggest_expiry(weeks_out: int = 3) -> str:
    """Return the next Friday at least `weeks_out` weeks from today (YYYY-MM-DD)."""
    from datetime import timedelta
    target = date.today() + timedelta(weeks=weeks_out)
    days_until_friday = (4 - target.weekday()) % 7
    return (target + timedelta(days=days_until_friday)).strftime("%Y-%m-%d")

# ── Alpaca REST configuration ─────────────────────────────────────────────────
# The SDK's TradingClient doesn't yet support options order submission in all versions,
# so we call the REST API directly using raw requests + auth headers.
OPTIONS_BASE = "https://paper-api.alpaca.markets/v2"  # paper trading base URL
HEADERS = {
    "APCA-API-KEY-ID":     API_KEY,     # public key — sent in every request header
    "APCA-API-SECRET-KEY": SECRET_KEY,  # private key — treat like a password
    "Content-Type":        "application/json",  # we send JSON payloads
}


# ── Options contract lookup ───────────────────────────────────────────────────

def get_option_contracts(symbol: str, expiry: str, strike: float, option_type: str) -> list[dict]:
    """Search Alpaca for active option contracts matching the given criteria.

    Args:
        symbol:      Underlying ticker, e.g. "AAPL"
        expiry:      Expiration date string YYYY-MM-DD, e.g. "2025-06-20"
        strike:      Strike price in dollars, e.g. 270.0
        option_type: "put" or "call"

    Returns:
        List of matching contract dicts. Each dict includes:
          symbol, strike_price, expiration_date, bid_price, ask_price.
        May be empty if no contracts match — caller should check.
    """
    resp = requests.get(
        f"{OPTIONS_BASE}/options/contracts",
        headers=HEADERS,
        params={
            "underlying_symbols": symbol,        # filter by the stock we care about
            "expiration_date":    expiry,         # exact expiry date
            "strike_price_gte":   strike - 1,    # small range around target strike
            "strike_price_lte":   strike + 1,    # handles rounding in contract names
            "type":               option_type,   # "put" or "call"
            "status":             "active",       # exclude expired or delisted contracts
        },
        timeout=15,
    )
    resp.raise_for_status()  # surface HTTP errors immediately
    return resp.json().get("option_contracts", [])  # Alpaca wraps the list in this key


# ── Order placement ───────────────────────────────────────────────────────────

def place_option_order(contract_symbol: str, qty: int, side: str, dry_run: bool) -> dict | None:
    """Submit an options order to Alpaca (or simulate it in dry-run mode).

    To open/write an option we sell it (side="sell").
    To close a position we buy it back (side="buy").

    Args:
        contract_symbol: OCC option symbol, e.g. "AAPL250620P00270000"
        qty:             Number of contracts (each = 100 shares)
        side:            "sell" to write/open, "buy" to close/buy-back
        dry_run:         If True, skip the real HTTP call

    Returns:
        Order response dict with .id and .status, or a simulated stub in dry-run.
    """
    action_label = "[DRY RUN] " if dry_run else ""
    print(f"  {action_label}{side.upper()} {qty} contract(s) of {contract_symbol}")

    if dry_run:
        # Return a fake order dict so callers don't need to special-case None
        return {"id": "dry-run", "status": "simulated"}

    payload = {
        "symbol":         contract_symbol,  # OCC symbol uniquely identifies the contract
        "qty":            str(qty),         # Alpaca requires qty as a string
        "side":           side,             # "sell" to open (write), "buy" to close
        "type":           "market",         # fill at the best available price
        "time_in_force":  "day",            # cancel if unfilled by market close
        "order_class":    "simple",         # no bracket/OCO — plain single order
    }
    resp = requests.post(f"{OPTIONS_BASE}/orders", headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()  # full order object from Alpaca


# ── Position inspection ───────────────────────────────────────────────────────

def get_all_positions() -> list[dict]:
    """Return all open positions (stocks and options) from Alpaca."""
    resp = requests.get(f"{OPTIONS_BASE}/positions", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()  # list of position objects


def has_enough_shares(symbol: str, min_shares: int = 100) -> bool:
    """Return True if we hold at least `min_shares` of `symbol` as stock (not options).

    We need 100 shares per contract to legally sell a covered call.
    Without them it becomes a naked call — requires much higher margin and risk.
    """
    for pos in get_all_positions():
        # Skip option positions (asset_class = "us_option") — we only want the stock
        if pos.get("symbol") == symbol and pos.get("asset_class") != "us_option":
            return float(pos.get("qty", 0)) >= min_shares
    return False  # position not found or insufficient qty


# ── Wheel Stage 1: Sell a cash-secured put ───────────────────────────────────

def sell_put(symbol: str, strike: float | None, expiry: str | None, contracts: int, dry_run: bool):
    """Stage 1 of the wheel: write a cash-secured put.

    If strike or expiry are omitted, auto-suggests 10% OTM and ~3 weeks out.
    Use /level3 in Claude Code for full reasoning on strike/expiry choice.
    """
    if strike is None or expiry is None:
        current_price = get_latest_price(symbol)
        if strike is None:
            strike = _suggest_strike(current_price, "put")
            print(f"  [AUTO] Strike: ${strike} (10% OTM below ${current_price:.2f})")
        if expiry is None:
            expiry = _suggest_expiry(weeks_out=3)
            print(f"  [AUTO] Expiry: {expiry} (~3 weeks out)")

    print(f"\n[WHEEL STAGE 1] Selling cash-secured put")
    print(f"  {symbol}  strike=${strike}  expiry={expiry}  contracts={contracts}")

    # Look up the exact OCC contract symbol from Alpaca's contract database
    matches = get_option_contracts(symbol, expiry, strike, "put")
    if not matches:
        print(f"  [ERROR] No active put contracts found for {symbol} ${strike} exp {expiry}")
        print("  Tip: try a round strike price (e.g. 270, 275) or verify the expiry date")
        return

    contract        = matches[0]               # use the closest matching contract
    contract_symbol = contract["symbol"]       # e.g. AAPL250620P00270000
    bid             = contract.get("bid_price")  # what the market will pay us to take the put
    ask             = contract.get("ask_price")  # what we'd pay to buy it back immediately

    print(f"  Contract: {contract_symbol}  bid=${bid}  ask=${ask}")

    order = place_option_order(contract_symbol, contracts, "sell", dry_run)
    if order:
        # Estimate premium: bid price × 100 shares/contract × number of contracts
        # Using bid (not mid) for a conservative estimate of actual fill
        est_premium = float(bid or 0) * 100 * contracts
        print(f"  Order submitted: id={order.get('id')}  est. premium=${est_premium:.2f}")
        if not dry_run:
            # Record this leg in the DB for status tracking and P&L calculation
            open_wheel_leg(symbol, "put", contract_symbol, strike, expiry, est_premium)


# ── Wheel Stage 2: Sell a covered call ───────────────────────────────────────

def sell_call(symbol: str, strike: float | None, expiry: str | None, contracts: int, dry_run: bool):
    """Stage 2 of the wheel: write a covered call against existing shares.

    If strike or expiry are omitted, auto-suggests 10% OTM above current price.
    Use /level3 in Claude Code for full reasoning on strike/expiry choice.
    """
    if not dry_run and not has_enough_shares(symbol, min_shares=100 * contracts):
        print(f"  [ERROR] Need {100 * contracts} shares of {symbol} to sell {contracts} covered call(s)")
        print("  Run Stage 1 first, or wait until your put is assigned.")
        return

    if strike is None or expiry is None:
        current_price = get_latest_price(symbol)
        if strike is None:
            strike = _suggest_strike(current_price, "call")
            print(f"  [AUTO] Strike: ${strike} (10% OTM above ${current_price:.2f})")
        if expiry is None:
            expiry = _suggest_expiry(weeks_out=3)
            print(f"  [AUTO] Expiry: {expiry} (~3 weeks out)")

    print(f"\n[WHEEL STAGE 2] Selling covered call")
    print(f"  {symbol}  strike=${strike}  expiry={expiry}  contracts={contracts}")

    matches = get_option_contracts(symbol, expiry, strike, "call")
    if not matches:
        print(f"  [ERROR] No active call contracts found for {symbol} ${strike} exp {expiry}")
        return

    contract        = matches[0]
    contract_symbol = contract["symbol"]
    bid             = contract.get("bid_price")
    ask             = contract.get("ask_price")

    print(f"  Contract: {contract_symbol}  bid=${bid}  ask=${ask}")

    order = place_option_order(contract_symbol, contracts, "sell", dry_run)
    if order:
        est_premium = float(bid or 0) * 100 * contracts
        print(f"  Order submitted: id={order.get('id')}  est. premium=${est_premium:.2f}")
        if not dry_run:
            open_wheel_leg(symbol, "call", contract_symbol, strike, expiry, est_premium)


# ── Status display ────────────────────────────────────────────────────────────

def show_status():
    """Print all open wheel legs from the local SQLite database."""
    legs = get_open_wheel_legs()
    if not legs:
        print("No open wheel positions.")
        return
    # Fixed-width columns for easy reading
    print(f"\n{'ID':<4} {'Symbol':<8} {'Stage':<6} {'Strike':>8} {'Expiry':<12} {'Premium':>10} {'Opened'}")
    print("-" * 70)
    for leg in legs:
        print(
            f"{leg['id']:<4} "
            f"{leg['symbol']:<8} "
            f"{leg['stage']:<6} "
            f"${leg['strike']:>7.2f} "
            f"{leg['expiry']:<12} "
            f"${leg['premium']:>9.2f}  "
            f"{leg['opened_at'][:16]}"   # trim seconds for cleaner display
        )


# ── LLM monitor loop ──────────────────────────────────────────────────────────

def _days_to_expiry(expiry_str: str) -> int:
    """Return calendar days from today to the expiry date string."""
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return max(0, (expiry - date.today()).days)


def get_option_current_premium(contract_symbol: str) -> float | None:
    """Return the current ask price for an open option position (the buy-back cost)."""
    resp = requests.get(
        f"{OPTIONS_BASE}/positions/{contract_symbol}",
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    pos = resp.json()
    # current_price on an options position is the per-share price; multiply by 100 for per-contract
    return float(pos.get("current_price", 0)) * 100


def monitor(interval: int, dry_run: bool):
    """Poll open wheel legs every `interval` seconds and ask Claude whether to act.

    For each open leg:
      1. Get the current buy-back premium from Alpaca.
      2. Applies the 50% profit rule — closes early if half the premium is captured.
      3. Flags ITM positions for manual review via Claude Code /level3.

    Run indefinitely until Ctrl+C.
    """
    print(f"[MONITOR] Watching open wheel legs every {interval}s")
    if dry_run:
        print("[MONITOR] DRY RUN — no orders will be placed\n")

    while True:
        legs = get_open_wheel_legs()
        if not legs:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No open legs to monitor.")
        else:
            for leg in legs:
                symbol   = leg["symbol"]
                stage    = leg["stage"]
                strike   = leg["strike"]
                expiry   = leg["expiry"]
                orig_prem = leg["premium"]
                contract = leg["contract_symbol"]
                dte      = _days_to_expiry(expiry)

                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Checking {symbol} {stage.upper()} ${strike} exp {expiry} (DTE={dte})")

                current_price = get_latest_price(symbol)

                # 50% profit rule — close early if we've captured half the premium
                current_prem = get_option_current_premium(contract)
                if current_prem is not None:
                    pct_captured = (orig_prem - current_prem) / orig_prem * 100 if orig_prem else 0
                    print(f"  Buy-back: ${current_prem:.2f}  Captured: {pct_captured:.1f}%  DTE: {dte}")
                    if pct_captured >= 50:
                        print(f"  [ACTION] 50% profit reached — closing early, buying back {contract}")
                        order = place_option_order(contract, 1, "buy", dry_run)
                        if order and not dry_run:
                            close_wheel_leg(leg["id"])
                        continue

                # ITM risk check — flag for Claude Code review via /level3
                itm = (stage == "put" and current_price < strike) or \
                      (stage == "call" and current_price > strike)
                if itm:
                    dist = abs(current_price - strike) / strike * 100
                    print(f"  [ALERT] Position is {dist:.1f}% ITM — consider rolling via /level3")

        print(f"\n  Next check in {interval}s  (Ctrl+C to stop)")
        time.sleep(interval)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Wheel strategy bot — sell puts and covered calls to collect premium."
    )
    parser.add_argument("--symbol",    help="Underlying stock ticker, e.g. AAPL")
    parser.add_argument("--strike",    type=float, default=None,
                        help="Strike price in dollars (omit to auto-suggest via Claude)")
    parser.add_argument("--expiry",    default=None,
                        help="Expiration date YYYY-MM-DD (omit to auto-suggest via Claude)")
    parser.add_argument("--contracts", type=int, default=1,  help="Number of contracts (each = 100 shares)")
    parser.add_argument("--stage",     choices=["put", "call"], default="put",
                        help="put = Stage 1 (sell put), call = Stage 2 (sell covered call)")
    parser.add_argument("--dry-run",   action="store_true", help="Simulate without placing orders")
    parser.add_argument("--status",    action="store_true", help="Show open wheel legs and exit")
    parser.add_argument("--monitor",   action="store_true",
                        help="Poll open legs every --interval seconds; Claude decides when to close or roll")
    parser.add_argument("--interval",  type=int, default=900,
                        help="Monitor poll interval in seconds (default 900 = 15 min)")
    args = parser.parse_args()

    if args.status:
        show_status()
        sys.exit(0)

    if args.monitor:
        monitor(args.interval, args.dry_run)
        sys.exit(0)

    # Place a new wheel leg — symbol is required; strike and expiry are optional (Claude suggests)
    if not args.symbol:
        parser.error("--symbol is required (or use --status / --monitor)")

    if args.stage == "put":
        sell_put(args.symbol.upper(), args.strike, args.expiry, args.contracts, args.dry_run)
    else:
        sell_call(args.symbol.upper(), args.strike, args.expiry, args.contracts, args.dry_run)
