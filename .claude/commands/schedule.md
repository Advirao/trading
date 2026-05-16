# /schedule — Schedule a Trading Bot

Use this skill to create OS-level scheduled tasks that run any trading bot automatically.
The bot runs at the specified time without you needing to keep a terminal open.

## What you can ask

- "Schedule the trailing stop bot for AAPL every weekday at 9:35am"
- "Run the wheel monitor every 15 minutes during market hours"
- "Copy trade Nancy Pelosi daily at market open"
- "Set up a daily account summary at 4:15pm"
- "Show me all scheduled trading tasks"
- "Remove the AAPL trailing stop schedule"

## Instructions

When the user asks to schedule a bot:

### Step 1 — Gather requirements
Ask (or infer from context):
- **Which bot**: trailing_stop, copy_trading, wheel (monitor), or account summary
- **Symbol / politician / parameters**: any flags needed for the command
- **When**: time of day, frequency (once, daily, weekday-only, every N minutes)
- **Dry-run first?**: recommend starting with `--dry-run` for the first scheduled run

### Step 2 — Build the command string
All commands run from the project root: `C:\Users\advir\Desktop\alpaca-trading`
Use `uv run python` with the full strategy path and all flags. Examples:

```
uv run python strategies/trailing_stop.py --symbol AAPL --qty 1 --stop-pct 10 --dry-run
uv run python strategies/wheel.py --monitor --dry-run
uv run python strategies/copy_trading.py --qty 1 --dry-run
uv run python core/account.py
```

### Step 3 — Create the scheduled task

**On Windows (this machine)** — use `schtasks.exe` via PowerShell:

```powershell
# Daily at 9:35am on weekdays
$cmd = 'uv run python strategies/trailing_stop.py --symbol AAPL --qty 1'
$workdir = 'C:\Users\advir\Desktop\alpaca-trading'
schtasks /create /tn "AlpacaTrailingStop_AAPL" /tr "powershell -WorkingDirectory '$workdir' -Command '$cmd'" /sc WEEKLY /d MON,TUE,WED,THU,FRI /st 09:35 /f
```

```powershell
# Every 15 minutes (wheel monitor)
schtasks /create /tn "AlpacaWheelMonitor" /tr "powershell -WorkingDirectory 'C:\Users\advir\Desktop\alpaca-trading' -Command 'uv run python strategies/wheel.py --monitor --interval 900 --dry-run'" /sc MINUTE /mo 15 /f
```

**On Mac/Linux** — add to crontab:
```bash
# 9:35am weekdays (M-F)
35 9 * * 1-5 cd /path/to/alpaca-trading && uv run python strategies/trailing_stop.py --symbol AAPL --qty 1

# Every 15 minutes
*/15 * * * * cd /path/to/alpaca-trading && uv run python strategies/wheel.py --monitor
```

### Step 4 — Verify and report
After creating the task:
1. Run `schtasks /query /tn "TaskName"` (Windows) or `crontab -l` (Mac/Linux) to confirm it was created.
2. Tell the user the task name, schedule, and how to remove it (`schtasks /delete /tn "TaskName" /f`).
3. Remind the user that logs go to the terminal — for background tasks, redirect output:
   ```powershell
   ... >> C:\Users\advir\Desktop\alpaca-trading\logs\trailing_stop.log 2>&1
   ```

### Step 5 — Mid-run adaptability
Remind the user they can change strategy parameters at any time by editing `bot_config.json`
in the project root — the trailing stop bot reads this file on every tick and adapts instantly.
No restart needed.

## Listing scheduled tasks

```powershell
# Windows — show all Alpaca tasks
schtasks /query /fo LIST | Select-String -Pattern "Alpaca" -Context 3,5
```

```bash
# Mac/Linux
crontab -l | grep alpaca
```

## Removing a task

```powershell
# Windows
schtasks /delete /tn "AlpacaTrailingStop_AAPL" /f
```

```bash
# Mac/Linux — edit crontab and remove the relevant line
crontab -e
```

## Important notes

- All trades run on the **paper account** — no real money at risk.
- Market hours: NYSE is open 9:30am–4:00pm ET Monday–Friday. Schedule entries to start after 9:30am.
- The trailing stop bot runs continuously once started — don't schedule it to start every 15 minutes or you'll get duplicate positions.
- The wheel `--monitor` flag is designed to be called repeatedly — safe to schedule every 15 minutes.
- Logs directory: create `C:\Users\advir\Desktop\alpaca-trading\logs\` if you want persistent logs.
