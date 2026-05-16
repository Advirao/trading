"""
pages/5_History.py — Trade History

Review all auto bot trades and wheel legs from the SQLite database.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from db import get_all_auto_trades, get_all_wheel_legs

st.set_page_config(page_title="History", page_icon="📋", layout="wide")
st.title("📋 Trade History")
st.caption("All trades logged by the /auto scanner and wheel strategy.")

# ── Auto Bot History ───────────────────────────────────────────────────────────

st.subheader("Auto Bot Trades")

try:
    auto_rows = get_all_auto_trades(limit=200)
    if auto_rows:
        df_auto = pd.DataFrame([dict(r) for r in auto_rows])

        # Filters
        col1, col2 = st.columns(2)
        status_filter = col1.multiselect(
            "Status", options=["open", "closed", "expired"], default=["open", "closed", "expired"]
        )
        type_filter = col2.multiselect(
            "Trade type",
            options=["stock_buy", "put_sell", "call_sell"],
            default=["stock_buy", "put_sell", "call_sell"],
        )

        filtered = df_auto[
            df_auto["status"].isin(status_filter) &
            df_auto["trade_type"].isin(type_filter)
        ]

        # Summary metrics
        total_trades   = len(filtered)
        total_premium  = filtered["est_premium"].fillna(0).sum()
        open_positions = (filtered["status"] == "open").sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Trades",     total_trades)
        m2.metric("Total Premium",    f"${total_premium:,.0f}")
        m3.metric("Open Positions",   open_positions)

        # Table
        display_cols = ["placed_at", "symbol", "trade_type", "score",
                        "qty", "est_premium", "contract_sym", "strike",
                        "expiry", "status", "notes"]
        display_cols = [c for c in display_cols if c in filtered.columns]

        def _status_color(row):
            if row.get("status") == "open":
                return ["background-color: #d4edda"] * len(row)
            elif row.get("status") == "expired":
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            filtered[display_cols].style.apply(_status_color, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "est_premium": st.column_config.NumberColumn("Premium", format="$%.0f"),
                "score":       st.column_config.NumberColumn("Score"),
                "placed_at":   st.column_config.TextColumn("Placed At"),
            },
        )
    else:
        st.info("No auto bot trades yet. Run a scan from the Scanner page to get started.")
except Exception as e:
    st.error(f"Could not load auto trade history: {e}")

st.divider()

# ── Wheel History ──────────────────────────────────────────────────────────────

st.subheader("Wheel Strategy Legs")

try:
    wheel_rows = get_all_wheel_legs(limit=200)
    if wheel_rows:
        df_wheel = pd.DataFrame([dict(r) for r in wheel_rows])

        status_filter_w = st.multiselect(
            "Status",
            options=["open", "expired", "assigned", "closed"],
            default=["open", "expired", "assigned", "closed"],
            key="wheel_status",
        )
        filtered_w = df_wheel[df_wheel["status"].isin(status_filter_w)]

        # Summary
        total_w   = len(filtered_w)
        premium_w = filtered_w["premium"].fillna(0).sum()
        open_w    = (filtered_w["status"] == "open").sum()
        closed_w  = filtered_w["status"].isin(["expired", "closed"]).sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Legs",      total_w)
        m2.metric("Total Premium",   f"${premium_w:,.0f}")
        m3.metric("Open",            open_w)
        m4.metric("Completed",       closed_w)

        display_cols_w = ["opened_at", "symbol", "stage", "strike",
                          "expiry", "premium", "status", "closed_at"]
        display_cols_w = [c for c in display_cols_w if c in filtered_w.columns]

        def _wheel_color(row):
            s = row.get("status", "")
            if s == "open":     return ["background-color: #d4edda"] * len(row)
            if s == "assigned": return ["background-color: #cce5ff"] * len(row)
            if s == "expired":  return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            filtered_w[display_cols_w].style.apply(_wheel_color, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "premium":   st.column_config.NumberColumn("Premium", format="$%.2f"),
                "strike":    st.column_config.NumberColumn("Strike",  format="$%.2f"),
                "opened_at": st.column_config.TextColumn("Opened"),
                "closed_at": st.column_config.TextColumn("Closed"),
            },
        )
        st.caption("Green = Open  |  Blue = Assigned  |  Yellow = Expired/Closed")
    else:
        st.info("No wheel legs yet. Use the Wheel page to sell your first put.")
except Exception as e:
    st.error(f"Could not load wheel history: {e}")
