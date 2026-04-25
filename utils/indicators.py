"""
Technical Indicators Engine
RSI, EMA, MACD, Bollinger Bands
SMC: Order Blocks, Fair Value Gaps (FVG)
Elliott Wave Detection
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema


# ─── Basic Indicators ────────────────────────────────────────────────────────

def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def add_ema(df: pd.DataFrame, periods: list = [9, 21, 50, 200]) -> pd.DataFrame:
    for p in periods:
        df[f"ema_{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return df

def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df

def add_bollinger(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    df["bb_upper"] = sma + 2 * std
    df["bb_lower"] = sma - 2 * std
    df["bb_mid"] = sma
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma
    return df

def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(period).mean()
    return df

def add_volume_profile(df: pd.DataFrame) -> pd.DataFrame:
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma20"].replace(0, np.nan)
    return df


# ─── SMC: Order Blocks ────────────────────────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Bullish OB: Last bearish candle before a strong bullish move
    Bearish OB: Last bullish candle before a strong bearish move
    """
    df = df.copy()
    df["ob_bull"] = False
    df["ob_bear"] = False
    df["ob_bull_high"] = np.nan
    df["ob_bull_low"] = np.nan
    df["ob_bear_high"] = np.nan
    df["ob_bear_low"] = np.nan

    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values

    for i in range(lookback, len(df) - 3):
        # Bullish Order Block: bearish candle followed by strong bullish move
        if closes[i] < opens[i]:  # bearish candle
            move = closes[i + 3] - closes[i]
            if move > (highs[i] - lows[i]) * 1.5:
                df.iloc[i, df.columns.get_loc("ob_bull")] = True
                df.iloc[i, df.columns.get_loc("ob_bull_high")] = highs[i]
                df.iloc[i, df.columns.get_loc("ob_bull_low")] = lows[i]

        # Bearish Order Block: bullish candle followed by strong bearish move
        if closes[i] > opens[i]:  # bullish candle
            move = closes[i] - closes[i + 3]
            if move > (highs[i] - lows[i]) * 1.5:
                df.iloc[i, df.columns.get_loc("ob_bear")] = True
                df.iloc[i, df.columns.get_loc("ob_bear_high")] = highs[i]
                df.iloc[i, df.columns.get_loc("ob_bear_low")] = lows[i]

    return df


# ─── SMC: Fair Value Gaps ─────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bullish FVG: candle[i-1].high < candle[i+1].low
    Bearish FVG: candle[i-1].low > candle[i+1].high
    """
    df = df.copy()
    df["fvg_bull"] = False
    df["fvg_bear"] = False
    df["fvg_bull_top"] = np.nan
    df["fvg_bull_bot"] = np.nan
    df["fvg_bear_top"] = np.nan
    df["fvg_bear_bot"] = np.nan

    highs = df["high"].values
    lows = df["low"].values

    for i in range(1, len(df) - 1):
        if highs[i - 1] < lows[i + 1]:
            df.iloc[i, df.columns.get_loc("fvg_bull")] = True
            df.iloc[i, df.columns.get_loc("fvg_bull_top")] = lows[i + 1]
            df.iloc[i, df.columns.get_loc("fvg_bull_bot")] = highs[i - 1]

        if lows[i - 1] > highs[i + 1]:
            df.iloc[i, df.columns.get_loc("fvg_bear")] = True
            df.iloc[i, df.columns.get_loc("fvg_bear_top")] = lows[i - 1]
            df.iloc[i, df.columns.get_loc("fvg_bear_bot")] = highs[i + 1]

    return df


# ─── Market Structure ─────────────────────────────────────────────────────────

def detect_structure(df: pd.DataFrame) -> dict:
    """BOS (Break of Structure), CHoCH detection"""
    highs = df["high"].rolling(10).max()
    lows = df["low"].rolling(10).min()
    close = df["close"]

    last_high = highs.iloc[-20:-1].max()
    last_low = lows.iloc[-20:-1].min()
    current = close.iloc[-1]

    if current > last_high:
        structure = "BOS Bullish 🟢"
    elif current < last_low:
        structure = "BOS Bearish 🔴"
    else:
        structure = "Consolidation ⚪"

    return {
        "structure": structure,
        "last_high": last_high,
        "last_low": last_low,
        "current": current
    }


# ─── Elliott Wave Detection ────────────────────────────────────────────────────

def detect_elliott_wave(df: pd.DataFrame, order: int = 5) -> dict:
    """Simplified Elliott Wave pivot detection"""
    closes = df["close"].values

    local_max_idx = argrelextrema(closes, np.greater, order=order)[0]
    local_min_idx = argrelextrema(closes, np.less, order=order)[0]

    pivots = []
    for idx in sorted(set(local_max_idx) | set(local_min_idx)):
        if idx in local_max_idx:
            pivots.append({"idx": int(idx), "price": float(closes[idx]), "type": "high"})
        else:
            pivots.append({"idx": int(idx), "price": float(closes[idx]), "type": "low"})

    pivots = sorted(pivots, key=lambda x: x["idx"])
    wave_count = len(pivots)

    if wave_count >= 5:
        wave_label = f"Wave {min(wave_count, 5)} detected"
    elif wave_count >= 3:
        wave_label = "Corrective ABC pattern"
    else:
        wave_label = "Insufficient data for wave analysis"

    return {
        "pivots": pivots[-8:],  # last 8 pivots
        "wave_label": wave_label,
        "pivot_count": wave_count
    }


# ─── Full Indicator Pipeline ──────────────────────────────────────────────────

def run_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Run all indicators on dataframe"""
    if df.empty or len(df) < 50:
        return df
    df = add_rsi(df)
    df = add_ema(df, [9, 21, 50, 200])
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_atr(df)
    df = add_volume_profile(df)
    df = detect_order_blocks(df)
    df = detect_fvg(df)
    return df
