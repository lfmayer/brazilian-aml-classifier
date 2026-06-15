"""
app.py — RiskRadar
Intelligent transaction risk classification for Brazilian financial compliance.
Dark theme — stable, no rendering artifacts.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from db.database import (
    fetch_classifications_df,
    fetch_classification_detail,
    fetch_jurisdiction_hits,
    fetch_summary,
    fetch_typology_counts,
    init_db,
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="RiskRadar · AML Compliance",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# DESIGN TOKENS
# ─────────────────────────────────────────────
RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

RISK_COLORS = {
    "LOW":      ("#1a4731", "#3fb950", "#3fb950"),
    "MEDIUM":   ("#3d2c0a", "#d29922", "#d29922"),
    "HIGH":     ("#3d1c1c", "#f85149", "#f85149"),
    "CRITICAL": ("#5c1a1a", "#ff7b72", "#ff7b72"),
}

CHART_COLORS = {
    "LOW":      "#3fb950",
    "MEDIUM":   "#d29922",
    "HIGH":     "#f85149",
    "CRITICAL": "#ff7b72",
}

ACTION_COLORS = {
    "MONITOR":             ("#1a4731", "#3fb950"),
    "ESCALATE_FOR_REVIEW": ("#3d2c0a", "#d29922"),
    "COMMUNICATE_TO_COAF": ("#5c1a1a", "#ff7b72"),
}

# ─────────────────────────────────────────────
# LABELS
# ─────────────────────────────────────────────
TYPOLOGY_LABELS = {
    "STRUCTURING":         "Structuring / Smurfing",
    "ATYPICAL_FREQUENCY":  "Unusual Transaction Frequency",
    "HIGH_RISK_GEOGRAPHY": "High-Risk Jurisdiction",
    "PEP_INVOLVEMENT":     "Politically Exposed Person (PEP)",
}

TYPOLOGY_DESC = {
    "STRUCTURING":         "Transactions structured below the R$10,000 reporting threshold to avoid mandatory disclosure (Lei 9.613/1998, Art. 11).",
    "ATYPICAL_FREQUENCY":  "Transaction frequency exceeds the expected pattern for this customer profile (Circular Bacen 3.978/2020).",
    "HIGH_RISK_GEOGRAPHY": "Transaction involves a jurisdiction flagged by FATF or the Brazilian Federal Revenue (IN RFB 1.037/2010).",
    "PEP_INVOLVEMENT":     "Sender or receiver holds or held a relevant public office within the last 5 years (Resolução COAF 40/2021).",
}

ACTION_LABELS = {
    "MONITOR":             "Routine Monitoring",
    "ESCALATE_FOR_REVIEW": "Escalate for Compliance Review",
    "COMMUNICATE_TO_COAF": "Report to COAF — Art. 11, Lei 9.613/1998",
}

ACTION_DESC = {
    "MONITOR":             "No immediate action required. Transaction falls within expected parameters for this customer profile.",
    "ESCALATE_FOR_REVIEW": "Forward to senior compliance officer for manual review and sign-off before any action is taken.",
    "COMMUNICATE_TO_COAF": "Mandatory suspicious activity report must be filed with COAF within the legal deadline. Document all evidence.",
}

ACTION_ICONS = {
    "MONITOR":             "✅",
    "ESCALATE_FOR_REVIEW": "⚠️",
    "COMMUNICATE_TO_COAF": "🚨",
}

PROFILE_LABELS = {
    "PF_STANDARD":    "Individual — Standard Profile",
    "PF_HIGH_INCOME": "Individual — High Income Profile",
    "PJ_SME":         "Legal Entity — Small / Medium Business",
    "PJ_LARGE":       "Legal Entity — Large Corporation",
    "UNKNOWN":        "Unknown Profile",
}

TX_TYPE_LABELS = {
    "PIX":             "PIX Transfer",
    "TED":             "TED Bank Transfer",
    "DOC":             "DOC Bank Transfer",
    "WIRE_TRANSFER":   "International Wire Transfer",
    "CASH_DEPOSIT":    "Cash Deposit",
    "CASH_WITHDRAWAL": "Cash Withdrawal",
}

DIRECTION_LABELS = {
    "OUTBOUND": "Outbound — sent",
    "INBOUND":  "Inbound — received",
}

PARTY_TYPE_LABELS = {
    "CPF":  "Individual (CPF)",
    "CNPJ": "Legal Entity (CNPJ)",
}

LIST_LABELS = {
    "FATF_BLACKLIST": "FATF Blacklist",
    "FATF_GREYLIST":  "FATF Grey List",
    "RFB_TAX_HAVEN":  "RFB Tax Haven — IN 1.037/2010",
}

LIST_SEVERITY = {
    "FATF_BLACKLIST": "CRITICAL",
    "FATF_GREYLIST":  "HIGH",
    "RFB_TAX_HAVEN":  "MEDIUM",
}

COUNTRY_NAMES = {
    "BRA": "Brazil",         "USA": "United States",
    "DEU": "Germany",        "GBR": "United Kingdom",
    "FRA": "France",         "CAN": "Canada",
    "AUS": "Australia",      "JPN": "Japan",
    "CHE": "Switzerland",    "CYM": "Cayman Islands",
    "PAN": "Panama",         "BHS": "Bahamas",
    "BMU": "Bermuda",        "VGB": "British Virgin Islands",
    "LIE": "Liechtenstein",  "MCO": "Monaco",
    "AND": "Andorra",        "IRN": "Iran",
    "PRK": "North Korea",    "MMR": "Myanmar",
    "VEN": "Venezuela",      "NGA": "Nigeria",
    "PHL": "Philippines",    "SYR": "Syria",
    "YEM": "Yemen",          "LBN": "Lebanon",
    "KEN": "Kenya",          "BOL": "Bolivia",
    "HKG": "Hong Kong",      "LBR": "Liberia",
    "MAC": "Macau",          "MUS": "Mauritius",
    "SYC": "Seychelles",     "DZA": "Algeria",
    "AGO": "Angola",         "BGR": "Bulgaria",
    "CMR": "Cameroon",       "HRV": "Croatia",
    "HTI": "Haiti",          "KWT": "Kuwait",
    "MOZ": "Mozambique",     "NAM": "Namibia",
    "NPL": "Nepal",          "TZA": "Tanzania",
    "VNM": "Vietnam",        "MNG": "Mongolia",
}

COUNTRY_FLAGS = {
    "BRA": "🇧🇷", "USA": "🇺🇸", "DEU": "🇩🇪", "GBR": "🇬🇧",
    "FRA": "🇫🇷", "CAN": "🇨🇦", "AUS": "🇦🇺", "JPN": "🇯🇵",
    "CHE": "🇨🇭", "CYM": "🇰🇾", "PAN": "🇵🇦", "BHS": "🇧🇸",
    "BMU": "🇧🇲", "VGB": "🇻🇬", "LIE": "🇱🇮", "MCO": "🇲🇨",
    "AND": "🇦🇩", "IRN": "🇮🇷", "PRK": "🇰🇵", "MMR": "🇲🇲",
    "VEN": "🇻🇪", "NGA": "🇳🇬", "PHL": "🇵🇭", "SYR": "🇸🇾",
    "YEM": "🇾🇪", "LBN": "🇱🇧", "KEN": "🇰🇪", "BOL": "🇧🇴",
    "HKG": "🇭🇰", "LBR": "🇱🇷", "MAC": "🇲🇴", "MUS": "🇲🇺",
    "SYC": "🇸🇨", "DZA": "🇩🇿", "AGO": "🇦🇴", "BGR": "🇧🇬",
    "CMR": "🇨🇲", "HRV": "🇭🇷", "HTI": "🇭🇹", "KWT": "🇰🇼",
    "MOZ": "🇲🇿", "NAM": "🇳🇦", "NPL": "🇳🇵", "TZA": "🇹🇿",
    "VNM": "🇻🇳", "MNG": "🇲🇳",
}

CSV_REQUIRED_COLUMNS = [
    "transaction_id", "transaction_type", "direction", "amount_brl",
    "sender_jurisdiction", "receiver_jurisdiction", "sender_is_pep",
    "receiver_is_pep", "customer_profile",
]

def country_label(code: str) -> str:
    name = COUNTRY_NAMES.get(code, code)
    flag = COUNTRY_FLAGS.get(code, "")
    return f"{flag} {name}" if flag else name

# ─────────────────────────────────────────────
# CSS — dark theme, no artifacts
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stMain"], [data-testid="block-container"] {
    background-color: #0d1117 !important;
}
[data-testid="stSidebar"] {
    background-color: #0d1b2e !important;
    border-right: 1px solid #1e3a5f !important;
}
h1, h2, h3, h4, h5 {
    font-family: 'Inter', sans-serif !important;
    color: #f0f6fc !important;
    letter-spacing: -0.02em !important;
}
p, span, div, label {
    font-family: 'Inter', sans-serif !important;
}
[data-testid="metric-container"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
}
[data-testid="stMetricValue"] {
    color: #58a6ff !important;
    font-weight: 800 !important;
    font-size: 2rem !important;
}
[data-testid="stMetricLabel"] {
    color: #8b949e !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: .06em !important;
}
[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}
hr { border-color: #21262d !important; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #21262d; border-radius: 3px; }

.rr-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.rr-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: #8b949e;
    margin-bottom: 6px;
    font-family: 'Inter', sans-serif;
}
.rr-party {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.rr-arrow {
    text-align: center;
    font-size: 26px;
    color: #58a6ff;
    padding-top: 20px;
}
.rr-amount-label {
    font-size: 11px;
    color: #8b949e;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-amount-value {
    font-size: 18px;
    font-weight: 800;
    color: #f0f6fc;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-field {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 0;
    border-bottom: 1px solid #21262d;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
}
.rr-field:last-child { border-bottom: none; }
.rr-field-k { color: #8b949e; font-weight: 500; }
.rr-field-v { color: #c9d1d9; font-weight: 600; text-align: right; }
.rr-mono { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #8b949e; }
.rr-signal {
    background: #2d1515;
    border-left: 3px solid #f85149;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: #c9d1d9;
    font-family: 'Inter', sans-serif;
}
.rr-narrative {
    background: #0d1117;
    border-left: 4px solid #58a6ff;
    padding: 16px 20px;
    border-radius: 0 8px 8px 0;
    font-size: 13px;
    line-height: 1.8;
    color: #c9d1d9;
    font-family: 'Inter', sans-serif;
}
.rr-lgpd {
    background: #161b22;
    border: 1px dashed #30363d;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 10px;
    color: #6e7681;
    margin-top: 8px;
    font-family: 'Inter', sans-serif;
    line-height: 1.5;
}
.rr-page-title {
    font-size: 24px;
    font-weight: 800;
    color: #f0f6fc;
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.03em;
    margin-bottom: 4px;
}
.rr-page-sub {
    font-size: 13px;
    color: #8b949e;
    font-family: 'Inter', sans-serif;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def risk_badge(level: str) -> str:
    bg, border, text = RISK_COLORS.get(level, ("#21262d", "#30363d", "#8b949e"))
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:20px;'
        f'font-size:11px;font-weight:700;letter-spacing:.06em;font-family:Inter,sans-serif;'
        f'background:{bg};color:{text};border:1px solid {border}">{level}</span>'
    )

def score_bar(score: int, compact: bool = False) -> str:
    level = "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    color = CHART_COLORS[level]
    label = {"LOW": "Low Risk", "MEDIUM": "Medium Risk", "HIGH": "High Risk", "CRITICAL": "Critical Risk"}[level]
    h = "6px" if compact else "8px"
    return (
        f'<div style="margin:{"4px" if compact else "10px"} 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:{"10px" if compact else "12px"};'
        f'color:#8b949e;margin-bottom:4px;font-family:Inter,sans-serif">'
        f'<span>Risk Score</span>'
        f'<span style="color:{color};font-weight:700">{score}/100 — {label}</span></div>'
        f'<div style="background:#21262d;border-radius:4px;height:{h}">'
        f'<div style="background:{color};height:{h};border-radius:4px;width:{score}%"></div>'
        f'</div></div>'
    )

def fmt_brl(value) -> str:
    if value is None:
        return "—"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def party_box(party_type: str, jurisdiction: str, is_pep: bool, label: str) -> str:
    pep_html = (
        '<div style="margin-top:8px">'
        '<span style="background:#5c1a1a;color:#ff7b72;border:1px solid #f85149;'
        'padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;'
        'font-family:Inter,sans-serif">PEP</span></div>'
    ) if is_pep else ""
    return (
        f'<div class="rr-party">'
        f'<div class="rr-label">{label}</div>'
        f'<div style="font-size:14px;font-weight:700;color:#f0f6fc;font-family:Inter,sans-serif;margin-top:2px">'
        f'{PARTY_TYPE_LABELS.get(party_type, party_type)}</div>'
        f'<div style="font-size:13px;color:#58a6ff;margin-top:4px;font-family:Inter,sans-serif;font-weight:500">'
        f'{country_label(jurisdiction)}</div>'
        f'<div class="rr-lgpd">Identity protected — LGPD Art. 5, Lei 13.709/2018</div>'
        f'{pep_html}</div>'
    )

def action_card(action: str) -> str:
    bg, border = ACTION_COLORS.get(action, ("#21262d", "#30363d"))
    icon  = ACTION_ICONS.get(action, "")
    label = ACTION_LABELS.get(action, action)
    desc  = ACTION_DESC.get(action, "")
    return (
        f'<div style="background:{bg};border:1.5px solid {border};border-radius:10px;'
        f'padding:16px 20px;margin:10px 0">'
        f'<div style="font-size:15px;font-weight:700;color:{border};font-family:Inter,sans-serif">'
        f'{icon} {label}</div>'
        f'<div style="font-size:12px;color:#c9d1d9;margin-top:6px;line-height:1.7;'
        f'font-family:Inter,sans-serif">{desc}</div>'
        f'</div>'
    )

def plotly_dark(fig, height: int = 280):
    fig.update_layout(
        paper_bgcolor="#161b22",
        plot_bgcolor="#161b22",
        font_color="#c9d1d9",
        font_family="Inter, sans-serif",
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
    )
    fig.update_xaxes(gridcolor="#21262d", zerolinecolor="#30363d", tickfont=dict(size=11, color="#8b949e"))
    fig.update_yaxes(gridcolor="#21262d", zerolinecolor="#30363d", tickfont=dict(size=11, color="#8b949e"))
    return fig

def section_header(title: str, sub: str = ""):
    st.markdown(
        f'<div class="rr-page-title">{title}</div>'
        + (f'<div class="rr-page-sub">{sub}</div>' if sub else ""),
        unsafe_allow_html=True,
    )

def card_title(text: str):
    st.markdown(
        f'<div style="font-size:13px;font-weight:700;color:#f0f6fc;margin-bottom:12px;'
        f'font-family:Inter,sans-serif">{text}</div>',
        unsafe_allow_html=True,
    )

@st.cache_data(ttl=30)
def load_data():
    init_db()
    rows = fetch_classifications_df()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["transaction_timestamp"] = pd.to_datetime(df["transaction_timestamp"], utc=True)
    df["risk_level"] = pd.Categorical(df["risk_level"], categories=RISK_ORDER, ordered=True)
    return df


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


# ─────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center;margin-bottom:32px">
          <div style="font-size:32px;font-weight:800;color:#f0f6fc;
            font-family:Inter,sans-serif;letter-spacing:-0.03em">RiskRadar</div>
          <div style="font-size:12px;color:#8b949e;font-family:Inter,sans-serif;margin-top:4px">
            AML Compliance Intelligence</div>
          <div style="font-size:14px;color:#8b949e;font-family:Inter,sans-serif;
            margin-top:12px;line-height:1.6">
            Intelligent transaction risk classification<br>
            for Brazilian financial compliance
          </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="rr-card">', unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:17px;font-weight:700;color:#f0f6fc;'
                'font-family:Inter,sans-serif;margin-bottom:20px">Sign in</div>',
                unsafe_allow_html=True,
            )
            username = st.text_input("Email address", placeholder="compliance@yourfirm.com", label_visibility="visible")
            password = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="visible")

            if st.button("Sign In", use_container_width=True, type="primary"):
                if username and password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Please enter your credentials.")

            st.markdown(
                '<div style="margin-top:16px;padding:10px 14px;background:#0d1117;'
                'border-radius:8px;font-size:11px;color:#8b949e;font-family:Inter,sans-serif;'
                'line-height:1.6;border:1px solid #21262d">'
                'Demo access: enter any email and password to explore the platform.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="text-align:center;margin-top:20px;font-size:10px;color:#484f58;'
            'font-family:Inter,sans-serif;line-height:1.8">'
            'Synthetic data only · Academic and portfolio project<br>'
            'Not a legal or compliance system</div>',
            unsafe_allow_html=True,
        )
    st.stop()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:4px 0 20px 0">'
        '<div style="font-size:19px;font-weight:800;color:#f0f6fc;'
        'font-family:Inter,sans-serif;letter-spacing:-0.02em">RiskRadar</div>'
        '<div style="font-size:11px;color:#8b949e;font-family:Inter,sans-serif;margin-top:2px">'
        'AML Compliance Intelligence</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Transaction Explorer",
            "Jurisdiction Map",
            "Transaction Detail",
            "Import Transactions",
            "About RiskRadar",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    summary = fetch_summary()
    st.markdown(
        f'<div style="font-family:Inter,sans-serif">'
        f'<div style="font-size:10px;font-weight:700;color:#484f58;text-transform:uppercase;'
        f'letter-spacing:.1em;margin-bottom:8px">Database</div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid #21262d;font-size:12px">'
        f'<span style="color:#8b949e">Transactions</span>'
        f'<span style="color:#f0f6fc;font-weight:600">{summary["total_transactions"]}</span></div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid #21262d;font-size:12px">'
        f'<span style="color:#8b949e">Classified</span>'
        f'<span style="color:#3fb950;font-weight:600">{summary["classified"]}</span></div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:12px">'
        f'<span style="color:#8b949e">Pending</span>'
        f'<span style="color:#d29922;font-weight:600">{summary["pending"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    username_display = st.session_state.get("username", "analyst@firm.com")
    st.markdown(
        f'<div style="font-size:11px;color:#8b949e;font-family:Inter,sans-serif;'
        f'line-height:1.7;margin-bottom:8px">'
        f'Signed in as<br>'
        f'<span style="color:#c9d1d9;font-weight:600">{username_display}</span></div>',
        unsafe_allow_html=True,
    )
    if st.button("Sign out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

    st.divider()
    st.markdown(
        '<div style="font-size:10px;color:#484f58;font-family:Inter,sans-serif;line-height:1.7">'
        'Synthetic data only.<br>Not a legal or compliance system.<br>'
        'Human review required before any real-world action.</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
df = load_data()
no_data = df.empty


# ═════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═════════════════════════════════════════════
if page == "Overview":
    section_header(
        "Transaction Risk Overview",
        "Classification dashboard — Brazilian AML regulatory framework",
    )

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    by_risk = df["risk_level"].value_counts()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Classified", len(df))
    k2.metric("Low Risk",    int(by_risk.get("LOW",      0)))
    k3.metric("Medium Risk", int(by_risk.get("MEDIUM",   0)))
    k4.metric("High Risk",   int(by_risk.get("HIGH",     0)))
    k5.metric("Critical",    int(by_risk.get("CRITICAL", 0)))

    criticals = df[df["risk_level"] == "CRITICAL"]
    if not criticals.empty:
        st.markdown(
            f'<div style="background:#5c1a1a;border:1.5px solid #ff7b72;border-radius:10px;'
            f'padding:14px 20px;margin:16px 0;display:flex;align-items:center;gap:14px">'
            f'<div><div style="font-weight:700;color:#ff7b72;font-family:Inter,sans-serif;font-size:14px">'
            f'🚨 {len(criticals)} Critical Alert(s) Require Immediate Action</div>'
            f'<div style="font-size:12px;color:#f85149;margin-top:2px;font-family:Inter,sans-serif">'
            f'Mandatory report to COAF — Art. 11, Lei 9.613/1998</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Risk Distribution")
        counts = df["risk_level"].value_counts().reindex(RISK_ORDER).fillna(0)
        fig = go.Figure(go.Pie(
            labels=counts.index.tolist(),
            values=counts.values.tolist(),
            hole=0.6,
            marker_colors=[CHART_COLORS[r] for r in counts.index],
            textinfo="label+percent",
            textfont=dict(size=11, family="Inter"),
        ))
        plotly_dark(fig, 260)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Triggered Risk Indicators")
        typo_data = fetch_typology_counts()
        if typo_data:
            tdf = pd.DataFrame(typo_data)
            tdf["label"] = tdf["typology"].map(lambda x: TYPOLOGY_LABELS.get(x, x))
            fig2 = px.bar(
                tdf, x="n", y="label", orientation="h",
                color_discrete_sequence=["#58a6ff"],
            )
            plotly_dark(fig2, 260)
            fig2.update_layout(
                xaxis_title="", yaxis_title="",
                yaxis=dict(categoryorder="total ascending"),
            )
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Risk by category bar chart (replaces histogram)
    st.markdown('<div class="rr-card">', unsafe_allow_html=True)
    card_title("Transactions by Risk Level")
    risk_counts = df["risk_level"].value_counts().reindex(RISK_ORDER).fillna(0).reset_index()
    risk_counts.columns = ["Risk Level", "Count"]
    fig3 = px.bar(
        risk_counts,
        x="Risk Level", y="Count",
        color="Risk Level",
        color_discrete_map=CHART_COLORS,
        category_orders={"Risk Level": RISK_ORDER},
        text="Count",
    )
    plotly_dark(fig3, 200)
    fig3.update_layout(
        xaxis_title="", yaxis_title="Transactions",
        showlegend=False,
    )
    fig3.update_traces(textposition="outside", textfont=dict(color="#c9d1d9", size=12))
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Latest alerts
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:16px 0 10px;'
        'font-family:Inter,sans-serif">Latest HIGH / CRITICAL Alerts</div>',
        unsafe_allow_html=True,
    )
    alerts = df[df["risk_level"].isin(["HIGH", "CRITICAL"])].head(6)
    if alerts.empty:
        st.caption("No high-risk transactions found.")
    else:
        for _, row in alerts.iterrows():
            tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
            with st.expander(
                f"{row['transaction_id']}  —  {row['risk_level']}  —  "
                f"{fmt_brl(row['amount_brl'])}  —  {tx_label}"
            ):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown(risk_badge(str(row["risk_level"])), unsafe_allow_html=True)
                    st.markdown(score_bar(row["risk_score"], compact=True), unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-size:11px;color:#8b949e;margin-top:8px;'
                        f'font-family:Inter,sans-serif;line-height:1.7">'
                        f'{DIRECTION_LABELS.get(row["direction"],"")}<br>'
                        f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        f'<div class="rr-narrative">{row["narrative"]}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 2 — TRANSACTION EXPLORER
# ═════════════════════════════════════════════
elif page == "Transaction Explorer":
    section_header("Transaction Explorer", "Search and filter all classified transactions")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    f1, f2, f3 = st.columns([1, 1, 2])
    risk_filter   = f1.multiselect("Risk Level", RISK_ORDER, default=RISK_ORDER)
    action_filter = f2.multiselect(
        "Action",
        ["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
        default=["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
    )
    search = f3.text_input("Search by ID or keyword", placeholder="TXN-00018 or keyword")

    filtered = df[
        df["risk_level"].isin(risk_filter) &
        df["recommended_action"].isin(action_filter)
    ]
    if search:
        mask = (
            filtered["transaction_id"].str.contains(search, case=False, na=False) |
            filtered["narrative"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"{len(filtered)} transaction(s) found")

    for _, row in filtered.iterrows():
        tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
        with st.expander(
            f"{row['transaction_id']}  —  {row['risk_level']}  —  "
            f"{fmt_brl(row['amount_brl'])}  —  {tx_label}"
        ):
            cs, ca, cr = st.columns([5, 2, 5])
            with cs:
                st.markdown(
                    party_box("CPF", row["sender_jurisdiction"],
                              bool(row["sender_is_pep"]), "Sender"),
                    unsafe_allow_html=True,
                )
            with ca:
                st.markdown(
                    f'<div class="rr-arrow">→</div>'
                    f'<div class="rr-amount-label" style="margin-top:4px">{tx_label}</div>'
                    f'<div class="rr-amount-value">{fmt_brl(row["amount_brl"])}</div>'
                    f'<div class="rr-amount-label">{DIRECTION_LABELS.get(row["direction"],"")}</div>',
                    unsafe_allow_html=True,
                )
            with cr:
                st.markdown(
                    party_box("CPF", row["receiver_jurisdiction"],
                              bool(row["receiver_is_pep"]), "Receiver"),
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(risk_badge(str(row["risk_level"])), unsafe_allow_html=True)
                st.markdown(score_bar(row["risk_score"], compact=True), unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:11px;color:#8b949e;margin-top:6px;'
                    f'font-family:Inter,sans-serif">'
                    f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="rr-narrative">'
                    f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.08em;color:#8b949e;margin-bottom:6px">Compliance Narrative</div>'
                    f'{row["narrative"]}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 3 — JURISDICTION MAP
# ═════════════════════════════════════════════
elif page == "Jurisdiction Map":
    section_header(
        "Jurisdiction Risk Map",
        "Countries flagged in classified transactions, by regulatory list membership",
    )

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    hits = fetch_jurisdiction_hits()
    if not hits:
        st.caption("No jurisdiction flags found.")
        st.stop()

    jdf = pd.DataFrame(hits)
    fig = px.choropleth(
        jdf,
        locations="jurisdiction_code",
        locationmode="ISO-3",
        color="risk_contribution",
        color_discrete_map={
            "HIGH":   "#f85149",
            "MEDIUM": "#d29922",
            "LOW":    "#3fb950",
        },
        hover_name="jurisdiction_code",
        hover_data={"n": True, "risk_contribution": True},
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True, coastlinecolor="#30363d",
        showland=True, landcolor="#161b22",
        showocean=True, oceancolor="#0d1117",
        projection_type="natural earth",
    )
    fig.update_layout(
        paper_bgcolor="#161b22", plot_bgcolor="#161b22",
        font_family="Inter, sans-serif", font_color="#c9d1d9",
        height=400, margin=dict(l=0, r=0, t=8, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:16px 0 10px;'
        'font-family:Inter,sans-serif">Flagged Jurisdictions — Detail</div>',
        unsafe_allow_html=True,
    )
    for _, row in jdf.iterrows():
        bg, border, text = RISK_COLORS.get(row["risk_contribution"], ("#21262d", "#30363d", "#8b949e"))
        st.markdown(
            f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:15px;font-weight:700;color:#f0f6fc;font-family:Inter,sans-serif">'
            f'{country_label(row["jurisdiction_code"])}</div>'
            f'<div style="font-size:12px;color:#8b949e;margin-top:2px;font-family:Inter,sans-serif">'
            f'{row["n"]} transaction(s) flagged</div>'
            f'</div>'
            f'<span style="background:{bg};color:{text};border:1px solid {border};'
            f'padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;'
            f'font-family:Inter,sans-serif">{row["risk_contribution"]} RISK</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 4 — TRANSACTION DETAIL
# ═════════════════════════════════════════════
elif page == "Transaction Detail":
    section_header("Transaction Detail", "Full compliance breakdown for a single transaction")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    selected = st.selectbox("Select a transaction", df["transaction_id"].tolist())
    detail = fetch_classification_detail(selected)
    if not detail:
        st.error("Transaction not found.")
        st.stop()

    tx    = detail["transaction"]
    cls   = detail["classification"]
    typos = detail["typologies"]
    juris = detail["jurisdictions"]
    dq    = detail["dq_flags"]

    # Executive Summary
    bg, border, text = RISK_COLORS.get(cls["risk_level"], ("#21262d", "#30363d", "#8b949e"))
    st.markdown(
        f'<div class="rr-card" style="border-left:5px solid {border}">'
        f'<div class="rr-label">Executive Summary</div>'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:6px">'
        f'<span style="font-size:26px;font-weight:800;color:{text};font-family:Inter,sans-serif;'
        f'letter-spacing:-0.02em">{cls["risk_level"]} RISK</span>'
        f'<span style="font-size:19px;font-weight:700;color:#f0f6fc;font-family:Inter,sans-serif">'
        f'Score: {cls["risk_score"]}/100</span>'
        f'<span class="rr-mono">{selected}</span>'
        f'</div>'
        f'{score_bar(cls["risk_score"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Transaction Flow
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 10px;'
        'font-family:Inter,sans-serif">Transaction Flow</div>',
        unsafe_allow_html=True,
    )
    col_s, col_a, col_r = st.columns([5, 2, 5])
    with col_s:
        st.markdown(
            party_box(tx["sender_type"], tx["sender_jurisdiction"],
                      bool(tx["sender_is_pep"]), "Sender"),
            unsafe_allow_html=True,
        )
    with col_a:
        tx_label = TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"])
        st.markdown(
            f'<div class="rr-arrow">→</div>'
            f'<div class="rr-amount-label" style="margin-top:4px">{tx_label}</div>'
            f'<div class="rr-amount-value">{fmt_brl(tx["amount_brl"])}</div>'
            f'<div class="rr-amount-label">{DIRECTION_LABELS.get(tx["direction"],"")}</div>',
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            party_box(tx["receiver_type"], tx["receiver_jurisdiction"],
                      bool(tx["receiver_is_pep"]), "Receiver"),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Transaction Details")
        fields = [
            ("Type",             TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"])),
            ("Direction",        DIRECTION_LABELS.get(tx["direction"], "")),
            ("Amount",           fmt_brl(tx["amount_brl"])),
            ("Customer Profile", PROFILE_LABELS.get(tx["customer_profile"], tx["customer_profile"])),
            ("Date / Time",      str(tx["transaction_timestamp"])[:19].replace("T", " ")),
            ("Purpose",          tx["purpose_description"] or "Not provided"),
        ]
        for k, v in fields:
            st.markdown(
                f'<div class="rr-field">'
                f'<span class="rr-field-k">{k}</span>'
                f'<span class="rr-field-v">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Transaction Frequency")
        freq_threshold = {"PF_STANDARD": 5, "PF_HIGH_INCOME": 15, "PJ_SME": 25, "PJ_LARGE": 60}
        threshold = freq_threshold.get(tx["customer_profile"], 5)
        for k, v, warn in [
            ("Transactions — last 24h", str(tx["transactions_last_24h"]),   tx["transactions_last_24h"] > threshold),
            ("Transactions — last 72h", str(tx["transactions_last_72h"]),   tx["transactions_last_72h"] > threshold * 2),
            ("Total amount — last 72h", fmt_brl(tx["total_amount_last_72h_brl"]), tx["total_amount_last_72h_brl"] > 10000),
            ("Average monthly amount",  fmt_brl(tx["avg_monthly_amount_brl"]), False),
        ]:
            warn_tag = ' <span style="color:#f85149;font-weight:600;font-size:11px">Above threshold</span>' if warn else ""
            color = "#f85149" if warn else "#c9d1d9"
            st.markdown(
                f'<div class="rr-field">'
                f'<span class="rr-field-k">{k}</span>'
                f'<span class="rr-field-v" style="color:{color}">{v}{warn_tag}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="font-size:10px;color:#484f58;margin-top:8px;font-family:Inter,sans-serif">'
            f'Expected daily limit: {threshold} tx/day — Circular Bacen 3.978/2020</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Risk Indicators
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 10px;'
        'font-family:Inter,sans-serif">Risk Indicators</div>',
        unsafe_allow_html=True,
    )
    for t in typos:
        signals = json.loads(t["signals_identified"]) if isinstance(t["signals_identified"], str) else t["signals_identified"]
        is_triggered = t["status"] == "TRIGGERED"
        label = TYPOLOGY_LABELS.get(t["typology"], t["typology"])
        status_text = "TRIGGERED" if is_triggered else t["status"].replace("_", " ")
        with st.expander(f"{label} — {status_text}", expanded=is_triggered):
            st.markdown(
                f'<div style="font-size:12px;color:#8b949e;margin-bottom:10px;'
                f'font-family:Inter,sans-serif;line-height:1.6">'
                f'{TYPOLOGY_DESC.get(t["typology"],"")}</div>',
                unsafe_allow_html=True,
            )
            if signals:
                for s in signals:
                    st.markdown(f'<div class="rr-signal">{s}</div>', unsafe_allow_html=True)
            else:
                st.caption("No signals identified for this indicator.")

    # Jurisdiction Flags
    if juris:
        st.markdown(
            '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 10px;'
            'font-family:Inter,sans-serif">Jurisdiction Flags</div>',
            unsafe_allow_html=True,
        )
        for j in juris:
            lists = json.loads(j["list_membership"]) if isinstance(j["list_membership"], str) else j["list_membership"]
            if not lists:
                continue
            bg, border, text = RISK_COLORS.get(j["risk_contribution"], ("#21262d", "#30363d", "#8b949e"))
            list_tags = "".join([
                f'<span style="background:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#21262d","#30363d","#8b949e"))[0]};'
                f'color:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#21262d","#30363d","#8b949e"))[2]};'
                f'border:1px solid {RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#21262d","#30363d","#8b949e"))[1]};'
                f'padding:2px 10px;border-radius:20px;font-size:10px;font-weight:600;'
                f'margin-right:6px;font-family:Inter,sans-serif">{LIST_LABELS.get(l,l)}</span>'
                for l in lists
            ])
            st.markdown(
                f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px;border-left:4px solid {border}">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'<div>'
                f'<div style="font-size:15px;font-weight:700;color:#f0f6fc;font-family:Inter,sans-serif">'
                f'{country_label(j["jurisdiction_code"])}</div>'
                f'<div style="margin-top:6px">{list_tags}</div>'
                f'</div>'
                f'<span style="background:{bg};color:{text};border:1px solid {border};'
                f'padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;'
                f'font-family:Inter,sans-serif;white-space:nowrap">{j["risk_contribution"]} RISK</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # Recommended Action
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 6px;'
        'font-family:Inter,sans-serif">Recommended Action</div>',
        unsafe_allow_html=True,
    )
    st.markdown(action_card(cls["recommended_action"]), unsafe_allow_html=True)

    # Narrative
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 6px;'
        'font-family:Inter,sans-serif">Compliance Narrative</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="rr-narrative">{cls["narrative"]}</div>', unsafe_allow_html=True)

    # Data Quality
    if dq:
        st.markdown(
            '<div style="font-size:14px;font-weight:700;color:#f0f6fc;margin:20px 0 6px;'
            'font-family:Inter,sans-serif">Data Quality Flags</div>',
            unsafe_allow_html=True,
        )
        st.caption("The following fields were missing and may affect classification accuracy.")
        for f in dq:
            st.markdown(
                f'<span style="background:#3d2c0a;color:#d29922;border:1px solid #d29922;'
                f'padding:3px 10px;border-radius:20px;font-size:11px;margin:2px;'
                f'display:inline-block;font-family:Inter,sans-serif">{f}</span>',
                unsafe_allow_html=True,
            )

    with st.expander("Raw JSON Output — Technical"):
        st.code(cls["raw_response_json"], language="json")

    st.markdown(
        f'<div style="font-size:10px;color:#484f58;margin-top:20px;padding-top:12px;'
        f'border-top:1px solid #21262d;font-family:Inter,sans-serif;line-height:1.8">'
        f'Classified: {str(cls["classified_at"])[:19]} · Prompt: {cls["prompt_version"]}<br>'
        f'Academic and portfolio project only. Human review required before any real-world action.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════
# PAGE 5 — IMPORT TRANSACTIONS
# ═════════════════════════════════════════════
elif page == "Import Transactions":
    section_header("Import Transactions", "Upload a CSV file to preview transactions before AI classification")

    st.markdown(
        '<div style="background:#0d1b2e;border:1px solid #1e3a5f;border-radius:10px;'
        'padding:14px 18px;margin-bottom:20px">'
        '<div style="font-weight:700;color:#58a6ff;font-family:Inter,sans-serif;font-size:13px">'
        'How this works</div>'
        '<div style="font-size:12px;color:#c9d1d9;margin-top:6px;font-family:Inter,sans-serif;line-height:1.7">'
        'Upload a CSV with your transactions. RiskRadar will validate the format and show a preview. '
        'In a production environment, the AI engine would classify each transaction automatically. '
        'Connect your API key to enable real-time classification.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Required CSV columns"):
        cols_html = "".join([
            f'<span style="background:#21262d;padding:3px 10px;border-radius:6px;'
            f'font-family:IBM Plex Mono,monospace;font-size:11px;margin:2px;'
            f'display:inline-block;color:#c9d1d9">{col}</span> '
            for col in CSV_REQUIRED_COLUMNS
        ])
        st.markdown(
            f'<div style="font-size:12px;color:#8b949e;font-family:Inter,sans-serif;'
            f'line-height:2">{cols_html}</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download CSV template",
            data=",".join(CSV_REQUIRED_COLUMNS) + "\n" +
                 "TXN-CUSTOM-01,PIX,OUTBOUND,5000.00,BRA,BRA,False,False,PF_STANDARD\n",
            file_name="riskradar_template.csv",
            mime="text/csv",
        )

    uploaded = st.file_uploader(
        "Upload your transactions CSV",
        type=["csv"],
        help="Max file size: 200MB",
    )

    if uploaded:
        try:
            upload_df = pd.read_csv(uploaded)
            missing = [c for c in CSV_REQUIRED_COLUMNS if c not in upload_df.columns]
            if missing:
                st.error(f"Missing required columns: {', '.join(missing)}")
            else:
                st.success(f"{len(upload_df)} transactions detected — format valid")

                col1, col2, col3 = st.columns(3)
                col1.metric("Transactions", len(upload_df))
                col2.metric("PEP Flagged",
                            int(upload_df["sender_is_pep"].astype(str).str.lower().eq("true").sum() +
                                upload_df["receiver_is_pep"].astype(str).str.lower().eq("true").sum()))
                col3.metric("Avg Amount",
                            fmt_brl(upload_df["amount_brl"].astype(float).mean()))

                st.markdown(
                    '<div style="font-size:13px;font-weight:700;color:#f0f6fc;margin:16px 0 8px;'
                    'font-family:Inter,sans-serif">Preview — first 10 rows</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(upload_df.head(10), use_container_width=True, hide_index=True)

                st.markdown(
                    '<div style="background:#3d2c0a;border:1.5px solid #d29922;border-radius:10px;'
                    'padding:16px 20px;margin-top:16px">'
                    '<div style="font-weight:700;color:#d29922;font-family:Inter,sans-serif;font-size:14px">'
                    'Ready for AI Classification</div>'
                    '<div style="font-size:12px;color:#c9d1d9;margin-top:8px;font-family:Inter,sans-serif;line-height:1.7">'
                    'In production, the AI engine would classify each transaction against COAF/Bacen typologies. '
                    'To enable: add your ANTHROPIC_API_KEY to Streamlit secrets and run batch_runner.py.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )
                st.button("Classify with AI Engine — requires API key", disabled=True, use_container_width=True)

        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        st.markdown(
            '<div style="text-align:center;padding:40px;color:#484f58;font-family:Inter,sans-serif">'
            '<div style="font-size:13px">Drag and drop your CSV file here, or click to browse</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 6 — ABOUT
# ═════════════════════════════════════════════
elif page == "About RiskRadar":
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown("""
        <div style="margin-bottom:28px">
          <div style="font-size:30px;font-weight:800;color:#f0f6fc;font-family:Inter,sans-serif;
            letter-spacing:-0.03em;margin-bottom:6px">RiskRadar</div>
          <div style="font-size:15px;color:#8b949e;font-family:Inter,sans-serif;line-height:1.6">
            Intelligent transaction risk classification for Brazilian financial compliance
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("What is RiskRadar?")
        st.markdown(
            '<div style="font-size:13px;color:#c9d1d9;font-family:Inter,sans-serif;line-height:1.9">'
            'RiskRadar is an AI-powered compliance tool that classifies financial transactions '
            'according to Brazilian AML (Anti-Money Laundering) regulation. It uses Claude (Anthropic) '
            'as its reasoning engine to evaluate transactions against known suspicious activity typologies '
            'defined by COAF and Bacen.'
            '<br><br>'
            'The system simulates a workflow used by compliance analysts in Brazilian financial institutions '
            '— receiving a batch of transactions, applying regulatory rules, and generating structured risk '
            'reports with natural language justifications that a licensed compliance officer can evaluate and act upon.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Regulatory Framework")
        regs = [
            ("Lei 9.613/1998",            "Brazilian AML law — mandatory reporting threshold R$10,000"),
            ("Circular Bacen 3.978/2020", "KYC and transaction monitoring obligations"),
            ("Resolução COAF 36/2021",    "AML/CFT internal policy requirements"),
            ("Resolução COAF 40/2021",    "PEP definition and enhanced due diligence"),
            ("IN RFB 1.037/2010",         "Brazilian tax haven jurisdiction list"),
            ("FATF Plenary Feb/2026",     "Blacklist (Iran, North Korea, Myanmar) and Grey List"),
        ]
        for reg, desc in regs:
            st.markdown(
                f'<div class="rr-field">'
                f'<span class="rr-mono" style="font-size:12px;color:#58a6ff">{reg}</span>'
                f'<span style="color:#8b949e;font-size:12px;text-align:right;max-width:55%">{desc}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Risk Typologies Covered")
        for t, d in [
            ("Structuring / Smurfing",          "Transactions below the R$10k threshold to avoid reporting"),
            ("Unusual Transaction Frequency",   "Activity exceeding expected patterns for the customer profile"),
            ("High-Risk Jurisdiction",          "Transactions involving FATF-listed or RFB tax haven countries"),
            ("Politically Exposed Person (PEP)", "Involvement of current or former public office holders"),
        ]:
            st.markdown(
                f'<div style="padding:10px 0;border-bottom:1px solid #21262d;font-family:Inter,sans-serif">'
                f'<div style="font-size:13px;font-weight:600;color:#f0f6fc">{t}</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:2px">{d}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="background:#5c1a1a;border:1px solid #f85149;border-radius:10px;'
            'padding:14px 18px;margin-top:8px">'
            '<div style="font-weight:700;color:#ff7b72;font-family:Inter,sans-serif;font-size:12px">'
            'Disclaimer</div>'
            '<div style="font-size:11px;color:#c9d1d9;margin-top:6px;font-family:Inter,sans-serif;line-height:1.7">'
            'Academic and portfolio project. All data is entirely synthetic. '
            'RiskRadar does not constitute a legal or official compliance system. '
            'Human review by a licensed compliance officer is required before any real-world action.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    with col_side:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Tech Stack")
        for k, v in [
            ("AI Engine",  "Claude — Anthropic"),
            ("Model",      "claude-sonnet-4-6"),
            ("Language",   "Python 3.11"),
            ("Interface",  "Streamlit"),
            ("Database",   "SQLite"),
            ("Data",       "Faker (pt_BR)"),
            ("Charts",     "Plotly"),
            ("Typography", "Inter · IBM Plex Mono"),
        ]:
            st.markdown(
                f'<div class="rr-field">'
                f'<span class="rr-field-k">{k}</span>'
                f'<span style="color:#8b949e;font-size:12px">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Author")
        st.markdown(
            '<div style="font-family:Inter,sans-serif">'
            '<div style="font-size:15px;font-weight:700;color:#f0f6fc;margin-bottom:4px">'
            'Luís Filipe Mayer</div>'
            '<div style="font-size:11px;color:#8b949e;line-height:1.7;margin-bottom:10px">'
            'Senior Banking Professional<br>'
            'Data Analytics · Analytics Translator<br>'
            'FIAP PosTech — Business Analytics</div>'
            '<div style="font-size:11px;color:#c9d1d9;line-height:1.8">'
            '15+ years in Brazilian financial services (Bradesco — Prime segment). '
            'This project bridges domain expertise in banking compliance with AI engineering.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Links")
        st.markdown(
            '<div style="font-family:Inter,sans-serif;font-size:13px">'
            '<div style="padding:8px 0;border-bottom:1px solid #21262d">'
            '<a href="https://github.com/lfmayer/brazilian-aml-classifier" '
            'style="color:#58a6ff;text-decoration:none;font-weight:500" target="_blank">'
            'GitHub Repository</a></div>'
            '<div style="padding:8px 0">'
            '<a href="https://www.linkedin.com/in/luisfilipemayer" '
            'style="color:#58a6ff;text-decoration:none;font-weight:500" target="_blank">'
            'LinkedIn</a></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
