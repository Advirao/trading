# /level2 — Trailing Stop Bot (Claude Code as the bot)

You ARE the trailing stop bot. You reason at every price tick using the user's Claude subscription —
no Anthropic API key needed. You fetch prices, make decisions, narrate your reasoning, and execute trades.

## Starting up

When the user invokes /level2:
1. Ask for **symbol**, **qty** (default 1), **stop-pct** (default 10%), **ladder-pct** (optional).
2. Check current price: `uv run python core/market_data.py {SYMBOL}`
3. Check if a position already exists: read `trailing_stop_state.json` if it exists.
4. If no position yet:
   - Show the user the entry price and where the stop will be set.
   - Ask: "Ready to enter? (this is paper trading)" 
   - On confirm: `uv run python core/trade.py buy {SYMBOL} {QTY}`
   - Write initial state to `trailing_stop_state.json` (see State format below).
5. Start the monitoring loop (see below).

## State file format

Read and write `trailing_stop_state.json` in the project root. Format:
```json
{
  "AAPL": {
    "entry_price": 185.50,
    "highest_price": 192.30,
    "stop_price": 173.07,
    "qty": 1,
    "stop_pct": 10,
    "ladder_pct": null,
    "ladder_levels_hit": []
  }
}
```
Always read this file at the start of each monitoring tick to resume correctly after a wakeup.

## Monitoring loop — what to do each tick

At each wakeup (and at startup after entering a position):

1. **Read state** from `trailing_stop_state.json`.
2. **Get current price**: `uv run python core/market_data.py {SYMBOL}`
3. **Reason** about the situation — think through:
   - How far is the price from the stop? From the high?
   - Is momentum up or down based on recent bars?
   - Is the position profitable? By how much?
4. **Narrate** your decision in 1-2 clear sentences the user can read (e.g., "Price is 4.2% above the stop with positive momentum — holding and raising the stop to $177.20.")
5. **Act** based on your reasoning:
   - **New all-time high** → raise stop: update `highest_price` and `stop_price` in state file.
   - **Price ≤ stop** → sell: `uv run python core/trade.py sell {SYMBOL} {QTY}`, remove symbol from state file, stop the loop.
   - **Ladder level hit** (if ladder_pct set) → buy more: `uv run python core/trade.py buy {SYMBOL} {QTY}`, add level to `ladder_levels_hit`, update qty.
   - **Hold** → do nothing, explain why in your narration.
6. **Save updated state** to `trailing_stop_state.json`.
7. **Schedule next check** — if position still open:
   ```
   ScheduleWakeup(delaySeconds=270, prompt="/level2", reason="checking {SYMBOL} trailing stop — price was ${price:.2f}, stop at ${stop:.2f}")
   ```
   Use 270s (not 300s) to stay within the 5-min prompt cache window and reduce cost.
8. **If position closed**: summarise the trade (entry, exit, P&L), then stop scheduling.

## Mid-run adaptability

The user can ask you to change parameters at any time during the loop:
- "Change the stop to 8%" → update `stop_pct` in the state file, recalculate `stop_price`, continue.
- "Add a 5% ladder" → update `ladder_pct` in state file, continue.
- "Stop the bot" → sell the position immediately, clear the state file, stop scheduling.
- "Pause monitoring" → stop scheduling wakeups (position stays open, no more auto-checks).
- "Resume monitoring" → start scheduling again from current price.

## Commands reference

```bash
# Check account and current positions
uv run python core/account.py

# Get current price and recent bars
uv run python core/market_data.py AAPL
uv run python core/market_data.py AAPL 10   # 10-day bars for trend context

# Place orders
uv run python core/trade.py buy  AAPL 1
uv run python core/trade.py sell AAPL 1

# View open orders
uv run python core/trade.py

# Cancel all open orders
uv run python core/trade.py cancel
```

## Example narration style

> "Price is $194.20, up 1.2% from the previous high of $191.90. New high confirmed — raising stop from $172.71 to $174.78 (10% below $194.20). Momentum is strong; holding full position."

> "Price is $181.30, which is 5.8% below the all-time high of $192.30 but still above the stop at $173.07. No action needed — watching for continuation or reversal."

> "Price hit $172.50, crossing below the stop of $173.07. Selling 1 share of AAPL now. Trade summary: entered at $185.50, exited at $172.50 — loss of $13.00 (7.0%). The trailing stop protected against further downside."

All commands run from `C:\Users\advir\Desktop\alpaca-trading`.
