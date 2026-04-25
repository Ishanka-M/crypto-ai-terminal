# ⚡ CryptoAI Terminal

**Binance + Gemini AI + ML Signals + SMC + Elliott Wave + Backtesting**

---

## ✅ Features

| Feature | Status |
|---|---|
| Multi-coin selection | ✅ |
| Live price dashboard | ✅ |
| AI signals (BUY/SELL) per coin | ✅ |
| Chart per coin with indicators | ✅ |
| Auto ML model training | ✅ |
| Clean dark UI | ✅ |
| SMC (Order Block + FVG) | ✅ |
| Elliott Wave auto detection | ✅ |
| News + sentiment filter | ✅ |
| Backtesting system | ✅ |
| Auto compounding strategy | ✅ |
| RSI, EMA, MACD, Bollinger | ✅ |
| ML model (XGBoost) | ✅ |
| Multi-timeframe | ✅ |
| Risk management | ✅ |
| Gemini API 7-key rotation | ✅ |

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/crypto-ai-terminal.git
cd crypto-ai-terminal
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

**Copy the secrets template:**
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

**Edit `.streamlit/secrets.toml`:**
```toml
[binance]
api_key = "your_binance_key"
api_secret = "your_binance_secret"

[gemini]
key_1 = "AIza..."
key_2 = "AIza..."
# ... up to key_7
```

**Also update `utils/gemini_rotator.py`** with your 7 Gemini keys in the `GEMINI_API_KEYS` list.

### 4. Run locally
```bash
streamlit run app.py
```

---

## ☁️ Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set `app.py` as the main file
5. In **App Settings → Secrets**, paste your secrets.toml contents
6. Click Deploy!

---

## 📁 Project Structure

```
crypto-ai-terminal/
├── app.py                  # Main Streamlit app
├── requirements.txt        # Python dependencies
├── .streamlit/
│   ├── config.toml         # UI theme config
│   └── secrets.toml.example
├── utils/
│   ├── binance_data.py     # Binance API fetcher
│   ├── indicators.py       # RSI, EMA, SMC, FVG, Elliott Wave
│   ├── ml_model.py         # XGBoost training & prediction
│   ├── charts.py           # Plotly charts
│   ├── gemini_rotator.py   # Gemini 7-key rotation
│   ├── news_fetcher.py     # Crypto news + sentiment
│   └── risk_manager.py     # Position sizing, SL/TP, compounding
└── models/                 # Saved ML models (auto-created)
```

---

## 🔑 Getting API Keys

### Binance API
1. Login to [binance.com](https://binance.com)
2. Profile → API Management → Create API
3. Enable **Read Only** permissions (no trading needed for analysis)

### Gemini API (7 keys for rotation)
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create API key (free tier has rate limits — that's why we use 7!)
3. Repeat 7 times with different Google accounts or projects

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. Crypto trading involves significant risk. Always do your own research. Not financial advice.
