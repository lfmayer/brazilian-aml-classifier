"""
app.py — RiskRadar
Intelligent transaction risk classification for Brazilian financial compliance.
"""

import json
import sys
import io
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
    "LOW":      ("#DCFCE7", "#16A34A", "#14532D"),
    "MEDIUM":   ("#DBEAFE", "#3B82F6", "#1E3A8A"),
    "HIGH":     ("#FEF3C7", "#F59E0B", "#78350F"),
    "CRITICAL": ("#FEE2E2", "#EF4444", "#7F1D1D"),
}

ACTION_COLORS = {
    "MONITOR":             ("#DCFCE7", "#16A34A", "#14532D"),
    "ESCALATE_FOR_REVIEW": ("#FEF3C7", "#F59E0B", "#78350F"),
    "COMMUNICATE_TO_COAF": ("#FEE2E2", "#EF4444", "#7F1D1D"),
}

# ─────────────────────────────────────────────
# LABELS
# ─────────────────────────────────────────────
TYPOLOGY_LABELS = {
    "STRUCTURING":         "Structuring (Smurfing)",
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

DIRECTION_ICONS = {"OUTBOUND": "↑", "INBOUND": "↓"}

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
    "BRA": "Brazil 🇧🇷",         "USA": "United States 🇺🇸",
    "DEU": "Germany 🇩🇪",        "GBR": "United Kingdom 🇬🇧",
    "FRA": "France 🇫🇷",         "CAN": "Canada 🇨🇦",
    "AUS": "Australia 🇦🇺",      "JPN": "Japan 🇯🇵",
    "CHE": "Switzerland 🇨🇭",    "CYM": "Cayman Islands 🇰🇾",
    "PAN": "Panama 🇵🇦",         "BHS": "Bahamas 🇧🇸",
    "BMU": "Bermuda 🇧🇲",        "VGB": "British Virgin Islands 🇻🇬",
    "LIE": "Liechtenstein 🇱🇮",  "MCO": "Monaco 🇲🇨",
    "AND": "Andorra 🇦🇩",        "IRN": "Iran 🇮🇷",
    "PRK": "North Korea 🇰🇵",    "MMR": "Myanmar 🇲🇲",
    "VEN": "Venezuela 🇻🇪",      "NGA": "Nigeria 🇳🇬",
    "PHL": "Philippines 🇵🇭",    "SYR": "Syria 🇸🇾",
    "YEM": "Yemen 🇾🇪",          "LBN": "Lebanon 🇱🇧",
    "KEN": "Kenya 🇰🇪",          "BOL": "Bolivia 🇧🇴",
    "HKG": "Hong Kong 🇭🇰",      "LBR": "Liberia 🇱🇷",
    "MAC": "Macau 🇲🇴",          "MUS": "Mauritius 🇲🇺",
    "SYC": "Seychelles 🇸🇨",     "DZA": "Algeria 🇩🇿",
    "AGO": "Angola 🇦🇴",         "BGR": "Bulgaria 🇧🇬",
    "CMR": "Cameroon 🇨🇲",       "HRV": "Croatia 🇭🇷",
    "HTI": "Haiti 🇭🇹",          "KWT": "Kuwait 🇰🇼",
    "MOZ": "Mozambique 🇲🇿",     "NAM": "Namibia 🇳🇦",
    "NPL": "Nepal 🇳🇵",          "TZA": "Tanzania 🇹🇿",
    "VNM": "Vietnam 🇻🇳",        "MNG": "Mongolia 🇲🇳",
}

CSV_REQUIRED_COLUMNS = [
    "transaction_id", "transaction_type", "direction", "amount_brl",
    "sender_jurisdiction", "receiver_jurisdiction", "sender_is_pep",
    "receiver_is_pep", "customer_profile",
]

def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)

# ─────────────────────────────────────────────
# GLOBAL CSS — clean, no markdown tricks in sidebar
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="block-container"] {
    background-color: #F4F6F9 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0F2645 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label {
    color: #CBD5E1 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stRadio > div {
    gap: 4px !important;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 13px !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    color: #CBD5E1 !important;
    font-weight: 400 !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.08) !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] button {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,0.2) !important;
}

/* Main content headings */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    color: #0F2645 !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricValue"] {
    color: #0F2645 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 800 !important;
    font-size: 2.2rem !important;
}
[data-testid="stMetricLabel"] {
    color: #475569 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

/* Expanders */
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    color: #1E293B !important;
    font-size: 13px !important;
}

/* Fix multiselect dark background */
[data-testid="stMultiSelect"] [data-baseweb="select"] {
    background: #FFFFFF !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background: #EFF6FF !important;
    color: #1E3A8A !important;
}
.stMultiSelect div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border-color: #E2E8F0 !important;
}

