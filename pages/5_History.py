"""
pages/5_History.py — Trade History

Review all auto bot trades and wheel legs from the SQLite database.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from db import get_all_auto_trades, get_all_wheel_legs
from _shared import inject_css, section_header, metric_card, alert, badge, COLORS

st.set_page_config(page_title="History", page_icon="📋", layout="wide")
inject_css()

st.markdown("# Trade History")
st.markdown(
    '<p style="color:#8892A4;font-size:0.9rem">All trades logged by the '
    '<code>/auto</code> scanner and wheel strategy.</p>',
    unsafe_allow_html=True,
)

# ── Auto Bot History ───────────────────────────────────────────────────────────

section_header("Auto Bot Trades")

try:
    auto_rows = get_all_auto_trades(limit=200)
    if auto_rows:
        df_auto = pd.DataFrame([dict(r) for r in auto_rows])

        # Summary metrics
        total_trades   = len(df_auto)
        total_premium  = df_auto["est_premium"].fillna(0).sum()
        open_positions = (df_auto["status"] == "open").sum()
        stock_count    = (df_auto["trade_type"] == "stock_buy").sum()

        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Total Trades",    str(total_trades),         color="blue")
        with c2: metric_card("Total Premium",   f"${total_premium:,.0f}",  color="green")
        with c3: metric_card("Open Positions",  str(open_positions),        color="teal")
        with c4: metric_card("Stock Buys",      str(stock_count),           color="purple")

        # Cumulative premium chart (options only)
        options_df = df_auto[df_auto["trade_type"].isin(["put_sell", "call_sell"])].copy()
        if not options_df.empty and "placed_at" in options_df.columns:
            options_df = options_df.sort_values("placed_at")
            options_df["cumulative_premium"] = options_df["est_premium"].fillna(0).cumsum()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=options_df["placed_at"].astype(str).str[:10].tolist(),
                y=options_df["cumulative_premium"].tolist(),
                mode="lines+markers",
                line=dict(color=COLORS["green"], width=2),
                marker=dict(size=5, color=COLORS["green"]),
                fill="tozeroy",
                fillcolor="rgba(76,175,80,0.08)",
                name="Cumulative Premium",
            ))
            fig.update_layout(
                height=200,
                margin=dict(t=10, b=10, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#8892A4",
                yaxis=dict(showgrid=True, gridcolor="#2D3748", zeroline=False,
                           tickprefix="$"),
                xaxis=dict(showgrid=False),
                showlegend=False,
                title=dict(text="Cumulative Options Premium Collected",
                           font=dict(color="#8892A4", size=12), x=0),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

        # Filters
        col1, col2 = st.columns(2)
        status_filter = col1.multiselect(
            "Status", options=["open", "closed", "expired"],
            default=["open", "closed", "expired"],
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

        display_cols = ["placed_at", "symbol", "trade_type", "score",
                        "qty", "est_premium", "contract_sym", "strike",
                        "expiry", "status", "notes"]
        display_cols = [c for c in display_cols if c in filtered.columns]

        def _status_color_auto(row):
            s = row.get("status", "")
            if s == "open":    return [f"background-color:{COLORS['green']}12"] * len(row)
            if s == "expired": return [f"background-color:{COLORS['gold']}12"] * len(row)
            return [""] * len(row)

        st.dataframe(
            filtered[display_cols].style.apply(_status_color_auto, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "est_premium":   st.column_config.NumberColumn("Premium",  format="$%.0f"),
                "score":         st.column_config.NumberColumn("Score"),
                "placed_at":     st.column_config.TextColumn("Placed At"),
                "contract_sym":  st.column_config.TextColumn("Contract"),
            },
        )
        st.markdown(
            f'<p style="font-size:0.78rem;color:#8892A4">'
            f'<span style="color:{COLORS["green"]}">■</span> Open &nbsp;'
            f'<span style="color:{COLORS["gold"]}">■</span> Expired/Closed</p>',
            unsafe_allow_html=True,
        )
    else:
        alert("No auto bot trades yet. Run a scan from the Scanner page to get started.", "info")
except Exception as e:
    alert(f"Could not load auto trade history: {e}", "danger")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Wheel History ──────────────────────────────────────────────────────────────

section_header("Wheel Strategy Legs")

try:
    wheel_rows = get_all_wheel_legs(limit=200)
    if wheel_rows:
        df_wheel = pd.DataFrame([dict(r) for r in wheel_rows])

        # Summary
        total_w   = len(df_wheel)
        premium_w = df_wheel["premium"].fillna(0).sum()
        open_w    = (df_wheel["status"] == "open").sum()
        closed_w  = df_wheel["status"].isin(["expired", "closed"]).sum()
        assigned_w = (df_wheel["status"] == "assigned").sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: metric_card("Total Legs",     str(total_w),            color="blue")
        with c2: metric_card("Total Premium",  f"${premium_w:,.0f}",    color="green")
        with c3: metric_card("Open",           str(open_w),             color="teal")
        with c4: metric_card("Completed",      str(closed_w),           color="gold")
        with c5: metric_card("Assigned",       str(assigned_w),         color="purple")

        # Cumulative wheel premium chart
        if "opened_at" in df_wheel.columns:
            wh_sorted = df_wheel.sort_values("opened_at").copy()
            wh_sorted["cum_premium"] = wh_sorted["premium"].fillna(0).cumsum()

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=wh_sorted["opened_at"].astype(str).str[:10].tolist(),
                y=wh_sorted["cum_premium"].tolist(),
                mode="lines+markers",
                line=dict(color=COLORS["teal"], width=2),
                marker=dict(size=5, color=COLORS["teal"]),
                fill="tozeroy",
                fillcolor="rgba(0,188,212,0.08)",
                name="Cumulative Premium",
            ))
            fig2.update_layout(
                height=200,
                margin=dict(t=10, b=10, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#8892A4",
                yaxis=dict(showgrid=True, gridcolor="#2D3748", zeroline=False,
                           tickprefix="$"),
                xaxis=dict(showgrid=False),
                showlegend=False,
                title=dict(text="Cumulative Wheel Premium Collected",
                           font=dict(color="#8892A4", size=12), x=0),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        status_filter_w = st.multiselect(
            "Status",
            options=["open", "expired", "assigned", "closed"],
            default=["open", "expired", "assigned", "closed"],
            key="wheel_status",
        )
        filtered_w = df_wheel[df_wheel["status"].isin(status_filter_w)]

        display_cols_w = ["opened_at", "symbol", "stage", "strike",
                          "expiry", "premium", "status", "closed_at"]
        display_cols_w = [c for c in display_cols_w if c in filtered_w.columns]

        def _wheel_color(row):
            s = row.get("status", "")
            if s == "open":     return [f"background-color:{COLORS['green']}12"] * len(row)
            if s == "assigned": return [f"background-color:{COLORS['blue']}12"]  * len(row)
            if s == "expired":  return [f"background-color:{COLORS['gold']}12"]  * len(row)
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
        st.markdown(
            f'<p style="font-size:0.78rem;color:#8892A4">'
            f'<span style="color:{COLORS["green"]}">■</span> Open &nbsp;'
            f'<span style="color:{COLORS["blue"]}">■</span> Assigned &nbsp;'
            f'<span style="color:{COLORS["gold"]}">■</span> Expired/Closed</p>',
            unsafe_allow_html=True,
        )
    else:
        alert("No wheel legs yet. Use the Wheel page to sell your first put.", "info")
except Exception as e:
    alert(f"Could not load wheel history: {e}", "danger")
