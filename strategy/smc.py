# strategy/smc.py
# ============================================
# Smart Money Concepts (SMC) Engine
# Order Blocks, FVG, BOS, CHOCH, Liquidity
# ============================================

import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────
# ORDER BLOCK DETECTION
# Areas where institutions placed large orders
# Price tends to return and react to these zones
# ─────────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, lookback: int = 10) -> list:
    """
    Order Block = Last bearish candle before a strong bullish move (bullish OB)
                  Last bullish candle before a strong bearish move (bearish OB)

    Returns:
        List of dicts with order block info
    """
    order_blocks = []
    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values

    for i in range(lookback, len(df) - 3):
        # Look for strong moves after candle i
        future_move_up   = max(closes[i+1:i+4]) - closes[i]
        future_move_down = closes[i] - min(closes[i+1:i+4])
        candle_body = abs(closes[i] - opens[i])

        # BULLISH Order Block
        # Bearish candle (close < open) followed by strong up move
        if (closes[i] < opens[i] and
                future_move_up > candle_body * 1.5):
            order_blocks.append({
                "type":       "bullish",
                "index":      i,
                "timestamp":  df.index[i],
                "top":        opens[i],    # Top of OB = open of bearish candle
                "bottom":     closes[i],   # Bottom of OB = close of bearish candle
                "high":       highs[i],
                "low":        lows[i],
                "strength":   future_move_up / candle_body,
                "mitigated":  False,       # Has price returned to this OB?
            })

        # BEARISH Order Block
        # Bullish candle (close > open) followed by strong down move
        elif (closes[i] > opens[i] and
              future_move_down > candle_body * 1.5):
            order_blocks.append({
                "type":       "bearish",
                "index":      i,
                "timestamp":  df.index[i],
                "top":        closes[i],   # Top of OB = close of bullish candle
                "bottom":     opens[i],    # Bottom of OB = open of bullish candle
                "high":       highs[i],
                "low":        lows[i],
                "strength":   future_move_down / candle_body,
                "mitigated":  False,
            })

    # Mark mitigated blocks (price has returned and touched them)
    current_price = closes[-1]
    for ob in order_blocks:
        if ob["type"] == "bullish" and current_price <= ob["top"]:
            ob["mitigated"] = True
        elif ob["type"] == "bearish" and current_price >= ob["bottom"]:
            ob["mitigated"] = True

    # Keep only recent + unmitigated blocks
    active_obs = [ob for ob in order_blocks[-20:] if not ob["mitigated"]]
    logger.debug(f"Detected {len(active_obs)} active order blocks")
    return active_obs


# ─────────────────────────────────────────
# FAIR VALUE GAP (FVG) DETECTION
# Imbalance in price - gaps between candles
# Price tends to fill these gaps later
# ─────────────────────────────────────────

def detect_fair_value_gaps(df: pd.DataFrame) -> list:
    """
    FVG = Gap between candle 1's high and candle 3's low (bullish FVG)
          Gap between candle 1's low and candle 3's high (bearish FVG)
    
    3-candle pattern: [candle_1][middle][candle_3]
    Bullish FVG: candle_3.low > candle_1.high (gap up)
    Bearish FVG: candle_3.high < candle_1.low (gap down)

    Returns:
        List of FVG dicts
    """
    fvgs = []

    for i in range(1, len(df) - 1):
        prev_high = df["high"].iloc[i - 1]
        prev_low  = df["low"].iloc[i - 1]
        next_high = df["high"].iloc[i + 1]
        next_low  = df["low"].iloc[i + 1]

        # Bullish FVG: Gap up (next candle's low is above previous candle's high)
        if next_low > prev_high:
            gap_size = next_low - prev_high
            fvgs.append({
                "type":      "bullish",
                "index":     i,
                "timestamp": df.index[i],
                "top":       next_low,
                "bottom":    prev_high,
                "size":      gap_size,
                "size_pct":  (gap_size / prev_high) * 100,
                "filled":    False,
            })

        # Bearish FVG: Gap down (next candle's high is below previous candle's low)
        elif next_high < prev_low:
            gap_size = prev_low - next_high
            fvgs.append({
                "type":      "bearish",
                "index":     i,
                "timestamp": df.index[i],
                "top":       prev_low,
                "bottom":    next_high,
                "size":      gap_size,
                "size_pct":  (gap_size / prev_low) * 100,
                "filled":    False,
            })

    # Check if FVGs have been filled by current price action
    current_price = df["close"].iloc[-1]
    for fvg in fvgs:
        if fvg["type"] == "bullish" and current_price <= fvg["top"]:
            fvg["filled"] = True
        elif fvg["type"] == "bearish" and current_price >= fvg["bottom"]:
            fvg["filled"] = True

    # Return unfilled FVGs only
    active_fvgs = [f for f in fvgs[-15:] if not f["filled"]]
    logger.debug(f"Detected {len(active_fvgs)} active FVGs")
    return active_fvgs


