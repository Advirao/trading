"""
pages/_shared.py — Shared design system for all Streamlit pages.

Provides CSS injection, metric cards, badges, and chart helpers.
Import at the top of every page: from pages._shared import inject_css, metric_card, badge
"""

import streamlit as st

# ── Color palette ──────────────────────────────────────────────────────────────

COLORS = {
    "green":   "#4CAF50",
    "red":     "#F44336",
    "blue":    "#2196F3",
    "gold":    "#FFC107",
    "purple":  "#9C27B0",
    "teal":    "#00BCD4",
    "card_bg": "#1A1F2E",
    "border":  "#2D3748",
    "muted":   "#8892A4",
}

CSS = """
<style>
/* ── Page-level layout ──────────────────────────────────────── */
.block-container { padding-top: 1.5rem !important; }
header[data-testid="stHeader"] { background: #0E1117; border-bottom: 1px solid #2D3748; }

/* ── Metric cards ───────────────────────────────────────────── */
.m-card {
    background: #1A1F2E;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 18px 20px 14px;
    text-align: center;
    height: 100%;
}
.m-card .label {
    font-size: 0.78rem;
    color: #8892A4;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}
.m-card .value {
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 4px;
}
.m-card .delta {
    font-size: 0.82rem;
    font-weight: 500;
}
.m-card.green  { border-left: 4px solid #4CAF50; }
.m-card.red    { border-left: 4px solid #F44336; }
.m-card.blue   { border-left: 4px solid #2196F3; }
.m-card.gold   { border-left: 4px solid #FFC107; }
.m-card.purple { border-left: 4px solid #9C27B0; }
.m-card.teal   { border-left: 4px solid #00BCD4; }

/* ── Status badges ──────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    vertical-align: middle;
}
.badge-green  { background: #1B5E2040; color: #4CAF50; border: 1px solid #4CAF5060; }
.badge-red    { background: #B71C1C40; color: #F44336; border: 1px solid #F4433660; }
.badge-blue   { background: #0D47A140; color: #64B5F6; border: 1px solid #2196F360; }
.badge-gold   { background: #F57F1740; color: #FFC107; border: 1px solid #FFC10760; }
.badge-purple { background: #4A148C40; color: #CE93D8; border: 1px solid #9C27B060; }
.badge-gray   { background: #37474F40; color: #90A4AE; border: 1px solid #90A4AE60; }

/* ── Section headers ────────────────────────────────────────── */
.section-header {
    font-size: 1.0rem;
    font-weight: 600;
    color: #8892A4;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 1.2rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #2D3748;
}

/* ── Candidate cards (scanner) ──────────────────────────────── */
.cand-card {
    background: #1A1F2E;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.cand-card:hover { border-color: #2196F3; }
.cand-card .symbol {
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.cand-card .score-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 6px;
}
.score-track {
    flex: 1;
    background: #2D3748;
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
}
.score-fill { height: 6px; border-radius: 4px; }
.score-num { font-size: 0.82rem; font-weight: 700; min-width: 28px; text-align: right; }

/* ── Info rows ──────────────────────────────────────────────── */
.info-row {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 8px;
    font-size: 0.8rem;
    color: #8892A4;
}
.info-item { display: flex; flex-direction: column; gap: 2px; }
.info-item .key { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; }
.info-item .val { font-weight: 600; color: #E8ECF0; font-size: 0.86rem; }

/* ── Alert boxes ────────────────────────────────────────────── */
.alert-box {
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.88rem;
    border-left: 4px solid;
}
.alert-warn { background: #F57F1715; border-color: #FFC107; color: #FFC107; }
.alert-danger { background: #F4433615; border-color: #F44336; color: #F44336; }
.alert-info { background: #2196F315; border-color: #2196F3; color: #64B5F6; }
.alert-success { background: #4CAF5015; border-color: #4CAF50; color: #4CAF50; }

/* ── Market status pill (header) ────────────────────────────── */
.market-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.06em;
}
.market-pill.open  { background: #1B5E2050; color: #4CAF50; border: 1px solid #4CAF5070; }
.market-pill.closed { background: #B71C1C30; color: #F44336; border: 1px solid #F4433650; }
.market-dot { width: 7px; height: 7px; border-radius: 50%; }
.market-dot.open  { background: #4CAF50; box-shadow: 0 0 6px #4CAF50; }
.market-dot.closed { background: #F44336; }

/* ── Page title row ─────────────────────────────────────────── */
.page-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}
.page-title-row h1 { margin: 0; font-size: 1.6rem; font-weight: 800; }

/* ── Divider ────────────────────────────────────────────────── */
.styled-divider { border: none; border-top: 1px solid #2D3748; margin: 1.4rem 0; }

/* ── Options card ───────────────────────────────────────────── */
.opt-card {
    background: #1A1F2E;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.opt-card .contract-sym {
    font-family: monospace;
    font-size: 0.78rem;
    color: #8892A4;
    margin-top: 4px;
}

/* ── DTE progress bar ───────────────────────────────────────── */
.dte-track {
    background: #2D3748;
    border-radius: 4px;
    height: 5px;
    margin-top: 6px;
    overflow: hidden;
}
.dte-fill { height: 5px; border-radius: 4px; }

/* ── Sidebar tweaks ─────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #12161F;
    border-right: 1px solid #2D3748;
}
section[data-testid="stSidebar"] .stButton button {
    width: 100%;
    border-radius: 8px;
}

/* ── Table tweaks ───────────────────────────────────────────── */
.stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
"""


def inject_css():
    """Inject the shared design system CSS. Call once at the top of each page."""
    st.markdown(CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str, delta: str = None, color: str = "blue"):
    """Render a styled metric card with optional delta line."""
    delta_color = COLORS["green"] if delta and "+" in delta else COLORS["red"] if delta else COLORS["muted"]
    delta_html  = f'<div class="delta" style="color:{delta_color}">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="m-card {color}">
        <div class="label">{label}</div>
        <div class="value" style="color:{COLORS[color]}">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def badge(text: str, color: str = "blue") -> str:
    """Return an HTML badge span."""
    return f'<span class="badge badge-{color}">{text}</span>'


def section_header(text: str):
    """Render a styled section sub-header."""
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def market_pill(is_open: bool):
    """Render the animated market open/closed pill."""
    cls  = "open" if is_open else "closed"
    text = "MARKET OPEN" if is_open else "MARKET CLOSED"
    st.markdown(f"""
    <div class="market-pill {cls}">
        <div class="market-dot {cls}"></div>{text}
    </div>
    """, unsafe_allow_html=True)


def alert(text: str, kind: str = "info"):
    """Render a styled alert box. kind: info | warn | danger | success"""
    st.markdown(f'<div class="alert-box alert-{kind}">{text}</div>', unsafe_allow_html=True)


def score_color(score: int) -> str:
    """Return color name for a 0-100 score."""
    if score >= 70: return COLORS["green"]
    if score >= 50: return COLORS["gold"]
    return COLORS["red"]


def dte_color(dte: int) -> str:
    """Return color for days-to-expiry urgency."""
    if dte <= 7:  return COLORS["red"]
    if dte <= 14: return COLORS["gold"]
    return COLORS["green"]
