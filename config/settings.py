# config/settings.py
# ============================================
# Central Configuration for Trading System
# ============================================

import os
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

# ── API Keys ────────────────────────────────
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "True") == "True"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Coins to Track ──────────────────────────
DEFAULT_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

# ── Timeframes ──────────────────────────────
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
DEFAULT_TIMEFRAME = "15m"

# ── Risk Management ─────────────────────────
RISK_PERCENT       = 1.0    # Risk 1% of balance per trade
MAX_DAILY_LOSS_PCT = 5.0    # Stop trading if daily loss > 5%
DEFAULT_RR_RATIO   = 2.0    # Risk:Reward ratio (1:2)

# ── Indicator Settings ──────────────────────
RSI_PERIOD        = 14
RSI_OVERBOUGHT    = 70
RSI_OVERSOLD      = 30
EMA_SHORT         = 9
EMA_MEDIUM        = 21
EMA_LONG          = 50
EMA_TREND         = 200
VOLUME_MA_PERIOD  = 20

# ── Signal Thresholds ───────────────────────
SIGNAL_CONFIDENCE_MIN = 60  # Minimum confidence % to show signal

# ── Demo Mode (no real API needed) ──────────
DEMO_MODE = os.getenv("DEMO_MODE", "True") == "True"

# ── Logging ─────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = "logs/trading.log"

# ── Backtesting ─────────────────────────────
BACKTEST_START = "2024-01-01"
BACKTEST_END   = "2024-12-31"
INITIAL_BALANCE = 1000.0  # USDT