# ─────────────────────────────────────────
# BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHOCH)
# BOS   = Trend continuation signal
# CHOCH = Potential trend reversal signal
# ─────────────────────────────────────────

def detect_bos_choch(df: pd.DataFrame, swing_lookback: int = 10) -> dict:
    """
    Detects Break of Structure and Change of Character.
    
    In uptrend:
    - BOS   = Price breaks above previous swing high (continuation)
    - CHOCH = Price breaks below previous swing low  (reversal warning)
    
    In downtrend:
    - BOS   = Price breaks below previous swing low  (continuation)
    - CHOCH = Price breaks above previous swing high (reversal warning)
    
    Returns:
        Dict with detected BOS/CHOCH events
    """
    highs  = df["high"].values
    lows   = df["low"].values
    closes = df["close"].values

    events = []
    recent_swing_high = None
    recent_swing_low  = None
    trend = "unknown"

    for i in range(swing_lookback, len(df)):
        window = slice(max(0, i - swing_lookback), i)

        local_high = max(highs[window])
        local_low  = min(lows[window])

        # Determine trend direction
        if len(events) == 0:
            if closes[i] > local_high * 0.98:
                trend = "bullish"
            elif closes[i] < local_low * 1.02:
                trend = "bearish"

        # Check for BOS (Break of Structure)
        if recent_swing_high and closes[i] > recent_swing_high:
            if trend == "bullish":
                events.append({
                    "type":       "BOS",
                    "direction":  "bullish",
                    "index":      i,
                    "timestamp":  df.index[i],
                    "price":      closes[i],
                    "level":      recent_swing_high,
                    "description": "Bullish BOS - Uptrend continues",
                })
            else:
                events.append({
                    "type":       "CHOCH",
                    "direction":  "bullish",
                    "index":      i,
                    "timestamp":  df.index[i],
                    "price":      closes[i],
                    "level":      recent_swing_high,
                    "description": "Bullish CHOCH - Potential reversal UP",
                })
            trend = "bullish"

        if recent_swing_low and closes[i] < recent_swing_low:
            if trend == "bearish":
                events.append({
                    "type":       "BOS",
                    "direction":  "bearish",
                    "index":      i,
                    "timestamp":  df.index[i],
                    "price":      closes[i],
                    "level":      recent_swing_low,
                    "description": "Bearish BOS - Downtrend continues",
                })
            else:
                events.append({
                    "type":       "CHOCH",
                    "direction":  "bearish",
                    "index":      i,
                    "timestamp":  df.index[i],
                    "price":      closes[i],
                    "level":      recent_swing_low,
                    "description": "Bearish CHOCH - Potential reversal DOWN",
                })
            trend = "bearish"

        # Update swing points
        recent_swing_high = local_high
        recent_swing_low  = local_low

    latest_event = events[-1] if events else None
    return {
        "events":       events[-5:],  # Last 5 events
        "latest":       latest_event,
        "current_trend": trend,
    }


# ─────────────────────────────────────────
# LIQUIDITY ZONES
# Areas where stop losses cluster (above highs / below lows)
# Smart money hunts these levels
# ─────────────────────────────────────────

