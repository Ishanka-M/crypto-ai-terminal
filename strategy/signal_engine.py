# strategy/signal_engine.py
# ============================================
# AI Signal Engine
# Combines: Technical Indicators + SMC + ML
# Output: BUY / SELL / HOLD + Confidence %
# ============================================

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    RSI_OVERBOUGHT, RSI_OVERSOLD, SIGNAL_CONFIDENCE_MIN,
    DEFAULT_RR_RATIO, RISK_PERCENT
)
from config.logger import get_logger
from strategy.indicators import add_all_indicators, detect_market_structure
from strategy.smc import run_smc_analysis

logger = get_logger(__name__)


# ─────────────────────────────────────────
# SIGNAL DATACLASS
# Clean structure for signal output
# ─────────────────────────────────────────

@dataclass
class TradeSignal:
    symbol:      str
    signal:      str       # "BUY", "SELL", "HOLD"
    confidence:  float     # 0 - 100 (%)
    price:       float
    stop_loss:   float
    take_profit: float
    reason:      list      # List of reasons for signal
    timeframe:   str
    timestamp:   str
    risk_reward: float
    smc_context: str       # SMC confirmation info

    def to_dict(self) -> dict:
        return {
            "symbol":      self.symbol,
            "signal":      self.signal,
            "confidence":  round(self.confidence, 1),
            "price":       round(self.price, 4),
            "stop_loss":   round(self.stop_loss, 4),
            "take_profit": round(self.take_profit, 4),
            "reason":      self.reason,
            "timeframe":   self.timeframe,
            "timestamp":   self.timestamp,
            "risk_reward": round(self.risk_reward, 2),
            "smc_context": self.smc_context,
        }


# ─────────────────────────────────────────
# TECHNICAL SCORING SYSTEM
# Each indicator adds/removes confidence points
# ─────────────────────────────────────────

def score_technical_indicators(row: pd.Series) -> tuple:
    """
    Scores technical indicators for BUY / SELL bias.
    
    Returns:
        (buy_score, sell_score, reasons)
        Each score is 0-100 based on points accumulated
    """
    buy_points  = 0
    sell_points = 0
    reasons     = []
    max_points  = 0

    # ── RSI ─────────────────────────────
    max_points += 20
    rsi = row.get("rsi", 50)
    if rsi < RSI_OVERSOLD:
        buy_points += 20
        reasons.append(f"RSI oversold ({rsi:.1f})")
    elif rsi > RSI_OVERBOUGHT:
        sell_points += 20
        reasons.append(f"RSI overbought ({rsi:.1f})")
    elif 40 < rsi < 55:  # Neutral zone with slight buy bias
        buy_points += 5
    elif 45 < rsi < 60:
        sell_points += 5

    # ── EMA Trend ───────────────────────
    max_points += 25
    trend_up   = row.get("trend_up", False)
    trend_down = row.get("trend_down", False)
    if trend_up:
        buy_points += 25
        reasons.append("EMA stack bullish (EMA9 > EMA21 > EMA50)")
    elif trend_down:
        sell_points += 25
        reasons.append("EMA stack bearish (EMA9 < EMA21 < EMA50)")

    # ── MACD ────────────────────────────
    max_points += 20
    macd      = row.get("macd", 0)
    macd_sig  = row.get("macd_signal", 0)
    macd_hist = row.get("macd_histogram", 0)
    if macd > macd_sig and macd_hist > 0:
        buy_points += 20
        reasons.append("MACD bullish crossover")
    elif macd < macd_sig and macd_hist < 0:
        sell_points += 20
        reasons.append("MACD bearish crossover")

    # ── Bollinger Bands ─────────────────
    max_points += 15
    bb_pct = row.get("bb_pct", 0.5)
    if bb_pct < 0.2:
        buy_points += 15
        reasons.append(f"Price near BB lower band (oversold)")
    elif bb_pct > 0.8:
        sell_points += 15
        reasons.append(f"Price near BB upper band (overbought)")

    # ── Volume Confirmation ──────────────
    max_points += 20
    vol_spike = row.get("volume_spike", False)
    vol_ratio = row.get("volume_ratio", 1.0)
    if vol_spike:
        # Volume spike amplifies the existing bias
        if buy_points > sell_points:
            buy_points += 20
            reasons.append(f"High volume confirms move ({vol_ratio:.1f}x avg)")
        else:
            sell_points += 20
            reasons.append(f"High volume confirms move ({vol_ratio:.1f}x avg)")

    return buy_points, sell_points, reasons, max_points


