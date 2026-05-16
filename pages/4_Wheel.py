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
)
from db import get_open_wheel_legs
from _shared import inject_css, section_header, metric_card, alert, badge, dte_color, COLORS

st.set_page_config(page_title="Wheel Strategy", page_icon="🎡", layout="wide")
inject_css()

st.markdown("# Wheel Strategy")
st.markdown(
    '<p style="color:#8892A4;font-size:0.9rem">Sell cash-secured puts to collect premium. '
    'If assigned, sell covered calls. The wheel keeps spinning.</p>',
    unsafe_allow_html=True,
)

# ── Open Legs ──────────────────────────────────────────────────────────────────

section_header("Open Wheel Legs")

col_refresh, _ = st.columns([1, 5])
if col_refresh.button("Refresh Positions", use_container_width=True):
    st.rerun()

try:
    legs = get_open_wheel_legs()
    if legs:
        today = date.today()

        # Summary row
        total_legs    = len(legs)
        total_premium = sum(float(leg["premium"] or 0) for leg in legs)
        put_count     = sum(1 for leg in legs if str(leg.get("stage","")).lower() == "put")
        call_count    = sum(1 for leg in legs if str(leg.get("stage","")).lower() == "call")

        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Open Legs",     str(total_legs),         color="blue")
        with c2: metric_card("Total Premium", f"${total_premium:,.2f}", color="green")
        with c3: metric_card("Puts Open",     str(put_count),          color="teal")
        with c4: metric_card("Calls Open",    str(call_count),         color="purple")

        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

        for leg in legs:
            expiry_str = str(leg["expiry"] or "")[:10]
            try:
                dte_val = (date.fromisoformat(expiry_str) - today).days
            except Exception:
                dte_val = None

            stage      = str(leg.get("stage", "")).upper()
            symbol     = leg["symbol"]
            strike     = float(leg["strike"] or 0)
            premium    = float(leg["premium"] or 0)
            opened_at  = str(leg.get("opened_at") or "")[:10]
            status     = str(leg.get("status", "open"))

            dte_display = f"{dte_val}d" if dte_val is not None else "—"
            dte_hex     = dte_color(dte_val) if dte_val is not None else COLORS["green"]
            dte_w       = max(0, min(100, int((dte_val or 0) / 50 * 100)))

            stage_color = "teal" if stage == "PUT" else "purple"
            stage_badge = badge(stage, stage_color)
            status_badge = badge(status, "green" if status == "open" else "gray")

            leg_html = (
                f'<div class="opt-card">'
                f'<div style="display:flex;align-items:center;justify-content:space-between">'
                f'<span style="font-size:1.1rem;font-weight:700">{symbol}</span>'
                f'<span style="font-size:1.1rem;font-weight:700;color:{COLORS["green"]}">${premium:.2f}</span>'
                f'</div>'
                f'<div style="margin-top:4px">{stage_badge} {status_badge}</div>'
                f'<div class="dte-track" style="margin-top:10px">'
                f'<div class="dte-fill" style="width:{dte_w}%;background:{dte_hex}"></div></div>'
                f'<div class="info-row" style="margin-top:10px">'
                f'<div class="info-item"><span class="key">Strike</span><span class="val">${strike:.2f}</span></div>'
                f'<div class="info-item"><span class="key">Expiry</span><span class="val">{expiry_str}</span></div>'
                f'<div class="info-item"><span class="key">DTE</span><span class="val" style="color:{dte_hex}">{dte_display}</span></div>'
                f'<div class="info-item"><span class="key">Opened</span><span class="val">{opened_at}</span></div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(leg_html, unsafe_allow_html=True)

        st.markdown(
            f'<p style="font-size:0.78rem;color:#8892A4;margin-top:8px">'
            f'<span style="color:{COLORS["red"]}">■</span> ≤7 DTE &nbsp;'
            f'<span style="color:{COLORS["gold"]}">■</span> ≤14 DTE &nbsp;'
            f'<span style="color:{COLORS["green"]}">■</span> &gt;14 DTE</p>',
            unsafe_allow_html=True,
        )
    else:
        alert("No open wheel legs. Set up your first position below.", "info")
except Exception as e:
    alert(f"Could not load wheel positions: {e}", "danger")

st.markdown('<hr class="styled-divider">', unsafe_allow_html=True)

# ── Setup New Position ─────────────────────────────────────────────────────────

section_header("Set Up New Position")

col1, col2 = st.columns([2, 1])
symbol = col1.text_input("Underlying symbol", placeholder="TQQQ").upper().strip()
stage  = col2.selectbox("Stage", ["Stage 1 — Sell Put", "Stage 2 — Sell Call"])
is_put = "Put" in stage

price_val = None

if symbol:
    col_price, _ = st.columns([1, 4])
    if col_price.button("Get Current Price", use_container_width=True):
        with st.spinner(f"Fetching {symbol}…"):
            try:
                price_val = get_latest_price(symbol)
                st.session_state[f"price_{symbol}"] = price_val
            except Exception as e:
                alert(f"Could not fetch price: {e}", "danger")

    price_val = st.session_state.get(f"price_{symbol}")

    if price_val:
        c1, c2 = st.columns([1, 4])
        with c1:
            metric_card("Current Price", f"${price_val:.2f}", color="blue")

if symbol and price_val:
    option_type      = "put" if is_put else "call"
    suggested_strike = _suggest_strike(price_val, option_type)
    suggested_expiry = _suggest_expiry(weeks_out=4)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    strike    = col1.number_input("Strike ($)", value=float(suggested_strike), step=0.5)
    expiry    = col2.text_input("Expiry (YYYY-MM-DD)", value=suggested_expiry)
    contracts = col3.number_input("Contracts", min_value=1, max_value=10, value=1)

    otm_pct   = abs(price_val - strike) / price_val * 100
    direction = "below" if is_put else "above"
    alert(
        f"Strike is <strong>{otm_pct:.1f}% {direction}</strong> current price — "
        f"<strong>{100 * contracts} shares</strong> cash secured",
        "info",
    )

    # Preview contract
    col_preview, _ = st.columns([1, 4])
    if col_preview.button("Preview Contract", use_container_width=True):
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
                        "symbol":        c.get("symbol"),
                        "bid":           bid,
                        "ask":           ask,
                        "mid":           mid,
                        "oi":            oi,
                        "premium_total": round(bid * 100 * contracts, 2),
                    }
                else:
                    alert("No matching contract found. Try adjusting strike or expiry.", "warn")
                    st.session_state.pop("preview_contract", None)
            except Exception as e:
                alert(f"Could not fetch contract: {e}", "danger")

    preview = st.session_state.get("preview_contract")
    if preview:
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Bid",           f"${preview['bid']:.2f}", color="red")
        with c2: metric_card("Ask",           f"${preview['ask']:.2f}", color="green")
        with c3: metric_card("Open Interest", str(preview["oi"]),        color="blue")
        with c4:
            label = f"Premium ({contracts} lot{'s' if contracts > 1 else ''})"
            metric_card(label, f"${preview['premium_total']:.0f}", color="teal")
        st.markdown(
            f'<p style="font-size:0.8rem;color:#8892A4;margin-top:4px">'
            f'Contract: <code>{preview["symbol"]}</code></p>',
            unsafe_allow_html=True,
        )

    # Execute
    action_label = f"Sell {'Put' if is_put else 'Call'}"
    col_sell, _ = st.columns([1, 4])
    if col_sell.button(action_label, type="primary", use_container_width=True):
        st.session_state["wheel_confirm"] = {
            "symbol": symbol, "strike": strike, "expiry": expiry,
            "contracts": contracts, "is_put": is_put,
        }

    pending = st.session_state.get("wheel_confirm")
    if pending:
        action = "PUT" if pending["is_put"] else "CALL"
        alert(
            f"Confirm: <strong>SELL {pending['contracts']} {action} {pending['symbol']} "
            f"${pending['strike']:.0f} exp {pending['expiry']}</strong>?",
            "warn",
        )
        c1, c2 = st.columns([1, 5])
        if c1.button("Yes, sell it", type="primary"):
            try:
                if pending["is_put"]:
                    sell_put(pending["symbol"], pending["strike"], pending["expiry"],
                             contracts=pending["contracts"], dry_run=False)
                else:
                    sell_call(pending["symbol"], pending["strike"], pending["expiry"],
                              contracts=pending["contracts"], dry_run=False)
                alert(f"{action} order placed for {pending['symbol']}.", "success")
                st.session_state.pop("wheel_confirm", None)
                st.session_state.pop("preview_contract", None)
                st.rerun()
            except Exception as e:
                alert(f"Order failed: {e}", "danger")
        if c2.button("Cancel##wheel"):
            st.session_state.pop("wheel_confirm", None)
            st.rerun()

elif symbol and not price_val:
    alert("Click <strong>Get Current Price</strong> to load strike and expiry suggestions.", "info")