/* Fix text input */
[data-testid="stTextInput"] input {
    background: #FFFFFF !important;
    color: #1E293B !important;
    border-color: #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Fix selectbox */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border-color: #E2E8F0 !important;
    color: #1E293B !important;
}

/* Login input fix */
[data-testid="stTextInput"] label {
    color: #374151 !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #FFFFFF !important;
    border: 2px dashed #CBD5E1 !important;
    border-radius: 10px !important;
}

hr { border-color: #E2E8F0 !important; margin: 16px 0 !important; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #F4F6F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }

/* Custom components */
.rr-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(15,38,69,0.06);
    margin-bottom: 12px;
}
.rr-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94A3B8;
    margin-bottom: 4px;
    font-family: 'Inter', sans-serif;
}
.rr-party-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.rr-arrow {
    text-align: center;
    font-size: 26px;
    color: #3B82F6;
    padding-top: 18px;
}
.rr-amount-label {
    font-size: 11px;
    color: #94A3B8;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-amount-value {
    font-size: 18px;
    font-weight: 800;
    color: #0F2645;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-field-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
}
.rr-field-row:last-child { border-bottom: none; }
.rr-field-key { color: #475569; font-weight: 500; }
.rr-field-val { color: #1E293B; font-weight: 600; text-align: right; }
.rr-mono { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #475569; }
.rr-signal {
    background: #FEF2F2;
    border-left: 3px solid #EF4444;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: #1E293B;
    font-family: 'Inter', sans-serif;
}
.rr-narrative {
    background: #EFF6FF;
    border-left: 4px solid #3B82F6;
    padding: 16px 20px;
    border-radius: 0 8px 8px 0;
    font-size: 13px;
    line-height: 1.8;
    color: #1E293B;
    font-family: 'Inter', sans-serif;
}
.rr-lgpd {
    background: #F8FAFC;
    border: 1px dashed #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11px;
    color: #64748B;
    margin-top: 8px;
    font-family: 'Inter', sans-serif;
    line-height: 1.5;
}
.rr-page-title {
    font-size: 26px;
    font-weight: 800;
    color: #0F2645;
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.03em;
    margin-bottom: 4px;
}
.rr-page-sub {
    font-size: 13px;
    color: #64748B;
    font-family: 'Inter', sans-serif;
    margin-bottom: 24px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def risk_badge(level: str) -> str:
    bg, border, text = RISK_COLORS.get(level, ("#F1F5F9", "#94A3B8", "#475569"))
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:20px;'
        f'font-size:11px;font-weight:700;letter-spacing:.06em;font-family:Inter,sans-serif;'
        f'background:{bg};color:{text};border:1px solid {border}">{level}</span>'
    )

def score_bar(score: int, compact: bool = False) -> str:
    level = "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    _, border, text = RISK_COLORS.get(level, ("#F1F5F9", "#94A3B8", "#475569"))
    label = {"LOW": "Low Risk", "MEDIUM": "Medium Risk", "HIGH": "High Risk", "CRITICAL": "Critical Risk"}[level]
    h = "6px" if compact else "8px"
    fs = "10px" if compact else "12px"
    return (
        f'<div style="margin:{"4px" if compact else "10px"} 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:{fs};'
        f'color:#475569;margin-bottom:4px;font-family:Inter,sans-serif">'
        f'<span style="font-weight:500">Risk Score</span>'
        f'<span style="color:{text};font-weight:700">{score}/100 — {label}</span></div>'
        f'<div style="background:#E2E8F0;border-radius:4px;height:{h}">'
        f'<div style="background:{border};height:{h};border-radius:4px;width:{score}%">'
        f'</div></div></div>'
    )

def fmt_brl(value) -> str:
    if value is None:
        return "—"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def party_box(party_type: str, jurisdiction: str, is_pep: bool, label: str) -> str:
    pep_html = (
        '<div style="margin-top:8px">'
        '<span style="background:#FEE2E2;color:#991B1B;border:1px solid #FCA5A5;'
        'padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;'
        'font-family:Inter,sans-serif">⚠️ PEP</span></div>'
    ) if is_pep else ""
    return (
        f'<div class="rr-party-box">'
        f'<div class="rr-label">{label}</div>'
        f'<div style="font-size:14px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif;margin-top:2px">'
        f'{PARTY_TYPE_LABELS.get(party_type, party_type)}</div>'
        f'<div style="font-size:13px;color:#3B82F6;margin-top:4px;font-family:Inter,sans-serif;font-weight:500">'
        f'{country_name(jurisdiction)}</div>'
        f'<div class="rr-lgpd">🔒 Identity protected — LGPD Art. 5, Lei 13.709/2018</div>'
        f'{pep_html}</div>'
    )

def action_card(action: str) -> str:
    bg, border, text = ACTION_COLORS.get(action, ("#F1F5F9", "#94A3B8", "#475569"))
    icon  = ACTION_ICONS.get(action, "")
    label = ACTION_LABELS.get(action, action)
    desc  = ACTION_DESC.get(action, "")
    return (
        f'<div style="background:{bg};border:1.5px solid {border};border-radius:10px;'
        f'padding:16px 20px;margin:10px 0">'
        f'<div style="font-size:15px;font-weight:700;color:{text};font-family:Inter,sans-serif">'
        f'{icon} {label}</div>'
        f'<div style="font-size:12px;color:#374151;margin-top:6px;line-height:1.7;'
        f'font-family:Inter,sans-serif">{desc}</div>'
        f'</div>'
    )

def plotly_light(fig, height: int = 280):
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font_color="#1E293B", font_family="Inter, sans-serif",
        height=height, margin=dict(l=8, r=8, t=8, b=8),
    )
    fig.update_xaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0", tickfont=dict(size=11))
    fig.update_yaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0", tickfont=dict(size=11))
    return fig

def section_header(title: str, sub: str = ""):
    st.markdown(
        f'<div class="rr-page-title">{title}</div>'
        f'{"<div class=rr-page-sub>" + sub + "</div>" if sub else ""}',
        unsafe_allow_html=True,
    )

def card_title(text: str):
    st.markdown(
        f'<div style="font-size:13px;font-weight:700;color:#0F2645;margin-bottom:12px;'
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
# SESSION STATE — login
# ─────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ─────────────────────────────────────────────
# LOGIN PAGE
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;margin-bottom:32px">
          <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:16px">
            <div style="width:48px;height:48px;background:#0F2645;border-radius:12px;
              display:flex;align-items:center;justify-content:center;font-size:28px">🎯</div>
            <div style="text-align:left">
              <div style="font-size:28px;font-weight:800;color:#0F2645;
                font-family:Inter,sans-serif;letter-spacing:-0.03em">RiskRadar</div>
              <div style="font-size:12px;color:#64748B;font-family:Inter,sans-serif">
                AML Compliance Intelligence</div>
            </div>
          </div>
          <div style="font-size:15px;color:#475569;font-family:Inter,sans-serif;line-height:1.6">
            Intelligent transaction risk classification<br>for Brazilian financial compliance
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;
          padding:32px;box-shadow:0 4px 24px rgba(15,38,69,0.10)">
        """, unsafe_allow_html=True)

        st.markdown('<div style="font-size:18px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif;margin-bottom:20px">Sign in to your account</div>', unsafe_allow_html=True)

        username = st.text_input("Email address", placeholder="compliance@yourfirm.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")

        if st.button("Sign In →", use_container_width=True, type="primary"):
            if username and password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Please enter your credentials.")

        st.markdown("""
        <div style="margin-top:20px;padding:12px;background:#F0F7FF;border-radius:8px;
          font-size:11px;color:#374151;font-family:Inter,sans-serif;line-height:1.6;
          border:1px solid #BFDBFE">
          <strong>Demo access:</strong> Enter any email and password to explore the platform.<br>
          In production, this connects to your organization's identity provider.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center;margin-top:24px;font-size:11px;color:#94A3B8;
          font-family:Inter,sans-serif;line-height:1.8">
          Synthetic data only · Academic & portfolio project<br>
          Not a legal or compliance system
        </div>
        """, unsafe_allow_html=True)
    st.stop()


# ─────────────────────────────────────────────
# SIDEBAR — post login
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:4px 0 20px 0">'
        '<div style="font-size:20px;font-weight:800;color:#FFFFFF;'
        'font-family:Inter,sans-serif;letter-spacing:-0.02em">🎯 RiskRadar</div>'
        '<div style="font-size:11px;color:#94A3B8;font-family:Inter,sans-serif;margin-top:2px">'
        'AML Compliance Intelligence</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "nav",
        ["📊  Overview", "🔎  Transaction Explorer",
         "🌍  Jurisdiction Map", "📋  Transaction Detail",
         "📥  Import Transactions", "ℹ️  About RiskRadar"],
        label_visibility="collapsed",
    )

    st.divider()

    summary = fetch_summary()
    st.markdown(
        f'<div style="font-family:Inter,sans-serif">'
        f'<div style="font-size:10px;font-weight:700;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:.1em;margin-bottom:10px">Database</div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid #1A3A6B;font-size:12px">'
        f'<span style="color:#94A3B8">Transactions</span>'
        f'<span style="color:#FFFFFF;font-weight:600">{summary["total_transactions"]}</span></div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid #1A3A6B;font-size:12px">'
        f'<span style="color:#94A3B8">Classified</span>'
        f'<span style="color:#4ADE80;font-weight:600">{summary["classified"]}</span></div>'
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:12px">'
        f'<span style="color:#94A3B8">Pending</span>'
        f'<span style="color:#FCD34D;font-weight:600">{summary["pending"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    username_display = st.session_state.get("username", "analyst@firm.com")
    st.markdown(
        f'<div style="font-size:11px;color:#64748B;font-family:Inter,sans-serif;line-height:1.7">'
        f'Signed in as<br>'
        f'<span style="color:#CBD5E1;font-weight:600">{username_display}</span></div>',
        unsafe_allow_html=True,
    )
    if st.button("Sign out", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

    st.markdown(
        '<div style="margin-top:16px;font-size:10px;color:#334155;'
        'font-family:Inter,sans-serif;line-height:1.7">'
        'Synthetic data only.<br>Not a legal or compliance system.<br>'
        'Human review required before<br>any real-world action.</div>',
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
if page == "📊  Overview":
    section_header("Transaction Risk Overview",
                   "Real-time classification dashboard — Brazilian AML regulatory framework")

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
            f'<div style="background:#FEF2F2;border:1.5px solid #EF4444;border-radius:10px;'
            f'padding:14px 20px;margin:16px 0;display:flex;align-items:center;gap:14px">'
            f'<span style="font-size:22px">🚨</span>'
            f'<div><div style="font-weight:700;color:#7F1D1D;font-family:Inter,sans-serif;font-size:14px">'
            f'{len(criticals)} Critical Alert(s) Require Immediate Action</div>'
            f'<div style="font-size:12px;color:#DC2626;margin-top:2px;font-family:Inter,sans-serif">'
            f'Mandatory report to COAF — Art. 11, Lei 9.613/1998</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container():
            st.markdown('<div class="rr-card">', unsafe_allow_html=True)
            card_title("Risk Distribution")
            counts = df["risk_level"].value_counts().reindex(RISK_ORDER).fillna(0)
            palette = [RISK_COLORS[r][1] for r in counts.index if r in RISK_COLORS]
            fig = go.Figure(go.Pie(
                labels=counts.index.tolist(),
                values=counts.values.tolist(),
                hole=0.6,
                marker_colors=palette,
                textinfo="label+percent",
                textfont=dict(size=11, family="Inter"),
            ))
            plotly_light(fig, 260)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        with st.container():
            st.markdown('<div class="rr-card">', unsafe_allow_html=True)
            card_title("Triggered Risk Indicators")
            typo_data = fetch_typology_counts()
            if typo_data:
                tdf = pd.DataFrame(typo_data)
                tdf["label"] = tdf["typology"].map(lambda x: TYPOLOGY_LABELS.get(x, x))
                fig2 = px.bar(
                    tdf, x="n", y="label", orientation="h",
                    color_discrete_sequence=["#3B82F6"],
                )
                plotly_light(fig2, 260)
                fig2.update_layout(xaxis_title="", yaxis_title="",
                                   yaxis=dict(categoryorder="total ascending"))
                st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Risk Score Distribution")
        fig3 = px.histogram(
            df, x="risk_score", nbins=20,
            color="risk_level",
            color_discrete_map={r: RISK_COLORS[r][1] for r in RISK_ORDER},
            category_orders={"risk_level": RISK_ORDER},
        )
        plotly_light(fig3, 180)
        fig3.update_layout(xaxis_title="Score (0–100)", yaxis_title="Transactions", bargap=0.05)
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 12px;'
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
                f"{row['transaction_id']}  ·  {row['risk_level']}  ·  "
                f"{fmt_brl(row['amount_brl'])}  ·  {tx_label}"
            ):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown(risk_badge(str(row["risk_level"])), unsafe_allow_html=True)
                    st.markdown(score_bar(row["risk_score"], compact=True), unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-size:11px;color:#475569;margin-top:8px;'
                        f'font-family:Inter,sans-serif;line-height:1.7">'
                        f'{DIRECTION_ICONS.get(row["direction"],"")} '
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
elif page == "🔎  Transaction Explorer":
    section_header("Transaction Explorer",
                   "Search and filter all classified transactions")

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
    search = f3.text_input("Search by ID or keyword", placeholder="TXN-00018 or keyword…")

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

    st.markdown(
        f'<div style="font-size:12px;color:#64748B;margin:8px 0 16px;'
        f'font-family:Inter,sans-serif">{len(filtered)} transaction(s) found</div>',
        unsafe_allow_html=True,
    )

    for _, row in filtered.iterrows():
        tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
        with st.expander(
            f"{row['transaction_id']}  ·  {row['risk_level']}  ·  "
            f"{fmt_brl(row['amount_brl'])}  ·  {tx_label}",
            expanded=False,
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
                    f'<div class="rr-amount-label">'
                    f'{DIRECTION_ICONS.get(row["direction"],"")} '
                    f'{DIRECTION_LABELS.get(row["direction"],"")}</div>',
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
                    f'<div style="font-size:11px;color:#475569;margin-top:6px;'
                    f'font-family:Inter,sans-serif">'
                    f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="rr-narrative">'
                    f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.08em;color:#94A3B8;margin-bottom:6px">Compliance Narrative</div>'
                    f'{row["narrative"]}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 3 — JURISDICTION MAP
# ═════════════════════════════════════════════
elif page == "🌍  Jurisdiction Map":
    section_header("Jurisdiction Risk Map",
                   "Countries flagged in classified transactions, by regulatory list membership")

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
            "HIGH": "#EF4444",
            "MEDIUM": "#F59E0B",
            "LOW": "#16A34A",
        },
        hover_name="jurisdiction_code",
        hover_data={"n": True, "risk_contribution": True},
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True, coastlinecolor="#E2E8F0",
        showland=True, landcolor="#F8FAFC",
        showocean=True, oceancolor="#EFF6FF",
        projection_type="natural earth",
    )
    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font_family="Inter, sans-serif", font_color="#1E293B",
        height=400, margin=dict(l=0, r=0, t=8, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 12px;'
        'font-family:Inter,sans-serif">Flagged Jurisdictions — Detail</div>',
        unsafe_allow_html=True,
    )
    for _, row in jdf.iterrows():
        bg, border, text = RISK_COLORS.get(row["risk_contribution"], ("#F1F5F9", "#94A3B8", "#475569"))
        st.markdown(
            f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:15px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif">'
            f'{country_name(row["jurisdiction_code"])}</div>'
            f'<div style="font-size:12px;color:#64748B;margin-top:2px;font-family:Inter,sans-serif">'
            f'{row["n"]} transaction(s) flagged</div>'
            f'</div>'
            f'<span style="background:{bg};color:{text};border:1px solid {border};'
            f'padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;'
            f'font-family:Inter,sans-serif;white-space:nowrap">{row["risk_contribution"]} RISK</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 4 — TRANSACTION DETAIL
# ═════════════════════════════════════════════
elif page == "📋  Transaction Detail":
    section_header("Transaction Detail",
                   "Full compliance breakdown for a single transaction")

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
    _, border, text = RISK_COLORS.get(cls["risk_level"], ("#F1F5F9", "#94A3B8", "#475569"))
    st.markdown(
        f'<div class="rr-card" style="border-left:5px solid {border}">'
        f'<div class="rr-label">Executive Summary</div>'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:6px">'
        f'<span style="font-size:28px;font-weight:800;color:{text};font-family:Inter,sans-serif;'
        f'letter-spacing:-0.02em">{cls["risk_level"]} RISK</span>'
        f'<span style="font-size:20px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif">'
        f'Score: {cls["risk_score"]}/100</span>'
        f'<span class="rr-mono">{selected}</span>'
        f'</div>'
        f'{score_bar(cls["risk_score"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Transaction Flow
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 10px;'
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
            f'<div class="rr-amount-label">'
            f'{DIRECTION_ICONS.get(tx["direction"],"")} '
            f'{DIRECTION_LABELS.get(tx["direction"],"")}</div>',
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
            ("Direction",        f'{DIRECTION_ICONS.get(tx["direction"],"")} {DIRECTION_LABELS.get(tx["direction"],"")}'.strip()),
            ("Amount",           fmt_brl(tx["amount_brl"])),
            ("Customer Profile", PROFILE_LABELS.get(tx["customer_profile"], tx["customer_profile"])),
            ("Date / Time",      str(tx["transaction_timestamp"])[:19].replace("T", " ")),
            ("Purpose",          tx["purpose_description"] or "⚠️ Not provided"),
        ]
        for k, v in fields:
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key">{k}</span>'
                f'<span class="rr-field-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Transaction Frequency")
        freq_threshold = {"PF_STANDARD": 5, "PF_HIGH_INCOME": 15, "PJ_SME": 25, "PJ_LARGE": 60}
        threshold = freq_threshold.get(tx["customer_profile"], 5)
        freq_fields = [
            ("Transactions — last 24h", str(tx["transactions_last_24h"]),   tx["transactions_last_24h"] > threshold),
            ("Transactions — last 72h", str(tx["transactions_last_72h"]),   tx["transactions_last_72h"] > threshold * 2),
            ("Total amount — last 72h", fmt_brl(tx["total_amount_last_72h_brl"]), tx["total_amount_last_72h_brl"] > 10000),
            ("Average monthly amount",  fmt_brl(tx["avg_monthly_amount_brl"]), False),
        ]
        for k, v, warn in freq_fields:
            warn_tag = ' <span style="color:#DC2626;font-weight:600;font-size:11px">⚠️ Above threshold</span>' if warn else ""
            color = "#DC2626" if warn else "#1E293B"
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key">{k}</span>'
                f'<span class="rr-field-val" style="color:{color}">{v}{warn_tag}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="font-size:10px;color:#94A3B8;margin-top:8px;font-family:Inter,sans-serif">'
            f'Expected daily limit: {threshold} tx/day — '
            f'{PROFILE_LABELS.get(tx["customer_profile"],"")} (Circular Bacen 3.978/2020)</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Risk Indicators
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 10px;'
        'font-family:Inter,sans-serif">Risk Indicators</div>',
        unsafe_allow_html=True,
    )
    for t in typos:
        signals = json.loads(t["signals_identified"]) if isinstance(t["signals_identified"], str) else t["signals_identified"]
        is_triggered = t["status"] == "TRIGGERED"
        label = TYPOLOGY_LABELS.get(t["typology"], t["typology"])
        with st.expander(
            f"{'🔴' if is_triggered else '⚪'} {label} — {t['status'].replace('_', ' ')}",
            expanded=is_triggered,
        ):
            st.markdown(
                f'<div style="font-size:12px;color:#475569;margin-bottom:10px;'
                f'font-family:Inter,sans-serif;line-height:1.6">'
                f'{TYPOLOGY_DESC.get(t["typology"],"")}</div>',
                unsafe_allow_html=True,
            )
            if signals:
                for s in signals:
                    st.markdown(f'<div class="rr-signal">⚑ {s}</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="font-size:12px;color:#94A3B8;font-family:Inter,sans-serif">'
                    'No signals identified for this indicator.</div>',
                    unsafe_allow_html=True,
                )

    # Jurisdiction Flags
    if juris:
        st.markdown(
            '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 10px;'
            'font-family:Inter,sans-serif">Jurisdiction Flags</div>',
            unsafe_allow_html=True,
        )
        for j in juris:
            lists = json.loads(j["list_membership"]) if isinstance(j["list_membership"], str) else j["list_membership"]
            if not lists:
                continue
            _, border, text = RISK_COLORS.get(j["risk_contribution"], ("#F1F5F9", "#94A3B8", "#475569"))
            list_tags = "".join([
                f'<span style="background:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#475569"))[0]};'
                f'color:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#475569"))[2]};'
                f'border:1px solid {RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#475569"))[1]};'
                f'padding:2px 10px;border-radius:20px;font-size:10px;font-weight:600;'
                f'margin-right:6px;font-family:Inter,sans-serif">{LIST_LABELS.get(l,l)}</span>'
                for l in lists
            ])
            st.markdown(
                f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px;border-left:4px solid {border}">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'<div>'
                f'<div style="font-size:15px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif">'
                f'{country_name(j["jurisdiction_code"])}</div>'
                f'<div style="margin-top:6px">{list_tags}</div>'
                f'</div>'
                f'<span style="background:{RISK_COLORS.get(j["risk_contribution"],("#F1F5F9","#94A3B8","#475569"))[0]};'
                f'color:{text};border:1px solid {border};padding:4px 14px;border-radius:20px;'
                f'font-size:11px;font-weight:700;font-family:Inter,sans-serif;white-space:nowrap">'
                f'{j["risk_contribution"]} RISK</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # Recommended Action
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 6px;'
        'font-family:Inter,sans-serif">Recommended Action</div>',
        unsafe_allow_html=True,
    )
    st.markdown(action_card(cls["recommended_action"]), unsafe_allow_html=True)

    # Narrative
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 6px;'
        'font-family:Inter,sans-serif">Compliance Narrative</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="rr-narrative">{cls["narrative"]}</div>', unsafe_allow_html=True)

    # Data Quality
    if dq:
        st.markdown(
            '<div style="font-size:14px;font-weight:700;color:#0F2645;margin:20px 0 6px;'
            'font-family:Inter,sans-serif">⚠️ Data Quality Flags</div>',
            unsafe_allow_html=True,
        )
        st.caption("The following fields were missing and may affect classification accuracy.")
        for f in dq:
            st.markdown(
                f'<span style="background:#FEF3C7;color:#78350F;border:1px solid #F59E0B;'
                f'padding:3px 10px;border-radius:20px;font-size:11px;margin:2px;'
                f'display:inline-block;font-family:Inter,sans-serif">⚠️ {f}</span>',
                unsafe_allow_html=True,
            )

    # Raw JSON
    with st.expander("🔧 Raw JSON Output — Technical"):
        st.code(cls["raw_response_json"], language="json")

    st.markdown(
        f'<div style="font-size:10px;color:#94A3B8;margin-top:20px;padding-top:12px;'
        f'border-top:1px solid #E2E8F0;font-family:Inter,sans-serif;line-height:1.8">'
        f'Classified: {str(cls["classified_at"])[:19]} · Prompt version: {cls["prompt_version"]}<br>'
        f'This output is generated by an AI system for academic and portfolio purposes only. '
        f'Human review by a licensed compliance officer is required before any real-world action.</div>',
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════
# PAGE 5 — IMPORT TRANSACTIONS
# ═════════════════════════════════════════════
elif page == "📥  Import Transactions":
    section_header("Import Transactions",
                   "Upload a CSV file to preview transactions before AI classification")

    st.markdown(
        '<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;'
        'padding:14px 18px;margin-bottom:20px">'
        '<div style="font-weight:700;color:#1E3A8A;font-family:Inter,sans-serif;font-size:13px">'
        'ℹ️ How this works</div>'
        '<div style="font-size:12px;color:#374151;margin-top:6px;font-family:Inter,sans-serif;line-height:1.7">'
        'Upload a CSV with your transactions. RiskRadar will validate the format and show a preview. '
        'In a production environment, the AI engine would then classify each transaction automatically. '
        'Connect your API key to enable real-time classification.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Required columns info
    with st.expander("📋 Required CSV columns"):
        st.markdown(
            '<div style="font-size:12px;color:#475569;font-family:Inter,sans-serif;line-height:1.8">'
            'Your CSV must contain the following columns:<br><br>'
            + "".join([
                f'<span style="background:#F1F5F9;padding:2px 8px;border-radius:4px;'
                f'font-family:IBM Plex Mono,monospace;font-size:11px;margin:2px;'
                f'display:inline-block">{col}</span> '
                for col in CSV_REQUIRED_COLUMNS
            ])
            + '</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download CSV template",
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
                st.success(f"✅ {len(upload_df)} transactions detected — format valid")

                col1, col2, col3 = st.columns(3)
                col1.metric("Transactions", len(upload_df))
                col2.metric("PEP Flagged",
                            int(upload_df["sender_is_pep"].astype(str).str.lower().eq("true").sum() +
                                upload_df["receiver_is_pep"].astype(str).str.lower().eq("true").sum()))
                col3.metric("Avg Amount",
                            fmt_brl(upload_df["amount_brl"].astype(float).mean()))

                st.markdown(
                    '<div style="font-size:13px;font-weight:700;color:#0F2645;margin:16px 0 8px;'
                    'font-family:Inter,sans-serif">Preview (first 10 rows)</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(
                    upload_df.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(
                    '<div style="background:#FEF3C7;border:1.5px solid #F59E0B;border-radius:10px;'
                    'padding:16px 20px;margin-top:16px">'
                    '<div style="font-weight:700;color:#78350F;font-family:Inter,sans-serif;font-size:14px">'
                    '⚡ Ready for AI Classification</div>'
                    '<div style="font-size:12px;color:#374151;margin-top:8px;font-family:Inter,sans-serif;line-height:1.7">'
                    'In production, clicking "Classify" would send each transaction to the Claude AI engine '
                    'for risk scoring against COAF/Bacen typologies. Results would be stored in the database '
                    'and immediately visible in the Overview and Explorer pages.<br><br>'
                    '<strong>To enable:</strong> Add your <code>ANTHROPIC_API_KEY</code> to Streamlit secrets '
                    'and run <code>batch_runner.py</code>.'
                    '</div></div>',
                    unsafe_allow_html=True,
                )

                st.button("⚡ Classify with AI Engine (requires API key)", disabled=True, use_container_width=True)

        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        st.markdown(
            '<div style="text-align:center;padding:40px;color:#94A3B8;font-family:Inter,sans-serif">'
            '<div style="font-size:32px;margin-bottom:8px">📂</div>'
            '<div style="font-size:13px">Drag and drop your CSV file here, or click to browse</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 6 — ABOUT
# ═════════════════════════════════════════════
elif page == "ℹ️  About RiskRadar":
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown("""
        <div style="margin-bottom:32px">
          <div style="font-size:32px;font-weight:800;color:#0F2645;font-family:Inter,sans-serif;
            letter-spacing:-0.03em;margin-bottom:6px">🎯 RiskRadar</div>
          <div style="font-size:16px;color:#475569;font-family:Inter,sans-serif;line-height:1.6">
            Intelligent transaction risk classification<br>for Brazilian financial compliance
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("What is RiskRadar?")
        st.markdown("""
        <div style="font-size:13px;color:#374151;font-family:Inter,sans-serif;line-height:1.9">
        RiskRadar is an AI-powered compliance tool that classifies financial transactions
        according to Brazilian AML (Anti-Money Laundering) regulation. It uses Claude
        (Anthropic) as its reasoning engine to evaluate transactions against known suspicious
        activity typologies defined by COAF and Bacen.
        <br><br>
        The system simulates a workflow used by compliance analysts in Brazilian financial
        institutions — receiving a batch of transactions, applying regulatory rules, and
        generating structured risk reports with natural language justifications that a
        licensed compliance officer can evaluate and act upon.
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Regulatory Framework")
        regs = [
            ("Lei 9.613/1998",         "Brazilian AML law — mandatory reporting threshold R$10,000"),
            ("Circular Bacen 3.978/2020", "KYC and transaction monitoring obligations"),
            ("Resolução COAF 36/2021", "AML/CFT internal policy requirements"),
            ("Resolução COAF 40/2021", "PEP definition and enhanced due diligence"),
            ("IN RFB 1.037/2010",      "Brazilian tax haven jurisdiction list"),
            ("FATF Plenary Feb/2026",  "Blacklist (Iran, North Korea, Myanmar) and Grey List"),
        ]
        for reg, desc in regs:
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key rr-mono" style="font-size:12px">{reg}</span>'
                f'<span style="color:#475569;font-size:12px;text-align:right;max-width:60%">{desc}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Risk Typologies Covered")
        typos_info = [
            ("Structuring (Smurfing)",          "Transactions below the R$10k threshold to avoid reporting"),
            ("Unusual Transaction Frequency",   "Activity exceeding expected patterns for the customer profile"),
            ("High-Risk Jurisdiction",          "Transactions involving FATF-listed or RFB tax haven countries"),
            ("Politically Exposed Person (PEP)", "Involvement of current or former public office holders"),
        ]
        for t, d in typos_info:
            st.markdown(
                f'<div style="padding:10px 0;border-bottom:1px solid #F1F5F9;font-family:Inter,sans-serif">'
                f'<div style="font-size:13px;font-weight:600;color:#0F2645">{t}</div>'
                f'<div style="font-size:12px;color:#64748B;margin-top:2px">{d}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="background:#FEE2E2;border:1px solid #FCA5A5;border-radius:10px;'
            'padding:14px 18px;margin-top:8px">'
            '<div style="font-weight:700;color:#7F1D1D;font-family:Inter,sans-serif;font-size:12px">'
            '⚠️ Important Disclaimer</div>'
            '<div style="font-size:11px;color:#374151;margin-top:6px;font-family:Inter,sans-serif;line-height:1.7">'
            'This is an academic and portfolio project. All transactions and data are entirely synthetic. '
            'RiskRadar does not constitute a legal or official compliance system. '
            'Human review by a licensed compliance officer is required before any real-world action.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    with col_side:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Tech Stack")
        stack = [
            ("AI Engine",     "Claude API — Anthropic"),
            ("Model",         "claude-sonnet-4-6"),
            ("Language",      "Python 3.11"),
            ("Interface",     "Streamlit"),
            ("Database",      "SQLite"),
            ("Data",          "Faker (pt_BR)"),
            ("Charts",        "Plotly"),
            ("Typography",    "Inter · IBM Plex Mono"),
        ]
        for k, v in stack:
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key">{k}</span>'
                f'<span style="color:#475569;font-size:12px;font-family:Inter,sans-serif">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Author")
        st.markdown("""
        <div style="font-family:Inter,sans-serif">
          <div style="font-size:15px;font-weight:700;color:#0F2645;margin-bottom:4px">
            Luís Filipe Mayer</div>
          <div style="font-size:11px;color:#64748B;line-height:1.7;margin-bottom:12px">
            Senior Banking Professional<br>
            Data Analytics · Analytics Translator<br>
            FIAP PosTech — Business Analytics
          </div>
          <div style="font-size:11px;color:#475569;line-height:1.8">
            15+ years in Brazilian financial services (Bradesco — Prime segment).
            This project bridges domain expertise in banking compliance with AI engineering.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        card_title("Links")
        st.markdown("""
        <div style="font-family:Inter,sans-serif;font-size:13px">
          <div style="padding:8px 0;border-bottom:1px solid #F1F5F9">
            <a href="https://github.com/lfmayer/brazilian-aml-classifier"
               style="color:#3B82F6;text-decoration:none;font-weight:500"
               target="_blank">⌥ GitHub Repository</a>
          </div>
          <div style="padding:8px 0">
            <a href="https://www.linkedin.com/in/luisfilipemayer"
               style="color:#3B82F6;text-decoration:none;font-weight:500"
               target="_blank">in LinkedIn</a>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