# ─────────────────────────────────────────
# SMC SCORING SYSTEM
# ─────────────────────────────────────────

def score_smc(smc_result: dict) -> tuple:
    """
    Converts SMC analysis to buy/sell bias scores.
    
    Returns:
        (buy_score, sell_score, smc_reasons, context_str)
    """
    buy_score  = 0
    sell_score = 0
    reasons    = []

    # ── Trend Direction from BOS/CHOCH ──
    trend = smc_result.get("current_trend", "unknown")
    if trend == "bullish":
        buy_score += 20
        reasons.append("SMC: Bullish market structure")
    elif trend == "bearish":
        sell_score += 20
        reasons.append("SMC: Bearish market structure")

    # ── Order Block Proximity ────────────
    if smc_result.get("near_bullish_ob"):
        buy_score += 25
        reasons.append("Price at Bullish Order Block (institutional demand)")
    if smc_result.get("near_bearish_ob"):
        sell_score += 25
        reasons.append("Price at Bearish Order Block (institutional supply)")

    # ── FVG Proximity ────────────────────
    if smc_result.get("near_bullish_fvg"):
        buy_score += 15
        reasons.append("Price at Bullish Fair Value Gap")

    # ── Latest BOS/CHOCH Event ───────────
    latest = smc_result.get("latest_event")
    if latest:
        if latest["type"] == "CHOCH" and latest["direction"] == "bullish":
            buy_score += 20
            reasons.append(f"Bullish CHOCH detected (reversal signal)")
        elif latest["type"] == "CHOCH" and latest["direction"] == "bearish":
            sell_score += 20
            reasons.append(f"Bearish CHOCH detected (reversal signal)")
        elif latest["type"] == "BOS" and latest["direction"] == "bullish":
            buy_score += 10
            reasons.append("Bullish BOS (trend continuation)")
        elif latest["type"] == "BOS" and latest["direction"] == "bearish":
            sell_score += 10
            reasons.append("Bearish BOS (trend continuation)")

    context = f"Trend: {trend} | OB: {'✓' if smc_result.get('near_bullish_ob') or smc_result.get('near_bearish_ob') else '✗'}"
    return buy_score, sell_score, reasons, context


# ─────────────────────────────────────────
# STOP LOSS & TAKE PROFIT CALCULATION
# ─────────────────────────────────────────

def calculate_sl_tp(
    signal:        str,
    price:         float,
    smc_result:    dict,
    rr_ratio:      float = DEFAULT_RR_RATIO,
    atr_pct:       float = 0.015,  # Default 1.5% if no ATR
) -> tuple:
    """
    Calculates Stop Loss and Take Profit.
    Uses nearest liquidity zones for precision, or ATR-based fallback.
    
    Returns:
        (stop_loss, take_profit, risk_reward)
    """
    liquidity = smc_result.get("liquidity", {})

    if signal == "BUY":
        # SL below nearest sell-side liquidity or ATR-based
        support = liquidity.get("nearest_support")
        if support and support < price * 0.99:
            sl = support * 0.999  # Just below support
        else:
            sl = price * (1 - atr_pct)

        risk = price - sl
        tp   = price + (risk * rr_ratio)

    elif signal == "SELL":
        # SL above nearest buy-side liquidity
        resistance = liquidity.get("nearest_target")
        if resistance and resistance > price * 1.01:
            sl = resistance * 1.001  # Just above resistance
        else:
            sl = price * (1 + atr_pct)

        risk = sl - price
        tp   = price - (risk * rr_ratio)

    else:  # HOLD
        sl = price
        tp = price
        return sl, tp, 0.0

    actual_rr = abs(tp - price) / abs(sl - price) if abs(sl - price) > 0 else 0
    return sl, tp, actual_rr


# ─────────────────────────────────────────
# MAIN SIGNAL GENERATION
# ─────────────────────────────────────────

