"""
pages/3_Copy_Trading.py — Congressional Copy Trading

Browse recent congressional disclosures and mirror individual trades.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from strategies.copy_trading import fetch_all_trades, classify_trade
from core.trade import buy_market, sell_market

st.set_page_config(page_title="Copy Trading", page_icon="🏛️", layout="wide")
st.title("🏛️ Congressional Copy Trading")
st.caption("Data from Quiver Quantitative — free, no API key required. "
           "For continuous mirroring, use the Claude Code `/level3` command.")

# ── Fetch disclosures ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _fetch():
    return fetch_all_trades()

col1, col2 = st.columns([1, 4])
if col1.button("Refresh Disclosures", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Loading congressional trade disclosures…"):
    try:
        all_trades = _fetch()
    except Exception as e:
        st.error(f"Could not fetch disclosures: {e}")
        st.stop()

if not all_trades:
    st.warning("No data returned from Quiver Quantitative.")
    st.stop()

st.caption(f"Loaded {len(all_trades):,} disclosures.")

# ── Filters ────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Filters")

col1, col2, col3 = st.columns(3)

chamber_filter = col1.selectbox("Chamber", ["Both", "Senate", "House"])
txn_filter     = col2.selectbox("Transaction", ["All", "Purchases", "Sales"])
days_back      = col3.slider("Days back", min_value=7, max_value=365, value=60)

cutoff = (date.today() - timedelta(days=days_back)).isoformat()

# ── Build DataFrame ────────────────────────────────────────────────────────────

rows = []
for t in all_trades:
    txn_date = (t.get("TransactionDate") or "")[:10]
    if txn_date < cutoff:
        continue

    chamber = (t.get("Chamber") or "").strip()
    if chamber_filter == "Senate" and "senate" not in chamber.lower():
        continue
    if chamber_filter == "House" and "representative" not in chamber.lower():
        continue

    txn = t.get("Transaction") or ""
    action = classify_trade(txn)
    if txn_filter == "Purchases" and action != "buy":
        continue
    if txn_filter == "Sales" and action != "sell":
        continue

    ticker = (t.get("Ticker") or "").upper().strip()
    if not ticker or ticker in ("--", "N/A"):
        continue

    rows.append({
        "Date":        txn_date,
        "Politician":  t.get("Representative") or t.get("Politician") or "",
        "Chamber":     chamber,
        "Ticker":      ticker,
        "Transaction": txn,
        "Amount":      t.get("Amount") or "",
        "_action":     action,
    })

if not rows:
    st.info("No disclosures match the selected filters.")
    st.stop()

df = pd.DataFrame(rows).sort_values("Date", ascending=False)

# Color-code: green for buys, red for sells
def _row_color(row):
    if row["_action"] == "buy":
        return ["background-color: #d4edda"] * len(row)
    elif row["_action"] == "sell":
        return ["background-color: #f8d7da"] * len(row)
    return [""] * len(row)

display_df = df.drop(columns=["_action"])
st.subheader(f"Disclosures ({len(df):,} matching)")
st.dataframe(
    display_df.style.apply(_row_color, axis=1),
    use_container_width=True,
    hide_index=True,
)

st.caption("Green = Purchase  |  Red = Sale")

# ── Mirror a trade ─────────────────────────────────────────────────────────────

st.divider()
st.subheader("Mirror a Trade (one-off)")

politicians = sorted(df["Politician"].unique().tolist())
selected_pol = st.selectbox("Select politician", ["— choose —"] + politicians)

if selected_pol and selected_pol != "— choose —":
    pol_trades = df[df["Politician"] == selected_pol].head(10)
    st.write(f"**Recent trades by {selected_pol}:**")
    st.dataframe(pol_trades[["Date", "Ticker", "Transaction", "Amount"]].style.apply(_row_color, axis=1),
                 hide_index=True, use_container_width=True)

    latest_buy = pol_trades[pol_trades["_action"] == "buy"].head(1)
    if not latest_buy.empty:
        latest_ticker = latest_buy.iloc[0]["Ticker"]
        st.info(f"Latest purchase: **{latest_ticker}**")
    else:
        latest_ticker = ""

    col1, col2, col3 = st.columns([2, 1, 1])
    mirror_sym = col1.text_input("Ticker to mirror", value=latest_ticker).upper().strip()
    mirror_qty = col2.number_input("Qty", min_value=1, max_value=100, value=1)
    mirror_side = col3.selectbox("Side", ["BUY", "SELL"])

    if st.button("Place Mirror Trade", type="primary"):
        if not mirror_sym:
            st.error("Enter a ticker.")
        else:
            st.session_state["mirror_confirm"] = {
                "symbol": mirror_sym, "qty": mirror_qty, "side": mirror_side
            }

    pending = st.session_state.get("mirror_confirm")
    if pending:
        st.warning(f"Confirm: **{pending['side']} {pending['qty']} share(s) of {pending['symbol']}**?")
        c1, c2 = st.columns([1, 1])
        if c1.button("Yes, place order", type="primary"):
            try:
                fn = buy_market if pending["side"] == "BUY" else sell_market
                order = fn(pending["symbol"], pending["qty"])
                st.success(f"Order placed — ID: {order.id}")
            except Exception as e:
                st.error(f"Order failed: {e}")
            st.session_state.pop("mirror_confirm", None)
            st.rerun()
        if c2.button("Cancel##mirror"):
            st.session_state.pop("mirror_confirm", None)
            st.rerun()

st.divider()
st.info("For **continuous** copy trading that automatically mirrors every new disclosure, "
        "use the Claude Code `/level3` command.")
