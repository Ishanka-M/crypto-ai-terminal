# 📡 CryptoAI Terminal

Full-featured cryptocurrency trading analysis system with Gemini AI, Google Sheets integration, and auto trading signals.

## 🚀 Streamlit Cloud Deploy (5 minutes)

### Step 1 — Fork & Clone
```bash
git clone https://github.com/yourusername/crypto-ai-terminal.git
cd crypto-ai-terminal
```

### Step 2 — Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect GitHub repo
3. Set **Main file**: `app.py`
4. Click **Deploy**

### Step 3 — Add Secrets
In Streamlit Cloud → **App Settings** → **Secrets**, paste:

```toml
GEMINI_API_KEYS = "AIzaSy...key1,AIzaSy...key2"

BINANCE_API_KEY    = "your_key"
BINANCE_API_SECRET = "your_secret"

SPREADSHEET_ID = "your_sheet_id"

[gcp_service_account]
type         = "service_account"
project_id   = "your-project"
private_key  = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "name@project.iam.gserviceaccount.com"
# ... rest of service account JSON
```

---

## 🔑 Getting API Keys

### Gemini AI (Free)
1. Go to [aistudio.google.com](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Add multiple keys for rotation

### Google Sheets
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Sheets API** + **Drive API**
3. Create **Service Account** → Download JSON
4. Share your Google Sheet with the service account email

### Binance
1. Go to Binance → Account → API Management
2. Create API key (Read-only for data, Enable Trading for auto-trade)
3. Enable testnet for paper trading

---

## 📁 Project Structure

```
crypto-ai-terminal/
├── app.py                    ← Main Streamlit app
├── requirements.txt          ← All dependencies
├── utils/
│   ├── gemini_rotator.py     ← Gemini AI + key rotation
│   └── sheets_manager.py     ← Google Sheets CRUD
├── .streamlit/
│   ├── config.toml           ← Theme + server config
│   └── secrets.toml          ← Local secrets (never commit!)
└── README.md
```

---

## 📊 Features

| Tab | Features |
|-----|---------|
| 📊 Dashboard | Live prices, signal cards, 24h change |
| 📈 Chart | Candlestick + EMA + BB + RSI + Volume |
| 🎯 Signals | BUY/SELL/HOLD + SL/TP + confidence gauge |
| 🤖 AI Chat | Gemini AI analyst + quick prompts |
| 📉 Backtest | Equity curve + win rate + metrics |
| 📋 Sheets | Save/load keys + settings + trade log |
| ⚙️ Settings | All API keys + Gemini keys + GCP creds |

---

## 🛠 Local Development

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create local secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your keys

streamlit run app.py
```

---

## ⚠️ Fix: ModuleNotFoundError for google.generativeai

If you see this error on Streamlit Cloud:
```
ModuleNotFoundError: No module named 'google.generativeai'
```

**Solution:** Make sure `requirements.txt` contains:
```
google-generativeai>=0.5.0
```
Then go to **Manage App** → **Reboot app**.

---

> **Disclaimer:** Educational purposes only. Crypto trading involves significant risk.
