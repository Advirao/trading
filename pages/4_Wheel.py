"""
pages/4_Wheel.py — Wheel Strategy

Set up cash-secured puts and covered calls, and monitor open legs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from core.market_data import get_latest_price
from strategies.wheel import (
    _suggest_strike, _suggest_expiry,
    get_option_contracts, sell_put, sell_call,
    show_status,
)
from db import get_open_wheel_legs

st.set_page_config(page_title="Wheel Strategy", page_icon="🎡", layout="wide")
st.title("🎡 Wheel Strategy")
st.caption("Sell cash-secured puts to collect premium. If assigned, sell covered calls.")

# ── Open Legs ──────────────────────────────────────────────────────────────────

st.subheader("Open Wheel Legs")

if st.button("Refresh Positions"):
    st.rerun()

try:
    legs = get_open_wheel_legs()
    if legs:
        rows = []
        today = date.today()
        for leg in legs:
            expiry_str = str(leg["expiry"] or "")[:10]
            try:
                dte = (date.fromisoformat(expiry_str) - today).days
            except Exception:
                dte = None

            dte_display = str(dte) if dte is not None else "—"
            rows.append({
                "Symbol":    leg["symbol"],
                "Stage":     leg["stage"].upper(),
                "Strike":    f"${float(leg['strike'] or 0):.2f}",
                "Expiry":    expiry_str,
                "DTE":       dte_display,
                "Premium":   f"${float(leg['premium'] or 0):.2f}",
                "Opened At": str(leg["opened_at"] or "")[:10],
                "Status":    leg["status"],
                "_dte_int":  dte if dte is not None else 9999,
            })

        df = pd.DataFrame(rows)

        def _dte_color(row):
            dte_val = row["_dte_int"]
            if dte_val <= 7:
                return ["background-color: #f8d7da"] * len(row)
            elif dte_val <= 14:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        display = df.drop(columns=["_dte_int"])
        st.dataframe(
            display.style.apply(_dte_color, axis=1),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Red = ≤7 DTE (approaching expiry)  |  Yellow = ≤14 DTE")
    else:
        st.info("No open wheel legs.")
except Exception as e:
    st.error(f"Could not load wheel positions: {e}")

st.divider()

# ── Setup New Position ─────────────────────────────────────────────────────────

st.subheader("Set Up New Position")

col1, col2 = st.columns([2, 1])
symbol = col1.text_input("Underlying symbol", placeholder="TQQQ").upper().strip()
stage  = col2.selectbox("Stage", ["Stage 1 — Sell Put", "Stage 2 — Sell Call"])
is_put = "Put" in stage

price_val = None
if symbol:
    if st.button("Get Current Price"):
        with st.spinner(f"Fetching {symbol}…"):
            try:
                price_val = get_latest_price(symbol)
                st.session_state[f"price_{symbol}"] = price_val
                st.metric("Current Price", f"${price_val:.2f}")
            except Exception as e:
                st.error(f"Could not fetch price: {e}")

    price_val = st.session_state.get(f"price_{symbol}")

if symbol and price_val:
    option_type = "put" if is_put else "call"
    suggested_strike = _suggest_strike(price_val, option_type)
    suggested_expiry = _suggest_expiry(weeks_out=4)

    col1, col2, col3 = st.columns(3)
    strike    = col1.number_input("Strike ($)", value=float(suggested_strike), step=0.5)
    expiry    = col2.text_input("Expiry (YYYY-MM-DD)", value=suggested_expiry)
    contracts = col3.number_input("Contracts", min_value=1, max_value=10, value=1)

    otm_pct = abs(price_val - strike) / price_val * 100
    st.caption(f"Strike is **{otm_pct:.1f}% {'below' if is_put else 'above'}** current price — "
               f"**{100*contracts} shares** cash secured")

    # Preview contract
    if st.button("Preview Contract"):
        with st.spinner("Fetching options chain…"):
            try:
                matches = get_option_contracts(symbol, expiry, strike, option_type)
                if matches:
                    c = matches[0]
                    bid = float(c.get("bid_price") or 0)
                    ask = float(c.get("ask_price") or bid)
                    mid = (bid + ask) / 2
                    oi  = c.get("open_interest", "—")
                    st.session_state["preview_contract"] = {
                        "symbol": c.get("symbol"),
                        "bid": bid, "ask": ask, "mid": mid, "oi": oi,
                        "premium_total": round(bid * 100 * contracts, 2),
                    }
                else:
                    st.warning("No matching contract found. Try adjusting strike or expiry.")
                    st.session_state.pop("preview_contract", None)
            except Exception as e:
                st.error(f"Could not fetch contract: {e}")

    preview = st.session_state.get("preview_contract")
    if preview:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bid",          f"${preview['bid']:.2f}")
        m2.metric("Ask",          f"${preview['ask']:.2f}")
        m3.metric("Open Interest", str(preview["oi"]))
        m4.metric(f"Est. Premium ({contracts} contract{'s' if contracts > 1 else ''})",
                  f"${preview['premium_total']:.0f}")
        st.caption(f"Contract: `{preview['symbol']}`")

    # Execute
    action_label = f"Sell {'Put' if is_put else 'Call'}"
    if st.button(action_label, type="primary"):
        st.session_state["wheel_confirm"] = {
            "symbol": symbol, "strike": strike, "expiry": expiry,
            "contracts": contracts, "is_put": is_put,
        }

    pending = st.session_state.get("wheel_confirm")
    if pending:
        action = "PUT" if pending["is_put"] else "CALL"
        st.warning(
            f"Confirm: **SELL {pending['contracts']} {action} {pending['symbol']} "
            f"${pending['strike']:.0f} exp {pending['expiry']}**?"
        )
        c1, c2 = st.columns([1, 1])
        if c1.button("Yes, sell it", type="primary"):
            try:
                if pending["is_put"]:
                    sell_put(pending["symbol"], pending["strike"], pending["expiry"],
                             contracts=pending["contracts"], dry_run=False)
                else:
                    sell_call(pending["symbol"], pending["strike"], pending["expiry"],
                              contracts=pending["contracts"], dry_run=False)
                st.success(f"{action} order placed for {pending['symbol']}.")
                st.session_state.pop("wheel_confirm", None)
                st.session_state.pop("preview_contract", None)
                st.rerun()
            except Exception as e:
                st.error(f"Order failed: {e}")
        if c2.button("Cancel##wheel"):
            st.session_state.pop("wheel_confirm", None)
            st.rerun()

elif symbol and not price_val:
    st.info("Click **Get Current Price** to load strike and expiry suggestions.")
