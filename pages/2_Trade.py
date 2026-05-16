"""
pages/2_Trade.py — Manual Trading

Buy, sell, cancel orders, and look up live prices.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from core.market_data import get_quote, get_bars
from core.trade import buy_market, sell_market, get_orders, cancel_all_orders

st.set_page_config(page_title="Trade", page_icon="💹", layout="wide")
st.title("💹 Manual Trading")
st.caption("All trades execute on your Alpaca paper account — no real money.")

# ── Price Lookup ───────────────────────────────────────────────────────────────

st.subheader("Price Lookup")

col1, col2 = st.columns([2, 1])
symbol_input = col1.text_input("Symbol", placeholder="AAPL", key="lookup_symbol").upper().strip()
lookup_btn   = col2.button("Get Quote", use_container_width=True)

if lookup_btn and symbol_input:
    with st.spinner(f"Fetching {symbol_input}…"):
        try:
            q    = get_quote(symbol_input)
            bars = get_bars(symbol_input, days=10)

            m1, m2, m3 = st.columns(3)
            m1.metric("Bid",  f"${float(q.bid_price):.2f}")
            m2.metric("Ask",  f"${float(q.ask_price):.2f}")
            m3.metric("Mid",  f"${(float(q.bid_price) + float(q.ask_price)) / 2:.2f}")

            if bars:
                bar_data = pd.DataFrame([
                    {"Date": str(b.timestamp.date()), "Close": float(b.close), "Volume": int(b.volume)}
                    for b in bars
                ]).set_index("Date")
                st.line_chart(bar_data[["Close"]], use_container_width=True)
                with st.expander("OHLCV Table"):
                    ohlcv = pd.DataFrame([
                        {"Date": str(b.timestamp.date()),
                         "Open": f"${float(b.open):.2f}",
                         "High": f"${float(b.high):.2f}",
                         "Low":  f"${float(b.low):.2f}",
                         "Close": f"${float(b.close):.2f}",
                         "Volume": f"{int(b.volume):,}"}
                        for b in bars
                    ])
                    st.dataframe(ohlcv, hide_index=True, use_container_width=True)

            st.session_state["trade_symbol"] = symbol_input
            st.session_state["trade_price"]  = float(q.ask_price or q.bid_price)

        except Exception as e:
            st.error(f"Could not fetch {symbol_input}: {e}")

st.divider()

# ── Trade Form ─────────────────────────────────────────────────────────────────

st.subheader("Place Order")

col1, col2, col3 = st.columns([2, 1, 1])
trade_sym = col1.text_input(
    "Symbol", value=st.session_state.get("trade_symbol", ""), placeholder="AAPL", key="trade_sym"
).upper().strip()
trade_qty = col2.number_input("Quantity", min_value=1, max_value=1000, value=1, step=1)
est_price = st.session_state.get("trade_price")
if est_price and trade_sym == st.session_state.get("trade_symbol", ""):
    col3.metric("Est. Cost", f"${est_price * trade_qty:,.2f}")

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
        sym = pending["symbol"]
        qty = pending["qty"]
        color = "primary" if side == "BUY" else "secondary"
        st.warning(f"Confirm: **{side} {qty} share(s) of {sym}** at market price?")
        c1, c2 = st.columns([1, 1])
        if c1.button(f"Yes, {side}", type=color):
            try:
                fn = buy_market if side == "BUY" else sell_market
                order = fn(sym, qty)
                st.success(f"{side} order placed — ID: {order.id} | Status: {order.status}")
            except Exception as e:
                st.error(f"Order failed: {e}")
            st.session_state.pop(key, None)
            st.rerun()
        if c2.button(f"Cancel##{side}"):
            st.session_state.pop(key, None)
            st.rerun()

st.divider()

# ── Open Orders ────────────────────────────────────────────────────────────────

st.subheader("Open Orders")

@st.cache_data(ttl=10)
def _open_orders():
    return get_orders("open")

if st.button("Refresh Orders"):
    st.cache_data.clear()

orders = _open_orders()
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

    if st.button("Cancel All Orders", type="secondary"):
        st.session_state["cancel_all"] = True

    if st.session_state.get("cancel_all"):
        st.warning("Cancel **all** open orders?")
        c1, c2 = st.columns([1, 1])
        if c1.button("Yes, cancel all", type="primary"):
            cancel_all_orders()
            st.cache_data.clear()
            st.session_state.pop("cancel_all", None)
            st.success("All orders cancelled.")
            st.rerun()
        if c2.button("No, keep them"):
            st.session_state.pop("cancel_all", None)
            st.rerun()
else:
    st.info("No open orders.")
