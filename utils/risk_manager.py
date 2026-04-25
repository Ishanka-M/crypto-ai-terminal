"""
Risk Management & Auto Compounding Strategy
Position sizing, SL/TP calculation, Kelly Criterion
"""
import math

def calculate_position_size(
    capital: float,
    risk_pct: float,  # e.g. 1.0 for 1%
    entry_price: float,
    stop_loss_price: float
) -> dict:
    """Risk-based position sizing"""
    risk_amount = capital * (risk_pct / 100)
    price_diff = abs(entry_price - stop_loss_price)
    if price_diff == 0:
        return {"error": "Stop loss equals entry price"}
    units = risk_amount / price_diff
    position_value = units * entry_price
    return {
        "units": round(units, 6),
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_pct": risk_pct,
    }

def calculate_sl_tp(
    entry: float,
    direction: str,  # "long" or "short"
    atr: float,
    sl_multiplier: float = 1.5,
    rr_ratio: float = 2.0,
) -> dict:
    """ATR-based Stop Loss and Take Profit"""
    if direction == "long":
        sl = entry - atr * sl_multiplier
        tp = entry + atr * sl_multiplier * rr_ratio
    else:
        sl = entry + atr * sl_multiplier
        tp = entry - atr * sl_multiplier * rr_ratio

    return {
        "entry": round(entry, 6),
        "stop_loss": round(sl, 6),
        "take_profit": round(tp, 6),
        "sl_distance": round(abs(entry - sl), 6),
        "tp_distance": round(abs(tp - entry), 6),
        "rr_ratio": rr_ratio,
    }

def auto_compound(
    initial_capital: float,
    monthly_return_pct: float,
    months: int
) -> list:
    """Calculate auto compounding growth over time"""
    curve = []
    capital = initial_capital
    for m in range(months + 1):
        curve.append({
            "month": m,
            "capital": round(capital, 2),
            "gain": round(capital - initial_capital, 2)
        })
        capital *= (1 + monthly_return_pct / 100)
    return curve

def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly Criterion for optimal position sizing"""
    if avg_loss == 0:
        return 0
    b = avg_win / avg_loss
    p = win_rate / 100
    q = 1 - p
    kelly = (b * p - q) / b
    # Half Kelly for safety
    return max(0, round(kelly * 50, 2))  # returns as % of capital

def get_risk_label(risk_pct: float) -> str:
    if risk_pct <= 1:
        return "🟢 Low Risk"
    elif risk_pct <= 2:
        return "🟡 Moderate"
    elif risk_pct <= 5:
        return "🟠 High Risk"
    return "🔴 Very High Risk"
