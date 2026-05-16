"""
strategies/auto_scanner.py — Multi-signal stock and options scanner for the /auto bot.

Pure execution only — no AI calls. Claude Code reads the JSON output and reasons about it.

CLI:
    uv run python strategies/auto_scanner.py --stocks
    uv run python strategies/auto_scanner.py --options
    uv run python strategies/auto_scanner.py --full
    uv run python strategies/auto_scanner.py --full --universe AAPL,MSFT,NVDA
"""

import sys
import json
import uuid
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import API_KEY, SECRET_KEY
from core.market_data import get_bars_multi, get_latest_price
from core.account import get_buying_power

# ── Universe ───────────────────────────────────────────────────────────────────

LEVERAGED_ETF_UNIVERSE = ["TQQQ", "SOXL", "UPRO", "SPXL", "TECL", "FNGU", "LABU"]
MEGA_CAP_UNIVERSE      = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "AVGO", "PLTR"]

# ── API endpoints ──────────────────────────────────────────────────────────────

FMP_BASE     = "https://financialmodelingprep.com/api/v3"
OPTIONS_BASE = "https://paper-api.alpaca.markets/v2"
ALPACA_HEADERS = {
    "APCA-API-KEY-ID":     API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY,
    "Content-Type":        "application/json",
}

# ── Technicals ────────────────────────────────────────────────────────────────

