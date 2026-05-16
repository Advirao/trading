"""
pages/1_Scanner.py — Auto Scanner

Runs the multi-signal stock + options scan and lets the user
approve trades with checkboxes before executing.
"""

import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from strategies.auto_scanner import (
    run_full_scan,
    MEGA_CAP_UNIVERSE,
    LEVERAGED_ETF_UNIVERSE,
)
from core.trade import buy_market
from strategies.wheel import sell_put
from db import log_auto_trade

st.set_page_config(page_title="Scanner", page_icon="🔍", layout="wide")
st.title("🔍 Auto Scanner")
st.caption("Scores stocks using momentum, RSI, volume, copy signals, and fundamentals. "
           "Finds options candidates with tight spreads and high open interest.")

# ── Universe selector ──────────────────────────────────────────────────────────

ALL_SYMBOLS = list(dict.fromkeys(MEGA_CAP_UNIVERSE + LEVERAGED_ETF_UNIVERSE))

with st.expander("Universe Settings", expanded=False):
    selected = st.multiselect(
        "Symbols to scan",
        options=ALL_SYMBOLS + ["SMCI", "CRWD", "COIN", "MSTR", "SOFI"],
        default=ALL_SYMBOLS,
    )
    custom = st.text_input("Add more symbols (comma-separated)", placeholder="SMCI,CRWD")
    if custom:
        extras = [s.strip().upper() for s in custom.split(",") if s.strip()]
        selected = list(dict.fromkeys(selected + extras))

universe = selected or ALL_SYMBOLS

# ── Run scan ───────────────────────────────────────────────────────────────────

col1, col2 = st.columns([1, 4])
run_btn = col1.button("Run Scan", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Scanning market — fetching bars, copy signals, and options data…"):
        try:
            result = run_full_scan(universe)
            st.session_state["scan_result"] = result
            st.session_state["confirm_pending"] = False
            st.session_state["selected_actions"] = {}
        except Exception as e:
            st.error(f"Scan failed: {e}")

result = st.session_state.get("scan_result")

if not result:
    st.info("Press **Run Scan** to start. Results will appear here.")
    st.stop()

# ── Scan metadata ──────────────────────────────────────────────────────────────

scanned_at = result.get("scanned_at", "")[:19].replace("T", " ")
bp         = result.get("buying_power", 0)
market_open = result.get("market_open", False)

m1, m2, m3 = st.columns(3)
m1.metric("Scanned At", scanned_at)
m2.metric("Buying Power", f"${bp:,.0f}")
m3.metric("Market", "OPEN" if market_open else "CLOSED")

st.divider()

# ── Stock candidates ───────────────────────────────────────────────────────────

st.subheader("Stock Candidates")

stock_candidates = result.get("stock_candidates", [])
if stock_candidates:
    rows = []
    for i, c in enumerate(stock_candidates[:15], 1):
        t = c.get("technicals", {})
        f = c.get("fundamentals", {}) or {}
        rsi  = t.get("rsi_14")
        mom  = t.get("momentum_5d")
        vr   = t.get("volume_ratio")
        rows.append({
            "Rank":         i,
            "Symbol":       c["symbol"],
            "Score":        c["total_score"],
            "RSI":          f"{rsi:.1f}" if rsi is not None else "n/a",
            "Mom 5d":       f"{mom:+.1%}" if mom is not None else "n/a",
            "Vol Ratio":    f"{vr:.1f}x"  if vr  is not None else "n/a",
            "Copy Signal":  "YES" if c.get("is_copy_signal") else "—",
            "PE":           f"{f['pe_ratio']:.1f}" if f.get("pe_ratio") else "—",
            "Status":       f"SKIP — {c['disqualify_reason']}" if c.get("disqualified") else "OK",
        })
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100)},
    )
else:
    st.info("No stock candidates found.")

st.divider()

# ── Options candidates ─────────────────────────────────────────────────────────

st.subheader("Wheel / Options Candidates")

