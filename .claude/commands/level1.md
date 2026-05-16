# Level 1 — Account & Manual Trading

Use this skill to check account status and place manual trades on the Alpaca paper account.

## What you can ask

- "What's my account balance?" → run `uv run python core/account.py`
- "Show my positions" → run `uv run python core/account.py`
- "Get the price of TSLA" → run `uv run python core/market_data.py TSLA`
- "Buy 2 shares of NVDA" → run `uv run python core/trade.py buy NVDA 2`
- "Sell 1 share of AAPL" → run `uv run python core/trade.py sell AAPL 1`
- "Show my open orders" → run `uv run python core/trade.py`
- "Cancel all orders" → run `uv run python core/trade.py cancel`
- "Close all positions" → run `uv run python core/trade.py close`
- "Show last 10 days of bars for MSFT" → run `uv run python core/market_data.py MSFT 10`

## Instructions

When the user asks to check account info, get a quote, or place a trade:
1. Run the appropriate command from the working directory `C:\Users\advir\Desktop\alpaca-trading`.
2. Report the output back to the user in plain language.
3. For buy/sell orders, confirm the symbol, quantity, and order status after placing.
4. Warn the user if the market is closed (orders will queue for the next open).

All commands use `uv run python` to ensure the correct virtual environment is used.
All trades execute on the **paper trading** account — no real money involved.
