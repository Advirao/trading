# /level3 — Copy Trading & Wheel Strategy (Claude Code as the bot)

You ARE the Level 3 trading bot. You reason about which politician to follow,
what strike and expiry to use, and when to close or roll — using your Claude subscription.
No Anthropic API key needed.

---

## Level 3a — Congressional Copy Trading

### Setup check
First verify `FMP_API_KEY` is set in `.env`. If it shows `your_fmp_key_here`, tell the user to get a free key at financialmodelingprep.com and add it before continuing.

### Step 1 — Browse and pick a politician

If the user hasn't specified a politician, fetch recent trades and reason about who to follow:

```bash
uv run python strategies/copy_trading.py --recent --chamber senate
uv run python strategies/copy_trading.py --recent --chamber house
```

Analyse the output — look for:
- **Consistent buyers** (not mostly sellers or hedgers)
- **Large dollar amounts** (signals high conviction)
- **Liquid tickers** (AAPL, MSFT, NVDA — easy to mirror, not illiquid small-caps)
- **Recency** — trades disclosed in the last 30 days are more actionable

Narrate your reasoning: "I recommend following [Name] because they have made 4 purchases in the past 2 weeks, all in mega-cap tech with amounts over $50,000, indicating high conviction in sector trends."

### Step 2 — Preview before live

```bash
uv run python strategies/copy_trading.py --politician "{NAME}" --qty 1 --dry-run
```

### Step 3 — Start the live bot

```bash
uv run python strategies/copy_trading.py --politician "{NAME}" --qty {QTY} --chamber both
```

### Monitoring with ScheduleWakeup

To keep polling without leaving a terminal open, after each check schedule a wakeup:
```
ScheduleWakeup(delaySeconds=900, prompt="/level3", reason="polling FMP for new {NAME} trades")
```
At each wakeup, run the `--recent` command, check for new disclosures, and decide whether to act.

---

## Level 3b — Wheel Strategy (Options)

### Step 1 — Pick a stock for the wheel

Ask the user for a symbol, or suggest one based on account size and current market conditions.
Good wheel candidates: liquid stocks, implied volatility > 20%, price range $50–$300.

### Step 2 — Suggest strike and expiry

Get the current price:
```bash
uv run python core/market_data.py {SYMBOL}
uv run python core/market_data.py {SYMBOL} 30   # 30-day bars for trend context
```

Then reason about the strike and expiry:
- **Put strike**: 10% below current price as a baseline. Adjust based on support levels and volatility. "AAPL is at $195 with support at $180. I'll suggest $175 (10.3% OTM) to stay safely below support."
- **Call strike** (after assignment): 10% above cost basis. "We own AAPL at $180. I'll suggest $198 — that's 10% above cost basis and near the recent resistance level."
- **Expiry**: 2–4 weeks out. Target the next monthly expiry (third Friday) for maximum liquidity. "June 20 is 3 weeks out — good theta decay, liquid contracts."

Narrate the full reasoning before executing.

### Step 3 — Execute Stage 1 (sell put)

```bash
# Preview first:
uv run python strategies/wheel.py --symbol {SYMBOL} --strike {STRIKE} --expiry {EXPIRY} --dry-run

# Execute:
uv run python strategies/wheel.py --symbol {SYMBOL} --strike {STRIKE} --expiry {EXPIRY}
```

Check the result — confirm the contract symbol, bid/ask, and estimated premium with the user.

### Step 4 — Monitor open positions

```bash
uv run python strategies/wheel.py --status
```

Schedule regular check-ins:
```
ScheduleWakeup(delaySeconds=900, prompt="/level3", reason="checking wheel positions for {SYMBOL}")
```

At each wakeup, check status, get current prices, and reason:

**Close early (50% profit rule):**
> "We collected $3.20 premium on the put. Current bid is $1.45 — that's 55% profit captured with 8 days left. The theta decay rate slows near expiry, so I recommend closing now to free up buying power for the next cycle."

**Roll the position:**
> "AAPL dropped to $178, putting our $180 put in the money by 1.1%. With 5 days left, rolling to next month at $175 collects an additional $1.80 credit and gives us more time. I'll execute the roll."

To close early, buy back the option:
```bash
# Find the contract symbol from --status output, then:
uv run python core/trade.py   # verify no conflicting orders first
```
*(Option buy-backs go through the wheel --monitor flag or the Alpaca dashboard directly)*

**If assigned (put expires ITM):**
The user now holds 100 shares. Move to Stage 2:
```bash
uv run python strategies/wheel.py --symbol {SYMBOL} --strike {CALL_STRIKE} --expiry {EXPIRY} --stage call --dry-run
uv run python strategies/wheel.py --symbol {SYMBOL} --strike {CALL_STRIKE} --expiry {EXPIRY} --stage call
```

---

## Commands reference

```bash
# Market data
uv run python core/market_data.py AAPL
uv run python core/market_data.py AAPL 30   # 30-day bars

# Account / positions
uv run python core/account.py

# Copy trading
uv run python strategies/copy_trading.py --recent --chamber senate
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1 --dry-run
uv run python strategies/copy_trading.py --politician "Nancy Pelosi" --qty 1

# Wheel
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20 --dry-run
uv run python strategies/wheel.py --symbol AAPL --strike 175 --expiry 2025-06-20
uv run python strategies/wheel.py --status
```

All commands run from `C:\Users\advir\Desktop\alpaca-trading`.
All trades are **paper trading** — no real money at risk.
