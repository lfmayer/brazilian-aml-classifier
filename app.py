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
# THEME TOKENS  (matches the HTML tester palette)
# ─────────────────────────────────────────────
COLORS = {
    "bg":        "#0d1117",
    "surface":   "#161b22",
    "border":    "#30363d",
    "text":      "#c9d1d9",
    "muted":     "#8b949e",
    "LOW":       "#3fb950",
    "MEDIUM":    "#d29922",
    "HIGH":      "#f85149",
    "CRITICAL":  "#ff7b72",
    "accent":    "#58a6ff",
}

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

BADGE_CSS = {
    "LOW":      "background:#1a4731;color:#3fb950;border:1px solid #3fb950",
    "MEDIUM":   "background:#3d2c0a;color:#d29922;border:1px solid #d29922",
    "HIGH":     "background:#3d1c1c;color:#f85149;border:1px solid #f85149",
    "CRITICAL": "background:#5c1a1a;color:#ff7b72;border:1px solid #ff7b72",
    "MONITOR":              "background:#1a4731;color:#3fb950",
    "ESCALATE_FOR_REVIEW":  "background:#3d2c0a;color:#d29922",
    "COMMUNICATE_TO_COAF":  "background:#5c1a1a;color:#ff7b72",
    "TRIGGERED":            "background:#3d1c1c;color:#f85149",
    "NOT_TRIGGERED":        "background:#1a1f26;color:#484f58",
    "INSUFFICIENT_DATA":    "background:#2d2a1a;color:#d29922",
}

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117 !important;
    color: #c9d1d9;
    font-family: 'Courier New', monospace;
  }
  [data-testid="stSidebar"] {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d;
  }
  /* Headings */
  h1, h2, h3 { color: #f0f6fc !important; letter-spacing: 0.03em; }
  h1 { font-size: 1.4rem !important; }
  /* Metric cards */
  [data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px 16px;
  }
  [data-testid="stMetricValue"] { color: #58a6ff !important; font-size: 2rem !important; }
  [data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.75rem !important; }
  /* Dataframe */
  [data-testid="stDataFrame"] { border: 1px solid #30363d; border-radius: 6px; }
  /* Expander */
  [data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px;
  }
  /* Selectbox / pills */
  .stSelectbox label, .stMultiSelect label { color: #8b949e !important; font-size: 0.75rem; }
  /* Divider */
  hr { border-color: #30363d !important; }
  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0d1117; }
  ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def badge(text: str, kind: str | None = None) -> str:
    key = kind or text
    style = BADGE_CSS.get(key, "background:#21262d;color:#8b949e")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:11px;font-weight:bold;letter-spacing:.05em;{style}">{text}</span>'
    )


def score_bar(score: int) -> str:
    color = COLORS.get(
        "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
    )
    return (
        f'<div style="background:#21262d;border-radius:4px;height:6px;width:100%">'
        f'<div style="background:{color};height:6px;border-radius:4px;width:{score}%"></div>'
        f'</div><span style="font-size:10px;color:{color}">{score}/100</span>'
    )


def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(ttl=15)
def load_data():
    init_db()
    rows = fetch_classifications_df()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["transaction_timestamp"] = pd.to_datetime(df["transaction_timestamp"], utc=True)
    df["classified_at"] = pd.to_datetime(df["classified_at"], utc=True)
    df["risk_level"] = pd.Categorical(df["risk_level"], categories=RISK_ORDER, ordered=True)
    return df


def plotly_defaults(fig):
    fig.update_layout(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font_color="#c9d1d9",
        font_family="Courier New, monospace",
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
        ["📊 Overview", "🔎 Transaction Explorer", "🌍 Jurisdiction Map", "📋 Detail View"],
        label_visibility="collapsed",
    )
    st.divider()

    summary = fetch_summary()
    st.markdown(
        f'<p style="color:#8b949e;font-size:11px">'
        f'🗄 {summary["total_transactions"]} transactions<br>'
        f'✅ {summary["classified"]} classified<br>'
        f'⏳ {summary["pending"]} pending</p>',
        unsafe_allow_html=True,
    )

    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        '<p style="color:#484f58;font-size:10px;line-height:1.5">'
        "Synthetic data only.<br>Not a legal or compliance system.<br>"
        "Academic & portfolio use.</p>",
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

    # ── KPI row ──────────────────────────────
    by_risk = df["risk_level"].value_counts()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total classified",  len(df))
    k2.metric("🟢 LOW",     int(by_risk.get("LOW",      0)))
    k3.metric("🟡 MEDIUM",  int(by_risk.get("MEDIUM",   0)))
    k4.metric("🔴 HIGH",    int(by_risk.get("HIGH",     0)))
    k5.metric("🔥 CRITICAL",int(by_risk.get("CRITICAL", 0)))

    st.divider()

    col_left, col_right = st.columns([1, 1])

    # ── Risk donut ────────────────────────────
    with col_left:
        st.markdown("##### Risk distribution")
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

    # ── Typology bar ──────────────────────────
    with col_right:
        st.markdown("##### Triggered typologies")
        typo_data = fetch_typology_counts()
        if typo_data:
            tdf = pd.DataFrame(typo_data)
            fig2 = px.bar(
                tdf, x="n", y="typology", orientation="h",
                color_discrete_sequence=[COLORS["accent"]],
            )
            plotly_defaults(fig2)
            fig2.update_layout(
                height=280,
                xaxis_title="", yaxis_title="",
                yaxis=dict(categoryorder="total ascending"),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.caption("No typology data yet.")

    st.divider()

    # ── Score distribution ────────────────────
    st.markdown("##### Risk score distribution")
    fig3 = px.histogram(
        df, x="risk_score", nbins=20,
        color="risk_level",
        color_discrete_map={r: COLORS[r] for r in RISK_ORDER},
        category_orders={"risk_level": RISK_ORDER},
    )
    plotly_defaults(fig3)
    fig3.update_layout(height=220, xaxis_title="Score (0–100)", yaxis_title="Count", bargap=0.05)
    st.plotly_chart(fig3, use_container_width=True)

    # ── Recent HIGH/CRITICAL ──────────────────
    st.markdown("##### Latest HIGH / CRITICAL alerts")
    alerts = df[df["risk_level"].isin(["HIGH", "CRITICAL"])].head(8)
    if alerts.empty:
        st.caption("No high-risk transactions classified yet.")
    else:
        for _, row in alerts.iterrows():
            cols = st.columns([2, 1.2, 1.5, 1.5, 4])
            cols[0].markdown(
                f'<span style="color:#58a6ff;font-size:12px">{row["transaction_id"]}</span>',
                unsafe_allow_html=True,
            )
            cols[1].markdown(badge(row["risk_level"]), unsafe_allow_html=True)
            cols[2].markdown(
                f'<span style="color:#c9d1d9;font-size:12px">{fmt_brl(row["amount_brl"])}</span>',
                unsafe_allow_html=True,
            )
            cols[3].markdown(
                f'<span style="color:#8b949e;font-size:11px">{row["transaction_type"]}</span>',
                unsafe_allow_html=True,
            )
            cols[4].markdown(
                f'<span style="color:#8b949e;font-size:11px">{row["narrative"][:120]}…</span>',
                unsafe_allow_html=True,
            )


# ═════════════════════════════════════════════
# PAGE 2 — TRANSACTION EXPLORER
# ═════════════════════════════════════════════
elif page == "🔎 Transaction Explorer":
    st.markdown("## 🔎 Transaction Explorer")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    # ── Filters ──────────────────────────────
    f1, f2, f3 = st.columns([1, 1, 2])
    risk_filter = f1.multiselect(
        "Risk level", RISK_ORDER, default=RISK_ORDER,
    )
    action_filter = f2.multiselect(
        "Recommended action",
        ["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
        default=["MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"],
    )
    search = f3.text_input("Search transaction ID or narrative", placeholder="TXN-… or keyword")

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

    st.caption(f"{len(filtered)} transactions shown")

    # ── Table ─────────────────────────────────
    for _, row in filtered.iterrows():
        with st.expander(
            f"{row['transaction_id']}  ·  {row['risk_level']}  ·  "
            f"{fmt_brl(row['amount_brl'])}  ·  {row['transaction_type']}",
            expanded=False,
        ):
            c1, c2, c3 = st.columns([1, 1, 2])
            c1.markdown(badge(row["risk_level"]), unsafe_allow_html=True)
            c1.markdown(score_bar(row["risk_score"]), unsafe_allow_html=True)
            c2.markdown(badge(row["recommended_action"]), unsafe_allow_html=True)
            c2.markdown(
                f'<span style="color:#8b949e;font-size:11px">Profile: {row["customer_profile"]}</span>',
                unsafe_allow_html=True,
            )
            c3.markdown(
                f'<div style="background:#0d1117;border-left:3px solid #58a6ff;'
                f'padding:10px;border-radius:0 4px 4px 0;font-size:12px;line-height:1.6">'
                f'{row["narrative"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<p style="color:#484f58;font-size:10px;margin-top:4px">'
                f'Sender: {row["sender_jurisdiction"]} · '
                f'Receiver: {row["receiver_jurisdiction"]} · '
                f'Direction: {row["direction"]} · '
                f'PEP: {"✓ sender" if row["sender_is_pep"] else ""}'
                f'{"✓ receiver" if row["receiver_is_pep"] else ""}'
                f'{"—" if not row["sender_is_pep"] and not row["receiver_is_pep"] else ""}'
                f'</p>',
                unsafe_allow_html=True,
            )


# ═════════════════════════════════════════════
# PAGE 3 — JURISDICTION MAP
# ═════════════════════════════════════════════
elif page == "🌍 Jurisdiction Map":
    st.markdown("## 🌍 Jurisdiction Flags")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    hits = fetch_jurisdiction_hits()
    if not hits:
        st.caption("No jurisdiction flags found in classified transactions.")
        st.stop()

    jdf = pd.DataFrame(hits)

    # ── Choropleth ────────────────────────────
    color_map = {"HIGH": COLORS["HIGH"], "MEDIUM": COLORS["MEDIUM"], "LOW": COLORS["LOW"]}
    fig = px.choropleth(
        jdf,
        locations="jurisdiction_code",
        locationmode="ISO-3",
        color="risk_contribution",
        color_discrete_map=color_map,
        hover_name="jurisdiction_code",
        hover_data={"n": True, "risk_contribution": True},
        title="Jurisdictions flagged in classified transactions",
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=True, coastlinecolor="#30363d",
        showland=True, landcolor="#161b22",
        showocean=True, oceancolor="#0d1117",
        showlakes=False,
        projection_type="natural earth",
    )
    plotly_defaults(fig)
    fig.update_layout(height=420, title_font_size=13)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Table ────────────────────────────────
    st.markdown("##### Detail")
    for _, row in jdf.iterrows():
        c1, c2, c3 = st.columns([1, 1, 1])
        c1.markdown(
            f'<span style="color:#58a6ff;font-size:13px;font-weight:bold">{row["jurisdiction_code"]}</span>',
            unsafe_allow_html=True,
        )
        c2.markdown(badge(row["risk_contribution"]), unsafe_allow_html=True)
        c3.markdown(
            f'<span style="color:#8b949e;font-size:12px">{row["n"]} transaction(s) flagged</span>',
            unsafe_allow_html=True,
        )


# ═════════════════════════════════════════════
# PAGE 4 — DETAIL VIEW
# ═════════════════════════════════════════════
elif page == "📋 Detail View":
    st.markdown("## 📋 Transaction Detail")

    if no_data:
        st.info("No classified transactions yet.")
        st.stop()

    tx_ids = df["transaction_id"].tolist()
    selected = st.selectbox("Select transaction", tx_ids)

    detail = fetch_classification_detail(selected)
    if not detail:
        st.error("Detail not found.")
        st.stop()

    tx  = detail["transaction"]
    cls = detail["classification"]
    typos = detail["typologies"]
    juris = detail["jurisdictions"]
    dq    = detail["dq_flags"]

    # ── Header ───────────────────────────────
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.markdown(
        f'<span style="color:#58a6ff;font-size:18px;font-weight:bold">{selected}</span>',
        unsafe_allow_html=True,
    )
    h2.markdown(badge(cls["risk_level"]), unsafe_allow_html=True)
    h3.markdown(badge(cls["recommended_action"]), unsafe_allow_html=True)

    st.markdown(score_bar(cls["risk_score"]), unsafe_allow_html=True)
    st.divider()

    left, right = st.columns(2)

    # ── Transaction info ──────────────────────
    with left:
        st.markdown("##### Transaction")
        fields = {
            "Type":      tx["transaction_type"],
            "Direction": tx["direction"],
            "Amount":    fmt_brl(tx["amount_brl"]),
            "Profile":   tx["customer_profile"],
            "Timestamp": tx["transaction_timestamp"],
            "Purpose":   tx["purpose_description"] or "—",
        }
        for k, v in fields.items():
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:5px 0;border-bottom:1px solid #21262d;font-size:12px">'
                f'<span style="color:#8b949e">{k}</span>'
                f'<span style="color:#c9d1d9">{v}</span></div>',
                unsafe_allow_html=True,
            )

    # ── Parties ───────────────────────────────
    with right:
        st.markdown("##### Parties")
        for label, id_hash, jur, is_pep in [
            ("Sender", tx["sender_id_hash"], tx["sender_jurisdiction"], tx["sender_is_pep"]),
            ("Receiver", tx["receiver_id_hash"], tx["receiver_jurisdiction"], tx["receiver_is_pep"]),
        ]:
            pep_tag = ' <span style="background:#5c1a1a;color:#ff7b72;padding:1px 6px;border-radius:3px;font-size:10px">PEP</span>' if is_pep else ""
            st.markdown(
                f'<div style="padding:8px 0;border-bottom:1px solid #21262d;font-size:12px">'
                f'<span style="color:#8b949e">{label}</span>{pep_tag}<br>'
                f'<span style="color:#58a6ff">{id_hash}</span> · '
                f'<span style="color:#c9d1d9">{jur}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("##### Frequency")
        for k, v in {
            "Tx last 24h": tx["transactions_last_24h"],
            "Tx last 72h": tx["transactions_last_72h"],
            "Total 72h":   fmt_brl(tx["total_amount_last_72h_brl"]),
            "Avg monthly": fmt_brl(tx["avg_monthly_amount_brl"]) if tx["avg_monthly_amount_brl"] else "—",
        }.items():
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:4px 0;font-size:12px">'
                f'<span style="color:#8b949e">{k}</span>'
                f'<span style="color:#c9d1d9">{v}</span></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Typologies ────────────────────────────
    st.markdown("##### Typology scan")
    for t in typos:
        signals = json.loads(t["signals_identified"]) if isinstance(t["signals_identified"], str) else t["signals_identified"]
        with st.expander(f"{t['typology']}  ·  {t['status']}", expanded=(t["status"] == "TRIGGERED")):
            st.markdown(badge(t["status"]), unsafe_allow_html=True)
            if signals:
                for s in signals:
                    st.markdown(
                        f'<span style="color:#d29922;font-size:11px">⚑ {s}</span>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown('<span style="color:#484f58;font-size:11px">No signals identified.</span>', unsafe_allow_html=True)

    # ── Jurisdiction flags ────────────────────
    if juris:
        st.markdown("##### Jurisdiction flags")
        for j in juris:
            lists = json.loads(j["list_membership"]) if isinstance(j["list_membership"], str) else j["list_membership"]
            st.markdown(
                f'<div style="padding:6px 0;border-bottom:1px solid #21262d;font-size:12px">'
                f'<span style="color:#58a6ff;font-weight:bold">{j["jurisdiction_code"]}</span> · '
                f'<span style="color:#8b949e">{", ".join(lists)}</span> · '
                + badge(j["risk_contribution"]) +
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Narrative ─────────────────────────────
    st.divider()
    st.markdown("##### Narrative")
    st.markdown(
        f'<div style="background:#0d1117;border-left:3px solid #58a6ff;'
        f'padding:14px;border-radius:0 4px 4px 0;font-size:13px;line-height:1.8;color:#c9d1d9">'
        f'{cls["narrative"]}</div>',
        unsafe_allow_html=True,
    )

    # ── Data quality flags ────────────────────
    if dq:
        st.markdown("##### Data quality flags")
        for f in dq:
            st.markdown(
                f'<span style="background:#3d2c0a;color:#d29922;padding:2px 8px;'
                f'border-radius:4px;font-size:11px;margin:2px;display:inline-block">{f}</span>',
                unsafe_allow_html=True,
            )

    # ── Raw JSON ──────────────────────────────
    with st.expander("Raw JSON output"):
        st.code(cls["raw_response_json"], language="json")

    st.markdown(
        f'<p style="color:#484f58;font-size:10px;margin-top:16px;border-top:1px solid #21262d;padding-top:8px">'
        f'Classified at {cls["classified_at"]} · Prompt version {cls["prompt_version"]}<br>'
        f'This output is generated by an AI system for academic and portfolio purposes only. '
        f'Human review by a licensed compliance officer is required before any real-world action.</p>',
        unsafe_allow_html=True,
    )
