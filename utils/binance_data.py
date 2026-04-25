"""
Binance API Data Fetcher
Live price, OHLCV data, multi-timeframe support
"""
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

BINANCE_BASE = "https://api.binance.com/api/v3"

POPULAR_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT", "DOTUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT"
]

TIMEFRAMES = {
    "1m": "1 Minute",
    "5m": "5 Minutes",
    "15m": "15 Minutes",
    "1h": "1 Hour",
    "4h": "4 Hours",
    "1d": "1 Day",
}

def get_live_price(symbol: str) -> dict:
    """Get live ticker price and 24h stats"""
    try:
        r = requests.get(f"{BINANCE_BASE}/ticker/24hr", params={"symbol": symbol}, timeout=10)
        data = r.json()
        return {
            "symbol": symbol,
            "price": float(data.get("lastPrice", 0)),
            "change_pct": float(data.get("priceChangePercent", 0)),
            "high": float(data.get("highPrice", 0)),
            "low": float(data.get("lowPrice", 0)),
            "volume": float(data.get("volume", 0)),
            "quote_volume": float(data.get("quoteVolume", 0)),
        }
    except Exception as e:
        return {"symbol": symbol, "price": 0, "change_pct": 0, "error": str(e)}

def get_all_prices(symbols: list) -> list:
    """Batch fetch prices for multiple coins"""
    results = []
    for sym in symbols:
        data = get_live_price(sym)
        results.append(data)
    return results

def get_klines(symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Get OHLCV candlestick data"""
    try:
        r = requests.get(
            f"{BINANCE_BASE}/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=15
        )
        data = r.json()
        if not data or isinstance(data, dict):
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df.set_index("timestamp", inplace=True)
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as e:
        return pd.DataFrame()

def get_multi_timeframe(symbol: str, timeframes: list = ["15m", "1h", "4h"]) -> dict:
    """Get OHLCV for multiple timeframes"""
    result = {}
    for tf in timeframes:
        result[tf] = get_klines(symbol, tf, limit=300)
    return result

def get_order_book(symbol: str, limit: int = 20) -> dict:
    """Get order book depth"""
    try:
        r = requests.get(f"{BINANCE_BASE}/depth", params={"symbol": symbol, "limit": limit}, timeout=10)
        return r.json()
    except:
        return {"bids": [], "asks": []}

def get_recent_trades(symbol: str, limit: int = 50) -> list:
    """Get recent trades"""
    try:
        r = requests.get(f"{BINANCE_BASE}/trades", params={"symbol": symbol, "limit": limit}, timeout=10)
        return r.json()
    except:
        return []
