"""
pages/3_Copy_Trading.py — Congressional Copy Trading

Browse recent congressional disclosures and mirror individual trades.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from collections import Counter

from strategies.copy_trading import fetch_all_trades, classify_trade
from core.trade import buy_market, sell_market
from _shared import inject_css, section_header, metric_card, alert, badge, COLORS

st.set_page_config(page_title="Copy Trading", page_icon="🏛️", layout="wide")
inject_css()

st.markdown("# Congressional Copy Trading")
st.markdown(
    '<p style="color:#8892A4;font-size:0.9rem">Data from Quiver Quantitative — free, no API key '
    'required. For continuous mirroring, use the Claude Code <code>/level3</code> command.</p>',
    unsafe_allow_html=True,
)

# ── Fetch disclosures ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _fetch():
    return fetch_all_trades()

col_refresh, _ = st.columns([1, 5])
if col_refresh.button("Refresh Disclosures", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Loading congressional trade disclosures…"):
    try:
        all_trades = _fetch()
    except Exception as e:
        alert(f"Could not fetch disclosures: {e}", "danger")
        st.stop()

if not all_trades:
    alert("No data returned from Quiver Quantitative.", "warn")
    st.stop()

# ── Filters ────────────────────────────────────────────────────────────────────

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
section_header("Filters")

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

    txn    = t.get("Transaction") or ""
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
    alert("No disclosures match the selected filters.", "info")
    st.stop()

df = pd.DataFrame(rows).sort_values("Date", ascending=False)

# ── Summary stats ──────────────────────────────────────────────────────────────

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
section_header("Overview")

total  = len(df)
buys   = (df["_action"] == "buy").sum()
sells  = (df["_action"] == "sell").sum()
pols   = df["Politician"].nunique()

c1, c2, c3, c4 = st.columns(4)
with c1: metric_card("Total Disclosures", str(total),   color="blue")
with c2: metric_card("Purchases",         str(buys),    color="green")
with c3: metric_card("Sales",             str(sells),   color="red")
with c4: metric_card("Politicians",       str(pols),    color="purple")

# ── Top politicians by activity ─────────────────────────────────────────────────

section_header("Most Active Politicians")

pol_counts = df.groupby("Politician").size().sort_values(ascending=False).head(8)
buy_counts = df[df["_action"] == "buy"].groupby("Politician").size()
sell_counts = df[df["_action"] == "sell"].groupby("Politician").size()

fig = go.Figure()
fig.add_trace(go.Bar(
    name="Purchases",
    x=pol_counts.index.tolist(),
    y=[buy_counts.get(p, 0) for p in pol_counts.index],
    marker_color=COLORS["green"],
))
fig.add_trace(go.Bar(
    name="Sales",
    x=pol_counts.index.tolist(),
    y=[sell_counts.get(p, 0) for p in pol_counts.index],
    marker_color=COLORS["red"],
))
fig.update_layout(
    barmode="stack",
    height=220,
    margin=dict(t=10, b=10, l=0, r=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#8892A4",
    yaxis=dict(showgrid=True, gridcolor="#2D3748", zeroline=False),
    xaxis=dict(showgrid=False, tickangle=-25),
    legend=dict(orientation="h", x=0, y=1.15, font_color="#8892A4"),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Disclosures table ──────────────────────────────────────────────────────────

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
section_header(f"Disclosures ({len(df):,} matching)")

def _row_color(row):
    if row["_action"] == "buy":
        return [f"background-color:{COLORS['green']}18"] * len(row)
    elif row["_action"] == "sell":
        return [f"background-color:{COLORS['red']}18"] * len(row)
    return [""] * len(row)

display_df = df.drop(columns=["_action"])
st.dataframe(
    display_df.style.apply(_row_color, axis=1),
    use_container_width=True,
    hide_index=True,
)
st.markdown(
    f'<p style="font-size:0.78rem;color:#8892A4">'
    f'<span style="color:{COLORS["green"]}">■</span> Purchase &nbsp;&nbsp;'
    f'<span style="color:{COLORS["red"]}">■</span> Sale</p>',
    unsafe_allow_html=True,
)

# ── Mirror a trade ─────────────────────────────────────────────────────────────

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
section_header("Mirror a Trade (one-off)")

politicians = sorted(df["Politician"].unique().tolist())
selected_pol = st.selectbox("Select politician", ["— choose —"] + politicians)

if selected_pol and selected_pol != "— choose —":
    pol_trades = df[df["Politician"] == selected_pol].head(10)

    # Mini activity summary for selected politician
    pol_buys  = (pol_trades["_action"] == "buy").sum()
    pol_sells = (pol_trades["_action"] == "sell").sum()
    top_tickers = pol_trades["Ticker"].value_counts().head(3).index.tolist()

    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Recent Purchases", str(pol_buys),  color="green")
    with c2: metric_card("Recent Sales",     str(pol_sells), color="red")
    with c3: metric_card("Top Tickers",      ", ".join(top_tickers) or "—", color="blue")

    st.dataframe(
        pol_trades[["Date", "Ticker", "Transaction", "Amount"]]
            .style.apply(_row_color, axis=1),
        hide_index=True,
        use_container_width=True,
    )

    latest_buy = pol_trades[pol_trades["_action"] == "buy"].head(1)
    if not latest_buy.empty:
        latest_ticker = latest_buy.iloc[0]["Ticker"]
        alert(f"Latest purchase by {selected_pol}: <strong>{latest_ticker}</strong>", "info")
    else:
        latest_ticker = ""

    col1, col2, col3 = st.columns([2, 1, 1])
    mirror_sym  = col1.text_input("Ticker to mirror", value=latest_ticker).upper().strip()
    mirror_qty  = col2.number_input("Qty", min_value=1, max_value=100, value=1)
    mirror_side = col3.selectbox("Side", ["BUY", "SELL"])

    if st.button("Place Mirror Trade", type="primary"):
        if not mirror_sym:
            alert("Enter a ticker.", "warn")
        else:
            st.session_state["mirror_confirm"] = {
                "symbol": mirror_sym, "qty": mirror_qty, "side": mirror_side
            }

    pending = st.session_state.get("mirror_confirm")
    if pending:
        kind = "success" if pending["side"] == "BUY" else "warn"
        alert(
            f"Confirm: <strong>{pending['side']} {pending['qty']} share(s) of "
            f"{pending['symbol']}</strong> at market?",
            kind,
        )
        c1, c2 = st.columns([1, 5])
        if c1.button("Yes, place order", type="primary"):
            try:
                fn    = buy_market if pending["side"] == "BUY" else sell_market
                order = fn(pending["symbol"], pending["qty"])
                alert(f"Order placed — ID: {order.id}", "success")
            except Exception as e:
                alert(f"Order failed: {e}", "danger")
            st.session_state.pop("mirror_confirm", None)
            st.rerun()
        if c2.button("Cancel##mirror"):
            st.session_state.pop("mirror_confirm", None)
            st.rerun()

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)
alert(
    "For <strong>continuous</strong> copy trading that automatically mirrors every new disclosure, "
    "use the Claude Code <code>/level3</code> command.",
    "info",
)
