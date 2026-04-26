# data/fetcher.py
# ============================================
# Market Data Fetcher
# Supports: Binance API (real) + Demo Mode (fake data for testing)
# ============================================

import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    BINANCE_TESTNET, DEMO_MODE, DEFAULT_COINS, TIMEFRAMES
)
from config.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────
# DEMO DATA GENERATOR
# Used when DEMO_MODE=True (no API key needed)
# ─────────────────────────────────────────

def generate_demo_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """
    Generates realistic-looking OHLCV candlestick data for testing.
    No API key required.
    """
    # Base prices for each coin
    base_prices = {
        "BTCUSDT": 65000, "ETHUSDT": 3500,
        "SOLUSDT": 180,   "XRPUSDT": 0.60,
        "BNBUSDT": 580,   "ADAUSDT": 0.45,
    }
    base = base_prices.get(symbol, 100)

    # Timeframe → minutes mapping
    tf_minutes = {
        "1m": 1, "5m": 5, "15m": 15,
        "1h": 60, "4h": 240, "1d": 1440
    }
    minutes = tf_minutes.get(timeframe, 15)

    # Generate timestamps (going backwards from now)
    end_time = datetime.now()
    timestamps = [
        end_time - timedelta(minutes=minutes * i)
        for i in range(limit, 0, -1)
    ]

    # Simulate realistic price movement using random walk
    np.random.seed(hash(symbol) % 1000)  # Consistent seed per symbol
    returns = np.random.normal(0.0002, 0.015, limit)  # Mean slight uptrend
    prices = base * np.cumprod(1 + returns)

    # Build OHLCV data
    rows = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        volatility = close * np.random.uniform(0.003, 0.02)
        open_p  = prices[i-1] if i > 0 else close
        high    = max(open_p, close) + abs(np.random.normal(0, volatility))
        low     = min(open_p, close) - abs(np.random.normal(0, volatility))
        volume  = np.random.uniform(100, 5000) * (base / 100)

        rows.append({
            "timestamp": ts,
            "open":   round(open_p, 4),
            "high":   round(high, 4),
            "low":    round(low, 4),
            "close":  round(close, 4),
            "volume": round(volume, 2),
        })

    df = pd.DataFrame(rows)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    logger.debug(f"[DEMO] Generated {len(df)} candles for {symbol} {timeframe}")
    return df


# ─────────────────────────────────────────
# REAL BINANCE DATA FETCHER
# Requires valid API key in .env
# ─────────────────────────────────────────

def fetch_binance_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> Optional[pd.DataFrame]:
    """
    Fetches real OHLCV data from Binance using ccxt library.
    Falls back to demo data if API call fails.
    """
    try:
        import ccxt
        exchange = ccxt.binance({
            "apiKey":  BINANCE_API_KEY,
            "secret":  BINANCE_API_SECRET,
            "sandbox": BINANCE_TESTNET,
            "enableRateLimit": True,
        })

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        df = pd.DataFrame(ohlcv, columns=[
            "timestamp", "open", "high", "low", "close", "volume"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        logger.info(f"[LIVE] Fetched {len(df)} candles for {symbol} {timeframe}")
        return df

    except ImportError:
        logger.warning("ccxt not installed. Run: pip install ccxt")
        return None
    except Exception as e:
        logger.error(f"Binance API error for {symbol}: {e}")
        return None


# ─────────────────────────────────────────
# MAIN INTERFACE (used by rest of system)
# ─────────────────────────────────────────

def get_ohlcv(symbol: str, timeframe: str = "15m", limit: int = 500) -> pd.DataFrame:
    """
    Main function to get OHLCV data.
    Automatically uses demo or live data based on settings.

    Args:
        symbol:    Trading pair e.g. "BTCUSDT"
        timeframe: Candle timeframe e.g. "15m", "1h"
        limit:     Number of candles to fetch

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    if DEMO_MODE or not BINANCE_API_KEY:
        return generate_demo_ohlcv(symbol, timeframe, limit)

    df = fetch_binance_ohlcv(symbol, timeframe, limit)
    if df is None:
        logger.warning(f"Falling back to demo data for {symbol}")
        return generate_demo_ohlcv(symbol, timeframe, limit)

    return df


def get_current_price(symbol: str) -> float:
    """Returns the latest closing price for a symbol."""
    df = get_ohlcv(symbol, "1m", 2)
    return float(df["close"].iloc[-1])


def get_multi_timeframe_data(symbol: str, timeframes: list = None) -> dict:
    """
    Fetches OHLCV data for multiple timeframes at once.

    Returns:
        Dict like {"15m": DataFrame, "1h": DataFrame, ...}
    """
    if timeframes is None:
        timeframes = ["15m", "1h", "4h"]

    result = {}
    for tf in timeframes:
        result[tf] = get_ohlcv(symbol, tf)
        time.sleep(0.1)  # Be respectful to API rate limits

    return result


# ─────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Testing Data Fetcher")
    print("=" * 50)

    df = get_ohlcv("BTCUSDT", "1h", limit=10)
    print(f"\nBTCUSDT 1h - Last 10 candles:")
    print(df.tail())
    print(f"\nCurrent BTC price: ${get_current_price('BTCUSDT'):,.2f}")
