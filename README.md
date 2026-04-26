# 📊 CryptoAI Trader

A modular, production-ready cryptocurrency trading analysis system with AI signals, Smart Money Concepts, and a live dashboard.

---

## 🏗️ Project Structure

```
crypto_trading/
├── config/
│   ├── settings.py       ← All configuration (API keys, thresholds)
│   └── logger.py         ← Centralized logging
├── data/
│   └── fetcher.py        ← Binance API + Demo data generator
├── strategy/
│   ├── indicators.py     ← RSI, EMA, MACD, Bollinger Bands
│   ├── smc.py            ← Smart Money Concepts (OB, FVG, BOS, CHOCH)
│   └── signal_engine.py  ← BUY/SELL/HOLD signal generator
├── ui/
│   └── dashboard.py      ← Streamlit web dashboard
├── models/               ← ML models (Phase 5)
├── backtest/             ← Backtesting engine (Phase 4)
├── logs/                 ← Auto-generated log files
├── .env.example          ← API key template
├── requirements.txt
├── main.py               ← CLI entry point
└── README.md
```

---

## ⚡ Quick Start (5 minutes)

### Step 1: Clone / Download

```bash
git clone https://github.com/yourusername/cryptoai-trader.git
cd cryptoai-trader
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Copy the template
cp .env.example .env

# Edit .env with your settings (optional for demo mode)
# DEMO_MODE=True means no API key needed!
```

### Step 5: Run

**Option A: CLI Signal Scan (no browser needed)**
```bash
python main.py
```

**Option B: Full Web Dashboard**
```bash
streamlit run ui/dashboard.py
```

Then open: http://localhost:8501

---

## 🔑 API Keys Setup (Optional)

The system works in **Demo Mode** without any API keys.

To use **real Binance data**:

1. Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Create a new API key (enable "Read" permissions only for data)
3. Add to your `.env` file:

```env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=True    # Keep True for safety
DEMO_MODE=False         # Switch to live data
```

---

## 📦 Build Phases

| Phase | Status | Description |
|-------|--------|-------------|
| ✅ Phase 1 | Complete | Data fetching, Indicators, SMC, Signal Engine, Dashboard |
| 🔄 Phase 2 | Next | Elliott Wave Detection, Multi-timeframe analysis |
| 📋 Phase 3 | Planned | News filter, Telegram/Email alerts |
| 📋 Phase 4 | Planned | Backtesting engine with metrics |
| 📋 Phase 5 | Planned | ML model (LSTM/XGBoost) + auto-training |
| 📋 Phase 6 | Planned | Auto trading execution + risk management |

---

## 🧠 How Signals Work

Signals combine two scoring systems:

**Technical Indicators (50% weight)**
- RSI: Oversold = BUY, Overbought = SELL
- EMA Stack: Bullish alignment = BUY
- MACD: Crossovers
- Bollinger Bands: Price at extremes
- Volume: Spike confirms signal direction

**Smart Money Concepts (50% weight)**
- BOS/CHOCH: Trend direction and reversals
- Order Blocks: Institutional demand/supply zones
- Fair Value Gaps: Price imbalance areas
- Liquidity Zones: For SL/TP placement

**Final Output:**
- BUY/SELL: when score difference ≥ 20 points
- HOLD: ambiguous market
- Confidence: 50% base + score difference

---

## 🚀 Deployment

### Streamlit Cloud (Free)
1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → select `ui/dashboard.py`
4. Add API keys as Secrets

### VPS (Ubuntu)
```bash
# Install dependencies
sudo apt update && sudo apt install python3-pip -y
pip install -r requirements.txt

# Run with screen (keeps running after logout)
screen -S trader
streamlit run ui/dashboard.py --server.port 8501

# Press Ctrl+A, D to detach
```

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**.  
Cryptocurrency trading involves significant financial risk.  
Never trade with money you cannot afford to lose.  
Past signal performance does not guarantee future results.

---

## 📝 License

MIT License - Free to use and modify.