def compute_technicals(bars: list) -> dict:
    """Compute RSI(14), SMA(20), 5-day momentum, and volume metrics from raw bars.

    Returns None for any metric that lacks sufficient bars rather than crashing.
    Requires no external libraries — pure Python arithmetic.
    """
    if not bars:
        return {
            "rsi_14": None, "sma_20": None, "momentum_5d": None,
            "avg_volume_20d": None, "volume_ratio": None,
            "latest_close": None, "bars_available": 0,
        }

    closes  = [float(b.close)  for b in bars]
    volumes = [float(b.volume) for b in bars]
    n = len(closes)

    # RSI(14) — Wilder smoothing, needs at least 15 bars (14 differences)
    rsi_14 = None
    if n >= 15:
        deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
        gains  = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14
        for i in range(14, len(deltas)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        if avg_loss == 0:
            rsi_14 = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_14 = round(100 - (100 / (1 + rs)), 2)

    # SMA(20) — use all available bars if fewer than 20
    sma_window = min(20, n)
    sma_20 = round(sum(closes[-sma_window:]) / sma_window, 4)

    # 5-day momentum — needs 6 bars
    momentum_5d = None
    if n >= 6:
        momentum_5d = round((closes[-1] / closes[-6]) - 1, 4)

    # Volume metrics
    vol_window      = min(20, n)
    avg_volume_20d  = sum(volumes[-vol_window:]) / vol_window
    latest_volume   = volumes[-1]
    volume_ratio    = round(latest_volume / avg_volume_20d, 2) if avg_volume_20d else None

    return {
        "rsi_14":        rsi_14,
        "sma_20":        sma_20,
        "momentum_5d":   momentum_5d,
        "avg_volume_20d": round(avg_volume_20d, 0),
        "latest_volume": latest_volume,
        "volume_ratio":  volume_ratio,
        "latest_close":  closes[-1],
        "bars_available": n,
    }


# ── Copy signals ───────────────────────────────────────────────────────────────

def fetch_copy_signals() -> list:
    """Return tickers with recent congressional buy signals, sorted by frequency.

    Fetches from Quiver Quantitative (same source as copy_trading.py).
    Filters for purchases within the last 30 days.
    """
    try:
        resp = requests.get(
            "https://api.quiverquant.com/beta/live/congresstrading",
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        trades = resp.json()
    except Exception:
        return []

    cutoff = (date.today() - timedelta(days=30)).isoformat()
    buy_keywords = {"purchase", "buy"}
    ticker_counts = {}

    for t in trades:
        txn = (t.get("Transaction") or "").lower()
        if not any(k in txn for k in buy_keywords):
            continue
        ticker_type = t.get("TickerType") or ""
        if ticker_type not in ("ST", ""):
            continue
        traded_at = (t.get("TransactionDate") or "")[:10]
        if traded_at < cutoff:
            continue
        ticker = (t.get("Ticker") or "").upper().strip()
        if not ticker or ticker in ("--", "N/A", ""):
            continue
        ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1

    return sorted(ticker_counts, key=lambda x: -ticker_counts[x])


# ── Fundamentals ───────────────────────────────────────────────────────────────

def fetch_fundamentals(symbol: str, fmp_api_key: str = None) -> dict:
    """Fetch P/E, EPS, beta, and sector from FMP profile endpoint.

    Returns {"error": "..."} if FMP key is missing or the call fails.
    The scorer treats error results as 0 points on the fundamentals dimension.
    """
    import os
    key = fmp_api_key or os.getenv("FMP_API_KEY", "")
    if not key or key == "your_fmp_key_here":
        return {"error": "FMP_API_KEY not configured"}

    try:
        resp = requests.get(
            f"{FMP_BASE}/profile/{symbol}",
            params={"apikey": key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return {"error": "no data"}
        p = data[0]
        return {
            "pe_ratio":       p.get("pe"),
            "eps":            p.get("eps"),
            "beta":           p.get("beta"),
            "sector":         p.get("sector"),
            "market_cap":     p.get("mktCap"),
            "dividend_yield": p.get("lastDiv"),
            "error":          None,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_stock(symbol: str, technicals: dict, fundamentals: dict, copy_signals: list) -> dict:
    """Score a stock 0–100 across five dimensions and return full breakdown."""
    breakdown = {"momentum": 0, "rsi": 0, "volume": 0, "copy_signal": 0, "fundamentals": 0}
    disqualified    = False
    disqualify_reason = None

    # Momentum (5-day, 0–25 pts)
    mom = technicals.get("momentum_5d")
    if mom is not None:
        if mom >= 0.05:   breakdown["momentum"] = 25
        elif mom >= 0.03: breakdown["momentum"] = 18
        elif mom >= 0.01: breakdown["momentum"] = 12
        elif mom >= 0.0:  breakdown["momentum"] = 6

    # RSI (0–20 pts; >70 disqualifies)
    rsi = technicals.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            disqualified = True
            disqualify_reason = f"RSI {rsi:.1f} — overbought"
        elif 30 <= rsi <= 55: breakdown["rsi"] = 20
        elif 55 < rsi <= 70:  breakdown["rsi"] = 12
        elif rsi < 30:        breakdown["rsi"] = 10  # oversold — risky but notable

    # Volume ratio (0–20 pts)
    vr = technicals.get("volume_ratio")
    if vr is not None:
        if vr >= 2.0:   breakdown["volume"] = 20
        elif vr >= 1.5: breakdown["volume"] = 15
        elif vr >= 1.2: breakdown["volume"] = 10
        elif vr >= 0.8: breakdown["volume"] = 5

    # Copy signal (0–20 pts)
    if symbol in copy_signals[:5]:      breakdown["copy_signal"] = 20
    elif symbol in copy_signals[5:15]:  breakdown["copy_signal"] = 12
    elif symbol in copy_signals[15:]:   breakdown["copy_signal"] = 6

    # Fundamentals (0–15 pts)
    if fundamentals and not fundamentals.get("error"):
        pe  = fundamentals.get("pe_ratio")
        eps = fundamentals.get("eps")
        beta = fundamentals.get("beta")
        f_score = 0
        if pe is not None:
            if 5 <= pe <= 30:   f_score += 8
            elif 30 < pe <= 50: f_score += 4
        if eps is not None and eps > 0:
            f_score += 5
        if beta is not None and 0.8 <= beta <= 2.0:
            f_score += 2
        breakdown["fundamentals"] = min(f_score, 15)

    total = sum(breakdown.values())
    return {
        "symbol":            symbol,
        "total_score":       total,
        "score_breakdown":   breakdown,
        "technicals":        technicals,
        "fundamentals":      fundamentals,
        "is_copy_signal":    symbol in copy_signals,
        "disqualified":      disqualified,
        "disqualify_reason": disqualify_reason,
    }


# ── Stock scanner ──────────────────────────────────────────────────────────────

def scan_stock_candidates(universe: list, fundamentals_cache: dict = None) -> list:
    """Score all symbols in universe and return ranked results (best first).

    Args:
        universe:            List of ticker symbols to evaluate.
        fundamentals_cache:  Dict of {symbol: {...}} pre-loaded from auto_state.json.
                             If provided, skips FMP calls for cached symbols.
    """
    if fundamentals_cache is None:
        fundamentals_cache = {}

    bars_by_symbol = get_bars_multi(universe, days=45)
    copy_signals   = fetch_copy_signals()

    results = []
    for symbol in universe:
        bars         = bars_by_symbol.get(symbol, [])
        technicals   = compute_technicals(bars)
        fundamentals = fundamentals_cache.get(symbol) or fetch_fundamentals(symbol)
        result       = score_stock(symbol, technicals, fundamentals, copy_signals)
        results.append(result)

    results.sort(key=lambda r: (-r["total_score"], r["symbol"]))
    return results


# ── Options scanner ────────────────────────────────────────────────────────────

def _next_fridays(n: int = 8) -> list:
    """Return the next n Fridays from today as 'YYYY-MM-DD' strings."""
    today   = date.today()
    days_to_friday = (4 - today.weekday()) % 7
    if days_to_friday == 0:
        days_to_friday = 7
    first_friday = today + timedelta(days=days_to_friday)
    return [(first_friday + timedelta(weeks=i)).isoformat() for i in range(n)]


def scan_options_candidates(symbols: list) -> list:
    """Find the best cash-secured put for each symbol (wheel strategy setup).

    Filters: open_interest >= 500, bid-ask spread <= 5% of mid, DTE 25-50.
    Returns qualified contracts ranked by open interest descending.
    """
    today = date.today()
    dte_min = today + timedelta(days=25)
    dte_max = today + timedelta(days=50)

    results = []
    for symbol in symbols:
        is_etf = symbol in LEVERAGED_ETF_UNIVERSE
        try:
            price = get_latest_price(symbol)
        except Exception:
            continue

        # ETFs get 10% OTM buffer; stocks get 8%
        otm_pct      = 0.10 if is_etf else 0.08
        target_strike = price * (1 - otm_pct)

        try:
            resp = requests.get(
                f"{OPTIONS_BASE}/options/contracts",
                headers=ALPACA_HEADERS,
                params={
                    "underlying_symbols":  symbol,
                    "expiration_date_gte": dte_min.isoformat(),
                    "expiration_date_lte": dte_max.isoformat(),
                    "strike_price_gte":    round(target_strike * 0.97, 2),
                    "strike_price_lte":    round(target_strike * 1.03, 2),
                    "type":                "put",
                    "status":              "active",
                    "limit":               20,
                },
                timeout=15,
            )
            resp.raise_for_status()
            contracts = resp.json().get("option_contracts", [])
        except Exception:
            continue

        for c in contracts:
            bid = float(c.get("bid_price") or c.get("close_price") or 0)
            ask = float(c.get("ask_price") or bid)
            mid = (bid + ask) / 2 if (bid + ask) > 0 else 0
            oi  = int(c.get("open_interest") or 0)
            expiry_str = str(c.get("expiration_date", ""))[:10]
            strike = float(c.get("strike_price", 0))

            try:
                expiry_date = date.fromisoformat(expiry_str)
                dte = (expiry_date - today).days
            except ValueError:
                continue

            spread_pct = round((ask - bid) / mid, 4) if mid > 0 else 1.0

            qualified = True
            disqualify_reason = None
            if oi < 500:
                qualified = False
                disqualify_reason = f"open interest {oi} < 500"
            elif spread_pct > 0.05:
                qualified = False
                disqualify_reason = f"spread {spread_pct:.1%} > 5%"

            results.append({
                "symbol":                   symbol,
                "contract_symbol":          c.get("symbol", ""),
                "strike":                   strike,
                "expiry":                   expiry_str,
                "dte":                      dte,
                "bid":                      bid,
                "ask":                      ask,
                "mid":                      round(mid, 2),
                "spread_pct":               spread_pct,
                "open_interest":            oi,
                "est_premium_per_contract": round(bid * 100, 2),
                "current_price":            price,
                "otm_pct":                  round((price - strike) / price, 4),
                "is_leveraged_etf":         is_etf,
                "qualified":                qualified,
                "disqualify_reason":        disqualify_reason,
            })

    # Sort: qualified first, then by open interest descending
    results.sort(key=lambda r: (not r["qualified"], -r["open_interest"]))
    return results


# ── Full scan ──────────────────────────────────────────────────────────────────

def run_full_scan(universe: list, fundamentals_cache: dict = None) -> dict:
    """Run both stock and options scans and return combined JSON-ready dict."""
    market_open = False
    try:
        from core.config import trading_client
        market_open = trading_client.get_clock().is_open
    except Exception:
        pass

    buying_power = 0.0
    try:
        buying_power = get_buying_power()
    except Exception:
        pass

    options_universe = list(set(LEVERAGED_ETF_UNIVERSE + universe))
    copy_signals     = fetch_copy_signals()
    stock_candidates = scan_stock_candidates(universe, fundamentals_cache)
    options_candidates = scan_options_candidates(options_universe)

    return {
        "scan_id":           str(uuid.uuid4()),
        "scanned_at":        datetime.now(timezone.utc).isoformat(),
        "market_open":       market_open,
        "buying_power":      buying_power,
        "copy_signals":      copy_signals[:20],
        "stock_candidates":  stock_candidates,
        "options_candidates": options_candidates,
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_stock_table(candidates: list):
    header = f"{'Rank':<5} {'Symbol':<7} {'Score':<6} {'RSI':<7} {'Mom5d':<8} {'VolRatio':<9} {'CopyBuys':<10} {'Status'}"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(candidates[:10], 1):
        t   = r["technicals"]
        rsi = f"{t['rsi_14']:.1f}" if t.get("rsi_14") is not None else "n/a"
        mom = f"{t['momentum_5d']:+.1%}" if t.get("momentum_5d") is not None else "n/a"
        vr  = f"{t['volume_ratio']:.1f}x" if t.get("volume_ratio") is not None else "n/a"
        cs  = "YES" if r["is_copy_signal"] else "no"
        status = f"SKIP ({r['disqualify_reason']})" if r["disqualified"] else "OK"
        print(f"{i:<5} {r['symbol']:<7} {r['total_score']:<6} {rsi:<7} {mom:<8} {vr:<9} {cs:<10} {status}")


def _print_options_table(candidates: list):
    qualified = [c for c in candidates if c["qualified"]]
    if not qualified:
        print("No qualified options candidates found.")
        return
    header = f"{'Symbol':<7} {'Contract':<25} {'Strike':<8} {'Expiry':<12} {'DTE':<5} {'Bid':<7} {'OI':<7} {'Spread':<8} {'Premium'}"
    print(header)
    print("-" * len(header))
    for c in qualified[:10]:
        print(
            f"{c['symbol']:<7} {c['contract_symbol']:<25} "
            f"${c['strike']:<7.2f} {c['expiry']:<12} {c['dte']:<5} "
            f"${c['bid']:<6.2f} {c['open_interest']:<7} "
            f"{c['spread_pct']:.1%}  "
            f"${c['est_premium_per_contract']:.0f}/contract"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto trading scanner")
    parser.add_argument("--stocks",   action="store_true", help="Scan stocks only")
    parser.add_argument("--options",  action="store_true", help="Scan options only")
    parser.add_argument("--full",     action="store_true", help="Full scan, output JSON")
    parser.add_argument("--universe", type=str, default="",
                        help="Comma-separated symbols (overrides default universe)")
    args = parser.parse_args()

    universe = [s.strip().upper() for s in args.universe.split(",") if s.strip()] \
               if args.universe else MEGA_CAP_UNIVERSE + LEVERAGED_ETF_UNIVERSE
    universe = list(dict.fromkeys(universe))  # deduplicate, preserve order

    if args.full:
        result = run_full_scan(universe)
        print(json.dumps(result, indent=2, default=str))

    elif args.stocks:
        print(f"\n=== STOCK CANDIDATES (universe: {len(universe)} symbols) ===\n")
        candidates = scan_stock_candidates(universe)
        _print_stock_table(candidates)

    elif args.options:
        opt_universe = list(set(LEVERAGED_ETF_UNIVERSE + universe))
        print(f"\n=== OPTIONS / WHEEL CANDIDATES (universe: {len(opt_universe)} symbols) ===\n")
        candidates = scan_options_candidates(opt_universe)
        _print_options_table(candidates)

    else:
        # Default: show both tables side by side
        print(f"\n=== STOCK CANDIDATES ===\n")
        stock_candidates = scan_stock_candidates(universe)
        _print_stock_table(stock_candidates)

        opt_universe = list(set(LEVERAGED_ETF_UNIVERSE + universe))
        print(f"\n=== OPTIONS / WHEEL CANDIDATES ===\n")
        opt_candidates = scan_options_candidates(opt_universe)
        _print_options_table(opt_candidates)
