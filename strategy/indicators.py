# strategy/indicators.py
# ============================================
# Technical Indicators Engine
# RSI, EMA, Volume Analysis, Market Structure
# ============================================

import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    EMA_SHORT, EMA_MEDIUM, EMA_LONG, EMA_TREND,
    VOLUME_MA_PERIOD
)
from config.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────
# RSI (Relative Strength Index)
# ─────────────────────────────────────────

def calculate_rsi(close: pd.Series, period: int = None) -> pd.Series:
    """
    Calculates RSI indicator.
    
    RSI > 70 → Overbought (potential SELL)
    RSI < 30 → Oversold  (potential BUY)
    """
    period = period or RSI_PERIOD
    delta  = close.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)  # Default neutral value for early candles


# ─────────────────────────────────────────
# EMA (Exponential Moving Average)
# ─────────────────────────────────────────

def calculate_ema(close: pd.Series, period: int) -> pd.Series:
    """Calculates EMA for given period."""
    return close.ewm(span=period, adjust=False).mean()


def calculate_all_emas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds all EMA columns to DataFrame.
    Returns same DataFrame with new columns added.
    """
    df = df.copy()
    df[f"ema_{EMA_SHORT}"]  = calculate_ema(df["close"], EMA_SHORT)
    df[f"ema_{EMA_MEDIUM}"] = calculate_ema(df["close"], EMA_MEDIUM)
    df[f"ema_{EMA_LONG}"]   = calculate_ema(df["close"], EMA_LONG)
    df[f"ema_{EMA_TREND}"]  = calculate_ema(df["close"], EMA_TREND)
    return df


# ─────────────────────────────────────────
# VOLUME ANALYSIS
# ─────────────────────────────────────────

def calculate_volume_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds volume indicators:
    - volume_ma: Moving average of volume
    - volume_ratio: Current vs average (>1.5 = high volume)
    - volume_spike: True if unusual volume
    """
    df = df.copy()
    df["volume_ma"]    = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]
    df["volume_spike"] = df["volume_ratio"] > 1.5  # 150% above average
    return df


# ─────────────────────────────────────────
# MARKET STRUCTURE ANALYSIS
# HH, HL, LH, LL (Higher Highs/Lows etc.)
# ─────────────────────────────────────────

