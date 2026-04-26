#!/usr/bin/env python3
# main.py
# ============================================
# CryptoAI Trader - Main Entry Point
# ============================================
#
# Usage:
#   python main.py              → Run signal scan once
#   streamlit run ui/dashboard.py → Run web dashboard
#
# ============================================

import sys
import os

# Make sure imports work from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import DEFAULT_COINS, DEFAULT_TIMEFRAME
from config.logger import get_logger
from data.fetcher import get_ohlcv, get_current_price
from strategy.signal_engine import generate_signal

logger = get_logger("main")


def run_signal_scan(coins: list = None, timeframe: str = None):
    """
    Scans all configured coins and prints signals.
    This is the core loop of the trading system.
    """
    coins = coins or DEFAULT_COINS
    timeframe = timeframe or DEFAULT_TIMEFRAME

    print("\n" + "=" * 65)
    print("  📊 CryptoAI Trading System - Signal Scan")
    print("=" * 65)
    print(f"  Coins:     {', '.join(coins)}")
    print(f"  Timeframe: {timeframe}")
    print("=" * 65)

    for symbol in coins:
        try:
            print(f"\n🔍 Analyzing {symbol}...")
            df = get_ohlcv(symbol, timeframe, 300)
            signal = generate_signal(symbol, df, timeframe)
            s = signal.to_dict()

            # Signal display
            icons = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
            print(f"\n  {icons[s['signal']]} {s['symbol']} [{s['timeframe']}]")
            print(f"     Signal:      {s['signal']} ({s['confidence']}% confidence)")
            print(f"     Price:       ${s['price']:,.4f}")
            print(f"     Stop Loss:   ${s['stop_loss']:,.4f}")
            print(f"     Take Profit: ${s['take_profit']:,.4f}")
            print(f"     R:R Ratio:   1:{s['risk_reward']:.1f}")
            print(f"     Context:     {s['smc_context']}")
            print(f"     Top reasons:")
            for r in s["reason"][:2]:
                print(f"       → {r}")

        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")
            print(f"  ❌ Error analyzing {symbol}: {e}")

    print("\n" + "=" * 65)
    print("  ✅ Scan complete")
    print("  💡 Run 'streamlit run ui/dashboard.py' for full dashboard")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_signal_scan()
