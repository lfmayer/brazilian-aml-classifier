"""
app.py
Streamlit dashboard for the Brazilian AML Risk Classifier.
Run: streamlit run app.py
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
    page_title="PLD Intelligence · AML Classifier",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# DESIGN TOKENS
# ─────────────────────────────────────────────
COLORS = {
    "bg":       "#0d1117",
    "surface":  "#161b22",
    "border":   "#30363d",
    "text":     "#c9d1d9",
    "muted":    "#8b949e",
    "LOW":      "#3fb950",
    "MEDIUM":   "#d29922",
    "HIGH":     "#f85149",
    "CRITICAL": "#ff7b72",
    "accent":   "#58a6ff",
}

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

BADGE_CSS = {
    "LOW":                  "background:#1a4731;color:#3fb950;border:1px solid #3fb950",
    "MEDIUM":               "background:#3d2c0a;color:#d29922;border:1px solid #d29922",
    "HIGH":                 "background:#3d1c1c;color:#f85149;border:1px solid #f85149",
    "CRITICAL":             "background:#5c1a1a;color:#ff7b72;border:1px solid #ff7b72",
    "MONITOR":              "background:#1a4731;color:#3fb950",
    "ESCALATE_FOR_REVIEW":  "background:#3d2c0a;color:#d29922",
    "COMMUNICATE_TO_COAF":  "background:#5c1a1a;color:#ff7b72",
    "TRIGGERED":            "background:#3d1c1c;color:#f85149",
    "NOT_TRIGGERED":        "background:#1a1f26;color:#484f58",
    "INSUFFICIENT_DATA":    "background:#2d2a1a;color:#d29922",
}

# ─────────────────────────────────────────────
# HUMAN-READABLE LABELS
# ─────────────────────────────────────────────
TYPOLOGY_LABELS = {
    "STRUCTURING":         "Structuring (Smurfing)",
    "ATYPICAL_FREQUENCY":  "Unusual Transaction Frequency",
    "HIGH_RISK_GEOGRAPHY": "High-Risk Jurisdiction",
    "PEP_INVOLVEMENT":     "Politically Exposed Person (PEP)",
}

TYPOLOGY_DESC = {
    "STRUCTURING":         "Transactions structured below the R$10,000 reporting threshold to avoid detection (Lei 9.613/1998, Art. 11).",
    "ATYPICAL_FREQUENCY":  "Number of transactions exceeds expected frequency for this customer profile (Circular Bacen 3.978/2020).",
    "HIGH_RISK_GEOGRAPHY": "Transaction involves a jurisdiction listed by FATF or the Brazilian tax authority (IN RFB 1.037/2010).",
    "PEP_INVOLVEMENT":     "Sender or receiver holds or held a relevant public office within the last 5 years (Resolução COAF 40/2021).",
}

ACTION_LABELS = {
    "MONITOR":              "✅ Routine Monitoring",
    "ESCALATE_FOR_REVIEW":  "⚠️ Escalate for Compliance Review",
    "COMMUNICATE_TO_COAF":  "🚨 Report to COAF — Art. 11, Lei 9.613/1998",
}

ACTION_DESC = {
    "MONITOR":              "No immediate action required. Continue standard transaction monitoring.",
    "ESCALATE_FOR_REVIEW":  "Forward to senior compliance officer for manual review before any action.",
    "COMMUNICATE_TO_COAF":  "Mandatory suspicious activity report to be filed with COAF within the legal deadline.",
}

PROFILE_LABELS = {
    "PF_STANDARD":   "Individual — Standard Profile",
    "PF_HIGH_INCOME": "Individual — High Income Profile",
    "PJ_SME":        "Legal Entity — Small/Medium Business",
    "PJ_LARGE":      "Legal Entity — Large Corporation",
    "UNKNOWN":       "Unknown Profile",
}

TX_TYPE_LABELS = {
    "PIX":              "PIX Transfer",
    "TED":              "TED Bank Transfer",
    "DOC":              "DOC Bank Transfer",
    "WIRE_TRANSFER":    "International Wire Transfer",
    "CASH_DEPOSIT":     "Cash Deposit",
    "CASH_WITHDRAWAL":  "Cash Withdrawal",
}

DIRECTION_LABELS = {
    "OUTBOUND": "⬆️ Outbound (sent)",
    "INBOUND":  "⬇️ Inbound (received)",
}

PARTY_TYPE_LABELS = {
    "CPF":   "Individual (CPF)",
    "CNPJ":  "Legal Entity (CNPJ)",
}

# Country names + flags
LIST_LABELS = {
    "FATF_BLACKLIST":  "FATF Blacklist 🔴",
    "FATF_GREYLIST":   "FATF Grey List 🟡",
    "RFB_TAX_HAVEN":   "RFB Tax Haven (IN 1.037/2010) 🟡",
}

COUNTRY_NAMES = {
    "BRA": "Brazil 🇧🇷", "USA": "United States 🇺🇸", "DEU": "Germany 🇩🇪",
    "GBR": "United Kingdom 🇬🇧", "FRA": "France 🇫🇷", "CAN": "Canada 🇨🇦",
    "AUS": "Australia 🇦🇺", "JPN": "Japan 🇯🇵", "CHE": "Switzerland 🇨🇭",
    "CYM": "Cayman Islands 🇰🇾", "PAN": "Panama 🇵🇦", "BHS": "Bahamas 🇧🇸",
    "BMU": "Bermuda 🇧🇲", "VGB": "British Virgin Islands 🇻🇬",
    "LIE": "Liechtenstein 🇱🇮", "MCO": "Monaco 🇲🇨", "AND": "Andorra 🇦🇩",
    "IRN": "Iran 🇮🇷", "PRK": "North Korea 🇰🇵", "MMR": "Myanmar 🇲🇲",
    "VEN": "Venezuela 🇻🇪", "NGA": "Nigeria 🇳🇬", "PHL": "Philippines 🇵🇭",
    "SYR": "Syria 🇸🇾", "YEM": "Yemen 🇾🇪", "LBN": "Lebanon 🇱🇧",
    "KEN": "Kenya 🇰🇪", "BOL": "Bolivia 🇧🇴", "HKG": "Hong Kong 🇭🇰",
    "LBR": "Liberia 🇱🇷", "MAC": "Macau 🇲🇴", "MUS": "Mauritius 🇲🇺",
    "SYC": "Seychelles 🇸🇨", "DZA": "Algeria 🇩🇿", "AGO": "Angola 🇦🇴",
    "BGR": "Bulgaria 🇧🇬", "CMR": "Cameroon 🇨🇲", "HRV": "Croatia 🇭🇷",
    "HTI": "Haiti 🇭🇹", "KWT": "Kuwait 🇰🇼", "MOZ": "Mozambique 🇲🇿",
    "NAM": "Namibia 🇳🇦", "NPL": "Nepal 🇳🇵", "TZA": "Tanzania 🇹🇿",
    "VNM": "Vietnam 🇻🇳", "MNG": "Mongolia 🇲🇳",
}

def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code, f"{code}")

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117 !important;
    color: #c9d1d9;
    font-family: 'Courier New', monospace;
  }
  [data-testid="stSidebar"] {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d;
  }
  h1, h2, h3 { color: #f0f6fc !important; letter-spacing: 0.03em; }
  h1 { font-size: 1.4rem !important; }
  [data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px 16px;
  }
  [data-testid="stMetricValue"] { color: #58a6ff !important; font-size: 2rem !important; }
  [data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.75rem !important; }
  [data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px;
  }
  hr { border-color: #30363d !important; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0d1117; }
  ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
  .flow-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .party-box {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
    font-size: 12px;
  }
  .arrow-box {
    text-align: center;
    font-size: 22px;
    color: #58a6ff;
    padding-top: 18px;
  }
  .amount-label {
    font-size: 11px;
    color: #8b949e;
    text-align: center;
  }
  .amount-value {
    font-size: 16px;
    font-weight: bold;
    color: #58a6ff;
    text-align: center;
  }
  .action-card {
    border-radius: 8px;
    padding: 14px 16px;
    margin: 10px 0;
    font-size: 13px;
    line-height: 1.6;
  }
  .reg-cite {
    font-size: 10px;
    color: #484f58;
    font-style: italic;
    margin-top: 4px;
  }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def badge(text: str, kind: str | None = None) -> str:
    key = kind or text
    style = BADGE_CSS.get(key, "background:#21262d;color:#8b949e")
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:12px;'
        f'font-size:11px;font-weight:bold;letter-spacing:.05em;{style}">{text}</span>'
    )

def score_bar(score: int) -> str:
    color = COLORS.get(
        "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    )
    label = "Low Risk" if score < 25 else "Medium Risk" if score < 50 else "High Risk" if score < 75 else "Critical Risk"
    return (
        f'<div style="margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#8b949e;margin-bottom:3px">'
        f'<span>Risk Score</span><span style="color:{color};font-weight:bold">{score}/100 — {label}</span></div>'
        f'<div style="background:#21262d;border-radius:4px;height:8px">'
        f'<div style="background:{color};height:8px;border-radius:4px;width:{score}%"></div>'
        f'</div></div>'
    )

def fmt_brl(value) -> str:
    if value is None:
        return "—"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def party_card(id_hash: str, party_type: str, jurisdiction: str, is_pep: bool, label: str) -> str:
    pep_tag = '<br><span style="background:#5c1a1a;color:#ff7b72;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:bold">⚠️ PEP</span>' if is_pep else ""
    return (
        f'<div class="party-box">'
        f'<div style="color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">{label}</div>'
        f'<div style="color:#f0f6fc;font-size:13px;font-weight:bold">{PARTY_TYPE_LABELS.get(party_type, party_type)}</div>'
        f'<div style="color:#58a6ff;font-size:11px;margin-top:2px">{country_name(jurisdiction)}</div>'
        f'<div style="color:#484f58;font-size:10px;margin-top:2px">ID: {id_hash[:16]}…</div>'
        f'{pep_tag}'
        f'</div>'
    )

def action_card(action: str) -> str:
    colors = {
        "MONITOR":             ("#1a4731", "#3fb950"),
        "ESCALATE_FOR_REVIEW": ("#3d2c0a", "#d29922"),
        "COMMUNICATE_TO_COAF": ("#5c1a1a", "#ff7b72"),
    }
    bg, fg = colors.get(action, ("#21262d", "#8b949e"))
    label = ACTION_LABELS.get(action, action)
    desc  = ACTION_DESC.get(action, "")
    return (
        f'<div class="action-card" style="background:{bg};border:1px solid {fg}">'
        f'<div style="color:{fg};font-weight:bold;font-size:14px">{label}</div>'
        f'<div style="color:#c9d1d9;font-size:12px;margin-top:6px">{desc}</div>'
        f'</div>'
    )

@st.cache_data(ttl=15)
def load_data():
    init_db()
    rows = fetch_classifications_df()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["transaction_timestamp"] = pd.to_datetime(df["transaction_timestamp"], utc=True)
    df["risk_level"] = pd.Categorical(df["risk_level"], categories=RISK_ORDER, ordered=True)
    return df

def plotly_defaults(fig):
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font_color="#c9d1d9", font_family="Courier New, monospace",
        margin=dict(l=12, r=12, t=32, b=12),
    )
    fig.update_xaxes(gridcolor="#21262d", zerolinecolor="#30363d")
    fig.update_yaxes(gridcolor="#21262d", zerolinecolor="#30363d")
    return fig


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 PLD Intelligence")
    st.markdown(
        '<p style="color:#8b949e;font-size:11px;margin-top:-8px">'
        "Brazilian AML Risk Classifier · Portfolio Project</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigation",
        ["📊 Overview", "🔎 Transaction Explorer", "🌍 Jurisdiction Map", "📋 Transaction Detail"],
        label_visibility="collapsed",
    )
    st.divider()

    summary = fetch_summary()
    st.markdown(
        f'<p style="color:#8b949e;font-size:11px">'
        f'🗄 {summary["total_transactions"]} transactions loaded<br>'
        f'✅ {summary["classified"]} classified<br>'
        f'⏳ {summary["pending"]} pending</p>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        '<p style="color:#484f58;font-size:10px;line-height:1.6">'
        "Synthetic data only.<br>Not a legal or compliance system.<br>"
        "For academic & portfolio use.</p>",
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
if page == "📊 Overview":
    st.markdown("## 📊 Overview")

    if no_data:
        st.info("No classified transactions yet. Run `batch_runner.py` to start.")
        st.stop()

    by_risk = df["risk_level"].value_counts()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Classified", len(df))
    k2.metric("🟢 Low Risk",      int(by_risk.get("LOW",      0)))
    k3.metric("🟡 Medium Risk",   int(by_risk.get("MEDIUM",   0)))
    k4.metric("🔴 High Risk",     int(by_risk.get("HIGH",     0)))
    k5.metric("🔥 Critical",      int(by_risk.get("CRITICAL", 0)))

    # CRITICAL alerts banner
    criticals = df[df["risk_level"] == "CRITICAL"]
    if not criticals.empty:
        st.markdown(
            f'<div style="background:#5c1a1a;border:1px solid #ff7b72;border-radius:8px;'
            f'padding:14px 18px;margin:16px 0">'
            f'<span style="color:#ff7b72;font-weight:bold;font-size:14px">'
            f'🚨 {len(criticals)} CRITICAL alert(s) require immediate attention — '
            f'Report to COAF (Art. 11, Lei 9.613/1998)</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### Risk Distribution")
        counts = df["risk_level"].value_counts().reindex(RISK_ORDER).fillna(0)
        fig = go.Figure(go.Pie(
            labels=counts.index.tolist(),
            values=counts.values.tolist(),
            hole=0.55,
            marker_colors=[COLORS[r] for r in counts.index],
            textinfo="label+percent",
            textfont_size=11,
        ))
        plotly_defaults(fig)
        fig.update_layout(showlegend=False, height=280)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("##### Triggered Risk Indicators")
        typo_data = fetch_typology_counts()
        if typo_data:
            tdf = pd.DataFrame(typo_data)
            tdf["label"] = tdf["typology"].map(lambda x: TYPOLOGY_LABELS.get(x, x))
            fig2 = px.bar(
                tdf, x="n", y="label", orientation="h",
                color_discrete_sequence=[COLORS["accent"]],
            )
            plotly_defaults(fig2)
            fig2.update_layout(
                height=280, xaxis_title="", yaxis_title="",
                yaxis=dict(categoryorder="total ascending"),
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("##### Risk Score Distribution")
    fig3 = px.histogram(
        df, x="risk_score", nbins=20,
        color="risk_level",
        color_discrete_map={r: COLORS[r] for r in RISK_ORDER},
        category_orders={"risk_level": RISK_ORDER},
    )
    plotly_defaults(fig3)
    fig3.update_layout(height=200, xaxis_title="Score (0–100)", yaxis_title="Transactions", bargap=0.05)
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.markdown("##### Latest HIGH / CRITICAL Alerts")
    alerts = df[df["risk_level"].isin(["HIGH", "CRITICAL"])].head(8)
    if alerts.empty:
        st.caption("No high-risk transactions classified yet.")
    else:
        for _, row in alerts.iterrows():
            action_label = ACTION_LABELS.get(row["recommended_action"], row["recommended_action"])
            tx_label = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
            with st.expander(
                f"{row['transaction_id']}  ·  {row['risk_level']}  ·  "
                f"{fmt_brl(row['amount_brl'])}  ·  {tx_label}"
            ):
                c1, c2 = st.columns([1, 2])
                c1.markdown(badge(row["risk_level"]), unsafe_allow_html=True)
                c1.markdown(score_bar(row["risk_score"]), unsafe_allow_html=True)
                c1.markdown(
                    f'<div style="font-size:11px;color:#8b949e;margin-top:6px">'
                    f'{DIRECTION_LABELS.get(row["direction"], row["direction"])}<br>'
                    f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}</div>',
                    unsafe_allow_html=True,
                )
                c2.markdown(
                    f'<div style="background:#0d1117;border-left:3px solid #ff7b72;'
                    f'padding:10px;border-radius:0 4px 4px 0;font-size:12px;line-height:1.7">'
                    f'{row["narrative"]}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 2 — TRANSACTION EXPLORER
# ═════════════════════════════════════════════
elif page == "🔎 Transaction Explorer":
    st.markdown("## 🔎 Transaction Explorer")

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
    search = f3.text_input("Search by Transaction ID or keyword", placeholder="TXN-… or keyword")

    filtered = df[df["risk_level"].isin(risk_filter) & df["recommended_action"].isin(action_filter)]
    if search:
        mask = (
            filtered["transaction_id"].str.contains(search, case=False, na=False) |
            filtered["narrative"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.caption(f"{len(filtered)} transaction(s) shown")

    for _, row in filtered.iterrows():
        tx_label    = TX_TYPE_LABELS.get(row["transaction_type"], row["transaction_type"])
        action_label = ACTION_LABELS.get(row["recommended_action"], row["recommended_action"])
        risk_color  = COLORS.get(str(row["risk_level"]), "#8b949e")

        with st.expander(
            f"{row['transaction_id']}  ·  {row['risk_level']}  ·  "
            f"{fmt_brl(row['amount_brl'])}  ·  {tx_label}",
            expanded=False,
        ):
            # Transaction flow
            col_s, col_a, col_r = st.columns([5, 2, 5])
            with col_s:
                st.markdown(
                    party_card(
                        "identity-protected", "CPF",
                        row["sender_jurisdiction"], bool(row["sender_is_pep"]), "Sender"
                    ),
                    unsafe_allow_html=True,
                )
            with col_a:
                st.markdown(
                    f'<div class="arrow-box">→</div>'
                    f'<div class="amount-label">{tx_label}</div>'
                    f'<div class="amount-value">{fmt_brl(row["amount_brl"])}</div>'
                    f'<div class="amount-label">{DIRECTION_LABELS.get(row["direction"], row["direction"])}</div>',
                    unsafe_allow_html=True,
                )
            with col_r:
                st.markdown(
                    party_card(
                        "identity-protected", "CPF",
                        row["receiver_jurisdiction"], bool(row["receiver_is_pep"]), "Receiver"
                    ),
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

            # Risk + narrative
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(badge(str(row["risk_level"])), unsafe_allow_html=True)
                st.markdown(score_bar(row["risk_score"]), unsafe_allow_html=True)
                st.markdown(
                    f'<div style="font-size:11px;color:#8b949e;margin-top:6px">'
                    f'{PROFILE_LABELS.get(row["customer_profile"], row["customer_profile"])}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f'<div style="background:#0d1117;border-left:3px solid #58a6ff;'
                    f'padding:12px;border-radius:0 4px 4px 0;font-size:12px;line-height:1.7">'
                    f'<strong style="color:#8b949e;font-size:10px">COMPLIANCE NARRATIVE</strong><br>'
                    f'{row["narrative"]}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown(action_card(row["recommended_action"]), unsafe_allow_html=True)


# ═════════════════════════════════════════════
# PAGE 3 — JURISDICTION MAP
# ═════════════════════════════════════════════
elif page == "🌍 Jurisdiction Map":
    st.markdown("## 🌍 Jurisdiction Flags")
    st.caption("Countries involved in flagged transactions, classified by risk list membership.")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    hits = fetch_jurisdiction_hits()
    if not hits:
        st.caption("No jurisdiction flags found.")
        st.stop()

    jdf = pd.DataFrame(hits)

    color_map = {"HIGH": COLORS["HIGH"], "MEDIUM": COLORS["MEDIUM"], "LOW": COLORS["LOW"]}
    fig = px.choropleth(
        jdf,
        locations="jurisdiction_code",
        locationmode="ISO-3",
        color="risk_contribution",
        color_discrete_map=color_map,
        hover_name="jurisdiction_code",
        hover_data={"n": True, "risk_contribution": True},
        title="Flagged jurisdictions by risk contribution",
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True, coastlinecolor="#30363d",
        showland=True, landcolor="#161b22",
        showocean=True, oceancolor="#0d1117",
        projection_type="natural earth",
    )
    plotly_defaults(fig)
    fig.update_layout(height=420, title_font_size=13)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("##### Flagged Jurisdictions — Detail")

    for _, row in jdf.iterrows():
        risk_color = COLORS.get(row["risk_contribution"], "#8b949e")
        full_name  = country_name(row["jurisdiction_code"])
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'padding:10px 0;border-bottom:1px solid #21262d">'
            f'<span style="color:#58a6ff;font-weight:bold;font-size:14px;min-width:200px">{full_name}</span>'
            f'<span style="color:{risk_color};font-size:11px;font-weight:bold">{row["risk_contribution"]} RISK</span>'
            f'<span style="color:#8b949e;font-size:11px">{row["n"]} transaction(s) flagged</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 4 — TRANSACTION DETAIL
# ═════════════════════════════════════════════
elif page == "📋 Transaction Detail":
    st.markdown("## 📋 Transaction Detail")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    tx_ids   = df["transaction_id"].tolist()
    selected = st.selectbox("Select a transaction to inspect", tx_ids)

    detail = fetch_classification_detail(selected)
    if not detail:
        st.error("Detail not found.")
        st.stop()

    tx   = detail["transaction"]
    cls  = detail["classification"]
    typos = detail["typologies"]
    juris = detail["jurisdictions"]
    dq    = detail["dq_flags"]

    # ── Executive Summary ────────────────────
    risk_color = COLORS.get(cls["risk_level"], "#8b949e")
    st.markdown(
        f'<div style="background:#161b22;border:1px solid {risk_color};'
        f'border-radius:10px;padding:18px 22px;margin-bottom:16px">'
        f'<div style="color:#8b949e;font-size:11px;text-transform:uppercase;'
        f'letter-spacing:.08em;margin-bottom:6px">Executive Summary</div>'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">'
        f'<span style="color:{risk_color};font-size:22px;font-weight:bold">'
        f'{cls["risk_level"]} RISK</span>'
        f'<span style="color:#58a6ff;font-size:18px;font-weight:bold">'
        f'Score: {cls["risk_score"]}/100</span>'
        f'<span style="color:#c9d1d9;font-size:13px">{selected}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Transaction Flow ─────────────────────
    st.markdown("##### Transaction Flow")
    col_s, col_a, col_r = st.columns([5, 2, 5])
    with col_s:
        st.markdown(
            party_card(
                tx["sender_id_hash"], tx["sender_type"],
                tx["sender_jurisdiction"], bool(tx["sender_is_pep"]), "Sender"
            ),
            unsafe_allow_html=True,
        )
    with col_a:
        tx_label = TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"])
        st.markdown(
            f'<div class="arrow-box">→</div>'
            f'<div class="amount-label">{tx_label}</div>'
            f'<div class="amount-value">{fmt_brl(tx["amount_brl"])}</div>'
            f'<div class="amount-label">{DIRECTION_LABELS.get(tx["direction"], tx["direction"])}</div>',
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            party_card(
                tx["receiver_id_hash"], tx["receiver_type"],
                tx["receiver_jurisdiction"], bool(tx["receiver_is_pep"]), "Receiver"
            ),
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Transaction Details ───────────────────
    left, right = st.columns(2)
    with left:
        st.markdown("##### Transaction Details")
        fields = {
            "Type":             TX_TYPE_LABELS.get(tx["transaction_type"], tx["transaction_type"]),
            "Direction":        DIRECTION_LABELS.get(tx["direction"], tx["direction"]),
            "Amount":           fmt_brl(tx["amount_brl"]),
            "Customer Profile": PROFILE_LABELS.get(tx["customer_profile"], tx["customer_profile"]),
            "Date / Time":      tx["transaction_timestamp"],
            "Purpose":          tx["purpose_description"] or "⚠️ Not provided",
        }
        for k, v in fields.items():
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:7px 0;border-bottom:1px solid #21262d;font-size:12px">'
                f'<span style="color:#8b949e">{k}</span>'
                f'<span style="color:#c9d1d9">{v}</span></div>',
                unsafe_allow_html=True,
            )

    with right:
        st.markdown("##### Transaction Frequency")
        freq_threshold = {"PF_STANDARD": 5, "PF_HIGH_INCOME": 15, "PJ_SME": 25, "PJ_LARGE": 60}
        threshold = freq_threshold.get(tx["customer_profile"], 5)

        for k, v, warn in [
            ("Transactions in last 24h", tx["transactions_last_24h"],
             tx["transactions_last_24h"] > threshold),
            ("Transactions in last 72h", tx["transactions_last_72h"],
             tx["transactions_last_72h"] > threshold * 2),
            ("Total amount in last 72h", fmt_brl(tx["total_amount_last_72h_brl"]),
             tx["total_amount_last_72h_brl"] > 10000),
            ("Average monthly amount", fmt_brl(tx["avg_monthly_amount_brl"]), False),
        ]:
            flag = " ⚠️" if warn else ""
            color = "#f85149" if warn else "#c9d1d9"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:7px 0;border-bottom:1px solid #21262d;font-size:12px">'
                f'<span style="color:#8b949e">{k}</span>'
                f'<span style="color:{color}">{v}{flag}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="font-size:10px;color:#484f58;margin-top:6px">'
            f'Expected daily threshold for {PROFILE_LABELS.get(tx["customer_profile"], tx["customer_profile"])}: '
            f'{threshold} transactions/day</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Risk Indicators ───────────────────────
    st.markdown("##### Risk Indicators")
    for t in typos:
        signals = json.loads(t["signals_identified"]) if isinstance(t["signals_identified"], str) else t["signals_identified"]
        is_triggered = t["status"] == "TRIGGERED"
        label = TYPOLOGY_LABELS.get(t["typology"], t["typology"])
        desc  = TYPOLOGY_DESC.get(t["typology"], "")

        with st.expander(
            f"{'🔴' if is_triggered else '⚪'} {label} — {t['status'].replace('_', ' ')}",
            expanded=is_triggered,
        ):
            st.markdown(
                f'<div style="color:#8b949e;font-size:11px;margin-bottom:8px">{desc}</div>',
                unsafe_allow_html=True,
            )
            if signals:
                for s in signals:
                    st.markdown(
                        f'<div style="background:#21262d;border-left:3px solid #f85149;'
                        f'padding:8px 12px;margin:4px 0;border-radius:0 4px 4px 0;font-size:12px;color:#c9d1d9">'
                        f'⚑ {s}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="color:#484f58;font-size:11px">No signals identified for this indicator.</div>',
                    unsafe_allow_html=True,
                )

    # ── Jurisdiction Flags ────────────────────
    if juris:
        st.divider()
        st.markdown("##### Jurisdiction Flags")
        for j in juris:
            lists = json.loads(j["list_membership"]) if isinstance(j["list_membership"], str) else j["list_membership"]
            if not lists:
                continue
            risk_color = COLORS.get(j["risk_contribution"], "#8b949e")
            list_labels = [LIST_LABELS.get(l, l) for l in lists]
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                f'padding:12px 16px;margin:6px 0">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span style="color:#58a6ff;font-weight:bold;font-size:14px">{country_name(j["jurisdiction_code"])}</span>'
                f'<span style="color:{risk_color};font-weight:bold;font-size:12px">{j["risk_contribution"]} RISK</span>'
                f'</div>'
                f'<div style="color:#8b949e;font-size:11px;margin-top:4px">'
                f'Listed on: {" · ".join(list_labels)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Recommended Action ────────────────────
    st.divider()
    st.markdown("##### Recommended Action")
    st.markdown(action_card(cls["recommended_action"]), unsafe_allow_html=True)

    # ── Compliance Narrative ──────────────────
    st.divider()
    st.markdown("##### Compliance Narrative")
    st.markdown(
        f'<div style="background:#0d1117;border-left:3px solid #58a6ff;'
        f'padding:16px;border-radius:0 4px 4px 0;font-size:13px;line-height:1.9;color:#c9d1d9">'
        f'{cls["narrative"]}</div>',
        unsafe_allow_html=True,
    )

    # ── Data Quality ──────────────────────────
    if dq:
        st.divider()
        st.markdown("##### ⚠️ Data Quality Flags")
        st.caption("The following fields were missing or incomplete, which may affect classification accuracy.")
        for f in dq:
            st.markdown(
                f'<span style="background:#3d2c0a;color:#d29922;padding:3px 10px;'
                f'border-radius:4px;font-size:11px;margin:2px;display:inline-block">'
                f'⚠️ {f}</span>',
                unsafe_allow_html=True,
            )

    # ── Raw JSON ──────────────────────────────
    with st.expander("🔧 Raw JSON Output (technical)"):
        st.code(cls["raw_response_json"], language="json")

    st.markdown(
        f'<p style="color:#484f58;font-size:10px;margin-top:16px;'
        f'border-top:1px solid #21262d;padding-top:10px">'
        f'Classified: {cls["classified_at"]} · Prompt version: {cls["prompt_version"]}<br>'
        f'This output is generated by an AI system for academic and portfolio purposes only. '
        f'Human review by a licensed compliance officer is required before any real-world action.</p>',
        unsafe_allow_html=True,
    )