def detect_swing_points(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """
    Detects swing highs and lows.
    
    Swing High: Highest point in lookback window (both sides)
    Swing Low:  Lowest point in lookback window (both sides)
    """
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"]  = False

    for i in range(lookback, len(df) - lookback):
        window_high = df["high"].iloc[i - lookback : i + lookback + 1]
        window_low  = df["low"].iloc[i - lookback : i + lookback + 1]

        if df["high"].iloc[i] == window_high.max():
            df.iloc[i, df.columns.get_loc("swing_high")] = True

        if df["low"].iloc[i] == window_low.min():
            df.iloc[i, df.columns.get_loc("swing_low")] = True

    return df


def detect_market_structure(df: pd.DataFrame) -> dict:
    """
    Identifies market structure:
    - HH/HL = Uptrend (Bullish)
    - LH/LL = Downtrend (Bearish)
    
    Returns:
        Dict with structure info
    """
    df_swings = detect_swing_points(df)

    swing_highs = df_swings[df_swings["swing_high"]]["high"].values
    swing_lows  = df_swings[df_swings["swing_low"]]["low"].values

    structure = "NEUTRAL"
    description = "No clear structure"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        hh = swing_highs[-1] > swing_highs[-2]  # Higher High
        hl = swing_lows[-1] > swing_lows[-2]    # Higher Low
        lh = swing_highs[-1] < swing_highs[-2]  # Lower High
        ll = swing_lows[-1] < swing_lows[-2]    # Lower Low

        if hh and hl:
            structure = "BULLISH"
            description = "Higher Highs + Higher Lows (Uptrend)"
        elif lh and ll:
            structure = "BEARISH"
            description = "Lower Highs + Lower Lows (Downtrend)"
        elif hh and ll:
            structure = "CHOPPY"
            description = "Mixed signals - ranging market"

    return {
        "structure":   structure,
        "description": description,
        "swing_highs": swing_highs.tolist()[-3:] if len(swing_highs) >= 3 else swing_highs.tolist(),
        "swing_lows":  swing_lows.tolist()[-3:] if len(swing_lows) >= 3 else swing_lows.tolist(),
    }


# ─────────────────────────────────────────
# MACD (Moving Average Convergence Divergence)
# ─────────────────────────────────────────

def calculate_macd(close: pd.Series, fast=12, slow=26, signal=9) -> dict:
    """
    Calculates MACD line, signal line, and histogram.
    
    MACD cross above signal → BUY
    MACD cross below signal → SELL
    """
    ema_fast   = calculate_ema(close, fast)
    ema_slow   = calculate_ema(close, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line

    return {
        "macd":      macd_line,
        "signal":    signal_line,
        "histogram": histogram,
    }


# ─────────────────────────────────────────
# BOLLINGER BANDS
# ─────────────────────────────────────────

def calculate_bollinger_bands(close: pd.Series, period=20, std_dev=2) -> dict:
    """
    Upper band, middle (SMA), lower band.
    Price near lower band → potential BUY
    Price near upper band → potential SELL
    """
    sma    = close.rolling(period).mean()
    std    = close.rolling(period).std()
    upper  = sma + (std * std_dev)
    lower  = sma - (std * std_dev)
    bb_pct = (close - lower) / (upper - lower)  # 0=lower, 1=upper

    return {
        "upper":  upper,
        "middle": sma,
        "lower":  lower,
        "bb_pct": bb_pct,
    }


# ─────────────────────────────────────────
# MASTER FUNCTION - Add All Indicators
# ─────────────────────────────────────────

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds ALL indicators to a DataFrame in one call.
    This is the main function used by the signal engine.
    
    Input:  DataFrame with open, high, low, close, volume
    Output: Same DataFrame with indicator columns added
    """
    df = df.copy()

    # RSI
    df["rsi"] = calculate_rsi(df["close"])

    # EMAs
    df = calculate_all_emas(df)

    # Volume
    df = calculate_volume_analysis(df)

    # MACD
    macd = calculate_macd(df["close"])
    df["macd"]           = macd["macd"]
    df["macd_signal"]    = macd["signal"]
    df["macd_histogram"] = macd["histogram"]

    # Bollinger Bands
    bb = calculate_bollinger_bands(df["close"])
    df["bb_upper"]  = bb["upper"]
    df["bb_middle"] = bb["middle"]
    df["bb_lower"]  = bb["lower"]
    df["bb_pct"]    = bb["bb_pct"]

    # Swing Points
    df = detect_swing_points(df)

    # Trend direction from EMA stack
    df["trend_up"] = (
        (df[f"ema_{EMA_SHORT}"] > df[f"ema_{EMA_MEDIUM}"]) &
        (df[f"ema_{EMA_MEDIUM}"] > df[f"ema_{EMA_LONG}"])
    )
    df["trend_down"] = (
        (df[f"ema_{EMA_SHORT}"] < df[f"ema_{EMA_MEDIUM}"]) &
        (df[f"ema_{EMA_MEDIUM}"] < df[f"ema_{EMA_LONG}"])
    )

    logger.debug(f"Indicators calculated. Shape: {df.shape}")
    return df


# ─────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.append("..")
    from data.fetcher import get_ohlcv

    print("Testing Indicators...")
    df = get_ohlcv("BTCUSDT", "1h", 100)
    df = add_all_indicators(df)

    last = df.iloc[-1]
    print(f"\nBTC Latest Indicators:")
    print(f"  RSI:       {last['rsi']:.1f}")
    print(f"  EMA9:      {last['ema_9']:.2f}")
    print(f"  EMA21:     {last['ema_21']:.2f}")
    print(f"  EMA50:     {last['ema_50']:.2f}")
    print(f"  MACD:      {last['macd']:.4f}")
    print(f"  Trend Up:  {last['trend_up']}")
    print(f"  Vol Spike: {last['volume_spike']}")

    ms = detect_market_structure(df)
    print(f"\nMarket Structure: {ms['structure']} - {ms['description']}")
