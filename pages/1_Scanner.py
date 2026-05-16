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
import plotly.graph_objects as go

from strategies.auto_scanner import (
    run_full_scan,
    MEGA_CAP_UNIVERSE,
    LEVERAGED_ETF_UNIVERSE,
)
from core.trade import buy_market
from strategies.wheel import sell_put
from db import log_auto_trade
from pages._shared import inject_css, section_header, metric_card, alert, badge, score_color, COLORS

st.set_page_config(page_title="Scanner", page_icon="🔍", layout="wide")
inject_css()

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown("# Scanner")
st.markdown(
    '<p style="color:#8892A4;font-size:0.9rem">Multi-signal scan: momentum · RSI · volume · '
    'congressional · fundamentals. Approve before any trade is placed.</p>',
    unsafe_allow_html=True,
)

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

col_btn, col_info = st.columns([1, 4])
run_btn = col_btn.button("Run Scan", type="primary", use_container_width=True)

if col_info.empty():
    pass

if run_btn:
    with st.spinner("Scanning market — fetching bars, copy signals, and options data…"):
        try:
            result = run_full_scan(universe)
            st.session_state["scan_result"] = result
            st.session_state["confirm_pending"] = False
            st.session_state["selected_actions"] = {}
        except Exception as e:
            alert(f"Scan failed: {e}", "danger")

result = st.session_state.get("scan_result")

if not result:
    alert("Press <strong>Run Scan</strong> to start. Results will appear here.", "info")
    st.stop()

# ── Scan metadata ──────────────────────────────────────────────────────────────

scanned_at  = result.get("scanned_at", "")[:19].replace("T", " ")
bp          = result.get("buying_power", 0)
market_open = result.get("market_open", False)

c1, c2, c3 = st.columns(3)
with c1: metric_card("Scanned At",    scanned_at,              color="blue")
with c2: metric_card("Buying Power",  f"${bp:,.0f}",           color="purple")
with c3: metric_card("Market Status", "OPEN" if market_open else "CLOSED",
                     color="green" if market_open else "red")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Stock candidates ───────────────────────────────────────────────────────────

section_header("Stock Candidates")

stock_candidates = result.get("stock_candidates", [])
qualified_stocks = [c for c in stock_candidates if not c.get("disqualified")][:3]

