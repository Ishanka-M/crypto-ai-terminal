"""
Crypto Data Fetcher - Maximum fallback chain
Binance → Bybit → OKX → Kraken → CoinGecko → CryptoCompare → Mexc
"""
import pandas as pd
import numpy as np
import requests
import streamlit as st

POPULAR_COINS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","AVAXUSDT","MATICUSDT","DOTUSDT",
    "LINKUSDT","UNIUSDT","LTCUSDT","ATOMUSDT","NEARUSDT",
    "APTUSDT","ARBUSDT","OPUSDT","INJUSDT","SUIUSDT",
]

TIMEFRAMES = {
    "1m":"1 Minute","5m":"5 Minutes","15m":"15 Minutes",
    "1h":"1 Hour","4h":"4 Hours","1d":"1 Day",
}

COINGECKO_IDS = {
    "BTCUSDT":"bitcoin","ETHUSDT":"ethereum","BNBUSDT":"binancecoin",
    "SOLUSDT":"solana","XRPUSDT":"ripple","ADAUSDT":"cardano",
    "DOGEUSDT":"dogecoin","AVAXUSDT":"avalanche-2","MATICUSDT":"matic-network",
    "DOTUSDT":"polkadot","LINKUSDT":"chainlink","UNIUSDT":"uniswap",
    "LTCUSDT":"litecoin","ATOMUSDT":"cosmos","NEARUSDT":"near",
    "APTUSDT":"aptos","ARBUSDT":"arbitrum","OPUSDT":"optimism",
    "INJUSDT":"injective-protocol","SUIUSDT":"sui",
}

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

def _sym(s): return s.replace("USDT","")


# ── LIVE PRICE SOURCES ────────────────────────────────────────────────────────

def _binance(symbol):
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                         params={"symbol":symbol}, headers=H, timeout=8)
        if r.status_code == 200:
            d = r.json()
            p = float(d.get("lastPrice",0))
            if p > 0:
                return {"symbol":symbol,"price":p,"change_pct":float(d["priceChangePercent"]),
                        "high":float(d["highPrice"]),"low":float(d["lowPrice"]),
                        "volume":float(d["volume"]),"source":"Binance"}
    except: pass
    return None

def _bybit(symbol):
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers",
                         params={"category":"spot","symbol":symbol}, headers=H, timeout=8)
        if r.status_code == 200:
            items = r.json().get("result",{}).get("list",[])
            if items:
                d = items[0]
                p = float(d.get("lastPrice",0))
                if p > 0:
                    prev = float(d.get("prevPrice24h",p) or p)
                    chg = ((p - prev)/prev*100) if prev else 0
                    return {"symbol":symbol,"price":p,"change_pct":round(chg,2),
                            "high":float(d.get("highPrice24h",p)),"low":float(d.get("lowPrice24h",p)),
                            "volume":float(d.get("volume24h",0)),"source":"Bybit"}
    except: pass
    return None

def _okx(symbol):
    try:
        inst = symbol.replace("USDT","-USDT")
        r = requests.get("https://www.okx.com/api/v5/market/ticker",
                         params={"instId":inst}, headers=H, timeout=8)
        if r.status_code == 200:
            data = r.json().get("data",[])
            if data:
                d = data[0]
                p = float(d.get("last",0))
                if p > 0:
                    op = float(d.get("sodUtc0",p) or p)
                    chg = ((p-op)/op*100) if op else 0
                    return {"symbol":symbol,"price":p,"change_pct":round(chg,2),
                            "high":float(d.get("high24h",p)),"low":float(d.get("low24h",p)),
                            "volume":float(d.get("vol24h",0)),"source":"OKX"}
    except: pass
    return None

def _kraken(symbol):
    kraken_map = {
        "BTCUSDT":"XBTUSD","ETHUSDT":"ETHUSD","LTCUSDT":"LTCUSD",
        "SOLUSDT":"SOLUSD","DOTUSDT":"DOTUSD","ADAUSDT":"ADAUSD",
        "XRPUSDT":"XRPUSD","LINKUSDT":"LINKUSD","ATOMUSDT":"ATOMUSD",
    }
    pair = kraken_map.get(symbol)
    if not pair: return None
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker",
                         params={"pair":pair}, headers=H, timeout=8)
        if r.status_code == 200:
            result = r.json().get("result",{})
            if result:
                d = list(result.values())[0]
                p = float(d["c"][0])
                if p > 0:
                    op = float(d["o"])
                    chg = ((p-op)/op*100) if op else 0
                    return {"symbol":symbol,"price":p,"change_pct":round(chg,2),
                            "high":float(d["h"][1]),"low":float(d["l"][1]),
                            "volume":float(d["v"][1]),"source":"Kraken"}
    except: pass
    return None