def generate_signal(
    symbol:    str,
    df:        pd.DataFrame,
    timeframe: str = "15m",
) -> TradeSignal:
    """
    Main function: generates a trading signal for a given coin.
    
    Steps:
    1. Add all technical indicators
    2. Run SMC analysis
    3. Score both systems
    4. Combine scores → BUY / SELL / HOLD
    5. Calculate SL/TP
    6. Return TradeSignal object
    
    Args:
        symbol:    e.g. "BTCUSDT"
        df:        OHLCV DataFrame
        timeframe: e.g. "15m"
    
    Returns:
        TradeSignal dataclass
    """
    # ── Step 1: Calculate Indicators ────
    df_ind = add_all_indicators(df)
    last   = df_ind.iloc[-1]
    price  = float(last["close"])

    # ── Step 2: SMC Analysis ─────────────
    smc_result = run_smc_analysis(df)

    # ── Step 3: Market Structure ─────────
    ms = detect_market_structure(df_ind)

    # ── Step 4: Score Everything ─────────
    tech_buy, tech_sell, tech_reasons, _ = score_technical_indicators(last)
    smc_buy, smc_sell, smc_reasons, smc_ctx = score_smc(smc_result)

    # Combined scores (equal weight: 50% tech + 50% SMC)
    total_buy  = (tech_buy  + smc_buy)  / 2
    total_sell = (tech_sell + smc_sell) / 2

    all_reasons = tech_reasons + smc_reasons

    # ── Step 5: Determine Signal ─────────
    score_diff = total_buy - total_sell

    if score_diff >= 20:
        signal     = "BUY"
        confidence = min(50 + score_diff, 95)  # Cap at 95% (never 100% certain)
    elif score_diff <= -20:
        signal     = "SELL"
        confidence = min(50 + abs(score_diff), 95)
    else:
        signal     = "HOLD"
        confidence = 50 + abs(score_diff) * 0.5

    # ── Step 6: SL / TP ─────────────────
    sl, tp, rr = calculate_sl_tp(signal, price, smc_result)

    # ── Step 7: Build Signal Object ──────
    trade_signal = TradeSignal(
        symbol      = symbol,
        signal      = signal,
        confidence  = confidence,
        price       = price,
        stop_loss   = sl,
        take_profit = tp,
        reason      = all_reasons if all_reasons else ["Insufficient data for signal"],
        timeframe   = timeframe,
        timestamp   = str(df_ind.index[-1]),
        risk_reward = rr,
        smc_context = smc_ctx,
    )

    logger.info(
        f"Signal [{symbol}] {signal} | Conf: {confidence:.1f}% | "
        f"Price: {price:.4f} | SL: {sl:.4f} | TP: {tp:.4f}"
    )
    return trade_signal


def generate_signals_for_all(
    coins:     list,
    timeframe: str,
    data_getter,  # Function to get OHLCV data
) -> list:
    """
    Generates signals for multiple coins at once.
    
    Returns:
        List of TradeSignal objects
    """
    signals = []
    for symbol in coins:
        try:
            df = data_getter(symbol, timeframe)
            if len(df) < 50:
                logger.warning(f"Not enough data for {symbol}")
                continue
            sig = generate_signal(symbol, df, timeframe)
            signals.append(sig)
        except Exception as e:
            logger.error(f"Signal generation failed for {symbol}: {e}")

    return signals


# ─────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.append("..")
    from data.fetcher import get_ohlcv

    coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    print("=" * 60)
    print("SIGNAL ENGINE TEST")
    print("=" * 60)

    for coin in coins:
        df = get_ohlcv(coin, "1h", 200)
        signal = generate_signal(coin, df, "1h")
        s = signal.to_dict()
        print(f"\n{s['symbol']} [{s['timeframe']}]")
        print(f"  Signal:     {s['signal']} ({s['confidence']}% confidence)")
        print(f"  Price:      {s['price']}")
        print(f"  Stop Loss:  {s['stop_loss']}")
        print(f"  Take Profit:{s['take_profit']}")
        print(f"  R:R Ratio:  1:{s['risk_reward']}")
        print(f"  Reasons:")
        for r in s["reason"][:3]:
            print(f"    → {r}")
