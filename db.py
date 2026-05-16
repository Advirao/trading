"""
db.py — SQLite persistence layer shared by all strategies.

Tables:
  seen_trades     — deduplication log for the copy-trading bot.
                    Prevents re-mirroring the same congressional disclosure twice.

  wheel_positions — lifecycle tracking for the wheel strategy.
                    Records each put/call leg, premium collected, and final outcome.

  auto_trades     — audit log for the /auto bot.
                    Tracks every stock buy and options trade placed by the auto scanner.

The database file is created automatically on first import.
Location: alpaca_trading.db (project root, excluded from git via .gitignore)
"""

import sqlite3                 # Python's built-in SQLite driver — no extra install needed
from pathlib import Path       # cross-platform path construction

# Place the database in the project root next to this file.
# Using an absolute path avoids surprises when scripts are run from different directories.
DB_PATH = Path(__file__).parent / "alpaca_trading.db"


def get_conn() -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection.

    row_factory = sqlite3.Row makes rows behave like dicts: row["column"].
    The caller is responsible for using this as a context manager (with get_conn()).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # enables column access by name, not just index
    return conn


def init_db():
    """Create all tables if they don't already exist.

    Called automatically at module import so every script starts with a valid schema.
    IF NOT EXISTS makes this idempotent — safe to call multiple times.
    """
    with get_conn() as conn:
        conn.executescript("""
            -- Deduplication table for congressional trade disclosures.
            -- trade_id is a composite key: "politician|ticker|date|type"
            CREATE TABLE IF NOT EXISTS seen_trades (
                trade_id    TEXT PRIMARY KEY,   -- unique composite key
                politician  TEXT,               -- senator or representative name
                ticker      TEXT,               -- stock symbol traded
                trade_type  TEXT,               -- "Purchase", "Sale (Full)", etc.
                amount      TEXT,               -- dollar range, e.g. "$1,001 - $15,000"
                traded_at   TEXT,               -- transaction date from the disclosure
                recorded_at TEXT DEFAULT (datetime('now'))  -- when we first saw it
            );

            -- Wheel strategy leg tracking: one row per put or call written.
            CREATE TABLE IF NOT EXISTS wheel_positions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT NOT NULL,      -- underlying stock ticker
                stage       TEXT NOT NULL,      -- 'put' (stage 1) or 'call' (stage 2)
                contract_id TEXT,               -- OCC option symbol, e.g. AAPL250620P00270000
                strike      REAL,               -- strike price in dollars
                expiry      TEXT,               -- expiration date YYYY-MM-DD
                premium     REAL,               -- premium collected at open (USD)
                opened_at   TEXT DEFAULT (datetime('now')),  -- when we sold the contract
                closed_at   TEXT,               -- when the leg was resolved (NULL if still open)
                status      TEXT DEFAULT 'open' -- 'open', 'expired', 'assigned', 'closed'
            );

            -- Auto bot trade audit log: one row per trade placed by /auto.
            CREATE TABLE IF NOT EXISTS auto_trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id      TEXT NOT NULL,     -- UUID identifying the scan cycle
                symbol       TEXT NOT NULL,     -- stock ticker
                trade_type   TEXT NOT NULL,     -- 'stock_buy', 'put_sell', 'call_sell'
                score        INTEGER,           -- scanner score at decision time (0-100)
                qty          REAL,              -- shares (stock) or contracts (options)
                order_id     TEXT,              -- Alpaca order ID
                contract_sym TEXT,              -- OCC symbol if options, NULL for stock
                strike       REAL,              -- strike price, NULL for stock
                expiry       TEXT,              -- expiry YYYY-MM-DD, NULL for stock
                est_premium  REAL,              -- estimated premium collected, NULL for stock
                status       TEXT DEFAULT 'open',
                notes        TEXT,              -- Claude's rationale at decision time
                placed_at    TEXT DEFAULT (datetime('now')),
                closed_at    TEXT
            );
        """)


# ── Copy-trading helpers ──────────────────────────────────────────────────────

def is_trade_seen(trade_id: str) -> bool:
    """Return True if this trade_id has already been processed.

    Used by the copy-trading bot before every trade to avoid placing duplicate orders
    when the same disclosure appears in multiple polls.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_trades WHERE trade_id = ?",
            (trade_id,)
        ).fetchone()
        return row is not None  # None means the row does not exist yet


def mark_trade_seen(
    trade_id: str,
    politician: str,
    ticker: str,
    trade_type: str,
    amount: str,
    traded_at: str,
):
    """Insert a trade into seen_trades so it is never processed again.

    INSERT OR IGNORE silently skips if the trade_id is already present,
    providing an extra safety net against race conditions.
    """
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO seen_trades
               (trade_id, politician, ticker, trade_type, amount, traded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (trade_id, politician, ticker, trade_type, amount, traded_at),
        )


# ── Wheel strategy helpers ────────────────────────────────────────────────────

def open_wheel_leg(
    symbol: str,
    stage: str,
    contract_id: str,
    strike: float,
    expiry: str,
    premium: float,
):
    """Record a newly opened put or call leg in the wheel_positions table."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO wheel_positions
               (symbol, stage, contract_id, strike, expiry, premium)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, stage, contract_id, strike, expiry, premium),
        )


def close_wheel_leg(position_id: int, status: str):
    """Mark a wheel leg as resolved with the given final status.

    Args:
        position_id: The row id from wheel_positions.
        status: One of 'expired' (worthless), 'assigned' (exercised), 'closed' (bought back).
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE wheel_positions SET status=?, closed_at=datetime('now') WHERE id=?",
            (status, position_id),
        )


def get_open_wheel_legs() -> list:
    """Return all wheel legs whose status is still 'open', newest first."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM wheel_positions WHERE status='open' ORDER BY opened_at DESC"
        ).fetchall()


# ── Auto bot helpers ──────────────────────────────────────────────────────────

def log_auto_trade(
    scan_id: str,
    symbol: str,
    trade_type: str,
    score: int,
    qty: float,
    order_id: str,
    contract_sym: str = None,
    strike: float = None,
    expiry: str = None,
    est_premium: float = None,
    notes: str = None,
) -> int:
    """Insert a new auto trade record and return its row id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO auto_trades
               (scan_id, symbol, trade_type, score, qty, order_id,
                contract_sym, strike, expiry, est_premium, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, symbol, trade_type, score, qty, order_id,
             contract_sym, strike, expiry, est_premium, notes),
        )
        return cur.lastrowid


def get_open_auto_trades() -> list:
    """Return all auto trades with status='open', newest first."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM auto_trades WHERE status='open' ORDER BY placed_at DESC"
        ).fetchall()


def close_auto_trade(trade_id: int, status: str = "closed"):
    """Mark an auto trade as closed or expired."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE auto_trades SET status=?, closed_at=datetime('now') WHERE id=?",
            (status, trade_id),
        )


def get_all_auto_trades(limit: int = 100) -> list:
    """Return all auto trades (any status), newest first, up to limit rows."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM auto_trades ORDER BY placed_at DESC LIMIT ?", (limit,)
        ).fetchall()


def get_all_wheel_legs(limit: int = 100) -> list:
    """Return all wheel legs (any status), newest first, up to limit rows."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM wheel_positions ORDER BY opened_at DESC LIMIT ?", (limit,)
        ).fetchall()


# ── Auto-initialize on import ─────────────────────────────────────────────────
# Every script that imports db.py gets a valid schema automatically.
init_db()
