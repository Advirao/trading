# Alpaca Trading Bot

An AI-powered automated stock trading system built on the [Alpaca](https://alpaca.markets) paper-trading API. Claude Code acts as the bot brain — it reasons, narrates every decision, and adapts mid-run. No separate AI API key required; it runs on your Claude subscription.

> **All trading is paper (simulated). No real money is ever at risk.**

---

## How it works

```
You (in Claude Code)
       ↓  /level1 / /level2 / /level3 / /auto
Claude Code reasons → calls Python scripts → Alpaca paper account
       ↑
  ScheduleWakeup keeps Claude checking prices on your subscription
```

The Python scripts handle **execution only** (placing orders, fetching prices, scanning signals). All reasoning, narration, and decision-making happen inside Claude Code using your subscription.

---

## Web Dashboard (for non-developers)

No terminal needed. Start the point-and-click dashboard:

```bash
uv run streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

| Page | What it does |
|---|---|
| Dashboard | Account balance, positions, day P&L, open orders |
| Scanner | Run the multi-signal scan, approve trades with checkboxes |
| Trade | Manual buy/sell with live price chart, cancel orders |
| Copy Trading | Browse congressional disclosures, mirror a trade |
| Wheel | Set up cash-secured puts and covered calls |
| History | Full trade history from the database |

> The dashboard complements Claude Code — it handles viewing and one-off trades.
> Continuous monitoring loops (`/level2`, `/auto`) still run through Claude Code.

---

## Quick Start

### 1. Prerequisites

| Tool | Install |
|------|---------|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| [uv](https://docs.astral.sh/uv/) | `pip install uv` |
| Free [Alpaca](https://alpaca.markets) account | Sign up → Paper Trading → API Keys |
| [Claude Code](https://claude.ai/code) | Mac/Windows app or `npm i -g @anthropic-ai/claude-code` |
| Free [FMP key](https://financialmodelingprep.com/developer/docs/) | For `/auto` fundamental scoring (optional) |

### 2. Clone and install

```bash
git clone https://github.com/Advirao/trading.git
cd trading
uv sync
```

### 3. Add your credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
ALPACA_API_KEY=your_key_id_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
FMP_API_KEY=your_fmp_key_here   # optional — for /auto fundamental scoring
```

### 4. Verify connection

```bash
uv run python core/account.py
```

Expected output:
```
=== Account Summary ===
Equity:        $100,000.00
Cash:          $100,000.00
Buying Power:  $200,000.00
Day P&L:       $0.00
Status:        ACTIVE

No open positions.
```

### 5. Open Claude Code in this folder

```bash
claude
```

---

## Usage Examples

### Level 1 — Account & Manual Trading

Run these commands directly in your terminal to verify everything works:

```bash
# Check your balance and positions
uv run python core/account.py

# Get live price + 5-day bars for AAPL
uv run python core/market_data.py AAPL

# Get 10-day bars for TSLA
uv run python core/market_data.py TSLA 10

# Buy 1 share of AAPL (paper trade)
uv run python core/trade.py buy AAPL 1

# Check open orders
uv run python core/trade.py

# Sell 1 share of AAPL
uv run python core/trade.py sell AAPL 1

# Cancel all open orders
uv run python core/trade.py cancel

# Close all positions
uv run python core/trade.py close
```

Or use Claude Code's `/level1` command and just ask:
- *"What's my balance?"*
- *"Buy 2 shares of NVDA"*
- *"Show me TSLA's price and last 10 bars"*

---

### Level 2 — Trailing Stop Bot

**With Claude Code as the bot (recommended):**

Open Claude Code and type `/level2`, then say:

> *"Watch AAPL with a 10% trailing stop, 1 share"*

Claude will:
1. Check the current price
2. Enter the position (paper buy)
3. Set a stop 10% below entry
4. Wake itself up every 5 minutes to check the price
5. Narrate every decision: *"Price is $194.20, up 1.2% — new high. Raising stop from $172.71 to $174.78."*
6. Sell automatically when the stop is hit

**To change strategy mid-run** — just tell Claude:
- *"Change the stop to 8%"* → Claude updates it instantly
- *"Add a 5% ladder"* → Claude starts buying on dips
- *"Stop the bot"* → Claude sells and exits

**Standalone mode** (no Claude Code open):

```bash
# Preview without placing orders
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --dry-run

# Start the bot (runs until stop is hit or Ctrl+C)
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --stop-pct 10

# With ladder buys every 5% drop (up to 3 levels)
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --stop-pct 10 --ladder-pct 5
```

State is saved to `trailing_stop_state.json` — the bot resumes if you restart it.

**To change params while the standalone bot is running**, edit `bot_config.json` in the project root:
```json
{ "symbol": "AAPL", "qty": 1, "stop_pct": 8, "ladder_pct": 5, "active": true }
```
Set `"active": false` to stop cleanly.

---

### Level 3a — Congressional Copy Trading

**With Claude Code:**

Type `/level3` and say:
> *"Start copy trading — pick the best politician to follow"*

Claude will browse recent Senate and House disclosures, analyse trade patterns, recommend someone, and start mirroring their trades.

Or tell Claude who you want:
> *"Copy trade Nancy Pelosi, 1 share per trade"*

**Standalone:**

```bash
# Browse recent disclosures
uv run python strategies/copy_trading.py --recent --chamber senate
uv run python strategies/copy_trading.py --recent --chamber house

# Preview mirroring (no real orders)
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1 --dry-run

# Start the live bot (polls every 15 minutes)
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1
```

---

### Level 3b — Wheel Strategy (Options)

**With Claude Code:**

Type `/level3` and say:
> *"Run the wheel strategy on AAPL — pick a strike and expiry for me"*

Claude will:
1. Get the current price and recent bars
2. Reason about the best strike (e.g., 10% OTM) and expiry (2–4 weeks out)
3. Explain the logic and present the premium
4. Execute on your confirmation
5. Monitor every 15 minutes — closing early at 50% profit or rolling if needed

**Standalone:**

```bash
# Stage 1 — Sell a cash-secured put (preview)
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20 --dry-run

# Stage 1 — Execute
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20

# Stage 2 — Sell covered call (after assignment)
uv run python strategies/wheel.py --symbol AAPL --strike 198 --expiry 2025-06-20 --stage call

# Check open wheel positions
uv run python strategies/wheel.py --status

# Monitor open positions (50% profit close, ITM alerts)
uv run python strategies/wheel.py --monitor --dry-run
```

---

### /auto — Autonomous Multi-Signal Trading Bot

The most powerful mode. Claude scans the market every 30 minutes using five signals, presents ranked candidates with full reasoning, and asks for your confirmation before placing any trade.

**Start it:**

Type `/auto` in Claude Code.

**What it scans:**

| Signal | Source |
|--------|--------|
| Momentum (5-day price change) | Alpaca bars |
| RSI(14) — healthy zone 30–55 | Computed from bars |
| Volume surge vs 20-day average | Alpaca bars |
| Congressional buy signals | Quiver Quantitative (free) |
| Fundamentals (P/E, EPS, beta) | FMP API (optional, cached 24h) |

**Options/Wheel candidates** are filtered by:
- Open interest ≥ 500 contracts (liquid)
- Bid-ask spread ≤ 5% of mid (tight)
- DTE 25–50 days (theta sweet spot)
- Covers 2×/3× leveraged ETFs: TQQQ, SOXL, UPRO, SPXL, TECL, FNGU, LABU

**Example confirmation dialog:**

```
=== AUTO SCAN #3 — 2026-05-16 10:35 ===
Buying Power: $20,000   Market: OPEN

--- STOCK CANDIDATES ---
Rank  Symbol  Score  RSI    Mom5d   VolRatio  Copy  Notes
  1   MSFT     74    48.1   +2.8%   1.6x      YES   Steady RSI + congressional signal
  2   NVDA     68    52.3   +4.7%   0.9x      no    Strong momentum
  (skipped: AAPL RSI=76.8 — overbought)

--- WHEEL / OPTIONS CANDIDATES ---
Symbol  Contract               Strike   Expiry      DTE  Bid   OI     Spread  Premium
TQQQ    TQQQ260618P00065000   $65.00   2026-06-18   33  $2.50 4,905   2.1%   $250/contract
PLTR    PLTR260618P00125000   $125.0   2026-06-18   33  $3.79 22,839  0.0%   $379/contract

--- PROPOSED ACTIONS ---
[A] BUY 1 MSFT @ market (~$415 est.)   — score 74, congressional signal
[B] SELL 1 put TQQQ $65 Jun-18         — $250 premium, 33 DTE, 13.2% OTM

Confirm? (A / B / all / none)
```

**Mid-run controls:**
- *"Stop the bot"* → pauses without closing positions
- *"Auto-confirm on"* → executes without asking each scan
- *"Change OTM to 10%"* → updates options filter immediately
- *"Add SMCI to universe"* → adds a symbol to the scan list
- *"Show my positions"* → prints current account + open wheel legs

**Scanner CLI (standalone):**

```bash
uv run python strategies/auto_scanner.py --stocks           # stock scoring table
uv run python strategies/auto_scanner.py --options          # options candidates
uv run python strategies/auto_scanner.py --full             # full JSON (Claude reads this)
uv run python strategies/auto_scanner.py --full --universe AAPL,MSFT,TQQQ,SOXL
```

---

## Verification Checklist

```bash
# 1. Connection test
uv run python core/account.py
# ✓ Shows equity, cash, buying power, status = ACTIVE

# 2. Market data test
uv run python core/market_data.py AAPL
# ✓ Shows bid/ask price and 5 daily bars

# 3. Order test
uv run python core/trade.py buy AAPL 1
# ✓ BUY 1 AAPL order_id=... status=pending_new

uv run python core/trade.py cancel
# ✓ Cancelled 1 order(s)

# 4. Auto scanner test
uv run python strategies/auto_scanner.py --stocks
# ✓ Shows scored stock table with RSI, momentum, volume

uv run python strategies/auto_scanner.py --options
# ✓ Shows qualified put candidates with OI, spread, premium

# 5. Trailing stop dry-run
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --dry-run
# ✓ Prints entry price and stop level, exits without orders

# 6. Copy trading
uv run python strategies/copy_trading.py --recent --chamber senate
# ✓ Shows recent senate trades table
```

---

## Sharing With a Friend

Your friend needs their own Alpaca paper account. They do not need your credentials.

```bash
git clone https://github.com/Advirao/trading.git
cd trading
cp .env.example .env   # fill in their own keys
uv sync
uv run python core/account.py   # should show their own paper account
claude                           # open Claude Code
```

Their credentials are independent — their trades don't affect yours.

---

## Project Structure

```
alpaca-trading/
├── core/                    # Execution library
│   ├── config.py            # Loads .env, creates trading_client and data_client
│   ├── account.py           # Account balance, positions, buying power
│   ├── market_data.py       # Live quotes, OHLCV bars, get_bars_multi()
│   └── trade.py             # Market buy/sell, list/cancel orders, close positions
│
├── strategies/              # Strategy bots — execution only, no AI calls
│   ├── trailing_stop.py     # Level 2: trailing stop with hot-reload config
│   ├── copy_trading.py      # Level 3a: mirrors congressional disclosures
│   ├── wheel.py             # Level 3b: sell puts + covered calls, monitor loop
│   └── auto_scanner.py      # /auto: multi-signal stock + options scanner
│
├── .claude/commands/        # Claude Code slash commands
│   ├── level1.md            # /level1 — account & manual trades
│   ├── level2.md            # /level2 — trailing stop bot (Claude monitors)
│   ├── level3.md            # /level3 — copy trading + wheel strategy
│   ├── schedule.md          # /schedule — Windows Task Scheduler setup
│   └── auto.md              # /auto — autonomous 30-min scan + trade bot
│
├── db.py                    # SQLite helpers (copy trading, wheel, auto trade log)
├── .env                     # Your credentials (gitignored — never committed)
├── .env.example             # Template — fill in and rename to .env
├── .gitignore
├── .python-version          # Pins Python 3.11 for uv
├── pyproject.toml           # uv project config + dependencies
├── CLAUDE.md                # Claude Code project instructions
└── README.md                # This file
```

---

## Claude Code Slash Commands

| Command | What Claude does |
|---------|-----------------|
| `/level1` | Check balance, get quotes, place manual trades in plain English |
| `/level2` | Trailing stop bot — Claude monitors every 5 min, narrates every decision |
| `/level3` | Copy trade a politician (Claude picks who) or run wheel (Claude picks strike/expiry) |
| `/schedule` | Create a Windows Task Scheduler entry to run any bot automatically |
| `/auto` | Autonomous bot — scans every 30 min with 5 signals, confirms before trading |

---

## Disclaimer

This project is for **educational and paper-trading purposes only**.  
Past performance of any strategy does not guarantee future results.  
Always understand a strategy fully before using it with real capital.