options_candidates = [c for c in result.get("options_candidates", []) if c.get("qualified")]
if options_candidates:
    rows = []
    for c in options_candidates[:12]:
        rows.append({
            "Symbol":       c["symbol"],
            "Contract":     c["contract_symbol"],
            "Strike":       f"${c['strike']:.2f}",
            "Expiry":       c["expiry"],
            "DTE":          c["dte"],
            "Bid":          f"${c['bid']:.2f}",
            "Open Interest": c["open_interest"],
            "Spread":       f"{c['spread_pct']:.1%}",
            "Premium/Contract": f"${c['est_premium_per_contract']:.0f}",
            "OTM %":        f"{c['otm_pct']:.1%}",
            "ETF":          "YES" if c.get("is_leveraged_etf") else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No qualified options candidates (OI ≥ 500, spread ≤ 5%, DTE 25–50).")

st.divider()

# ── Proposed actions ───────────────────────────────────────────────────────────

st.subheader("Proposed Actions")
st.caption("Select the trades you want to execute, then click **Execute Selected**.")

qualified_stocks  = [c for c in stock_candidates if not c.get("disqualified")][:3]
qualified_options = options_candidates[:3]

if not qualified_stocks and not qualified_options:
    st.info("No actionable candidates this scan.")
    st.stop()

actions = {}

for c in qualified_stocks:
    sym   = c["symbol"]
    score = c["total_score"]
    price = c.get("technicals", {}).get("latest_close", 0)
    label = f"BUY 1 {sym} @ market (~${price:.2f} est.)  —  score {score}"
    key   = f"stock_{sym}"
    actions[key] = {"type": "stock", "symbol": sym, "qty": 1, "score": score, "label": label}

for c in qualified_options:
    sym      = c["symbol"]
    strike   = c["strike"]
    expiry   = c["expiry"]
    premium  = c["est_premium_per_contract"]
    dte      = c["dte"]
    oi       = c["open_interest"]
    otm      = c["otm_pct"]
    label    = (f"SELL 1 put {sym} ${strike:.0f} exp {expiry}  —  "
                f"${premium:.0f} premium, {dte} DTE, {otm:.1%} OTM, OI={oi:,}")
    key      = f"opt_{sym}_{strike}_{expiry}"
    actions[key] = {
        "type": "put", "symbol": sym, "strike": strike,
        "expiry": expiry, "premium": premium, "score": 0, "label": label,
    }

selected_keys = {}
for key, action in actions.items():
    selected_keys[key] = st.checkbox(action["label"], key=f"chk_{key}")

any_selected = any(selected_keys.values())

if st.button("Execute Selected Trades", type="primary", disabled=not any_selected):
    st.session_state["confirm_pending"] = True

if st.session_state.get("confirm_pending"):
    st.warning("This will place paper trades on your Alpaca account. Confirm?")
    c1, c2 = st.columns([1, 1])

    if c1.button("Yes, execute now", type="primary"):
        scan_id = result.get("scan_id", str(uuid.uuid4()))
        errors  = []

        for key, action in actions.items():
            if not selected_keys.get(key):
                continue
            sym = action["symbol"]
            try:
                if action["type"] == "stock":
                    order = buy_market(sym, action["qty"])
                    oid   = str(order.id)
                    log_auto_trade(scan_id, sym, "stock_buy", action["score"],
                                   action["qty"], oid)
                    st.success(f"BUY {sym}: order {oid} accepted")

                elif action["type"] == "put":
                    sell_put(sym, action["strike"], action["expiry"], contracts=1, dry_run=False)
                    log_auto_trade(scan_id, sym, "put_sell", 0, 1, "via_wheel",
                                   strike=action["strike"], expiry=action["expiry"],
                                   est_premium=action["premium"])
                    st.success(f"PUT {sym} ${action['strike']} {action['expiry']}: order placed")

            except Exception as e:
                errors.append(f"{sym}: {e}")

        if errors:
            for err in errors:
                st.error(err)

        st.session_state["confirm_pending"] = False
        st.cache_data.clear()

    if c2.button("Cancel"):
        st.session_state["confirm_pending"] = False
        st.rerun()