def _coingecko(symbol):
    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id: return None
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
            params={"ids":cg_id,"vs_currencies":"usd","include_24hr_change":"true",
                    "include_24hr_vol":"true","include_high_24h":"true","include_low_24h":"true"},
            headers=H, timeout=10)
        if r.status_code == 200:
            d = r.json().get(cg_id,{})
            p = d.get("usd",0)
            if p and p > 0:
                return {"symbol":symbol,"price":float(p),
                        "change_pct":float(d.get("usd_24h_change",0)),
                        "high":float(d.get("usd_24h_high",p)),
                        "low":float(d.get("usd_24h_low",p)),
                        "volume":float(d.get("usd_24h_vol",0)),"source":"CoinGecko"}
    except: pass
    return None

def _cryptocompare(symbol):
    sym = _sym(symbol)
    try:
        r = requests.get("https://min-api.cryptocompare.com/data/pricemultifull",
            params={"fsyms":sym,"tsyms":"USD"}, headers=H, timeout=8)
        if r.status_code == 200:
            raw = r.json().get("RAW",{}).get(sym,{}).get("USD",{})
            p = raw.get("PRICE",0)
            if p and p > 0:
                return {"symbol":symbol,"price":float(p),
                        "change_pct":float(raw.get("CHANGEPCT24HOUR",0)),
                        "high":float(raw.get("HIGH24HOUR",p)),
                        "low":float(raw.get("LOW24HOUR",p)),
                        "volume":float(raw.get("VOLUME24HOUR",0)),"source":"CryptoCompare"}
    except: pass
    return None

def _mexc(symbol):
    try:
        r = requests.get("https://api.mexc.com/api/v3/ticker/24hr",
                         params={"symbol":symbol}, headers=H, timeout=8)
        if r.status_code == 200:
            d = r.json()
            p = float(d.get("lastPrice",0))
            if p > 0:
                return {"symbol":symbol,"price":p,
                        "change_pct":float(d.get("priceChangePercent",0)),
                        "high":float(d.get("highPrice",p)),
                        "low":float(d.get("lowPrice",p)),
                        "volume":float(d.get("volume",0)),"source":"MEXC"}
    except: pass
    return None

# Full fallback chain
PRICE_SOURCES = [_binance, _bybit, _okx, _kraken, _coingecko, _cryptocompare, _mexc]

def get_live_price(symbol: str) -> dict:
    errors = []
    for fn in PRICE_SOURCES:
        try:
            result = fn(symbol)
            if result and result.get("price",0) > 0:
                return result
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
    return {"symbol":symbol,"price":0,"change_pct":0,"high":0,"low":0,
            "volume":0,"source":"FAILED","errors":errors}


# ── OHLCV SOURCES ─────────────────────────────────────────────────────────────

