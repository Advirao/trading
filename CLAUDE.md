# Alpaca Trading Bot — Claude Code Guide

## Project Overview

An AI-powered automated stock trading system built on the Alpaca paper-trading API.
Claude Code acts as the bot brain — it reasons using your subscription, narrates every decision, and adapts mid-run. No separate Anthropic API key required.

## Folder Structure

```
alpaca-trading/
├── core/                        # Execution library
│   ├── config.py                # Loads .env, creates API clients
│   ├── account.py               # Account balance, positions, buying power
│   ├── market_data.py           # Live quotes, OHLCV bars, batched multi-symbol fetch
│   └── trade.py                 # Market buy/sell, list/cancel orders, close positions
│
├── strategies/                  # Strategy bots — execution only, no AI calls
│   ├── trailing_stop.py         # Level 2: trailing stop with hot-reload config
│   ├── copy_trading.py          # Level 3a: mirrors congressional disclosures via Quiver
│   ├── wheel.py                 # Level 3b: sell puts + covered calls, monitor loop
│   └── auto_scanner.py          # /auto: multi-signal stock + options scanner
│
├── pages/                       # Streamlit multi-page dashboard
│   ├── _shared.py               # Design system: CSS, metric_card, badge, alert, chart helpers
│   ├── 1_Scanner.py             # Auto scanner with candidate cards and score bar chart
│   ├── 2_Trade.py               # Manual buy/sell with live price chart
│   ├── 3_Copy_Trading.py        # Congressional disclosures + politician leaderboard
│   ├── 4_Wheel.py               # Wheel setup + open legs with DTE progress bars
│   └── 5_History.py             # Trade history + cumulative P&L charts
│
├── .claude/commands/            # Slash commands — Claude Code does the reasoning here
│   ├── level1.md                # /level1 — account & manual trades
│   ├── level2.md                # /level2 — Claude monitors trailing stop, reasons every tick
│   ├── level3.md                # /level3 — Claude picks politician, strike, expiry, monitors wheel
│   ├── schedule.md              # /schedule — create Windows Task Scheduler entries
│   └── auto.md                  # /auto — autonomous 30-min scan + trade bot
│
├── .streamlit/
│   └── config.toml              # Dark theme: #0E1117 bg, #2196F3 primary, #E8ECF0 text
│
├── app.py                       # Streamlit entry point — Dashboard (equity, positions, P&L)
├── db.py                        # SQLite helpers (copy trading dedup + wheel + auto trade log)
├── .env                         # Credentials (gitignored)
├── .env.example                 # Template for sharing
├── .gitignore
├── .python-version              # Pins Python 3.11 for uv
├── pyproject.toml               # uv project config + dependencies
├── CLAUDE.md                    # This file
└── README.md                    # Full documentation + sharing guide
```

## Key Files

| File | Purpose |
|------|---------|
| `core/config.py` | Single source of truth for API credentials and client objects |
| `core/market_data.py` | Quotes, bars, and `get_bars_multi()` for batched multi-symbol fetching |
| `db.py` | SQLite schema + helpers — auto-initialises on import, no migration needed |
| `strategies/trailing_stop.py` | Level 2 execution — `/level2` is the Claude-powered version |
| `strategies/copy_trading.py` | Level 3a execution — `/level3` picks the politician |
| `strategies/wheel.py` | Level 3b execution — `/level3` picks strike/expiry and monitors |
| `strategies/auto_scanner.py` | `/auto` execution — scores stocks (RSI, momentum, volume, copy signals, fundamentals) and scans options (OI, spread, DTE) |
| `pages/_shared.py` | Shared design system — CSS injection, `metric_card()`, `badge()`, `alert()`, color palette |
| `app.py` | Streamlit Dashboard — equity, cash, positions table, portfolio donut chart, open orders |
| `.streamlit/config.toml` | Streamlit dark theme configuration |

## Running Commands

Always run from the project root with `uv run python`:

