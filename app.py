# app.py
# ============================================
# CryptoAI Terminal — Main Application
# Streamlit Cloud Ready | All Phases Included
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import os
import sys

# ── Path setup ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Page config (MUST be first Streamlit call) ──
st.set_page_config(
    page_title="CryptoAI Terminal",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Safe imports (no crash if package missing) ──
try:
    from utils.gemini_rotator import (
        get_gemini_rotator, initialize_rotator_from_keys,
        quick_chat, is_gemini_available, get_genai_install_status,
        GENAI_AVAILABLE,
    )
except Exception as e:
    GENAI_AVAILABLE = False
    def quick_chat(p, s=""): return "⚠️ Gemini not available"
    def is_gemini_available(): return False
    def get_genai_install_status(): return {"installed": False, "configured": False, "key_count": 0}
    def initialize_rotator_from_keys(k, m=""): return None
    def get_gemini_rotator(): return None

try:
    from utils.sheets_manager import (
        save_api_keys_to_sheet, load_api_keys_from_sheet,
        save_settings_to_sheet, load_settings_from_sheet,
        log_signal_to_sheet, get_trade_history,
        is_sheets_available, get_sheets_status,
    )
    SHEETS_AVAILABLE = True
except Exception:
    SHEETS_AVAILABLE = False
    def save_api_keys_to_sheet(*a, **k): return False
    def load_api_keys_from_sheet(*a, **k): return {}
    def save_settings_to_sheet(*a, **k): return False
    def load_settings_from_sheet(*a, **k): return {}
    def log_signal_to_sheet(*a, **k): return False
    def get_trade_history(*a, **k): return pd.DataFrame()
    def is_sheets_available(): return False
    def get_sheets_status(): return {"library_installed": False, "authenticated": False}


# ─────────────────────────────────────────
# DEMO DATA ENGINE
# ─────────────────────────────────────────

def generate_ohlcv(symbol: str, tf: str = "1h", limit: int = 300) -> pd.DataFrame:
    BASE = {"BTCUSDT": 65000, "ETHUSDT": 3500, "SOLUSDT": 180,
            "XRPUSDT": 0.60, "BNBUSDT": 580, "ADAUSDT": 0.45}
    base = BASE.get(symbol, 100)
    TF_MIN = {"1m":1,"5m":5,"15m":15,"1h":60,"4h":240,"1d":1440}
    mins = TF_MIN.get(tf, 60)
    from datetime import timedelta
    end = datetime.now()
    ts = [end - timedelta(minutes=mins*i) for i in range(limit,0,-1)]
    np.random.seed(hash(symbol) % 999)
    rets = np.random.normal(0.0002, 0.015, limit)
    prices = base * np.cumprod(1 + rets)
    rows = []
    for i,(t,c) in enumerate(zip(ts,prices)):
        vol = c * np.random.uniform(0.003, 0.018)
        o = prices[i-1] if i>0 else c
        rows.append({"timestamp":t,"open":round(o,4),"high":round(max(o,c)+abs(np.random.normal(0,vol)),4),
                     "low":round(min(o,c)-abs(np.random.normal(0,vol)),4),
                     "close":round(c,4),"volume":round(np.random.uniform(100,5000)*base/100,2)})
    df = pd.DataFrame(rows).set_index("timestamp")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    # RSI
    d = close.diff()
    g = d.where(d>0,0).ewm(com=13,min_periods=14).mean()
    l = (-d.where(d<0,0)).ewm(com=13,min_periods=14).mean()
    df["rsi"] = (100 - 100/(1+g/l.replace(0,np.nan))).fillna(50)
    # EMAs
    for p in [9,21,50,200]: df[f"ema{p}"] = close.ewm(span=p,adjust=False).mean()
    # MACD
    df["macd"] = close.ewm(span=12,adjust=False).mean() - close.ewm(span=26,adjust=False).mean()
    df["macd_sig"] = df["macd"].ewm(span=9,adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]
    # BB
    sma = close.rolling(20).mean(); std = close.rolling(20).std()
    df["bb_up"] = sma+2*std; df["bb_lo"] = sma-2*std; df["bb_mid"] = sma
    df["bb_pct"] = ((close-df["bb_lo"])/(df["bb_up"]-df["bb_lo"])).clip(0,1)
    # Volume
    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"]/df["vol_ma"]
    df["trend_up"]  = (df["ema9"]>df["ema21"]) & (df["ema21"]>df["ema50"])
    df["trend_dn"]  = (df["ema9"]<df["ema21"]) & (df["ema21"]<df["ema50"])
    return df


def generate_signal(symbol: str, df: pd.DataFrame, tf: str) -> dict:
    last = df.iloc[-1]
    buy_pts = sell_pts = 0
    reasons = []
    rsi = last["rsi"]
    if rsi < 32:  buy_pts+=25; reasons.append(f"RSI oversold ({rsi:.1f})")
    elif rsi > 68: sell_pts+=25; reasons.append(f"RSI overbought ({rsi:.1f})")
    if last["trend_up"]:  buy_pts+=25; reasons.append("EMA bullish stack")
    elif last["trend_dn"]: sell_pts+=25; reasons.append("EMA bearish stack")
    if last["macd"]>last["macd_sig"] and last["macd_hist"]>0: buy_pts+=20; reasons.append("MACD bullish")
    elif last["macd"]<last["macd_sig"] and last["macd_hist"]<0: sell_pts+=20; reasons.append("MACD bearish")
    if last["bb_pct"]<0.2: buy_pts+=15; reasons.append("Near BB lower band")
    elif last["bb_pct"]>0.8: sell_pts+=15; reasons.append("Near BB upper band")
    if last["vol_ratio"]>1.5:
        if buy_pts>sell_pts: buy_pts+=15; reasons.append(f"High volume confirms ({last['vol_ratio']:.1f}x)")
        else: sell_pts+=15; reasons.append(f"High volume confirms ({last['vol_ratio']:.1f}x)")
    diff = buy_pts - sell_pts
    price = float(last["close"])
    atr = float(df["high"].iloc[-20:].max() - df["low"].iloc[-20:].min()) * 0.03
    if diff >= 20:
        sig = "BUY"; conf = min(50+diff, 92)
        sl = price - atr*1.5; tp = price + atr*3
    elif diff <= -20:
        sig = "SELL"; conf = min(50+abs(diff), 92)
        sl = price + atr*1.5; tp = price - atr*3
    else:
        sig = "HOLD"; conf = 45; sl = price; tp = price
    rr = abs(tp-price)/abs(sl-price) if abs(sl-price)>0 else 0
    return {"symbol":symbol,"signal":sig,"confidence":round(conf,1),"price":price,
            "stop_loss":round(sl,4),"take_profit":round(tp,4),"risk_reward":round(rr,2),
            "timeframe":tf,"reason":reasons,"timestamp":str(df.index[-1])}


# ─────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────

DEFAULTS = {
    "coins": ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"],
    "timeframe": "1h",
    "risk_pct": 1.0,
    "auto_trading": False,
    "ai_signals": True,
    "news_filter": True,
    "binance_api_key": "",
    "binance_api_secret": "",
    "gemini_api_keys": [],
    "telegram_token": "",
    "telegram_chat_id": "",
    "spreadsheet_id": "",
    "gemini_model": "gemini-1.5-flash",
    "gcp_credentials": None,
    "signals_cache": {},
    "chat_history": [],
    "trade_log": [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────
# GLOBAL CSS — Terminal Dark Theme
# ─────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;700;800&display=swap');

:root {
  --bg:      #060910;
  --surface: #0c1117;
  --panel:   #111827;
  --border:  #1e2d3d;
  --accent:  #00d4ff;
  --green:   #00ff88;
  --red:     #ff3355;
  --yellow:  #ffbb00;
  --text:    #c9d1d9;
  --muted:   #4a5568;
}

.stApp                    { background: var(--bg); font-family: 'JetBrains Mono', monospace; }
.stSidebar                { background: var(--surface) !important; border-right: 1px solid var(--border); }
h1,h2,h3                  { font-family: 'Syne', sans-serif !important; color: var(--accent) !important; }
.stButton > button        { background: transparent; border: 1px solid var(--accent); color: var(--accent);
                            font-family: 'JetBrains Mono'; border-radius: 6px; transition: all .2s; }
.stButton > button:hover  { background: var(--accent)22; }
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  background: var(--panel) !important; border: 1px solid var(--border) !important;
  color: var(--text) !important; font-family: 'JetBrains Mono' !important; }
.stTabs [data-baseweb="tab"]           { color: var(--muted); font-family: 'JetBrains Mono'; font-size: 0.8em; }
.stTabs [aria-selected="true"]         { color: var(--accent) !important; border-bottom-color: var(--accent) !important; }
div[data-testid="metric-container"]    { background: var(--panel); border: 1px solid var(--border);
                                         border-radius: 10px; padding: 12px; }
.stDataFrame                           { background: var(--panel) !important; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:12px;
        padding:16px; margin:8px 0; }
.sig-buy  { border-color:var(--green)88 !important; background:linear-gradient(135deg,#0a1f14,#0d1117); }
.sig-sell { border-color:var(--red)88   !important; background:linear-gradient(135deg,#1f0a0d,#0d1117); }
.sig-hold { border-color:var(--yellow)88!important; background:linear-gradient(135deg,#1f1a0a,#0d1117); }
.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-green  { background:var(--green); box-shadow:0 0 8px var(--green); }
.dot-red    { background:var(--red);   box-shadow:0 0 8px var(--red); }
.dot-yellow { background:var(--yellow);box-shadow:0 0 8px var(--yellow); }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────

with st.sidebar:
    st.markdown("<h2 style='margin:0;letter-spacing:2px'>📡 CRYPTOAI</h2>", unsafe_allow_html=True)
    st.markdown("<small style='color:#4a5568'>Terminal v2.0</small>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Detailed API Status Panel ────────────
    gemini_ok   = is_gemini_available()
    sheets_ok   = is_sheets_available()
    binance_ok  = bool(st.session_state.binance_api_key)
    tg_ok       = bool(st.session_state.telegram_token)
    genai_info  = get_genai_install_status()
    sheets_info = get_sheets_status()

    def _status_row(label, ok, detail="", warn=False):
        if ok:
            dot="dot-green"; badge="LIVE"; bc="#00ff8822"; tc="#00ff88"
        elif warn:
            dot="dot-yellow"; badge="DEMO"; bc="#ffbb0022"; tc="#ffbb00"
        else:
            dot="dot-red"; badge="OFF"; bc="#ff335522"; tc="#ff3355"
        d_html = f"<div style='font-size:0.68em;color:#4a5568;padding:0 8px 4px'>{detail}</div>" if detail else ""
        return (f"<div style='display:flex;align-items:center;justify-content:space-between;"
                f"background:{bc};border-radius:6px;padding:5px 8px;margin:3px 0;font-size:0.75em'>"
                f"<span><span class='status-dot {dot}'></span>{label}</span>"
                f"<span style='color:{tc};font-weight:700;font-size:0.85em'>{badge}</span></div>{d_html}")

    if gemini_ok:
        rotator  = get_gemini_rotator()
        g_detail = f"Keys: {genai_info['key_count']} · Model: {st.session_state.get('gemini_model','flash')[:12]}"
    elif genai_info["installed"]:
        g_detail = "Installed · No API key"
    else:
        g_detail = "Package missing → add to requirements.txt"

    if sheets_ok:
        sid      = st.session_state.spreadsheet_id
        s_detail = f"Sheet: {sid[:18]}..." if sid else "Auth OK · No sheet ID"
    elif sheets_info.get("library_installed"):
        s_detail = "Installed · No credentials"
    else:
        s_detail = "gspread not installed"

    b_detail = f"Key: {st.session_state.binance_api_key[:8]}..." if binance_ok else "Using demo data (safe)"
    t_detail = "Alerts enabled" if tg_ok else "Not configured"

    st.markdown(
        _status_row("🤖 Gemini AI",    gemini_ok,  g_detail, warn=False) +
        _status_row("📋 Google Sheets",sheets_ok,  s_detail, warn=not sheets_ok) +
        _status_row("🔶 Binance",      binance_ok, b_detail, warn=not binance_ok) +
        _status_row("📬 Telegram",     tg_ok,      t_detail, warn=not tg_ok),
        unsafe_allow_html=True
    )
    if st.button("🔄 Check Status", use_container_width=True):
        st.rerun()

    st.markdown("---")
    st.markdown("**🪙 Coins**")
    coins = st.multiselect("Active", st.session_state.coins,
                           default=st.session_state.coins[:4], label_visibility="collapsed")
    new_c = st.text_input("Add coin", placeholder="BNBUSDT").upper()
    if st.button("➕ Add") and new_c and new_c not in st.session_state.coins:
        st.session_state.coins.append(new_c); st.rerun()

    st.markdown("---")
    tf = st.select_slider("⏱ Timeframe", ["1m","5m","15m","1h","4h","1d"],
                          value=st.session_state.timeframe)
    st.session_state.timeframe = tf

    st.markdown("---")
    st.toggle("🤖 Auto Trading", key="auto_trading")
    st.toggle("🧠 AI Signals",   key="ai_signals")
    st.toggle("📰 News Filter",  key="news_filter")
    if st.session_state.auto_trading:
        st.error("⚠️ Auto trading ON")

    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.session_state.signals_cache = {}; st.rerun()


# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────

col_h1, col_h2 = st.columns([4,1])
with col_h1:
    st.markdown("<h1 style='margin:0;font-size:1.8em;letter-spacing:3px'>📡 CRYPTOAI TERMINAL</h1>",
                unsafe_allow_html=True)
with col_h2:
    st.markdown(f"<div style='text-align:right;color:#4a5568;font-size:0.75em;padding-top:8px'>"
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>", unsafe_allow_html=True)
st.markdown("---")


# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────

(tab_dash, tab_chart, tab_signals, tab_ai,
 tab_backtest, tab_sheets, tab_settings) = st.tabs([
    "📊 Dashboard", "📈 Chart", "🎯 Signals",
    "🤖 AI Chat", "📉 Backtest", "📋 Sheets", "⚙️ Settings"
])


# ══════════════════════════════════════════
# TAB 1 — DASHBOARD
# ══════════════════════════════════════════

with tab_dash:
    if not coins:
        st.warning("Select coins in the sidebar.")
    else:
        # Fetch and cache signals
        prog = st.progress(0, "Analyzing markets...")
        for i, sym in enumerate(coins):
            prog.progress((i+1)/len(coins), f"Analyzing {sym}...")
            key = f"{sym}_{tf}"
            if key not in st.session_state.signals_cache:
                df  = generate_ohlcv(sym, tf, 300)
                df  = add_indicators(df)
                sig = generate_signal(sym, df, tf)
                ch24 = ((df["close"].iloc[-1]-df["close"].iloc[-min(96,len(df)-1)])/
                        df["close"].iloc[-min(96,len(df)-1)]*100)
                st.session_state.signals_cache[key] = {
                    "sig": sig, "df": df, "ch24": round(ch24,2)
                }
        prog.empty()

        cached = {s: st.session_state.signals_cache[f"{s}_{tf}"] for s in coins
                  if f"{s}_{tf}" in st.session_state.signals_cache}

        # ── Market table ─────────────────────
        rows = []
        for sym, c in cached.items():
            s = c["sig"]
            ch = c["ch24"]
            rows.append({
                "Symbol": sym,
                "Price":  f"${s['price']:,.4f}",
                "24h":    f"{ch:+.2f}%",
                "Signal": s["signal"],
                "Conf":   f"{s['confidence']}%",
                "SL":     f"${s['stop_loss']:,.4f}",
                "TP":     f"${s['take_profit']:,.4f}",
                "R:R":    f"1:{s['risk_reward']:.1f}",
            })
        df_tbl = pd.DataFrame(rows)

        def _color_sig(v):
            return ("color:#00ff88;font-weight:700" if v=="BUY" else
                    "color:#ff3355;font-weight:700" if v=="SELL" else "color:#ffbb00")
        def _color_ch(v):
            return "color:#00ff88" if float(v.replace("%","").replace("+",""))>=0 else "color:#ff3355"

        st.dataframe(
            df_tbl.style.map(_color_sig, subset=["Signal"])
                        .map(_color_ch, subset=["24h"]),
            use_container_width=True, height=220
        )

        # ── Summary metrics ───────────────────
        buy_n  = sum(1 for c in cached.values() if c["sig"]["signal"]=="BUY")
        sell_n = sum(1 for c in cached.values() if c["sig"]["signal"]=="SELL")
        hold_n = sum(1 for c in cached.values() if c["sig"]["signal"]=="HOLD")
        avg_c  = np.mean([c["sig"]["confidence"] for c in cached.values()])
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("🟢 BUY",  buy_n)
        m2.metric("🔴 SELL", sell_n)
        m3.metric("🟡 HOLD", hold_n)
        m4.metric("📊 Avg Conf", f"{avg_c:.1f}%")

        # ── Signal cards ──────────────────────
        st.markdown("---")
        cols = st.columns(min(len(coins), 4))
        for i, (sym, c) in enumerate(cached.items()):
            s = c["sig"]
            css = {"BUY":"sig-buy","SELL":"sig-sell","HOLD":"sig-hold"}[s["signal"]]
            clr = {"BUY":"#00ff88","SELL":"#ff3355","HOLD":"#ffbb00"}[s["signal"]]
            emj = {"BUY":"▲","SELL":"▼","HOLD":"━"}[s["signal"]]
            with cols[i%4]:
                st.markdown(f"""
                <div class='card {css}'>
                  <div style='font-size:0.75em;color:#4a5568'>{sym}</div>
                  <div style='font-size:1.6em;color:{clr};font-weight:700'>{emj} {s['signal']}</div>
                  <div style='font-size:0.85em;color:{clr}'>{s['confidence']}% confidence</div>
                  <div style='font-size:0.78em;color:#6b7280;margin-top:6px'>
                    Price: ${s['price']:,.4f}<br>
                    SL: ${s['stop_loss']:,.4f}<br>
                    TP: ${s['take_profit']:,.4f}
                  </div>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════
# TAB 2 — CHART
# ══════════════════════════════════════════

with tab_chart:
    if not coins:
        st.warning("Select coins in sidebar.")
    else:
        c1,c2,c3 = st.columns([2,2,1])
        chart_sym = c1.selectbox("Coin", coins, key="chart_sym")
        chart_tf  = c2.select_slider("Timeframe", ["1m","5m","15m","1h","4h","1d"],
                                     value=tf, key="chart_tf2")
        n_candles = c3.select_slider("Candles", [100,200,300,500], value=200)

        with st.spinner("Loading chart..."):
            df_c = generate_ohlcv(chart_sym, chart_tf, n_candles)
            df_c = add_indicators(df_c)

        fig = make_subplots(rows=3,cols=1,row_heights=[0.6,0.2,0.2],
                            shared_xaxes=True,vertical_spacing=0.03,
                            subplot_titles=[f"{chart_sym} ({chart_tf})", "RSI", "Volume"])

        # Candles
        fig.add_trace(go.Candlestick(x=df_c.index,open=df_c["open"],high=df_c["high"],
            low=df_c["low"],close=df_c["close"],name="Price",
            increasing_line_color="#00ff88",decreasing_line_color="#ff3355"), row=1,col=1)

        # EMAs
        for ema,col in [(9,"#ffbb00"),(21,"#00aaff"),(50,"#ff44aa")]:
            fig.add_trace(go.Scatter(x=df_c.index,y=df_c[f"ema{ema}"],
                name=f"EMA{ema}",line=dict(color=col,width=1.2)), row=1,col=1)

        # BB
        fig.add_trace(go.Scatter(x=df_c.index,y=df_c["bb_up"],name="BB+",
            line=dict(color="#334466",dash="dot")), row=1,col=1)
        fig.add_trace(go.Scatter(x=df_c.index,y=df_c["bb_lo"],name="BB-",
            line=dict(color="#334466",dash="dot"),fill="tonexty",
            fillcolor="rgba(100,150,255,0.04)"), row=1,col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df_c.index,y=df_c["rsi"],name="RSI",
            line=dict(color="#ffbb00",width=1.5)), row=2,col=1)
        fig.add_hline(y=70,line_color="#ff3355",line_dash="dash",row=2,col=1)
        fig.add_hline(y=30,line_color="#00ff88",line_dash="dash",row=2,col=1)
        fig.add_hline(y=50,line_color="#333",line_dash="dot",row=2,col=1)

        # Volume
        vclr = ["#00ff88" if c>=o else "#ff3355"
                for c,o in zip(df_c["close"],df_c["open"])]
        fig.add_trace(go.Bar(x=df_c.index,y=df_c["volume"],name="Vol",
            marker_color=vclr,opacity=0.7), row=3,col=1)
        fig.add_trace(go.Scatter(x=df_c.index,y=df_c["vol_ma"],name="Vol MA",
            line=dict(color="#ffbb00",width=1)), row=3,col=1)

        fig.update_layout(height=700,paper_bgcolor="#060910",plot_bgcolor="#0c1117",
            font=dict(color="#c9d1d9",family="JetBrains Mono"),
            legend=dict(bgcolor="#0c1117",bordercolor="#1e2d3d",orientation="h",y=1.02),
            xaxis_rangeslider_visible=False,margin=dict(l=8,r=8,t=35,b=8))
        for ax in ["xaxis","xaxis2","xaxis3","yaxis","yaxis2","yaxis3"]:
            fig.update_layout(**{ax: dict(gridcolor="#1e2d3d",showgrid=True)})

        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════
# TAB 3 — SIGNALS
# ══════════════════════════════════════════

with tab_signals:
    if not coins:
        st.warning("Select coins in sidebar.")
    else:
        sig_sym = st.selectbox("Analyze", coins, key="sig_sym")
        with st.spinner(f"Generating signal for {sig_sym}..."):
            df_s = generate_ohlcv(sig_sym, tf, 300)
            df_s = add_indicators(df_s)
            sig  = generate_signal(sig_sym, df_s, tf)

        s   = sig
        clr = {"BUY":"#00ff88","SELL":"#ff3355","HOLD":"#ffbb00"}[s["signal"]]
        emj = {"BUY":"▲ BUY","SELL":"▼ SELL","HOLD":"━ HOLD"}[s["signal"]]

        st.markdown(f"""
        <div style='background:#0c1117;border:2px solid {clr}44;border-radius:16px;
                    padding:28px;text-align:center;margin:12px 0'>
          <div style='font-size:0.9em;color:#4a5568;letter-spacing:3px'>{s['symbol']} · {s['timeframe']}</div>
          <div style='font-size:3em;color:{clr};font-weight:800;font-family:Syne'>{emj}</div>
          <div style='font-size:1em;color:{clr}'>{s['confidence']}% confidence</div>
          <div style='font-size:0.75em;color:#4a5568;margin-top:4px'>{s['timestamp']}</div>
        </div>""", unsafe_allow_html=True)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Entry",  f"${s['price']:,.4f}")
        c2.metric("Stop Loss",   f"${s['stop_loss']:,.4f}",
                  delta=f"{(s['stop_loss']-s['price'])/s['price']*100:+.2f}%")
        c3.metric("Take Profit", f"${s['take_profit']:,.4f}",
                  delta=f"{(s['take_profit']-s['price'])/s['price']*100:+.2f}%")
        c4.metric("R:R", f"1 : {s['risk_reward']:.1f}")

        st.markdown("---")
        col1,col2 = st.columns(2)
        with col1:
            st.markdown("#### 📋 Signal Reasons")
            for r in s["reason"]:
                ic = "✅" if s["signal"]=="BUY" else "⚠️" if s["signal"]=="SELL" else "ℹ️"
                st.markdown(f"{ic} {r}")

        with col2:
            # Confidence gauge
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=s["confidence"],
                gauge={"axis":{"range":[0,100]},"bar":{"color":clr},
                       "bgcolor":"#0c1117","bordercolor":"#1e2d3d",
                       "steps":[{"range":[0,40],"color":"#1a0d0d"},
                                 {"range":[40,65],"color":"#1a1a0d"},
                                 {"range":[65,100],"color":"#0d1a0d"}]},
                number={"suffix":"%","font":{"color":clr,"size":36}},
                title={"text":"Confidence","font":{"color":"#4a5568"}},
            ))
            fig_g.update_layout(height=260,paper_bgcolor="#060910",
                font=dict(color="#c9d1d9"),margin=dict(l=20,r=20,t=40,b=10))
            st.plotly_chart(fig_g, use_container_width=True)

        # Log to Sheets
        sid = st.session_state.spreadsheet_id
        if sid and SHEETS_AVAILABLE:
            if st.button("📋 Log signal to Google Sheets"):
                ok = log_signal_to_sheet(sid, s)
                if ok: st.success("Signal logged ✓")
                else:  st.error("Failed to log signal")


# ══════════════════════════════════════════
# TAB 4 — AI CHAT
# ══════════════════════════════════════════

with tab_ai:
    st.markdown("### 🤖 Gemini AI Trading Analyst")

    status = get_genai_install_status()
    if not status["installed"]:
        st.error("❌ `google-generativeai` not installed. Add to requirements.txt and redeploy.")
        st.code("google-generativeai>=0.5.0", language="text")
    elif not status["configured"]:
        st.warning("⚠️ Gemini API key not configured. Go to **⚙️ Settings** tab.")
    else:
        rotator = get_gemini_rotator()
        st.success(f"✅ Connected | Key: {rotator.current_key_masked} | "
                   f"Model: {st.session_state.gemini_model}")

        # Quick analysis buttons
        st.markdown("**Quick Analysis:**")
        qcols = st.columns(4)
        quick_prompts = {
            "📊 Market Overview": f"Give a brief crypto market overview for {', '.join(coins[:4])} right now.",
            "📈 BTC Analysis":    "Analyze BTC price action and key levels to watch this week.",
            "⚠️ Risk Check":     "What are the biggest risks for crypto traders right now?",
            "💡 Trade Idea":      f"Suggest one high-quality trade setup for {coins[0] if coins else 'BTC'}.",
        }
        for i,(label,prompt) in enumerate(quick_prompts.items()):
            with qcols[i]:
                if st.button(label):
                    st.session_state.chat_history.append({"role":"user","content":prompt})

        st.markdown("---")

        # Chat display
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history[-10:]:
                role = msg["role"]
                icon = "👤" if role=="user" else "🤖"
                bg   = "#111827" if role=="user" else "#0d1f0d"
                bc   = "#1e2d3d" if role=="user" else "#00ff8833"
                st.markdown(f"""
                <div style='background:{bg};border:1px solid {bc};border-radius:10px;
                            padding:12px 16px;margin:6px 0;font-size:0.88em'>
                  <span style='color:#4a5568'>{icon} {'You' if role=='user' else 'Gemini AI'}</span><br>
                  <span style='color:#c9d1d9'>{msg['content']}</span>
                </div>""", unsafe_allow_html=True)

            # Process pending user message
            last = st.session_state.chat_history[-1] if st.session_state.chat_history else None
            if last and last["role"] == "user" and (
                len(st.session_state.chat_history) < 2 or
                st.session_state.chat_history[-2]["role"] != "user"
            ):
                with st.spinner("Gemini thinking..."):
                    system = ("You are a professional cryptocurrency trading analyst. "
                              "Be concise, data-driven, and always mention risk management.")
                    response = quick_chat(last["content"], system)
                    st.session_state.chat_history.append({"role":"assistant","content":response})
                st.rerun()

        # Input
        user_input = st.chat_input("Ask Gemini about crypto markets...")
        if user_input:
            st.session_state.chat_history.append({"role":"user","content":user_input})
            st.rerun()

        if st.button("🗑 Clear Chat"):
            st.session_state.chat_history = []; st.rerun()

        # Key usage stats
        if rotator := get_gemini_rotator():
            with st.expander("🔑 API Key Usage"):
                stats = rotator.get_usage_stats()
                for s_info in stats:
                    active = "◉ ACTIVE" if s_info["active"] else "○"
                    st.markdown(f"`{active}` Key #{s_info['index']}: {s_info['key']} | "
                                f"Calls: {s_info['calls']} | Errors: {s_info['errors']}")


# ══════════════════════════════════════════
# TAB 5 — BACKTEST
# ══════════════════════════════════════════

with tab_backtest:
    st.markdown("### 📉 Backtesting Engine")
    c1,c2,c3 = st.columns(3)
    bt_sym  = c1.selectbox("Coin", coins or ["BTCUSDT"], key="bt_sym")
    bt_tf   = c2.select_slider("TF", ["15m","1h","4h","1d"], value="1h", key="bt_tf")
    bt_bal  = c3.number_input("Balance ($)", 100.0, 100000.0, 1000.0, key="bt_bal")
    bt_risk = st.slider("Risk per trade (%)", 0.5, 5.0, 1.0, 0.5, key="bt_risk")
    bt_conf = st.slider("Min confidence (%)", 50, 85, 65, key="bt_conf")

    if st.button("▶️ Run Backtest", type="primary"):
        with st.spinner("Running backtest..."):
            df_bt = generate_ohlcv(bt_sym, bt_tf, 500)
            df_bt = add_indicators(df_bt)

            balance = bt_bal
            equity  = [bt_bal]
            trades  = []

            for i in range(60, len(df_bt)-1, 4):
                window = df_bt.iloc[max(0,i-200):i+1]
                sig    = generate_signal(bt_sym, window, bt_tf)
                if sig["signal"]=="HOLD" or sig["confidence"]<bt_conf: continue

                entry = float(df_bt["close"].iloc[i])
                sl    = sig["stop_loss"]
                tp    = sig["take_profit"]
                risk_amt = balance*(bt_risk/100)
                pr   = abs(entry-sl)
                if pr<=0: continue
                size = min(risk_amt/pr*entry, balance*0.2)

                # Simulate outcome
                future = df_bt.iloc[i+1:i+20]
                won = False
                for _,fc in future.iterrows():
                    if sig["signal"]=="BUY":
                        if fc["low"]<=sl:  break
                        if fc["high"]>=tp: won=True; break
                    else:
                        if fc["high"]>=sl: break
                        if fc["low"]<=tp:  won=True; break

                pnl = size*(abs(tp-entry)/entry) if won else -size*(abs(sl-entry)/entry)
                balance += pnl
                equity.append(round(balance,2))
                trades.append({"dir":sig["signal"],"won":won,"pnl":round(pnl,2)})

            if trades:
                wins  = [t for t in trades if t["won"]]
                loses = [t for t in trades if not t["won"]]
                wr    = len(wins)/len(trades)*100
                pnl   = balance-bt_bal
                gp    = sum(t["pnl"] for t in wins)
                gl    = abs(sum(t["pnl"] for t in loses))
                pf    = gp/gl if gl>0 else float("inf")

                # Drawdown
                peak  = bt_bal; max_dd = 0
                for b in equity:
                    peak = max(peak,b)
                    max_dd = max(max_dd, (peak-b)/peak*100)

                pnl_c = "#00ff88" if pnl>=0 else "#ff3355"
                st.markdown(f"""
                <div style='background:#0c1117;border:2px solid {pnl_c}44;border-radius:14px;
                            padding:20px;text-align:center'>
                  <div style='font-size:2em;color:{pnl_c};font-weight:700'>
                    ${pnl:+,.2f} ({pnl/bt_bal*100:+.1f}%)
                  </div>
                  <div style='color:#4a5568;font-size:0.85em'>
                    {bt_sym} · {bt_tf} · {len(trades)} trades
                  </div>
                </div>""", unsafe_allow_html=True)

                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("Win Rate",  f"{wr:.1f}%")
                m2.metric("Profit Factor", f"{pf:.2f}")
                m3.metric("Max DD",    f"{max_dd:.1f}%")
                m4.metric("Avg Win",   f"${np.mean([t['pnl'] for t in wins]):.2f}" if wins else "$0")
                m5.metric("Avg Loss",  f"${abs(np.mean([t['pnl'] for t in loses])):.2f}" if loses else "$0")

                # Equity curve
                fig_eq = go.Figure()
                fill_rgba = "rgba(0,255,136,0.08)" if pnl >= 0 else "rgba(255,51,85,0.08)"
                fig_eq.add_trace(go.Scatter(y=equity, mode="lines", name="Equity",
                    fill="tozeroy", fillcolor=fill_rgba,
                    line=dict(color=pnl_c, width=2)))
                fig_eq.add_hline(y=bt_bal,line_dash="dash",line_color="#4a5568")
                fig_eq.update_layout(height=280,paper_bgcolor="#060910",plot_bgcolor="#0c1117",
                    font=dict(color="#c9d1d9"),margin=dict(l=8,r=8,t=30,b=8),
                    title="Equity Curve",yaxis=dict(gridcolor="#1e2d3d"),
                    xaxis=dict(gridcolor="#1e2d3d"))
                st.plotly_chart(fig_eq, use_container_width=True)
            else:
                st.info("No trades triggered with current settings. Lower min confidence.")
    else:
        st.info("Configure settings and click **▶️ Run Backtest**")


# ══════════════════════════════════════════
# TAB 6 — GOOGLE SHEETS
# ══════════════════════════════════════════

with tab_sheets:
    st.markdown("### 📋 Google Sheets Integration")

    sheets_status = get_sheets_status()
    if not sheets_status["library_installed"]:
        st.error("❌ `gspread` not installed. Add to requirements.txt: `gspread>=6.0.0`")
    elif not sheets_status["authenticated"]:
        st.warning("⚠️ Google Sheets not authenticated. Configure credentials in **⚙️ Settings**.")
    else:
        st.success("✅ Google Sheets connected")

    st.markdown("---")

    # Spreadsheet ID input
    sid = st.text_input(
        "Google Spreadsheet ID",
        value=st.session_state.spreadsheet_id,
        placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
        help="Copy from your Google Sheet URL: docs.google.com/spreadsheets/d/**[ID]**/edit"
    )
    if sid != st.session_state.spreadsheet_id:
        st.session_state.spreadsheet_id = sid

    if not SHEETS_AVAILABLE:
        st.info("Install gspread to enable Google Sheets features.")
    elif not sid:
        st.info("Enter your Spreadsheet ID above to get started.")
    else:
        st.markdown("#### 📤 Export to Sheets")
        c1,c2,c3 = st.columns(3)

        with c1:
            if st.button("💾 Save Settings"):
                settings = {
                    "risk_percent":   st.session_state.risk_pct,
                    "timeframe":      st.session_state.timeframe,
                    "coins":          ",".join(st.session_state.coins),
                    "auto_trading":   st.session_state.auto_trading,
                    "ai_signals":     st.session_state.ai_signals,
                    "gemini_model":   st.session_state.gemini_model,
                }
                ok = save_settings_to_sheet(sid, settings)
                st.success("Settings saved ✓") if ok else st.error("Failed")

        with c2:
            if st.button("🔑 Save API Keys"):
                keys_data = {
                    "binance_api_key":    st.session_state.binance_api_key,
                    "binance_api_secret": st.session_state.binance_api_secret,
                    "gemini_keys":        st.session_state.gemini_api_keys,
                    "telegram_token":     st.session_state.telegram_token,
                    "telegram_chat_id":   st.session_state.telegram_chat_id,
                }
                ok = save_api_keys_to_sheet(sid, keys_data)
                st.success("API keys saved ✓") if ok else st.error("Failed")

        with c3:
            if st.button("📥 Load from Sheets"):
                loaded = load_api_keys_from_sheet(sid)
                if loaded:
                    for k,v in loaded.items():
                        if k in st.session_state: st.session_state[k] = v
                    st.success(f"Loaded {len(loaded)} settings ✓")
                else:
                    st.warning("Nothing to load")

        st.markdown("---")
        st.markdown("#### 📊 Trade History from Sheets")
        if st.button("📥 Load Trade History"):
            df_hist = get_trade_history(sid)
            if not df_hist.empty:
                st.dataframe(df_hist, use_container_width=True, height=300)
            else:
                st.info("No trades logged yet.")

    # Setup guide
    with st.expander("📖 Google Sheets Setup Guide"):
        st.markdown("""
**Step 1 — Create Service Account:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Google Sheets API** + **Google Drive API**
3. Create **Service Account** → Download JSON key

**Step 2 — Share your Sheet:**
1. Open your Google Sheet
2. Share with the service account email (ends with `@...gserviceaccount.com`)
3. Give **Editor** permission

**Step 3 — Add credentials:**
- **Streamlit Cloud**: Add JSON content to Secrets as `gcp_service_account`
- **Local**: Place `service_account.json` in project root

**Step 4 — Get Spreadsheet ID:**
From URL: `docs.google.com/spreadsheets/d/`**`[ID_HERE]`**`/edit`
        """)


# ══════════════════════════════════════════
# TAB 7 — SETTINGS
# ══════════════════════════════════════════

with tab_settings:
    st.markdown("### ⚙️ Settings & API Configuration")

    # ── Section 1: Gemini AI ─────────────────
    st.markdown("#### 🤖 Gemini AI Configuration")

    gemini_status = get_genai_install_status()
    if not gemini_status["installed"]:
        st.error("""
        ❌ `google-generativeai` not installed!

        Add this to `requirements.txt`:
        ```
        google-generativeai>=0.5.0
        ```
        Then redeploy your Streamlit app.
        """)
    else:
        st.success(f"✅ google-generativeai installed | Keys configured: {gemini_status['key_count']}")

    with st.expander("🔑 Add Gemini API Keys", expanded=not gemini_status["configured"]):
        st.markdown("""
        Get free API keys at [aistudio.google.com](https://aistudio.google.com/app/apikey)

        Add multiple keys for automatic rotation when quota is exceeded.
        """)
        gemini_keys_text = st.text_area(
            "Gemini API Keys (one per line)",
            value="\n".join(st.session_state.gemini_api_keys),
            placeholder="AIza...\nAIza...\nAIza...",
            height=120,
            help="Add multiple keys — system auto-rotates when quota exceeded"
        )
        gemini_model = st.selectbox(
            "Model",
            ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
            index=["gemini-1.5-flash","gemini-1.5-pro","gemini-2.0-flash-exp"].index(
                st.session_state.gemini_model
            ) if st.session_state.gemini_model in ["gemini-1.5-flash","gemini-1.5-pro","gemini-2.0-flash-exp"] else 0
        )

        if st.button("💾 Save & Connect Gemini", type="primary"):
            keys = [k.strip() for k in gemini_keys_text.split("\n") if k.strip()]
            if not keys:
                st.error("Enter at least one API key")
            elif not GENAI_AVAILABLE:
                st.error("Install google-generativeai first")
            else:
                try:
                    rotator = initialize_rotator_from_keys(keys, gemini_model)
                    # Quick test
                    test = rotator.generate("Say 'OK' in one word.")
                    if "error" not in test.lower() and len(test) < 50:
                        st.success(f"✅ Connected! {len(keys)} key(s) | Test: {test.strip()}")
                    else:
                        st.success(f"✅ {len(keys)} key(s) saved")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

    st.markdown("---")

    # ── Section 2: Binance ───────────────────
    st.markdown("#### 🔶 Binance API")
    col1,col2 = st.columns(2)
    with col1:
        b_key = st.text_input("API Key", value=st.session_state.binance_api_key,
                              type="password", key="b_key_input")
    with col2:
        b_sec = st.text_input("Secret Key", value=st.session_state.binance_api_secret,
                              type="password", key="b_sec_input")
    b_testnet = st.checkbox("Use Testnet (Paper Trading)", value=True)

    if st.button("💾 Save Binance Keys"):
        st.session_state.binance_api_key    = b_key
        st.session_state.binance_api_secret = b_sec
        st.success("Binance keys saved ✓")

    st.markdown("---")

    # ── Section 3: Telegram / Email ──────────
    st.markdown("#### 📬 Alerts")
    col1,col2 = st.columns(2)
    with col1:
        t_tok = st.text_input("Telegram Bot Token", value=st.session_state.telegram_token,
                              type="password")
        t_cid = st.text_input("Telegram Chat ID",   value=st.session_state.telegram_chat_id)
    with col2:
        e_sender = st.text_input("Gmail Sender", placeholder="you@gmail.com")
        e_pass   = st.text_input("App Password", type="password")

    if st.button("💾 Save Alert Settings"):
        st.session_state.telegram_token   = t_tok
        st.session_state.telegram_chat_id = t_cid
        st.success("Alert settings saved ✓")

    st.markdown("---")

    # ── Section 4: Google Sheets Credentials ─
    st.markdown("#### 📋 Google Sheets Credentials")
    cred_json = st.text_area(
        "Service Account JSON",
        placeholder='{"type":"service_account","project_id":"...","private_key":"..."}',
        height=120,
        help="Paste your downloaded service_account.json content here"
    )
    if st.button("💾 Save GCP Credentials"):
        if cred_json.strip():
            try:
                import json
                st.session_state.gcp_credentials = json.loads(cred_json)
                st.success("✅ Credentials saved")
            except Exception:
                st.error("Invalid JSON. Paste the entire service_account.json content.")

    st.markdown("---")

    # ── Section 5: Trading Parameters ────────
    st.markdown("#### 📊 Trading Parameters")
    col1,col2,col3 = st.columns(3)
    with col1:
        rp = st.number_input("Risk per trade (%)", 0.5, 10.0,
                             st.session_state.risk_pct, 0.5, key="risk_input")
        st.session_state.risk_pct = rp
    with col2:
        st.number_input("Risk:Reward ratio", 1.0, 5.0, 2.0, 0.5)
    with col3:
        st.number_input("Max daily loss (%)", 1.0, 20.0, 5.0, 1.0)

    st.markdown("---")

    # ── Section 6: Streamlit secrets template ─
    with st.expander("📋 Streamlit Cloud Secrets Template"):
        st.code("""
# Add this in Streamlit Cloud → Settings → Secrets

GEMINI_API_KEYS = "AIza...key1,AIza...key2"
GEMINI_API_KEY  = "AIza...key1"

BINANCE_API_KEY    = "your_binance_key"
BINANCE_API_SECRET = "your_binance_secret"

TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID   = "your_chat_id"

SPREADSHEET_ID = "your_google_sheet_id"

[gcp_service_account]
type = "service_account"
project_id = "your-project"
private_key_id = "key-id"
private_key = "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\\n"
client_email = "name@project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
        """, language="toml")

    st.markdown("""
    > **⚠️ Disclaimer:** For educational purposes only.
    > Cryptocurrency trading involves significant risk. Never risk money you can't afford to lose.
    """)
