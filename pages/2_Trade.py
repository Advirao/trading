"""
pages/2_Trade.py — Manual Trading

Buy, sell, cancel orders, and look up live prices.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.market_data import get_quote, get_bars
from core.trade import buy_market, sell_market, get_orders, cancel_all_orders
from _shared import inject_css, section_header, metric_card, alert, badge, COLORS

st.set_page_config(page_title="Trade", page_icon="💹", layout="wide")
inject_css()

st.markdown("# Manual Trading")
st.markdown(
    '<p style="color:#8892A4;font-size:0.9rem">All trades execute on your Alpaca '
    '<strong>paper account</strong> — no real money involved.</p>',
    unsafe_allow_html=True,
)

# ── Price Lookup ───────────────────────────────────────────────────────────────

section_header("Price Lookup")

col1, col2 = st.columns([3, 1])
symbol_input = col1.text_input("Symbol", placeholder="AAPL", key="lookup_symbol",
                                label_visibility="collapsed").upper().strip()
lookup_btn   = col2.button("Get Quote", use_container_width=True, type="primary")

if lookup_btn and symbol_input:
    with st.spinner(f"Fetching {symbol_input}…"):
        try:
            q    = get_quote(symbol_input)
            bars = get_bars(symbol_input, days=10)

            bid = float(q.bid_price)
            ask = float(q.ask_price)
            mid = (bid + ask) / 2

            c1, c2, c3 = st.columns(3)
            with c1: metric_card("Bid",  f"${bid:.2f}", color="red")
            with c2: metric_card("Ask",  f"${ask:.2f}", color="green")
            with c3: metric_card("Mid",  f"${mid:.2f}", color="blue")

            if bars:
                closes = [float(b.close) for b in bars]
                dates  = [str(b.timestamp.date()) for b in bars]
                volumes = [int(b.volume) for b in bars]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=closes,
                    mode="lines+markers",
                    line=dict(color=COLORS["blue"], width=2),
                    marker=dict(size=5, color=COLORS["blue"]),
                    fill="tozeroy",
                    fillcolor="rgba(33,150,243,0.08)",
                    name="Close",
                ))
                fig.update_layout(
                    height=220,
                    margin=dict(t=10, b=10, l=0, r=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#8892A4",
                    yaxis=dict(showgrid=True, gridcolor="#2D3748", zeroline=False,
                               tickprefix="$"),
                    xaxis=dict(showgrid=False),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                with st.expander("OHLCV Table"):
                    ohlcv = pd.DataFrame([{
                        "Date":   str(b.timestamp.date()),
                        "Open":   float(b.open),
                        "High":   float(b.high),
                        "Low":    float(b.low),
                        "Close":  float(b.close),
                        "Volume": int(b.volume),
                    } for b in bars])
                    st.dataframe(
                        ohlcv, hide_index=True, use_container_width=True,
                        column_config={
                            "Open":  st.column_config.NumberColumn(format="$%.2f"),
                            "High":  st.column_config.NumberColumn(format="$%.2f"),
                            "Low":   st.column_config.NumberColumn(format="$%.2f"),
                            "Close": st.column_config.NumberColumn(format="$%.2f"),
                            "Volume": st.column_config.NumberColumn(format="%d"),
                        },
                    )

            st.session_state["trade_symbol"] = symbol_input
            st.session_state["trade_price"]  = ask

        except Exception as e:
            alert(f"Could not fetch {symbol_input}: {e}", "danger")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Trade Form ─────────────────────────────────────────────────────────────────

section_header("Place Order")

col1, col2, col3 = st.columns([2, 1, 1])
trade_sym = col1.text_input(
    "Symbol", value=st.session_state.get("trade_symbol", ""),
    placeholder="AAPL", key="trade_sym",
).upper().strip()
trade_qty = col2.number_input("Quantity", min_value=1, max_value=1000, value=1, step=1)
est_price = st.session_state.get("trade_price")

if est_price and trade_sym == st.session_state.get("trade_symbol", ""):
    with col3:
        metric_card("Est. Cost", f"${est_price * trade_qty:,.2f}", color="blue")

col_buy, col_sell, _ = st.columns([1, 1, 3])
buy_btn  = col_buy.button("BUY",  type="primary",    use_container_width=True)
sell_btn = col_sell.button("SELL", type="secondary", use_container_width=True)

if (buy_btn or sell_btn) and trade_sym:
    side = "BUY" if buy_btn else "SELL"
    key  = f"{side.lower()}_confirm"
    st.session_state[key] = {"symbol": trade_sym, "qty": trade_qty, "side": side}

for side in ("BUY", "SELL"):
    key     = f"{side.lower()}_confirm"
    pending = st.session_state.get(key)
    if pending:
        sym  = pending["symbol"]
        qty  = pending["qty"]
        kind = "success" if side == "BUY" else "warn"
        alert(
            f"Confirm: <strong>{side} {qty} share(s) of {sym}</strong> at market price?",
            kind,
        )
        c1, c2 = st.columns([1, 5])
        if c1.button(f"Yes, {side}", type="primary"):
            try:
                fn    = buy_market if side == "BUY" else sell_market
                order = fn(sym, qty)
                alert(f"{side} order placed — ID: {order.id} | Status: {order.status}", "success")
            except Exception as e:
                alert(f"Order failed: {e}", "danger")
            st.session_state.pop(key, None)
            st.rerun()
        if c2.button(f"Cancel##{side}"):
            st.session_state.pop(key, None)
            st.rerun()

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Open Orders ────────────────────────────────────────────────────────────────

section_header("Open Orders")

@st.cache_data(ttl=10)
def _open_orders():
    return get_orders("open")

col_refresh, _ = st.columns([1, 5])
if col_refresh.button("Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

orders = _open_orders()
if orders:
    rows = []
    for o in orders:
        side_raw   = str(o.side).replace("OrderSide.", "").upper()
        status_raw = str(o.status).replace("OrderStatus.", "").upper()
        rows.append({
            "Symbol":    o.symbol,
            "Side":      side_raw,
            "Qty":       float(o.qty or 0),
            "Type":      str(o.type).replace("OrderType.", "").upper(),
            "Status":    status_raw,
            "Submitted": str(o.submitted_at)[:16].replace("T", " ") if o.submitted_at else "—",
        })
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={"Qty": st.column_config.NumberColumn(format="%.0f")},
    )

    col_btn, _ = st.columns([1, 4])
    if col_btn.button("Cancel All Orders", type="secondary", use_container_width=True):
        st.session_state["cancel_all"] = True

    if st.session_state.get("cancel_all"):
        alert("This will cancel <strong>all</strong> open orders immediately.", "warn")
        c1, c2 = st.columns([1, 5])
        if c1.button("Yes, cancel all", type="primary"):
            cancel_all_orders()
            st.cache_data.clear()
            st.session_state.pop("cancel_all", None)
            alert("All orders cancelled.", "success")
            st.rerun()
        if c2.button("No, keep them"):
            st.session_state.pop("cancel_all", None)
            st.rerun()
else:
    alert("No open orders.", "info")
