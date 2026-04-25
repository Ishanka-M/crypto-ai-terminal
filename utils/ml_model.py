"""
Machine Learning Model for Crypto Signal Prediction
XGBoost + Feature Engineering
Multi-timeframe features
"""
import pandas as pd
import numpy as np
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from xgboost import XGBClassifier
from utils.indicators import run_all_indicators

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering from indicator data"""
    df = run_all_indicators(df.copy())
    features = pd.DataFrame(index=df.index)

    # Price action
    features["returns_1"] = df["close"].pct_change(1)
    features["returns_3"] = df["close"].pct_change(3)
    features["returns_5"] = df["close"].pct_change(5)
    features["returns_10"] = df["close"].pct_change(10)

    # RSI
    if "rsi" in df:
        features["rsi"] = df["rsi"]
        features["rsi_oversold"] = (df["rsi"] < 30).astype(int)
        features["rsi_overbought"] = (df["rsi"] > 70).astype(int)

    # EMA structure
    if "ema_9" in df and "ema_21" in df:
        features["ema_9_21_cross"] = (df["ema_9"] > df["ema_21"]).astype(int)
        features["ema_21_50_cross"] = (df["ema_21"] > df["ema_50"]).astype(int)
        features["price_above_ema50"] = (df["close"] > df["ema_50"]).astype(int)
        features["price_above_ema200"] = (df["close"] > df["ema_200"]).astype(int)

    # MACD
    if "macd" in df:
        features["macd"] = df["macd"]
        features["macd_hist"] = df["macd_hist"]
        features["macd_bullish"] = (df["macd"] > df["macd_signal"]).astype(int)

    # Bollinger
    if "bb_upper" in df:
        features["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)
        features["bb_squeeze"] = df["bb_width"]

    # Volume
    if "vol_ratio" in df:
        features["vol_ratio"] = df["vol_ratio"].fillna(1)

    # ATR
    if "atr" in df:
        features["atr_pct"] = df["atr"] / df["close"]

    # SMC
    if "ob_bull" in df:
        features["near_ob_bull"] = df["ob_bull"].astype(int)
        features["near_ob_bear"] = df["ob_bear"].astype(int)
    if "fvg_bull" in df:
        features["fvg_bull"] = df["fvg_bull"].astype(int)
        features["fvg_bear"] = df["fvg_bear"].astype(int)

    # Candle pattern
    features["candle_body"] = abs(df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-10)
    features["upper_wick"] = (df["high"] - df[["open", "close"]].max(axis=1)) / (df["high"] - df["low"] + 1e-10)
    features["lower_wick"] = (df[["open", "close"]].min(axis=1) - df["low"]) / (df["high"] - df["low"] + 1e-10)

    return features


def build_labels(df: pd.DataFrame, forward_bars: int = 5, threshold: float = 0.005) -> pd.Series:
    """
    1 = BUY (price goes up >0.5% in next N bars)
    0 = SELL/HOLD (price goes down or stays)
    """
    future_return = df["close"].shift(-forward_bars) / df["close"] - 1
    return (future_return > threshold).astype(int)


def train_model(df: pd.DataFrame, symbol: str) -> dict:
    """Train XGBoost model for given coin"""
    features = build_features(df)
    labels = build_labels(df)

    # Align and drop NaNs
    combined = pd.concat([features, labels.rename("label")], axis=1).dropna()
    if len(combined) < 100:
        return {"error": "Not enough data to train", "symbol": symbol}

    X = combined.drop("label", axis=1)
    y = combined["label"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42
    )
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    y_pred = model.predict(X_test_s)
    acc = accuracy_score(y_test, y_pred)

    # Save model and scaler
    safe_sym = symbol.replace("/", "_")
    joblib.dump(model, f"{MODEL_DIR}/{safe_sym}_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/{safe_sym}_scaler.pkl")
    joblib.dump(list(X.columns), f"{MODEL_DIR}/{safe_sym}_features.pkl")

    return {
        "symbol": symbol,
        "accuracy": round(acc * 100, 2),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "model_saved": True
    }


def predict_signal(df: pd.DataFrame, symbol: str) -> dict:
    """Predict BUY/SELL signal for latest candle"""
    safe_sym = symbol.replace("/", "_")
    model_path = f"{MODEL_DIR}/{safe_sym}_model.pkl"
    scaler_path = f"{MODEL_DIR}/{safe_sym}_scaler.pkl"
    feat_path = f"{MODEL_DIR}/{safe_sym}_features.pkl"

    if not all(os.path.exists(p) for p in [model_path, scaler_path, feat_path]):
        return {"signal": "⚠️ NOT TRAINED", "confidence": 0, "trained": False}

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    feature_cols = joblib.load(feat_path)

    features = build_features(df)
    features = features.dropna()

    if features.empty:
        return {"signal": "⚠️ NO DATA", "confidence": 0, "trained": True}

    latest = features.iloc[[-1]][feature_cols]
    latest_scaled = scaler.transform(latest)

    proba = model.predict_proba(latest_scaled)[0]
    pred = model.predict(latest_scaled)[0]

    confidence = round(float(max(proba)) * 100, 1)
    signal = "🟢 BUY" if pred == 1 else "🔴 SELL"

    return {
        "signal": signal,
        "confidence": confidence,
        "buy_prob": round(float(proba[1]) * 100, 1) if len(proba) > 1 else 0,
        "sell_prob": round(float(proba[0]) * 100, 1),
        "trained": True
    }


def run_backtest(df: pd.DataFrame, symbol: str, initial_capital: float = 1000.0) -> dict:
    """Simple backtest using model predictions"""
    safe_sym = symbol.replace("/", "_")
    model_path = f"{MODEL_DIR}/{safe_sym}_model.pkl"
    scaler_path = f"{MODEL_DIR}/{safe_sym}_scaler.pkl"
    feat_path = f"{MODEL_DIR}/{safe_sym}_features.pkl"

    if not all(os.path.exists(p) for p in [model_path, scaler_path, feat_path]):
        return {"error": "Model not trained"}

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    feature_cols = joblib.load(feat_path)

    features = build_features(df)
    combined = pd.concat([features[feature_cols], df["close"]], axis=1).dropna()

    X = combined[feature_cols]
    closes = combined["close"]

    X_scaled = scaler.transform(X)
    signals = model.predict(X_scaled)

    capital = initial_capital
    position = 0
    trades = []
    equity_curve = [capital]
    buy_price = 0

    for i in range(1, len(signals)):
        price = closes.iloc[i]
        if signals[i] == 1 and position == 0:
            position = capital / price
            buy_price = price
            capital = 0
            trades.append({"type": "BUY", "price": price, "idx": i})
        elif signals[i] == 0 and position > 0:
            capital = position * price
            pnl = ((price - buy_price) / buy_price) * 100
            trades.append({"type": "SELL", "price": price, "pnl": round(pnl, 2), "idx": i})
            position = 0
        equity_curve.append(capital if position == 0 else position * price)

    final_capital = capital if position == 0 else position * closes.iloc[-1]
    total_return = ((final_capital - initial_capital) / initial_capital) * 100
    win_trades = [t for t in trades if t.get("type") == "SELL" and t.get("pnl", 0) > 0]
    win_rate = len(win_trades) / max(len([t for t in trades if t.get("type") == "SELL"]), 1) * 100

    return {
        "initial_capital": initial_capital,
        "final_capital": round(final_capital, 2),
        "total_return_pct": round(total_return, 2),
        "total_trades": len([t for t in trades if t.get("type") == "SELL"]),
        "win_rate": round(win_rate, 1),
        "equity_curve": equity_curve,
        "trades": trades[-20:]
    }
