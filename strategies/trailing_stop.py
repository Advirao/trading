"""
strategies/trailing_stop.py — Level 2: Trailing Stop Bot (pure Python execution).

This script handles ORDER EXECUTION only. All reasoning and narration is done by
Claude Code via the /level2 slash command, which monitors this bot using your
Claude subscription (no API key required).

To run standalone (without Claude Code monitoring):
    uv run python strategies/trailing_stop.py --symbol AAPL --qty 1
    uv run python strategies/trailing_stop.py --symbol AAPL --qty 2 --stop-pct 8 --ladder-pct 5
    uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --dry-run

To let Claude Code reason at every tick instead, use the /level2 command in Claude Code.

State file: trailing_stop_state.json — survives restarts, readable by Claude Code.
Config file: bot_config.json — edit mid-run to change stop_pct, ladder_pct, or stop the bot.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config      import trading_client
from core.market_data import get_latest_price
from core.trade       import buy_market, sell_market

ROOT        = Path(__file__).parent.parent
STATE_FILE  = ROOT / "trailing_stop_state.json"
CONFIG_FILE = ROOT / "bot_config.json"


# ── State & config persistence ────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_config() -> dict:
    """Read bot_config.json each tick — edit this file mid-run to change params."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# ── Market hours ──────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    return trading_client.get_clock().is_open


# ── Position entry ────────────────────────────────────────────────────────────

def enter_position(symbol: str, qty: float, stop_pct: float, state: dict, dry_run: bool):
    if not dry_run:
        buy_market(symbol, qty)
        time.sleep(2)

    price      = get_latest_price(symbol)
    stop_price = round(price * (1 - stop_pct / 100), 2)

    state[symbol] = {
        "entry_price":       price,
        "highest_price":     price,
        "stop_price":        stop_price,
        "qty":               qty,
        "ladder_levels_hit": [],
    }
    save_state(state)
    tag = "[DRY RUN] " if dry_run else ""
    print(f"{tag}[ENTRY] {symbol}  price=${price:.2f}  stop=${stop_price:.2f}  qty={qty}")


# ── Main monitoring loop ──────────────────────────────────────────────────────

def run(symbol: str, qty: float, stop_pct: float, ladder_pct: float | None,
        interval: int, dry_run: bool):
    """Pure-Python trailing stop loop. Claude Code /level2 can monitor instead."""

    # Write config so Claude Code and the user can see/edit live params
    save_config({"symbol": symbol, "qty": qty, "stop_pct": stop_pct,
                 "ladder_pct": ladder_pct, "active": True})
    print(f"[CONFIG] Edit {CONFIG_FILE.name} mid-run to change params or set active=false to stop.\n")

    state = load_state()

    if symbol not in state:
        if not is_market_open() and not dry_run:
            print("Market closed — entry order queued for next open.")
        enter_position(symbol, qty, stop_pct, state, dry_run)

    print(
        f"[BOT] Monitoring {symbol} every {interval}s | stop={stop_pct}%"
        + (f" | ladder={ladder_pct}%" if ladder_pct else "")
        + (" | DRY RUN" if dry_run else "")
    )

    while True:
        # Hot-reload config each tick
        live = load_config()
        if not live.get("active", True):
            print(f"[{_ts()}] bot_config.json → active=false. Stopping.")
            break
        stop_pct   = live.get("stop_pct",   stop_pct)
        ladder_pct = live.get("ladder_pct", ladder_pct)

        if not is_market_open():
            print(f"[{_ts()}] Market closed — sleeping 60s")
            time.sleep(60)
            continue

        s = state[symbol]

        try:
            price = get_latest_price(symbol)
        except Exception as e:
            print(f"[{_ts()}] Price error: {e} — retry in 30s")
            time.sleep(30)
            continue

        stop = s["stop_price"]
        high = s["highest_price"]

        print(f"[{_ts()}] {symbol}  price=${price:.2f}  high=${high:.2f}  stop=${stop:.2f}  qty={s['qty']}")

        # Stop triggered → sell and exit
        if price <= stop:
            print(f"  [STOP HIT] Selling {s['qty']} shares at ${price:.2f}")
            if not dry_run:
                sell_market(symbol, s["qty"])
                del state[symbol]
                save_state(state)
            print("  Position closed. Bot exiting.")
            break

        # New all-time high → raise the trailing stop
        if price > high:
            new_stop           = round(price * (1 - stop_pct / 100), 2)
            s["highest_price"] = price
            s["stop_price"]    = new_stop
            save_state(state)
            print(f"  ↑ New high! Stop raised to ${new_stop:.2f}")

        # Ladder buy → average down on each configured drop level
        if ladder_pct:
            entry = s["entry_price"]
            for n in range(1, 4):
                level = round(entry * (1 - n * ladder_pct / 100), 2)
                if price <= level and level not in s["ladder_levels_hit"]:
                    print(f"  LADDER BUY #{n} at ${price:.2f} (level=${level:.2f})")
                    if not dry_run:
                        buy_market(symbol, qty)
                        s["qty"] += qty
                    s["ladder_levels_hit"].append(level)
                    save_state(state)

        time.sleep(interval)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trailing stop bot. Use /level2 in Claude Code for AI reasoning at every tick."
    )
    parser.add_argument("--symbol",     required=True)
    parser.add_argument("--qty",        type=float, default=1)
    parser.add_argument("--stop-pct",   type=float, default=10.0)
    parser.add_argument("--ladder-pct", type=float, default=None)
    parser.add_argument("--interval",   type=int,   default=300)
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    run(
        symbol     = args.symbol.upper(),
        qty        = args.qty,
        stop_pct   = args.stop_pct,
        ladder_pct = args.ladder_pct,
        interval   = args.interval,
        dry_run    = args.dry_run,
    )