```bash
# Level 1 — Account & manual trading
uv run python core/account.py
uv run python core/market_data.py AAPL
uv run python core/trade.py buy AAPL 1
uv run python core/trade.py sell AAPL 1
uv run python core/trade.py cancel

# Level 2 — Trailing stop (standalone)
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --dry-run
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --stop-pct 10 --ladder-pct 5

# Level 3a — Copy trading
uv run python strategies/copy_trading.py --recent --chamber senate
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1 --dry-run
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1

# Level 3b — Wheel strategy
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20 --dry-run
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20
uv run python strategies/wheel.py --status
uv run python strategies/wheel.py --monitor --dry-run

# /auto — Multi-signal autonomous scanner
uv run python strategies/auto_scanner.py --stocks           # stock scoring table
uv run python strategies/auto_scanner.py --options          # options/wheel candidates
uv run python strategies/auto_scanner.py --full             # full JSON output (Claude reads this)
uv run python strategies/auto_scanner.py --full --universe AAPL,MSFT,TQQQ
```

## Environment Variables (.env)

| Variable | Description |
|----------|-------------|
| `ALPACA_API_KEY` | Alpaca Key ID (from paper-api dashboard) |
| `ALPACA_SECRET_KEY` | Alpaca Secret Key |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` |
| `FMP_API_KEY` | Financial Modeling Prep key (free — for `/auto` fundamental scoring) |

No Anthropic API key needed — Claude Code uses your subscription.

## Streamlit Dashboard

Start the point-and-click dashboard (no terminal skills required):

```bash
uv run streamlit run app.py
```

Open **http://localhost:8501** in your browser.

| Page | What it does |
|------|-------------|
| Dashboard | Equity, cash, buying power, day P&L — portfolio donut chart |
| Scanner | Run multi-signal scan, view candidate cards + score bar chart, approve trades |
| Trade | Manual buy/sell with live Plotly price chart, open orders management |
| Copy Trading | Congressional disclosures, politician leaderboard chart, one-off mirror trades |
| Wheel | Set up puts/calls with DTE progress bars, preview contract bid/ask/OI |
| History | Cumulative P&L charts, full auto bot and wheel leg history |

The Streamlit app is a **control panel and dashboard** — it does not replace Claude Code's AI layer.
Adaptive monitoring loops (`/level2`, `/auto`) still run through Claude Code.

## Dependencies

Managed by uv. Key packages:

| Package | Purpose |
|---------|---------|
| `alpaca-py` | Official Alpaca SDK for trading and market data |
| `python-dotenv` | Load `.env` into environment variables |
| `requests` | HTTP calls for options API, FMP API, and Quiver Quantitative |
| `streamlit` | Web dashboard framework |
| `plotly` | Interactive charts (donut, line, bar) used in the dashboard |

## Architecture

- **Claude Code is the reasoning layer** — slash commands use ScheduleWakeup to keep monitoring positions between wakes, on your subscription.
- **Python scripts are execution-only** — they place orders, fetch prices, and read/write state. Zero AI calls inside them.
- **Hot config**: `bot_config.json` is written at bot startup and re-read every tick. Edit mid-run to change `stop_pct`, `ladder_pct`, or set `active: false` to stop cleanly.
- **State persistence**: `trailing_stop_state.json` (trailing stop), `auto_state.json` (/auto bot), and `alpaca_trading.db` (copy trading + wheel + auto trades) survive restarts.
- **Paper trading**: `TradingClient(paper=True)` — all orders go to the Alpaca sandbox.

## Claude Code Slash Commands

| Command | What Claude does |
|---------|-----------------|
| `/level1` | Account & manual trading in plain English |
| `/level2` | Trailing stop bot — Claude monitors every 5 min, reasons and narrates each tick |
| `/level3` | Copy trading (Claude picks politician) + wheel (Claude picks strike/expiry + monitors) |
| `/schedule` | Create Windows Task Scheduler entries for any bot |
| `/auto` | Fully autonomous bot — scans stocks + options every 30 min using 5 signals, presents ranked candidates, confirms before trading |

## /auto Scoring System

Each stock is scored 0–100 across five dimensions:

| Dimension | Max | Signal |
|-----------|-----|--------|
| Momentum (5d) | 25 | Price change over last 5 trading days |
| RSI(14) | 20 | Healthy zone 30–55; >70 disqualifies |
| Volume ratio | 20 | Recent volume vs 20-day average |
| Copy signal | 20 | Congressional buy disclosures (Quiver) |
| Fundamentals | 15 | P/E, EPS, beta via FMP API (cached 24h) |

Options are filtered by: open interest ≥ 500, bid-ask spread ≤ 5%, DTE 25–50 days.
