"""
app.py — Streamlit Dashboard (main page)

Account overview: equity, positions, P&L, open orders.
Run: uv run streamlit run app.py
"""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.account import get_account, get_positions
from core.trade import get_orders, cancel_all_orders, close_all_positions
from core.config import trading_client
from pages._shared import inject_css, metric_card, section_header, market_pill, alert, COLORS

st.set_page_config(
    page_title="Alpaca Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# ── Cached fetchers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def _account():   return get_account()

@st.cache_data(ttl=15)
def _positions(): return get_positions()

@st.cache_data(ttl=10)
def _orders():    return get_orders("open")

@st.cache_data(ttl=30)
def _clock():
    try:    return trading_client.get_clock()
    except: return None

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📈 Alpaca Trading Bot")
    st.caption("Paper Trading · No real money at risk")
    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

    clock = _clock()
    is_open = clock.is_open if clock else None
    if is_open is True:    market_pill(True)
    elif is_open is False: market_pill(False)
    else:                  st.warning("Market status unknown")

    st.markdown(f'<p style="color:#8892A4;font-size:0.78rem;margin-top:8px">Refreshed {time.strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)
    if st.button("🔄  Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.toggle("Auto-refresh (30s)", value=False)
    st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
    st.caption("Navigate using the sidebar pages above.")

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown("# Dashboard")

try:
    acct    = _account()
    equity  = float(acct.equity)
    cash    = float(acct.cash)
    bp      = float(acct.buying_power)
    last_eq = float(acct.last_equity)
    pnl     = equity - last_eq
    pnl_pct = pnl / last_eq * 100 if last_eq else 0

    # ── Metric cards ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Equity",       f"${equity:,.2f}", color="blue")
    with c2: metric_card("Cash",         f"${cash:,.2f}",   color="teal")
    with c3: metric_card("Buying Power", f"${bp:,.2f}",     color="purple")
    with c4:
        color = "green" if pnl >= 0 else "red"
        metric_card("Day P&L", f"${pnl:+,.2f}",
                    delta=f"{pnl_pct:+.2f}%", color=color)

except Exception as e:
    alert(f"Could not load account data: {e}", "danger")
    st.stop()

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Positions ──────────────────────────────────────────────────────────────────

section_header("Open Positions")

try:
    positions = _positions()
    if positions:
        rows = []
        for p in positions:
            pnl_pos = float(p.unrealized_pl)
            pnl_pct_pos = float(p.unrealized_plpc) * 100 if hasattr(p, "unrealized_plpc") else 0
            rows.append({
                "Symbol":     p.symbol,
                "Qty":        float(p.qty),
                "Avg Entry":  float(p.avg_entry_price),
                "Mkt Value":  float(p.market_value),
                "P&L ($)":    pnl_pos,
                "P&L (%)":    pnl_pct_pos,
                "Side":       str(p.side).replace("PositionSide.", "").upper(),
            })
        df_pos = pd.DataFrame(rows)

        # Positions table + donut chart side by side
        col_tbl, col_chart = st.columns([3, 2])

        with col_tbl:
            st.dataframe(
                df_pos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Avg Entry": st.column_config.NumberColumn(format="$%.2f"),
                    "Mkt Value": st.column_config.NumberColumn(format="$%.2f"),
                    "P&L ($)":   st.column_config.NumberColumn(format="$%.2f"),
                    "P&L (%)":   st.column_config.NumberColumn(format="%.2f%%"),
                },
            )

        with col_chart:
            labels = [r["Symbol"] for r in rows]
            values = [r["Mkt Value"] for r in rows]
            fig = go.Figure(go.Pie(
                labels=labels, values=values,
                hole=0.6,
                marker=dict(colors=[COLORS["blue"], COLORS["teal"], COLORS["purple"],
                                    COLORS["green"], COLORS["gold"], COLORS["red"]]),
                textinfo="label+percent",
                textfont_size=11,
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E8ECF0",
                height=240,
                annotations=[dict(text="Portfolio", x=0.5, y=0.5,
                                  font_size=13, showarrow=False, font_color="#8892A4")],
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    else:
        alert("No open positions. Head to the Trade or Scanner page to get started.", "info")

except Exception as e:
    alert(f"Could not load positions: {e}", "danger")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Open Orders ────────────────────────────────────────────────────────────────

section_header("Open Orders")

try:
    orders = _orders()
    if orders:
        rows = []
        for o in orders:
            rows.append({
                "Symbol":    o.symbol,
                "Side":      str(o.side).replace("OrderSide.", "").upper(),
                "Qty":       float(o.qty or 0),
                "Type":      str(o.type).replace("OrderType.", "").upper(),
                "Status":    str(o.status).replace("OrderStatus.", "").upper(),
                "Submitted": str(o.submitted_at)[:16].replace("T", " ") if o.submitted_at else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        col_btn, _ = st.columns([1, 3])
        if col_btn.button("Cancel All Orders", type="secondary", use_container_width=True):
            st.session_state["cancel_confirm"] = True

        if st.session_state.get("cancel_confirm"):
            alert("This will cancel ALL open orders immediately.", "warn")
            c1, c2 = st.columns([1, 4])
            if c1.button("Confirm Cancel", type="primary"):
                cancel_all_orders()
                st.cache_data.clear()
                st.session_state.pop("cancel_confirm", None)
                st.rerun()
            if c2.button("Never mind##cancel"):
                st.session_state.pop("cancel_confirm", None)
                st.rerun()
    else:
        alert("No open orders.", "info")

except Exception as e:
    alert(f"Could not load orders: {e}", "danger")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Danger zone ────────────────────────────────────────────────────────────────

with st.expander("⚠️  Danger Zone — Close All Positions"):
    alert("Closes every open position at market price and cancels all orders. Cannot be undone.", "danger")
    if st.button("Close Everything", type="primary"):
        st.session_state["close_confirm"] = True

    if st.session_state.get("close_confirm"):
        st.error("Last chance — are you absolutely sure?")
        c1, c2 = st.columns([1, 4])
        if c1.button("Yes, close all"):
            close_all_positions()
            st.cache_data.clear()
            st.session_state.pop("close_confirm", None)
            st.rerun()
        if c2.button("No, go back"):
            st.session_state.pop("close_confirm", None)
            st.rerun()

# ── Auto-refresh ───────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