if stock_candidates:
    # Score bar chart (top 10)
    top10 = stock_candidates[:10]
    bar_colors = [score_color(c["total_score"]) for c in top10]
    fig = go.Figure(go.Bar(
        x=[c["symbol"] for c in top10],
        y=[c["total_score"] for c in top10],
        marker_color=bar_colors,
        text=[str(c["total_score"]) for c in top10],
        textposition="outside",
        textfont_color="#E8ECF0",
    ))
    fig.update_layout(
        height=200,
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8892A4",
        yaxis=dict(range=[0, 110], showgrid=False, zeroline=False, visible=False),
        xaxis=dict(showgrid=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Candidate cards
    for i, c in enumerate(stock_candidates[:10], 1):
        t       = c.get("technicals", {})
        f       = c.get("fundamentals", {}) or {}
        score   = c["total_score"]
        sym     = c["symbol"]
        rsi     = t.get("rsi_14")
        mom     = t.get("momentum_5d")
        vr      = t.get("volume_ratio")
        price   = t.get("latest_close", 0)
        disq    = c.get("disqualified", False)
        reason  = c.get("disqualify_reason", "")

        score_hex  = score_color(score)
        copy_badge = badge("COPY SIGNAL", "green")  if c.get("is_copy_signal") else ""
        skip_badge = badge(f"SKIP: {reason}", "gray") if disq else ""
        opacity    = "opacity:0.5;" if disq else ""

        rsi_display = f"{rsi:.1f}" if rsi is not None else "n/a"
        mom_display = f"{mom:+.1%}" if mom is not None else "n/a"
        vr_display  = f"{vr:.1f}x"  if vr  is not None else "n/a"
        pe_display  = f"{f['pe_ratio']:.1f}" if f.get("pe_ratio") else "—"

        score_w  = min(score, 100)
        st.markdown(f"""
        <div class="cand-card" style="{opacity}">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <span class="symbol">#{i} {sym}</span>
                <span style="font-size:0.8rem;color:#8892A4">${price:.2f}</span>
            </div>
            <div class="score-row">
                <div class="score-track">
                    <div class="score-fill" style="width:{score_w}%;background:{score_hex}"></div>
                </div>
                <span class="score-num" style="color:{score_hex}">{score}</span>
                {copy_badge}{skip_badge}
            </div>
            <div class="info-row">
                <div class="info-item"><span class="key">RSI(14)</span><span class="val">{rsi_display}</span></div>
                <div class="info-item"><span class="key">Mom 5d</span><span class="val">{mom_display}</span></div>
                <div class="info-item"><span class="key">Vol Ratio</span><span class="val">{vr_display}</span></div>
                <div class="info-item"><span class="key">P/E</span><span class="val">{pe_display}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    alert("No stock candidates found.", "info")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Options candidates ─────────────────────────────────────────────────────────

section_header("Wheel / Options Candidates")

options_candidates = [c for c in result.get("options_candidates", []) if c.get("qualified")]

if options_candidates:
    for c in options_candidates[:8]:
        sym     = c["symbol"]
        strike  = c["strike"]
        expiry  = c["expiry"]
        dte     = c["dte"]
        bid     = c["bid"]
        oi      = c["open_interest"]
        spread  = c["spread_pct"]
        premium = c["est_premium_per_contract"]
        otm     = c["otm_pct"]
        is_etf  = c.get("is_leveraged_etf", False)

        # DTE bar (0–50 days)
        dte_w     = max(0, min(100, int(dte / 50 * 100)))
        dte_color_hex = COLORS["red"] if dte <= 7 else COLORS["gold"] if dte <= 14 else COLORS["green"]
        etf_badge = badge("LEVERAGED ETF", "gold") if is_etf else ""

        st.markdown(f"""
        <div class="opt-card">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <span style="font-size:1.1rem;font-weight:700">{sym}</span>
                <span style="font-size:1.1rem;font-weight:700;color:{COLORS['green']}">${premium:,.0f} <span style="font-size:0.75rem;color:#8892A4">/ contract</span></span>
            </div>
            <div class="contract-sym">{c.get('contract_symbol','')}</div>
            <div class="dte-track">
                <div class="dte-fill" style="width:{dte_w}%;background:{dte_color_hex}"></div>
            </div>
            <div class="info-row" style="margin-top:10px">
                <div class="info-item"><span class="key">Strike</span><span class="val">${strike:.2f}</span></div>
                <div class="info-item"><span class="key">Expiry</span><span class="val">{expiry}</span></div>
                <div class="info-item"><span class="key">DTE</span><span class="val" style="color:{dte_color_hex}">{dte}d</span></div>
                <div class="info-item"><span class="key">Bid</span><span class="val">${bid:.2f}</span></div>
                <div class="info-item"><span class="key">Open Interest</span><span class="val">{oi:,}</span></div>
                <div class="info-item"><span class="key">Spread</span><span class="val">{spread:.1%}</span></div>
                <div class="info-item"><span class="key">OTM</span><span class="val">{otm:.1%}</span></div>
                <div class="info-item"><span class="key">Type</span><span class="val">{etf_badge if is_etf else badge("STOCK","blue")}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    alert("No qualified options candidates (OI ≥ 500, spread ≤ 5%, DTE 25–50).", "info")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Proposed actions ───────────────────────────────────────────────────────────

section_header("Proposed Actions")
st.markdown(
    '<p style="color:#8892A4;font-size:0.85rem;margin-bottom:12px">'
    'Select the trades you want to execute, then click <strong>Execute Selected</strong>.</p>',
    unsafe_allow_html=True,
)

qualified_options = options_candidates[:3]

if not qualified_stocks and not qualified_options:
    alert("No actionable candidates this scan.", "info")
    st.stop()

actions = {}

for c in qualified_stocks:
    sym   = c["symbol"]
    score = c["total_score"]
    price = c.get("technicals", {}).get("latest_close", 0)
    label = f"BUY 1 {sym} @ market (~${price:.2f})  —  score {score}"
    key   = f"stock_{sym}"
    actions[key] = {"type": "stock", "symbol": sym, "qty": 1, "score": score, "label": label, "color": score_color(score)}

for c in qualified_options:
    sym     = c["symbol"]
    strike  = c["strike"]
    expiry  = c["expiry"]
    premium = c["est_premium_per_contract"]
    dte     = c["dte"]
    oi      = c["open_interest"]
    otm     = c["otm_pct"]
    label   = f"SELL 1 put {sym} ${strike:.0f} exp {expiry}  —  ${premium:.0f} premium, {dte} DTE, {otm:.1%} OTM"
    key     = f"opt_{sym}_{strike}_{expiry}"
    actions[key] = {
        "type": "put", "symbol": sym, "strike": strike,
        "expiry": expiry, "premium": premium, "score": 0, "label": label, "color": COLORS["teal"],
    }

selected_keys = {}
for key, action in actions.items():
    selected_keys[key] = st.checkbox(action["label"], key=f"chk_{key}")

any_selected = any(selected_keys.values())

if st.button("Execute Selected Trades", type="primary", disabled=not any_selected):
    st.session_state["confirm_pending"] = True

if st.session_state.get("confirm_pending"):
    alert("This will place <strong>paper trades</strong> on your Alpaca account. Review and confirm.", "warn")
    c1, c2 = st.columns([1, 5])

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
                    alert(f"BUY {sym}: order {oid} accepted", "success")

                elif action["type"] == "put":
                    sell_put(sym, action["strike"], action["expiry"], contracts=1, dry_run=False)
                    log_auto_trade(scan_id, sym, "put_sell", 0, 1, "via_wheel",
                                   strike=action["strike"], expiry=action["expiry"],
                                   est_premium=action["premium"])
                    alert(f"PUT {sym} ${action['strike']} {action['expiry']}: order placed", "success")

            except Exception as e:
                errors.append(f"{sym}: {e}")

        for err in errors:
            alert(err, "danger")

        st.session_state["confirm_pending"] = False
        st.cache_data.clear()

    if c2.button("Cancel##exec"):
        st.session_state["confirm_pending"] = False
        st.rerun()
