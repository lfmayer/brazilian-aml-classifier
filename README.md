# 🔍 PLD Intelligence Agent — Brazilian AML Risk Classifier

> **⚠️ Disclaimer:** Academic and portfolio project. All transactions, clients, and financial
> data used here are **entirely fictitious and synthetically generated**. This project does not
> represent any real institution, does not use real customer data, and does not constitute a
> compliance or legal system.

---

## 📌 What is this?

A proof-of-concept AI agent that classifies financial transactions according to risk criteria
aligned with Brazilian AML regulation (Lei 9.613/1998, COAF resolutions, and Bacen normatives).
The agent uses Claude (Anthropic) as its reasoning engine, combined with Python, SQLite, and
Streamlit for data processing and interface.

The project simulates a workflow used by compliance analysts in Brazilian financial institutions:
receiving a batch of transactions, enriching them with contextual rules, and generating a
structured risk report with natural language justifications.

---

## 🎯 Motivation

Major global banks — JPMorgan, AIG, BMO — are already deploying Claude-based agents for AML
and financial crimes investigation, compressing analysis from days to minutes. This project
explores what a Brazilian adaptation of that workflow would look like, considering:

- The specific regulatory framework of Bacen and COAF
- The operational reality of Brazilian retail banking (Pix, TED, DOC patterns)
- The need for explainable outputs that a compliance officer can validate and sign off on

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| AI Engine | Claude API (Anthropic) — `claude-sonnet-4-6` |
| Data Processing | pandas, numpy |
| Interface | Streamlit |
| Synthetic Data | Faker (pt_BR locale) |
| Database | SQLite |
| Visualization | Plotly |

---

## ⚙️ How it works

```
[Faker — Synthetic Transactions]
        ↓
[SQLite — transactions table]
        ↓
[batch_runner.py]
        ↓
[Claude API] ← system_prompt_v2.txt (COAF/Bacen rules)
        ↓
[Risk Classification] → LOW / MEDIUM / HIGH / CRITICAL
        ↓
[SQLite — classifications, typologies, jurisdictions]
        ↓
[Streamlit Dashboard] → analyst review interface
```

---

## 🚀 Running locally

### 1. Clone and install

```bash
git clone https://github.com/your-username/aml-classifier.git
cd aml-classifier
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key:
# ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Generate synthetic data

```bash
python pipeline/faker_generator.py
# Creates data/synthetic_transactions.json with 100 transactions
```

### 4. Classify transactions

```bash
# Test first (no DB writes, no API cost):
python -m pipeline.batch_runner --limit 3 --dry-run

# Then classify for real (start small — each tx = 1 API call):
python -m pipeline.batch_runner --limit 20
```

### 5. Launch dashboard

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

---

## ☁️ Deploy to Streamlit Cloud (free)

The `outputs/results.db` is committed with pre-classified data so the dashboard works
immediately on Streamlit Cloud without any API calls.

### Step-by-step

**1. Fork or push to GitHub**
- Create a new public repository on github.com
- Push this entire project folder to it

**2. Create account on Streamlit Cloud**
- Go to [share.streamlit.io](https://share.streamlit.io)
- Sign in with your GitHub account

**3. Deploy the app**
- Click **"New app"**
- Select your repository, branch (`main`), and main file (`app.py`)
- Click **"Deploy"**

**4. Add secrets (optional — only needed if running batch_runner)**
- In the app dashboard → **Settings → Secrets**
- Add:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

**5. Done** — your app will be live at:
```
https://your-app-name.streamlit.app
```

---

## 📊 Dashboard pages

| Page | Description |
|---|---|
| 📊 Overview | KPIs, risk distribution donut, typology bar chart, score histogram, recent alerts |
| 🔎 Explorer | Filter and search all classified transactions with full narrative |
| 🌍 Jurisdiction Map | Choropleth of flagged jurisdictions by risk contribution |
| 📋 Detail View | Full breakdown: typologies, signals, jurisdiction flags, raw JSON |

---

## 🔬 Regulatory basis

| Regulation | Scope |
|---|---|
| Lei 9.613/1998 | Brazilian AML law — mandatory reporting threshold R$10,000 |
| Circular Bacen 3.978/2020 | KYC and transaction monitoring obligations |
| Resolução COAF 36/2021 | AML/CFT internal policy requirements |
| Resolução COAF 40/2021 | PEP definition and enhanced due diligence |
| IN RFB 1.037/2010 | Brazilian tax haven jurisdiction list |
| FATF Plenary Feb/2026 | Blacklist (Iran, North Korea, Myanmar) and Grey List |

---

## 🚧 Scope & Limitations

- 100% synthetic data — no real financial information used anywhere
- Not a production-ready compliance system
- Regulatory thresholds simplified for demonstration
- Claude outputs require review by a licensed compliance officer in real-world use

---

## 👤 Author

**Luís Filipe Mayer**
Senior Banking Professional | Data Analytics | Analytics Translator

15+ years in Brazilian financial services (Bradesco — Prime segment). Currently completing
a postgraduate degree in Business Analytics & Data-Driven Decision at FIAP PosTech.

This project bridges domain expertise in banking compliance with AI engineering —
demonstrating that the best analytical systems are built by people who understand
both the data and the business behind it.

[LinkedIn](https://linkedin.com/in/luisfilipemayer) · [GitHub](#)

---

## 📄 License

MIT License — free to use, adapt, and reference with attribution.
