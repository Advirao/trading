"""
core/config.py — Alpaca API client initialization.

Creates two singleton clients shared across the entire project:
  - trading_client : place/cancel orders, read account & positions
  - data_client    : fetch historical price bars and live quotes

Credentials are loaded from the .env file in the project root.
Never hard-code keys — always read them from environment variables.

Run this file directly to confirm authentication works:
    uv run python core/config.py
"""

import os                                          # read environment variables

from dotenv import load_dotenv                     # parse .env into os.environ
from alpaca.trading.client import TradingClient    # order management + account
from alpaca.data.historical import StockHistoricalDataClient  # price data

# ── Load credentials from .env ────────────────────────────────────────────────
load_dotenv()  # reads .env from the current working directory (project root)

API_KEY    = os.getenv("ALPACA_API_KEY")    # public identifier for the API user
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY") # private key — never log or commit
BASE_URL   = os.getenv("ALPACA_BASE_URL")   # paper: https://paper-api.alpaca.markets

# Fail fast at import time if credentials are missing.
# This surfaces the problem immediately instead of getting a cryptic 401 later.
if not API_KEY or not SECRET_KEY:
    raise EnvironmentError(
        "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env\n"
        "Copy .env.example to .env and fill in your keys."
    )

# ── Build clients ─────────────────────────────────────────────────────────────

# paper=True forces all orders to the paper-trading sandbox (no real money).
# Switch to paper=False only when you are ready for live trading.
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# The data client only reads market prices — it never routes orders.
# It does still need authentication because Alpaca gates real-time data.
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)


# ── Quick connection test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # Fetch the account object to confirm credentials are accepted.
    account = trading_client.get_account()
    print(f"Connected — account {account.account_number}  status={account.status}")