def _ohlcv_binance(symbol, interval, limit):
    try:
        r = requests.get("https://api.binance.com/api/v3/klines",
            params={"symbol":symbol,"interval":interval,"limit":limit},
            headers=H, timeout=12)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 10:
                df = pd.DataFrame(data, columns=[
                    "timestamp","open","high","low","close","volume",
                    "close_time","quote_vol","trades","tb_base","tb_quote","ignore"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                for c in ["open","high","low","close","volume"]:
                    df[c] = df[c].astype(float)
                df.set_index("timestamp", inplace=True)
                if df["close"].iloc[-1] > 0:
                    return df[["open","high","low","close","volume"]]
    except: pass
    return pd.DataFrame()

def _ohlcv_bybit(symbol, interval, limit):
    bybit_tf = {"1m":"1","5m":"5","15m":"15","1h":"60","4h":"240","1d":"D"}
    tf = bybit_tf.get(interval,"60")
    try:
        r = requests.get("https://api.bybit.com/v5/market/kline",
            params={"category":"spot","symbol":symbol,"interval":tf,"limit":limit},
            headers=H, timeout=12)
        if r.status_code == 200:
            items = r.json().get("result",{}).get("list",[])
            if items and len(items) > 10:
                df = pd.DataFrame(items, columns=["timestamp","open","high","low","close","volume","turnover"])
                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
                for c in ["open","high","low","close","volume"]:
                    df[c] = df[c].astype(float)
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
                if df["close"].iloc[-1] > 0:
                    return df[["open","high","low","close","volume"]]
    except: pass
    return pd.DataFrame()

def _ohlcv_okx(symbol, interval, limit):
    okx_tf = {"1m":"1m","5m":"5m","15m":"15m","1h":"1H","4h":"4H","1d":"1D"}
    tf = okx_tf.get(interval,"1H")
    inst = symbol.replace("USDT","-USDT")
    try:
        r = requests.get("https://www.okx.com/api/v5/market/candles",
            params={"instId":inst,"bar":tf,"limit":limit},
            headers=H, timeout=12)
        if r.status_code == 200:
            items = r.json().get("data",[])
            if items and len(items) > 10:
                df = pd.DataFrame(items, columns=["timestamp","open","high","low","close","vol","volCcy","volCcyQuote","confirm"])
                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
                for c in ["open","high","low","close","vol"]:
                    df[c] = df[c].astype(float)
                df = df.rename(columns={"vol":"volume"})
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
                if df["close"].iloc[-1] > 0:
                    return df[["open","high","low","close","volume"]]
    except: pass
    return pd.DataFrame()

CC_EP  = {"1m":"histominute","5m":"histominute","15m":"histominute","1h":"histohour","4h":"histohour","1d":"histoday"}
CC_AGG = {"1m":1,"5m":5,"15m":15,"1h":1,"4h":4,"1d":1}

def _ohlcv_cryptocompare(symbol, interval, limit):
    sym = _sym(symbol)
    ep  = CC_EP.get(interval,"histohour")
    agg = CC_AGG.get(interval,1)
    try:
        r = requests.get(f"https://min-api.cryptocompare.com/data/v2/{ep}",
            params={"fsym":sym,"tsym":"USD","limit":limit,"aggregate":agg},
            headers=H, timeout=12)
        if r.status_code == 200:
            data = r.json().get("Data",{}).get("Data",[])
            if data and len(data) > 10:
                df = pd.DataFrame(data)
                df["timestamp"] = pd.to_datetime(df["time"], unit="s")
                df = df.rename(columns={"volumefrom":"volume"})
                df.set_index("timestamp", inplace=True)
                df = df[["open","high","low","close","volume"]].astype(float)
                if df["close"].iloc[-1] > 0:
                    return df
    except: pass
    return pd.DataFrame()

def _ohlcv_mexc(symbol, interval, limit):
    try:
        r = requests.get("https://api.mexc.com/api/v3/klines",
            params={"symbol":symbol,"interval":interval,"limit":limit},
            headers=H, timeout=12)
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 10:
                df = pd.DataFrame(data, columns=[
                    "timestamp","open","high","low","close","volume",
                    "close_time","quote_vol","trades","tb_base","tb_quote","ignore"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                for c in ["open","high","low","close","volume"]:
                    df[c] = df[c].astype(float)
                df.set_index("timestamp", inplace=True)
                if df["close"].iloc[-1] > 0:
                    return df[["open","high","low","close","volume"]]
    except: pass
    return pd.DataFrame()

OHLCV_SOURCES = [_ohlcv_binance, _ohlcv_bybit, _ohlcv_okx, _ohlcv_cryptocompare, _ohlcv_mexc]

def get_klines(symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    for fn in OHLCV_SOURCES:
        try:
            df = fn(symbol, interval, limit)
            if not df.empty and len(df) > 20:
                return df
        except: pass
    return pd.DataFrame()


# ── API STATUS ────────────────────────────────────────────────────────────────

def get_api_status() -> dict:
    endpoints = {
        "Binance":       "https://api.binance.com/api/v3/ping",
        "Bybit":         "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
        "OKX":           "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
        "Kraken":        "https://api.kraken.com/0/public/Time",
        "CoinGecko":     "https://api.coingecko.com/api/v3/ping",
        "CryptoCompare": "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD",
        "MEXC":          "https://api.mexc.com/api/v3/ping",
    }
    status = {}
    for name, url in endpoints.items():
        try:
            r = requests.get(url, headers=H, timeout=5)
            if r.status_code == 200:
                status[name] = "🟢 Online"
            else:
                status[name] = f"🔴 HTTP {r.status_code}"
        except Exception as e:
            status[name] = f"🔴 {str(e)[:30]}"
    return status

def get_multi_timeframe(symbol, timeframes=["15m","1h","4h"]):
    return {tf: get_klines(symbol, tf, limit=300) for tf in timeframes}
