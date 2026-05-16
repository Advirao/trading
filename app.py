"""
app.py — Streamlit Dashboard (main page)

Shows account summary, open positions, and open orders.
Run with: uv run streamlit run app.py
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd

from core.account import get_account, get_positions
from core.trade import get_orders, cancel_all_orders, close_all_positions
from core.config import trading_client

st.set_page_config(
    page_title="Alpaca Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cached data fetchers ───────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def _account():
    return get_account()

@st.cache_data(ttl=15)
def _positions():
    return get_positions()

@st.cache_data(ttl=10)
def _orders():
    return get_orders("open")

@st.cache_data(ttl=30)
def _market_open():
    try:
        return trading_client.get_clock().is_open
    except Exception:
        return None

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Alpaca Trading Bot")
    st.caption("Paper Trading — No real money at risk")
    st.divider()

    is_open = _market_open()
    if is_open is True:
        st.success("Market: OPEN")
    elif is_open is False:
        st.error("Market: CLOSED")
    else:
        st.warning("Market: Unknown")

    st.caption(f"Last refreshed: {time.strftime('%H:%M:%S')}")
    if st.button("Refresh Now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.toggle("Auto-refresh every 30s", value=False)

# ── Main content ───────────────────────────────────────────────────────────────

st.title("Dashboard")

try:
    acct = _account()
    equity     = float(acct.equity)
    cash       = float(acct.cash)
    bp         = float(acct.buying_power)
    last_eq    = float(acct.last_equity)
    day_pnl    = equity - last_eq

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Equity",       f"${equity:,.2f}")
    col2.metric("Cash",         f"${cash:,.2f}")
    col3.metric("Buying Power", f"${bp:,.2f}")
    col4.metric("Day P&L",      f"${day_pnl:+,.2f}",
                delta=f"{day_pnl/last_eq*100:+.2f}%" if last_eq else None)

except Exception as e:
    st.error(f"Could not load account: {e}")
    st.stop()

st.divider()

# ── Positions ──────────────────────────────────────────────────────────────────

st.subheader("Open Positions")

try:
    positions = _positions()
    if positions:
        rows = []
        for p in positions:
            pnl = float(p.unrealized_pl)
            rows.append({
                "Symbol":       p.symbol,
                "Qty":          float(p.qty),
                "Avg Entry":    float(p.avg_entry_price),
                "Market Value": float(p.market_value),
                "Unrealised P&L": pnl,
                "Side":         str(p.side).replace("PositionSide.", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Avg Entry":      st.column_config.NumberColumn(format="$%.2f"),
                "Market Value":   st.column_config.NumberColumn(format="$%.2f"),
                "Unrealised P&L": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
        )
    else:
        st.info("No open positions.")
except Exception as e:
    st.error(f"Could not load positions: {e}")

st.divider()

# ── Open Orders ────────────────────────────────────────────────────────────────

st.subheader("Open Orders")

try:
    orders = _orders()
    if orders:
        rows = []
        for o in orders:
            rows.append({
                "Symbol":    o.symbol,
                "Side":      str(o.side).replace("OrderSide.", ""),
                "Qty":       float(o.qty or 0),
                "Type":      str(o.type).replace("OrderType.", ""),
                "Status":    str(o.status).replace("OrderStatus.", ""),
                "Submitted": str(o.submitted_at)[:19] if o.submitted_at else "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider()
        col1, col2 = st.columns([1, 4])
        if col1.button("Cancel All Orders", type="secondary"):
            st.session_state["cancel_confirm"] = True

        if st.session_state.get("cancel_confirm"):
            st.warning("Cancel all open orders?")
            c1, c2 = st.columns([1, 1])
            if c1.button("Yes, cancel all", type="primary"):
                cancel_all_orders()
                st.cache_data.clear()
                st.session_state.pop("cancel_confirm", None)
                st.success("All orders cancelled.")
                st.rerun()
            if c2.button("Never mind"):
                st.session_state.pop("cancel_confirm", None)
                st.rerun()
    else:
        st.info("No open orders.")
except Exception as e:
    st.error(f"Could not load orders: {e}")

st.divider()

# ── Danger zone ────────────────────────────────────────────────────────────────

with st.expander("Danger Zone"):
    st.warning("Closing all positions will sell everything at market price immediately.")
    if st.button("Close All Positions", type="primary"):
        st.session_state["close_confirm"] = True

    if st.session_state.get("close_confirm"):
        st.error("Are you absolutely sure? This cannot be undone.")
        c1, c2 = st.columns([1, 1])
        if c1.button("Yes, close everything"):
            close_all_positions()
            st.cache_data.clear()
            st.session_state.pop("close_confirm", None)
            st.success("All positions closed.")
            st.rerun()
        if c2.button("No, go back"):
            st.session_state.pop("close_confirm", None)
            st.rerun()

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
