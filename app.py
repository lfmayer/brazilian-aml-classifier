"""
app.py — RiskRadar
Intelligent transaction risk classification for Brazilian financial compliance.
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
C = {
    "navy":       "#0F2645",
    "navy_light": "#1A3A6B",
    "bg":         "#FFFFFF",
    "bg_soft":    "#F4F6F9",
    "bg_card":    "#FFFFFF",
    "border":     "#E2E8F0",
    "text":       "#1A202C",
    "text_muted": "#64748B",
    "text_light": "#94A3B8",
    "CRITICAL":   "#DC2626",
    "HIGH":       "#D97706",
    "MEDIUM":     "#2563EB",
    "LOW":        "#16A34A",
    "accent":     "#2563EB",
}

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

RISK_COLORS = {
    "LOW":      ("#DCFCE7", "#16A34A", "#166534"),
    "MEDIUM":   ("#DBEAFE", "#2563EB", "#1E3A8A"),
    "HIGH":     ("#FEF3C7", "#D97706", "#92400E"),
    "CRITICAL": ("#FEE2E2", "#DC2626", "#991B1B"),
}

ACTION_COLORS = {
    "MONITOR":             ("#DCFCE7", "#16A34A", "#166534"),
    "ESCALATE_FOR_REVIEW": ("#FEF3C7", "#D97706", "#92400E"),
    "COMMUNICATE_TO_COAF": ("#FEE2E2", "#DC2626", "#991B1B"),
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
    "MONITOR":              "Routine Monitoring",
    "ESCALATE_FOR_REVIEW":  "Escalate for Compliance Review",
    "COMMUNICATE_TO_COAF":  "Report to COAF — Art. 11, Lei 9.613/1998",
}

ACTION_DESC = {
    "MONITOR":              "No immediate action required. Transaction falls within expected parameters for this customer profile.",
    "ESCALATE_FOR_REVIEW":  "Forward to senior compliance officer for manual review and sign-off before any action is taken.",
    "COMMUNICATE_TO_COAF":  "Mandatory suspicious activity report must be filed with COAF within the legal deadline. Document all evidence.",
}

ACTION_ICONS = {
    "MONITOR":              "✅",
    "ESCALATE_FOR_REVIEW":  "⚠️",
    "COMMUNICATE_TO_COAF":  "🚨",
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

DIRECTION_ICONS = {
    "OUTBOUND": "↑",
    "INBOUND":  "↓",
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

def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, code)

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #F4F6F9 !important;
    color: #1A202C !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: #0F2645 !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: #CBD5E1 !important;
    font-size: 13px !important;
    padding: 6px 0 !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: #FFFFFF !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    color: #0F2645 !important;
    font-weight: 600 !important;
}

[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricValue"] {
    color: #0F2645 !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 2rem !important;
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    color: #1A202C !important;
    font-size: 13px !important;
}

hr { border-color: #E2E8F0 !important; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #F4F6F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }

.rr-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 12px;
}
.rr-section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94A3B8;
    margin-bottom: 6px;
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
    font-size: 24px;
    color: #2563EB;
    padding-top: 20px;
    font-weight: 300;
}
.rr-amount-label {
    font-size: 11px;
    color: #94A3B8;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-amount-value {
    font-size: 17px;
    font-weight: 700;
    color: #0F2645;
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.rr-field-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 13px;
}
.rr-field-row:last-child { border-bottom: none; }
.rr-field-key { color: #64748B; font-weight: 500; }
.rr-field-val { color: #1A202C; font-weight: 500; text-align: right; }
.rr-mono { font-family: 'IBM Plex Mono', monospace; font-size: 12px; }
.rr-signal {
    background: #FEF2F2;
    border-left: 3px solid #DC2626;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    color: #1A202C;
}
.rr-narrative {
    background: #F0F7FF;
    border-left: 4px solid #2563EB;
    padding: 16px 20px;
    border-radius: 0 8px 8px 0;
    font-size: 13px;
    line-height: 1.8;
    color: #1A202C;
}
.rr-lgpd-note {
    background: #F8FAFC;
    border: 1px dashed #CBD5E1;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
    color: #64748B;
    margin-top: 8px;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def risk_badge(level: str) -> str:
    bg, border, text = RISK_COLORS.get(level, ("#F1F5F9", "#94A3B8", "#64748B"))
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:20px;'
        f'font-size:11px;font-weight:700;letter-spacing:.06em;font-family:Inter,sans-serif;'
        f'background:{bg};color:{text};border:1px solid {border}">{level}</span>'
    )

def action_badge(action: str) -> str:
    bg, border, text = ACTION_COLORS.get(action, ("#F1F5F9", "#94A3B8", "#64748B"))
    icon = ACTION_ICONS.get(action, "")
    label = ACTION_LABELS.get(action, action)
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:20px;'
        f'font-size:11px;font-weight:600;font-family:Inter,sans-serif;'
        f'background:{bg};color:{text};border:1px solid {border}">{icon} {label}</span>'
    )

def score_bar(score: int, compact: bool = False) -> str:
    level = "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    _, border, text = RISK_COLORS.get(level, ("#F1F5F9", "#94A3B8", "#64748B"))
    label = {"LOW": "Low Risk", "MEDIUM": "Medium Risk", "HIGH": "High Risk", "CRITICAL": "Critical Risk"}[level]
    h = "6px" if compact else "8px"
    return (
        f'<div style="margin:{"4px" if compact else "8px"} 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:{"10px" if compact else "11px"};'
        f'color:#64748B;margin-bottom:3px;font-family:Inter,sans-serif">'
        f'<span>Risk Score</span>'
        f'<span style="color:{text};font-weight:700">{score}/100 — {label}</span></div>'
        f'<div style="background:#E2E8F0;border-radius:4px;height:{h}">'
        f'<div style="background:{border};height:{h};border-radius:4px;width:{score}%;'
        f'transition:width .4s ease"></div></div></div>'
    )

def fmt_brl(value) -> str:
    if value is None:
        return "—"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def party_box(party_type: str, jurisdiction: str, is_pep: bool, label: str) -> str:
    pep = (
        '<div style="margin-top:6px">'
        '<span style="background:#FEE2E2;color:#DC2626;border:1px solid #FCA5A5;'
        'padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700">⚠️ PEP</span>'
        '</div>'
    ) if is_pep else ""
    return (
        f'<div class="rr-party-box">'
        f'<div class="rr-section-label">{label}</div>'
        f'<div style="font-size:14px;font-weight:600;color:#0F2645;font-family:Inter,sans-serif">'
        f'{PARTY_TYPE_LABELS.get(party_type, party_type)}</div>'
        f'<div style="font-size:12px;color:#2563EB;margin-top:3px;font-family:Inter,sans-serif">'
        f'{country_name(jurisdiction)}</div>'
        f'<div class="rr-lgpd-note" style="margin-top:8px;font-size:10px">'
        f'🔒 Identity protected — LGPD Art. 5, Lei 13.709/2018</div>'
        f'{pep}'
        f'</div>'
    )

def action_card(action: str) -> str:
    bg, border, text = ACTION_COLORS.get(action, ("#F1F5F9", "#94A3B8", "#64748B"))
    icon  = ACTION_ICONS.get(action, "")
    label = ACTION_LABELS.get(action, action)
    desc  = ACTION_DESC.get(action, "")
    return (
        f'<div style="background:{bg};border:1.5px solid {border};border-radius:10px;'
        f'padding:16px 20px;margin:8px 0">'
        f'<div style="font-size:15px;font-weight:700;color:{text};font-family:Inter,sans-serif">'
        f'{icon} {label}</div>'
        f'<div style="font-size:12px;color:#374151;margin-top:6px;line-height:1.6;'
        f'font-family:Inter,sans-serif">{desc}</div>'
        f'</div>'
    )

def plotly_defaults(fig):
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font_color="#1A202C",
        font_family="Inter, sans-serif",
        margin=dict(l=12, r=12, t=32, b=12),
    )
    fig.update_xaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0")
    fig.update_yaxes(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0")
    return fig

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
# SIDEBAR — RiskRadar brand
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:8px 0 24px 0">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:36px;height:36px;background:#2563EB;border-radius:8px;
          display:flex;align-items:center;justify-content:center;font-size:20px">🎯</div>
        <div>
          <div style="font-size:18px;font-weight:700;color:#FFFFFF;
            font-family:Inter,sans-serif;letter-spacing:-0.02em">RiskRadar</div>
          <div style="font-size:10px;color:#94A3B8;font-family:Inter,sans-serif;
            margin-top:1px">AML Compliance Intelligence</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="border-top:1px solid #1A3A6B;margin-bottom:16px"></div>',
                unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        ["📊  Overview", "🔎  Transaction Explorer", "🌍  Jurisdiction Map", "📋  Transaction Detail"],
        label_visibility="collapsed",
    )

    st.markdown('<div style="border-top:1px solid #1A3A6B;margin:16px 0"></div>',
                unsafe_allow_html=True)

    summary = fetch_summary()
    st.markdown(f"""
    <div style="font-family:Inter,sans-serif">
      <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;
        letter-spacing:.08em;margin-bottom:10px">Database Status</div>
      <div style="display:flex;justify-content:space-between;
        padding:6px 0;border-bottom:1px solid #1A3A6B;font-size:12px">
        <span style="color:#94A3B8">Transactions</span>
        <span style="color:#FFFFFF;font-weight:600">{summary["total_transactions"]}</span>
      </div>
      <div style="display:flex;justify-content:space-between;
        padding:6px 0;border-bottom:1px solid #1A3A6B;font-size:12px">
        <span style="color:#94A3B8">Classified</span>
        <span style="color:#4ADE80;font-weight:600">{summary["classified"]}</span>
      </div>
      <div style="display:flex;justify-content:space-between;
        padding:6px 0;font-size:12px">
        <span style="color:#94A3B8">Pending</span>
        <span style="color:#FCD34D;font-weight:600">{summary["pending"]}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    if st.button("↻  Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<div style="border-top:1px solid #1A3A6B;margin:20px 0 12px 0"></div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:10px;color:#475569;line-height:1.7;font-family:Inter,sans-serif">
      Synthetic data only.<br>
      Not a legal or compliance system.<br>
      Human review required before<br>any real-world action.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
df = load_data()
no_data = df.empty


# ═════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═════════════════════════════════════════════
if page == "📊  Overview":
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:24px;font-weight:700;color:#0F2645;
        font-family:Inter,sans-serif;letter-spacing:-0.02em">Transaction Risk Overview</div>
      <div style="font-size:13px;color:#64748B;margin-top:3px;font-family:Inter,sans-serif">
        Real-time classification dashboard — Brazilian AML regulatory framework</div>
    </div>
    """, unsafe_allow_html=True)

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    by_risk = df["risk_level"].value_counts()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Classified",  len(df))
    k2.metric("Low Risk",          int(by_risk.get("LOW",      0)))
    k3.metric("Medium Risk",       int(by_risk.get("MEDIUM",   0)))
    k4.metric("High Risk",         int(by_risk.get("HIGH",     0)))
    k5.metric("Critical",          int(by_risk.get("CRITICAL", 0)))

    criticals = df[df["risk_level"] == "CRITICAL"]
    if not criticals.empty:
        st.markdown(
            f'<div style="background:#FEE2E2;border:1.5px solid #DC2626;border-radius:10px;'
            f'padding:14px 20px;margin:16px 0;display:flex;align-items:center;gap:12px">'
            f'<span style="font-size:20px">🚨</span>'
            f'<div><div style="font-weight:700;color:#991B1B;font-family:Inter,sans-serif;font-size:14px">'
            f'{len(criticals)} Critical Alert(s) Require Immediate Action</div>'
            f'<div style="font-size:12px;color:#DC2626;margin-top:2px;font-family:Inter,sans-serif">'
            f'Mandatory report to COAF — Art. 11, Lei 9.613/1998</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin-bottom:12px;font-family:Inter,sans-serif">Risk Distribution</div>', unsafe_allow_html=True)
        counts = df["risk_level"].value_counts().reindex(RISK_ORDER).fillna(0)
        risk_palette = [RISK_COLORS[r][1] for r in counts.index]
        fig = go.Figure(go.Pie(
            labels=counts.index.tolist(),
            values=counts.values.tolist(),
            hole=0.6,
            marker_colors=risk_palette,
            textinfo="label+percent",
            textfont=dict(size=11, family="Inter"),
        ))
        plotly_defaults(fig)
        fig.update_layout(showlegend=False, height=260, margin=dict(l=0,r=0,t=8,b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin-bottom:12px;font-family:Inter,sans-serif">Triggered Risk Indicators</div>', unsafe_allow_html=True)
        typo_data = fetch_typology_counts()
        if typo_data:
            tdf = pd.DataFrame(typo_data)
            tdf["label"] = tdf["typology"].map(lambda x: TYPOLOGY_LABELS.get(x, x))
            fig2 = px.bar(
                tdf, x="n", y="label", orientation="h",
                color_discrete_sequence=["#2563EB"],
            )
            plotly_defaults(fig2)
            fig2.update_layout(
                height=260, xaxis_title="", yaxis_title="",
                yaxis=dict(categoryorder="total ascending"),
                margin=dict(l=0,r=0,t=8,b=0),
            )
            fig2.update_traces(marker_color="#2563EB")
            st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="rr-card" style="margin-top:4px">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin-bottom:12px;font-family:Inter,sans-serif">Risk Score Distribution</div>', unsafe_allow_html=True)
    risk_color_map = {r: RISK_COLORS[r][1] for r in RISK_ORDER}
    fig3 = px.histogram(
        df, x="risk_score", nbins=20,
        color="risk_level",
        color_discrete_map=risk_color_map,
        category_orders={"risk_level": RISK_ORDER},
    )
    plotly_defaults(fig3)
    fig3.update_layout(height=180, xaxis_title="Score (0–100)", yaxis_title="Transactions",
                       bargap=0.05, margin=dict(l=0,r=0,t=8,b=0))
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 12px 0;font-family:Inter,sans-serif">Latest HIGH / CRITICAL Alerts</div>', unsafe_allow_html=True)
    alerts = df[df["risk_level"].isin(["HIGH", "CRITICAL"])].head(6)
    if alerts.empty:
        st.caption("No high-risk transactions found.")
    else:
        for _, row in alerts.iterrows():
            tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
            with st.expander(
                f"{row['transaction_id']}  ·  {row['risk_level']}  ·  {fmt_brl(row['amount_brl'])}  ·  {tx_label}"
            ):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown(risk_badge(str(row["risk_level"])), unsafe_allow_html=True)
                    st.markdown(score_bar(row["risk_score"], compact=True), unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-size:11px;color:#64748B;margin-top:8px;'
                        f'font-family:Inter,sans-serif;line-height:1.7">'
                        f'{DIRECTION_ICONS.get(row["direction"],"")} {DIRECTION_LABELS.get(row["direction"],"")}<br>'
                        f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}</div>',
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
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:24px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif;letter-spacing:-0.02em">Transaction Explorer</div>
      <div style="font-size:13px;color:#64748B;margin-top:3px;font-family:Inter,sans-serif">Search and filter all classified transactions</div>
    </div>
    """, unsafe_allow_html=True)

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    f1, f2, f3 = st.columns([1, 1, 2])
    risk_filter = f1.multiselect("Risk Level", RISK_ORDER, default=RISK_ORDER)
    action_filter = f2.multiselect(
        "Recommended Action",
        ["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
        default=["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
    )
    search = f3.text_input("Search transaction ID or keyword", placeholder="TXN-00018 or keyword…")

    filtered = df[df["risk_level"].isin(risk_filter) & df["recommended_action"].isin(action_filter)]
    if search:
        mask = (
            filtered["transaction_id"].str.contains(search, case=False, na=False) |
            filtered["narrative"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.markdown(
        f'<div style="font-size:12px;color:#64748B;margin:8px 0 16px 0;font-family:Inter,sans-serif">'
        f'{len(filtered)} transaction(s) found</div>',
        unsafe_allow_html=True,
    )

    for _, row in filtered.iterrows():
        tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
        with st.expander(
            f"{row['transaction_id']}  ·  {row['risk_level']}  ·  {fmt_brl(row['amount_brl'])}  ·  {tx_label}",
            expanded=False,
        ):
            col_s, col_a, col_r = st.columns([5, 2, 5])
            with col_s:
                st.markdown(
                    party_box("CPF", row["sender_jurisdiction"], bool(row["sender_is_pep"]), "Sender"),
                    unsafe_allow_html=True,
                )
            with col_a:
                st.markdown(
                    f'<div class="rr-arrow">→</div>'
                    f'<div class="rr-amount-label" style="margin-top:4px">{tx_label}</div>'
                    f'<div class="rr-amount-value">{fmt_brl(row["amount_brl"])}</div>'
                    f'<div class="rr-amount-label">'
                    f'{DIRECTION_ICONS.get(row["direction"],"")} {DIRECTION_LABELS.get(row["direction"],"")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col_r:
                st.markdown(
                    party_box("CPF", row["receiver_jurisdiction"], bool(row["receiver_is_pep"]), "Receiver"),
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(risk_badge(str(row["risk_level"])), unsafe_allow_html=True)
                st.markdown(score_bar(row["risk_score"], compact=True), unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:11px;color:#64748B;margin-top:6px;font-family:Inter,sans-serif">'
                    f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div class="rr-narrative">'
                    f'<div style="font-size:10px;font-weight:600;text-transform:uppercase;'
                    f'letter-spacing:.08em;color:#94A3B8;margin-bottom:6px">Compliance Narrative</div>'
                    f'{row["narrative"]}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 3 — JURISDICTION MAP
# ═════════════════════════════════════════════
elif page == "🌍  Jurisdiction Map":
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:24px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif;letter-spacing:-0.02em">Jurisdiction Risk Map</div>
      <div style="font-size:13px;color:#64748B;margin-top:3px;font-family:Inter,sans-serif">Countries flagged in classified transactions, by regulatory list membership</div>
    </div>
    """, unsafe_allow_html=True)

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    hits = fetch_jurisdiction_hits()
    if not hits:
        st.caption("No jurisdiction flags found.")
        st.stop()

    jdf = pd.DataFrame(hits)
    risk_color_map = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#16A34A"}

    fig = px.choropleth(
        jdf,
        locations="jurisdiction_code",
        locationmode="ISO-3",
        color="risk_contribution",
        color_discrete_map=risk_color_map,
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
        font_family="Inter, sans-serif", font_color="#1A202C",
        height=400, margin=dict(l=0,r=0,t=16,b=0),
    )
    st.markdown('<div class="rr-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 12px 0;font-family:Inter,sans-serif">Flagged Jurisdictions — Detail</div>', unsafe_allow_html=True)

    for _, row in jdf.iterrows():
        _, border, text = RISK_COLORS.get(row["risk_contribution"], ("#F1F5F9","#94A3B8","#64748B"))
        full_name = country_name(row["jurisdiction_code"])
        st.markdown(
            f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:15px;font-weight:600;color:#0F2645;font-family:Inter,sans-serif">{full_name}</div>'
            f'<div style="font-size:11px;color:#64748B;margin-top:2px;font-family:Inter,sans-serif">'
            f'{row["n"]} transaction(s) flagged</div>'
            f'</div>'
            f'<span style="background:{RISK_COLORS.get(row["risk_contribution"],("#F1F5F9","#94A3B8","#64748B"))[0]};'
            f'color:{text};border:1px solid {border};padding:4px 14px;border-radius:20px;'
            f'font-size:11px;font-weight:700;font-family:Inter,sans-serif">'
            f'{row["risk_contribution"]} RISK</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 4 — TRANSACTION DETAIL
# ═════════════════════════════════════════════
elif page == "📋  Transaction Detail":
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:24px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif;letter-spacing:-0.02em">Transaction Detail</div>
      <div style="font-size:13px;color:#64748B;margin-top:3px;font-family:Inter,sans-serif">Full compliance breakdown for a single transaction</div>
    </div>
    """, unsafe_allow_html=True)

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    tx_ids   = df["transaction_id"].tolist()
    selected = st.selectbox("Select a transaction", tx_ids)

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
    _, border, text = RISK_COLORS.get(cls["risk_level"], ("#F1F5F9","#94A3B8","#64748B"))
    st.markdown(
        f'<div class="rr-card" style="border-left:5px solid {border}">'
        f'<div class="rr-section-label">Executive Summary</div>'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:6px">'
        f'<span style="font-size:26px;font-weight:800;color:{text};font-family:Inter,sans-serif">'
        f'{cls["risk_level"]} RISK</span>'
        f'<span style="font-size:20px;font-weight:700;color:#0F2645;font-family:Inter,sans-serif">'
        f'Score: {cls["risk_score"]}/100</span>'
        f'<span class="rr-mono" style="color:#64748B;font-size:13px">{selected}</span>'
        f'</div>'
        f'{score_bar(cls["risk_score"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Transaction Flow
    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 10px 0;font-family:Inter,sans-serif">Transaction Flow</div>', unsafe_allow_html=True)
    col_s, col_a, col_r = st.columns([5, 2, 5])
    with col_s:
        st.markdown(
            party_box(tx["sender_type"], tx["sender_jurisdiction"], bool(tx["sender_is_pep"]), "Sender"),
            unsafe_allow_html=True,
        )
    with col_a:
        tx_label = TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"])
        st.markdown(
            f'<div class="rr-arrow">→</div>'
            f'<div class="rr-amount-label" style="margin-top:4px">{tx_label}</div>'
            f'<div class="rr-amount-value">{fmt_brl(tx["amount_brl"])}</div>'
            f'<div class="rr-amount-label">'
            f'{DIRECTION_ICONS.get(tx["direction"],"")} {DIRECTION_LABELS.get(tx["direction"],"")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            party_box(tx["receiver_type"], tx["receiver_jurisdiction"], bool(tx["receiver_is_pep"]), "Receiver"),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin-bottom:12px;font-family:Inter,sans-serif">Transaction Details</div>', unsafe_allow_html=True)
        fields = [
            ("Type",             TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"])),
            ("Direction",        f'{DIRECTION_ICONS.get(tx["direction"],"")} {DIRECTION_LABELS.get(tx["direction"],"")}'),
            ("Amount",           fmt_brl(tx["amount_brl"])),
            ("Customer Profile", PROFILE_LABELS.get(tx["customer_profile"], tx["customer_profile"])),
            ("Date / Time",      str(tx["transaction_timestamp"])[:19].replace("T", " ")),
            ("Purpose",          tx["purpose_description"] or "⚠️ Not provided"),
        ]
        for k, v in fields:
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key">{k}</span>'
                f'<span class="rr-field-val">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="rr-card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin-bottom:12px;font-family:Inter,sans-serif">Transaction Frequency</div>', unsafe_allow_html=True)
        freq_threshold = {"PF_STANDARD": 5, "PF_HIGH_INCOME": 15, "PJ_SME": 25, "PJ_LARGE": 60}
        threshold = freq_threshold.get(tx["customer_profile"], 5)
        for k, v, warn in [
            ("Transactions — last 24h", str(tx["transactions_last_24h"]), tx["transactions_last_24h"] > threshold),
            ("Transactions — last 72h", str(tx["transactions_last_72h"]), tx["transactions_last_72h"] > threshold * 2),
            ("Total amount — last 72h", fmt_brl(tx["total_amount_last_72h_brl"]), tx["total_amount_last_72h_brl"] > 10000),
            ("Average monthly amount",  fmt_brl(tx["avg_monthly_amount_brl"]), False),
        ]:
            warn_tag = ' <span style="color:#DC2626;font-weight:700">⚠️ Above threshold</span>' if warn else ""
            val_color = "#DC2626" if warn else "#1A202C"
            st.markdown(
                f'<div class="rr-field-row">'
                f'<span class="rr-field-key">{k}</span>'
                f'<span class="rr-field-val" style="color:{val_color}">{v}{warn_tag}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="font-size:10px;color:#94A3B8;margin-top:8px;font-family:Inter,sans-serif">'
            f'Expected daily limit for {PROFILE_LABELS.get(tx["customer_profile"],tx["customer_profile"])}: '
            f'{threshold} transactions/day (Circular Bacen 3.978/2020)</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # Risk Indicators
    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 10px 0;font-family:Inter,sans-serif">Risk Indicators</div>', unsafe_allow_html=True)
    for t in typos:
        signals = json.loads(t["signals_identified"]) if isinstance(t["signals_identified"], str) else t["signals_identified"]
        is_triggered = t["status"] == "TRIGGERED"
        label = TYPOLOGY_LABELS.get(t["typology"], t["typology"])
        desc  = TYPOLOGY_DESC.get(t["typology"], "")
        icon  = "🔴" if is_triggered else "⚪"
        with st.expander(f"{icon} {label} — {t['status'].replace('_', ' ')}", expanded=is_triggered):
            st.markdown(
                f'<div style="font-size:12px;color:#64748B;margin-bottom:10px;'
                f'font-family:Inter,sans-serif;line-height:1.6">{desc}</div>',
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
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 10px 0;font-family:Inter,sans-serif">Jurisdiction Flags</div>', unsafe_allow_html=True)
        for j in juris:
            lists = json.loads(j["list_membership"]) if isinstance(j["list_membership"], str) else j["list_membership"]
            if not lists:
                continue
            _, border, text = RISK_COLORS.get(j["risk_contribution"], ("#F1F5F9","#94A3B8","#64748B"))
            list_labels = [LIST_LABELS.get(l, l) for l in lists]
            severity_tags = "".join([
                f'<span style="background:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#64748B"))[0]};'
                f'color:{RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#64748B"))[2]};'
                f'border:1px solid {RISK_COLORS.get(LIST_SEVERITY.get(l,"LOW"),("#F1F5F9","#94A3B8","#64748B"))[1]};'
                f'padding:2px 10px;border-radius:20px;font-size:10px;font-weight:600;'
                f'margin-right:6px;font-family:Inter,sans-serif">{LIST_LABELS.get(l,l)}</span>'
                for l in lists
            ])
            st.markdown(
                f'<div class="rr-card" style="padding:14px 20px;margin-bottom:8px;border-left:4px solid {border}">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'<div>'
                f'<div style="font-size:15px;font-weight:600;color:#0F2645;font-family:Inter,sans-serif">'
                f'{country_name(j["jurisdiction_code"])}</div>'
                f'<div style="margin-top:6px">{severity_tags}</div>'
                f'</div>'
                f'<span style="background:{RISK_COLORS.get(j["risk_contribution"],("#F1F5F9","#94A3B8","#64748B"))[0]};'
                f'color:{text};border:1px solid {border};padding:4px 14px;border-radius:20px;'
                f'font-size:11px;font-weight:700;font-family:Inter,sans-serif;white-space:nowrap">'
                f'{j["risk_contribution"]} RISK</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Recommended Action
    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 6px 0;font-family:Inter,sans-serif">Recommended Action</div>', unsafe_allow_html=True)
    st.markdown(action_card(cls["recommended_action"]), unsafe_allow_html=True)

    # Compliance Narrative
    st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 6px 0;font-family:Inter,sans-serif">Compliance Narrative</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rr-narrative">{cls["narrative"]}</div>', unsafe_allow_html=True)

    # Data Quality
    if dq:
        st.markdown('<div style="font-size:13px;font-weight:600;color:#0F2645;margin:20px 0 6px 0;font-family:Inter,sans-serif">⚠️ Data Quality Flags</div>', unsafe_allow_html=True)
        st.caption("The following fields were missing or incomplete and may affect classification accuracy.")
        for f in dq:
            st.markdown(
                f'<span style="background:#FEF3C7;color:#92400E;border:1px solid #D97706;'
                f'padding:3px 10px;border-radius:20px;font-size:11px;margin:2px;'
                f'display:inline-block;font-family:Inter,sans-serif">⚠️ {f}</span>',
                unsafe_allow_html=True,
            )

    # Raw JSON
    with st.expander("🔧 Raw JSON Output — Technical"):
        st.code(cls["raw_response_json"], language="json")

    st.markdown(
        f'<div style="font-size:10px;color:#94A3B8;margin-top:20px;padding-top:12px;'
        f'border-top:1px solid #E2E8F0;font-family:Inter,sans-serif;line-height:1.7">'
        f'Classified: {str(cls["classified_at"])[:19]} · Prompt version: {cls["prompt_version"]}<br>'
        f'This output is generated by an AI system for academic and portfolio purposes only. '
        f'Human review by a licensed compliance officer is required before any real-world action.</div>',
        unsafe_allow_html=True,
    )