def detect_liquidity_zones(df: pd.DataFrame, tolerance: float = 0.002) -> dict:
    """
    Detects liquidity zones where stop losses likely sit.
    
    Buy-side liquidity  = Above swing highs (stops from shorts)
    Sell-side liquidity = Below swing lows  (stops from longs)

    Returns:
        Dict with buy-side and sell-side liquidity levels
    """
    highs = df["high"].values
    lows  = df["low"].values

    # Find significant swing highs (potential buy-side liquidity)
    buy_side  = []
    sell_side = []

    # Rolling window to find local extremes
    window = 10
    for i in range(window, len(df) - window):
        # Local high = potential buy-side liquidity
        if highs[i] == max(highs[i - window:i + window]):
            buy_side.append({
                "price":     float(highs[i]),
                "index":     i,
                "timestamp": df.index[i],
                "type":      "buy_side",
                "description": "Buyside Liquidity - Shorts' stops cluster here",
            })

        # Local low = potential sell-side liquidity
        if lows[i] == min(lows[i - window:i + window]):
            sell_side.append({
                "price":     float(lows[i]),
                "index":     i,
                "timestamp": df.index[i],
                "type":      "sell_side",
                "description": "Sellside Liquidity - Longs' stops cluster here",
            })

    current_price = float(df["close"].iloc[-1])

    # Filter nearest liquidity zones above and below current price
    above = sorted(
        [z for z in buy_side if z["price"] > current_price],
        key=lambda x: x["price"]
    )[:3]

    below = sorted(
        [z for z in sell_side if z["price"] < current_price],
        key=lambda x: x["price"], reverse=True
    )[:3]

    return {
        "buy_side":  above,    # Above current price
        "sell_side": below,    # Below current price
        "nearest_target": above[0]["price"] if above else None,
        "nearest_support": below[0]["price"] if below else None,
    }


# ─────────────────────────────────────────
# MASTER SMC ANALYSIS FUNCTION
# ─────────────────────────────────────────

def run_smc_analysis(df: pd.DataFrame) -> dict:
    """
    Runs all SMC analysis and returns a combined dict.
    Main entry point for the signal engine.
    """
    order_blocks = detect_order_blocks(df)
    fvgs         = detect_fair_value_gaps(df)
    bos_choch    = detect_bos_choch(df)
    liquidity    = detect_liquidity_zones(df)

    current_price = float(df["close"].iloc[-1])

    # Check if price is near any active order block
    near_bullish_ob = any(
        ob["bottom"] <= current_price <= ob["top"] * 1.01
        for ob in order_blocks if ob["type"] == "bullish"
    )
    near_bearish_ob = any(
        ob["bottom"] * 0.99 <= current_price <= ob["top"]
        for ob in order_blocks if ob["type"] == "bearish"
    )

    # Check if price is near any FVG
    near_bullish_fvg = any(
        fvg["bottom"] <= current_price <= fvg["top"] * 1.01
        for fvg in fvgs if fvg["type"] == "bullish"
    )

    return {
        "order_blocks":     order_blocks,
        "fvgs":             fvgs,
        "bos_choch":        bos_choch,
        "liquidity":        liquidity,
        "near_bullish_ob":  near_bullish_ob,
        "near_bearish_ob":  near_bearish_ob,
        "near_bullish_fvg": near_bullish_fvg,
        "current_trend":    bos_choch["current_trend"],
        "latest_event":     bos_choch["latest"],
    }


# ─────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.append("..")
    from data.fetcher import get_ohlcv

    print("Testing SMC Analysis...")
    df = get_ohlcv("BTCUSDT", "1h", 200)

    result = run_smc_analysis(df)

    print(f"\nOrder Blocks: {len(result['order_blocks'])}")
    print(f"Fair Value Gaps: {len(result['fvgs'])}")
    print(f"Current Trend: {result['current_trend']}")
    print(f"Near Bullish OB: {result['near_bullish_ob']}")
    print(f"Near Bearish OB: {result['near_bearish_ob']}")

    if result["latest_event"]:
        print(f"Latest Event: {result['latest_event']['description']}")

    liq = result["liquidity"]
    print(f"\nNearest Target:  {liq['nearest_target']}")
    print(f"Nearest Support: {liq['nearest_support']}")
