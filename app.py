"""
🚀 CryptoAI Terminal v2
Binance + Multi-API fallback + Supabase + Email Alerts + Trade Tracker
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="CryptoAI Terminal", page_icon="🚀",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Rajdhani',sans-serif;background:#0A0E1A;}
.stApp{background:#0A0E1A;}
.main-title{font-family:'Share Tech Mono',monospace;font-size:2.2rem;color:#00FFA3;
    text-shadow:0 0 20px rgba(0,255,163,0.5);letter-spacing:4px;margin-bottom:0;}
.sub-title{color:#4488FF;font-size:0.9rem;letter-spacing:6px;font-family:'Share Tech Mono',monospace;}
.metric-card{background:linear-gradient(135deg,#111827 0%,#0D1520 100%);
    border:1px solid #1E2A3A;border-radius:8px;padding:16px;text-align:center;
    position:relative;overflow:hidden;}
.metric-card::before{content:'';position:absolute;top:0;left:0;width:100%;height:2px;
    background:linear-gradient(90deg,#00FFA3,#4488FF);}
.metric-value{font-family:'Share Tech Mono',monospace;font-size:1.6rem;color:#00FFA3;font-weight:bold;}
.metric-label{color:#64748B;font-size:0.75rem;letter-spacing:2px;text-transform:uppercase;}
.price-card{background:#111827;border:1px solid #1E2A3A;border-radius:8px;padding:12px;margin:4px 0;}
section[data-testid="stSidebar"]{background:#0D1520 !important;border-right:1px solid #1E2A3A;}
.stTabs [data-baseweb="tab-list"]{background:#111827;border-radius:8px;gap:4px;}
.stTabs [data-baseweb="tab"]{color:#64748B;font-family:'Share Tech Mono',monospace;font-size:0.8rem;}
.stTabs [aria-selected="true"]{color:#00FFA3 !important;background:rgba(0,255,163,0.1) !important;}
.stButton>button{background:linear-gradient(135deg,#00FFA3,#4488FF);color:#0A0E1A;
    border:none;border-radius:6px;font-family:'Share Tech Mono',monospace;font-weight:bold;}
hr{border-color:#1E2A3A;}
::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-thumb{background:#1E2A3A;border-radius:2px;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}
.live-dot{display:inline-block;width:8px;height:8px;background:#00FFA3;
    border-radius:50%;animation:blink 1.5s infinite;margin-right:6px;}
.win-badge{background:rgba(0,255,163,0.15);border:1px solid #00FFA3;color:#00FFA3;
    padding:2px 10px;border-radius:12px;font-size:0.8rem;font-family:monospace;}
.loss-badge{background:rgba(255,68,102,0.15);border:1px solid #FF4466;color:#FF4466;
    padding:2px 10px;border-radius:12px;font-size:0.8rem;font-family:monospace;}
</style>
""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
from utils.binance_data import (get_live_price, get_klines, get_api_status,
                                 POPULAR_COINS, TIMEFRAMES)
from utils.indicators import run_all_indicators, detect_structure, detect_elliott_wave
from utils.ml_model import train_model, predict_signal, run_backtest
from utils.charts import create_candlestick_chart, create_equity_curve, create_compound_chart
from utils.gemini_rotator import get_gemini_rotator
from utils.news_fetcher import fetch_news, get_overall_market_sentiment
from utils.risk_manager import (calculate_position_size, calculate_sl_tp,
                                 auto_compound, kelly_criterion, get_risk_label)
from utils.gsheets_db import (save_trade, close_trade, get_trades,
                               get_trade_stats, save_alert, get_alerts,
                               update_stats_sheet, is_configured, SETUP_GUIDE)
from utils.email_alerts import send_alert_email, send_test_email

# ── Header ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3,1])
with c1:
    st.markdown('<div class="main-title">⚡ CRYPTO AI TERMINAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">BINANCE · SMC · ELLIOTT · ML · GEMINI AI</div>', unsafe_allow_html=True)
with c2:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    st.markdown(f'<div style="text-align:right;color:#64748B;font-family:monospace;font-size:0.8rem;margin-top:16px;"><span class="live-dot"></span>LIVE · {now}</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="color:#00FFA3;font-family:monospace;font-weight:bold;letter-spacing:2px;">⚙️ SETTINGS</div>', unsafe_allow_html=True)
    st.markdown("---")
    selected_coins = st.multiselect("Select Coins", POPULAR_COINS,
                                    default=["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"])
    primary_coin = st.selectbox("Primary Coin", selected_coins if selected_coins else ["BTCUSDT"])
    timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=2,
                             format_func=lambda x: f"{x} — {TIMEFRAMES[x]}")
    st.markdown("---")
    show_smc = st.toggle("Show SMC Zones", value=True)
    candle_limit = st.slider("Candles", 100, 500, 200)
    st.markdown("---")
    capital  = st.number_input("Capital ($)", value=1000.0, step=100.0)
    risk_pct = st.slider("Risk per Trade (%)", 0.5, 10.0, 1.0, 0.5)
    st.markdown(f'<div style="text-align:center;margin-top:4px;">{get_risk_label(risk_pct)}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # ── API Status in Sidebar ────────────────────────────────────────────────
    st.markdown('<div style="color:#64748B;font-size:0.75rem;letter-spacing:2px;">API STATUS</div>', unsafe_allow_html=True)
    if st.button("🔌 Check APIs", use_container_width=True):
        with st.spinner("Testing..."):
            statuses = get_api_status()
        for name, status in statuses.items():
            st.markdown(f'<div style="font-family:monospace;font-size:0.8rem;padding:2px 0;">{status} {name}</div>', unsafe_allow_html=True)

    st.markdown("---")
    auto_refresh = st.toggle("Auto Refresh (30s)", value=False)

if auto_refresh:
    time.sleep(30)
    st.rerun()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8 = st.tabs([
    "📊 DASHBOARD","📈 CHART","🤖 AI SIGNALS",
    "📰 NEWS","⚗️ BACKTEST","💰 RISK",
    "📋 TRADES","⚙️ SETUP"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    if not selected_coins:
        st.warning("Sidebar එකෙන් coin select කරන්න.")
    else:
        # ── API Debug Panel ──────────────────────────────────────────────────
        test_data = get_live_price(selected_coins[0])
        src = test_data.get("source","FAILED")
        src_color = "#00FFA3" if src not in ["FAILED","None","?"] else "#FF4466"

        if src == "FAILED":
            st.error("⚠️ All APIs failed! Checking details...")
            with st.expander("🔍 API Debug Info", expanded=True):
                errors = test_data.get("errors", [])
                for e in errors:
                    st.code(e)
                st.info("Sidebar → 'Check APIs' click කරලා which APIs work කියලා බලන්න.")
        else:
            st.markdown(f'<div style="color:{src_color};font-family:monospace;font-size:0.75rem;margin-bottom:8px;">📡 Data Source: <b>{src}</b> ✅</div>', unsafe_allow_html=True)

        cols = st.columns(min(len(selected_coins),4))
        price_data = {}
        for i, coin in enumerate(selected_coins):
            data = get_live_price(coin)
            price_data[coin] = data
            change = data.get("change_pct",0)
            color = "#00FFA3" if change >= 0 else "#FF4466"
            arrow = "▲" if change >= 0 else "▼"
            price = data.get("price",0)
            with cols[i % 4]:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{coin.replace('USDT','')}</div>
                    <div class="metric-value">${price:,.2f}</div>
                    <div style="color:{color};font-size:0.9rem;font-family:monospace;">{arrow} {change:+.2f}%</div>
                    <div style="color:#64748B;font-size:0.7rem;margin-top:4px;">Vol: {data.get('volume',0):,.0f}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        rows = []
        for coin, d in price_data.items():
            rows.append({"Coin":coin.replace("USDT",""),"Price ($)":f"{d.get('price',0):,.4f}",
                "24h Change":f"{d.get('change_pct',0):+.2f}%","24h High":f"{d.get('high',0):,.4f}",
                "24h Low":f"{d.get('low',0):,.4f}","Volume":f"{d.get('volume',0):,.0f}",
                "Source":d.get("source","?")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2: CHART
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(f'<div style="color:#00FFA3;font-family:monospace;letter-spacing:2px;">{primary_coin} · {timeframe}</div>', unsafe_allow_html=True)
    with st.spinner("Chart data loading..."):
        df = get_klines(primary_coin, timeframe, limit=candle_limit)

    if df.empty:
        st.error("⚠️ Chart data load වෙන්නේ නැහැ. API status check කරන්න.")
    else:
        df_ind = run_all_indicators(df.copy())
        structure = detect_structure(df_ind)
        waves = detect_elliott_wave(df_ind)
        rsi_val = df_ind["rsi"].iloc[-1] if "rsi" in df_ind.columns else 0
        price_now = df["close"].iloc[-1]

        cs1,cs2,cs3,cs4 = st.columns(4)
        cs1.markdown(f'<div class="metric-card"><div class="metric-label">STRUCTURE</div><div style="font-size:0.9rem;color:#E2E8F0;font-family:monospace;margin-top:4px;">{structure["structure"]}</div></div>', unsafe_allow_html=True)
        cs2.markdown(f'<div class="metric-card"><div class="metric-label">ELLIOTT</div><div style="font-size:0.85rem;color:#FFD700;font-family:monospace;margin-top:4px;">{waves["wave_label"]}</div></div>', unsafe_allow_html=True)
        rsi_c = "#FF4466" if rsi_val>70 else "#00FFA3" if rsi_val<30 else "#E2E8F0"
        cs3.markdown(f'<div class="metric-card"><div class="metric-label">RSI</div><div style="font-size:1.4rem;color:{rsi_c};font-family:monospace;">{rsi_val:.1f}</div></div>', unsafe_allow_html=True)
        cs4.markdown(f'<div class="metric-card"><div class="metric-label">PRICE</div><div class="metric-value">${price_now:,.2f}</div></div>', unsafe_allow_html=True)

        fig = create_candlestick_chart(df_ind, f"{primary_coin}/{timeframe}", show_smc=show_smc)
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3: AI SIGNALS + EMAIL ALERT + TRADE CAPTURE
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    col_train, col_sig = st.columns([1,2])

    with col_train:
        st.markdown("**🔥 Train Models**")
        train_coins = st.multiselect("Coins", POPULAR_COINS,
                                     default=selected_coins[:2] if selected_coins else ["BTCUSDT"])
        train_tf = st.selectbox("Train TF", ["1h","4h","1d"])
        if st.button("Train", use_container_width=True):
            for coin in train_coins:
                with st.spinner(f"Training {coin}..."):
                    df_t = get_klines(coin, train_tf, limit=500)
                    if not df_t.empty:
                        r = train_model(df_t, coin)
                        if "error" in r: st.error(f"{coin}: {r['error']}")
                        else: st.success(f"✅ {coin} — {r['accuracy']}%")
                    else: st.warning(f"⚠️ {coin}: No data")

    with col_sig:
        st.markdown("**📡 Live Signals**")
        send_email_on_signal = st.toggle("📧 Email alert on signal", value=False)
        save_signal_as_trade = st.toggle("💾 Save to Supabase", value=False)

        if st.button("🔍 Generate Signals", use_container_width=True):
            for coin in (selected_coins if selected_coins else ["BTCUSDT"]):
                df_s = get_klines(coin, timeframe, limit=300)
                if df_s.empty: continue
                sig   = predict_signal(df_s, coin)
                price = get_live_price(coin)
                px    = price.get("price",0)
                signal_text = sig.get("signal","N/A")
                conf  = sig.get("confidence",0)
                color = "#00FFA3" if "BUY" in signal_text else "#FF4466" if "SELL" in signal_text else "#64748B"

                st.markdown(f"""
                <div class="metric-card" style="margin-bottom:8px;text-align:left;
                     display:flex;justify-content:space-between;align-items:center;">
                  <div>
                    <div style="color:#E2E8F0;font-family:monospace;">{coin.replace('USDT','/USDT')}</div>
                    <div style="color:#64748B;font-size:0.75rem;">${px:,.4f} · {price.get('source','?')}</div>
                  </div>
                  <div style="text-align:right;">
                    <div style="color:{color};font-family:monospace;font-size:1.1rem;font-weight:bold;">{signal_text}</div>
                    <div style="color:#64748B;font-size:0.75rem;">Confidence: {conf}%</div>
                  </div>
                </div>""", unsafe_allow_html=True)

                if sig.get("trained") and px > 0:
                    # Email alert
                    if send_email_on_signal and ("BUY" in signal_text or "SELL" in signal_text):
                        ok, msg = send_alert_email(coin, signal_text, px, conf)
                        st.caption(f"📧 {msg}")

                    # Save trade to Supabase
                    if save_signal_as_trade and ("BUY" in signal_text or "SELL" in signal_text):
                        df_atr = run_all_indicators(df_s.copy())
                        atr = df_atr["atr"].iloc[-1] if "atr" in df_atr.columns else px*0.01
                        direction = "long" if "BUY" in signal_text else "short"
                        sltp = calculate_sl_tp(px, direction, atr)
                        result = save_trade(coin, signal_text, px, conf,
                                           sltp["stop_loss"], sltp["take_profit"])
                        if "error" not in str(result):
                            st.caption(f"💾 Trade saved to Supabase")
                        else:
                            st.caption(f"⚠️ Supabase: {result}")

    # ── Gemini AI ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**🤖 Gemini AI Analysis**")
    gemini = get_gemini_rotator()
    if st.button("💬 Get AI Analysis", use_container_width=True):
        with st.spinner("Consulting Gemini AI..."):
            df_ai = get_klines(primary_coin, timeframe, limit=100)
            if not df_ai.empty:
                df_ai = run_all_indicators(df_ai)
                structure = detect_structure(df_ai)
                rsi_raw = df_ai["rsi"].iloc[-1] if "rsi" in df_ai.columns else None
                rsi_now = f"{rsi_raw:.1f}" if rsi_raw is not None else "N/A"
                px = df_ai["close"].iloc[-1]
                prompt = f"""Analyze {primary_coin} {timeframe}:
Price: ${px:,.4f}, RSI: {rsi_now}
Structure: {structure['structure']}, High: ${structure['last_high']:,.4f}, Low: ${structure['last_low']:,.4f}
Give: 1) Sentiment 2) Key levels 3) BUY/SELL/WAIT recommendation 4) Risk warning. Under 250 words."""
                response = gemini.generate(prompt)
                st.markdown(f'<div style="background:#111827;border:1px solid #1E2A3A;border-radius:8px;padding:16px;font-size:0.9rem;line-height:1.7;color:#CBD5E1;">{response.replace(chr(10),"<br>")}</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4: NEWS
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    cn1,cn2 = st.columns([3,1])
    with cn2: news_filter = st.selectbox("Coin filter", ["All"]+selected_coins)
    if st.button("📰 Fetch News"):
        with st.spinner("Fetching..."):
            articles = fetch_news(None if news_filter=="All" else news_filter, 20)
            sentiment = get_overall_market_sentiment(articles)
        st.markdown(f'Market Sentiment: **{sentiment}**')
        for art in articles:
            sc = "#00FFA3" if "Bullish" in art["sentiment"] else "#FF4466" if "Bearish" in art["sentiment"] else "#64748B"
            st.markdown(f"""<div class="price-card" style="margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;">
                  <a href="{art['link']}" target="_blank" style="color:#E2E8F0;text-decoration:none;font-size:0.9rem;flex:1;margin-right:12px;">{art['title']}</a>
                  <span style="color:{sc};font-size:0.8rem;white-space:nowrap;font-family:monospace;">{art['sentiment']}</span>
                </div>
                <div style="color:#64748B;font-size:0.7rem;margin-top:4px;">{art['source']}</div>
            </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 5: BACKTEST
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    bc1,bc2 = st.columns([1,2])
    with bc1:
        bt_coin    = st.selectbox("Coin", POPULAR_COINS)
        bt_tf      = st.selectbox("TF", list(TIMEFRAMES.keys()), index=2)
        bt_capital = st.number_input("Capital ($)", value=1000.0, step=100.0)
        bt_limit   = st.slider("Candles", 200, 1000, 500)
    with bc2:
        if st.button("▶️ Run Backtest", use_container_width=True):
            with st.spinner("Running..."):
                df_bt = get_klines(bt_coin, bt_tf, limit=bt_limit)
                if df_bt.empty:
                    st.error("No data")
                else:
                    if not predict_signal(df_bt, bt_coin).get("trained"):
                        train_model(df_bt, bt_coin)
                    result = run_backtest(df_bt, bt_coin, bt_capital)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        rc = "#00FFA3" if result["total_return_pct"]>=0 else "#FF4466"
                        r1,r2,r3,r4 = st.columns(4)
                        r1.markdown(f'<div class="metric-card"><div class="metric-label">FINAL</div><div class="metric-value">${result["final_capital"]:,.2f}</div></div>', unsafe_allow_html=True)
                        r2.markdown(f'<div class="metric-card"><div class="metric-label">RETURN</div><div style="font-size:1.4rem;color:{rc};font-family:monospace;">{result["total_return_pct"]:+.2f}%</div></div>', unsafe_allow_html=True)
                        r3.markdown(f'<div class="metric-card"><div class="metric-label">TRADES</div><div class="metric-value">{result["total_trades"]}</div></div>', unsafe_allow_html=True)
                        r4.markdown(f'<div class="metric-card"><div class="metric-label">WIN RATE</div><div class="metric-value">{result["win_rate"]}%</div></div>', unsafe_allow_html=True)
                        st.plotly_chart(create_equity_curve(result["equity_curve"], result["trades"]), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 6: RISK
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    rr1,rr2 = st.columns(2)
    with rr1:
        st.markdown("**Position Size Calculator**")
        entry_p = st.number_input("Entry ($)", value=50000.0, step=100.0)
        sl_p    = st.number_input("Stop Loss ($)", value=49000.0, step=100.0)
        direction = st.radio("Direction", ["long","short"], horizontal=True)
        if st.button("Calculate", use_container_width=True):
            pos  = calculate_position_size(capital, risk_pct, entry_p, sl_p)
            atr  = abs(entry_p - sl_p)
            sltp = calculate_sl_tp(entry_p, direction, atr)
            if "error" not in pos:
                st.markdown(f"""<div class="metric-card" style="text-align:left;margin-top:12px;">
                <div style="font-family:monospace;line-height:2;font-size:0.9rem;">
                💰 Risk: <span style="color:#FFD700;">${pos['risk_amount']}</span><br>
                📊 Units: <span style="color:#00FFA3;">{pos['units']}</span><br>
                🛑 SL: <span style="color:#FF4466;">${sltp['stop_loss']:,.4f}</span><br>
                🎯 TP: <span style="color:#00FFA3;">${sltp['take_profit']:,.4f}</span><br>
                ⚖️ R:R: <span style="color:#FFD700;">1:{sltp['rr_ratio']}</span>
                </div></div>""", unsafe_allow_html=True)
    with rr2:
        st.markdown("**Auto Compounding**")
        cr   = st.slider("Monthly Return (%)", 1.0, 50.0, 10.0, 0.5)
        cm   = st.slider("Months", 3, 60, 24)
        cc   = st.number_input("Start Capital ($)", value=capital, step=100.0)
        if st.button("📈 Calculate", use_container_width=True):
            curve = auto_compound(cc, cr, cm)
            final = curve[-1]["capital"]
            st.markdown(f"""<div class="metric-card" style="text-align:left;margin-top:12px;">
            <div style="font-family:monospace;line-height:2;">
            🚀 Final: <span style="color:#00FFA3;">${final:,.2f}</span><br>
            ✖️ Multiplier: <span style="color:#4488FF;">{final/cc:.2f}x</span>
            </div></div>""", unsafe_allow_html=True)
            st.plotly_chart(create_compound_chart(curve), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 7: TRADES (Supabase)
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown('<div style="color:#64748B;font-size:0.75rem;letter-spacing:3px;margin-bottom:12px;">TRADE TRACKER · SUPABASE</div>', unsafe_allow_html=True)

    # Stats
    stats = get_trade_stats()
    ts1,ts2,ts3,ts4,ts5 = st.columns(5)
    ts1.markdown(f'<div class="metric-card"><div class="metric-label">TOTAL</div><div class="metric-value">{stats["total"]}</div></div>', unsafe_allow_html=True)
    ts2.markdown(f'<div class="metric-card"><div class="metric-label">OPEN</div><div style="font-size:1.4rem;color:#FFD700;font-family:monospace;">{stats["open"]}</div></div>', unsafe_allow_html=True)
    ts3.markdown(f'<div class="metric-card"><div class="metric-label">WIN RATE</div><div class="metric-value">{stats["win_rate"]}%</div></div>', unsafe_allow_html=True)
    ts4.markdown(f'<div class="metric-card"><div class="metric-label">AVG P&L</div><div style="font-size:1.4rem;color:{"#00FFA3" if stats["avg_pnl"]>=0 else "#FF4466"};font-family:monospace;">{stats["avg_pnl"]:+.2f}%</div></div>', unsafe_allow_html=True)
    ts5.markdown(f'<div class="metric-card"><div class="metric-label">TOTAL P&L</div><div style="font-size:1.4rem;color:{"#00FFA3" if stats["total_pnl"]>=0 else "#FF4466"};font-family:monospace;">{stats["total_pnl"]:+.2f}%</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    col_tl, col_tc = st.columns([2,1])

    with col_tl:
        st.markdown("**Open Trades**")
        open_trades = get_trades(status="OPEN", limit=20)
        if open_trades:
            for t in open_trades:
                sig_color = "#00FFA3" if "BUY" in str(t.get("signal","")) else "#FF4466"
                st.markdown(f"""<div class="price-card" style="margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <div>
                    <span style="color:#E2E8F0;font-family:monospace;">{t.get('symbol','?')}</span>
                    <span style="color:{sig_color};margin-left:8px;font-size:0.85rem;">{t.get('signal','?')}</span>
                  </div>
                  <div style="text-align:right;font-size:0.8rem;">
                    <div style="color:#E2E8F0;">Entry: ${t.get('entry_price',0):,.4f}</div>
                    <div style="color:#64748B;">Conf: {t.get('confidence',0)}%</div>
                  </div>
                </div></div>""", unsafe_allow_html=True)
        else:
            st.info("Open trades නැහැ. AI Signals tab → Generate Signals → 'Save to Supabase' enable කරන්න.")

    with col_tc:
        st.markdown("**Close Trade**")
        trade_id   = st.number_input("Trade ID", min_value=1, step=1)
        exit_price = st.number_input("Exit Price ($)", value=0.0, step=1.0)
        exit_reason = st.selectbox("Reason", ["TP Hit","SL Hit","Manual","Signal"])
        if st.button("✅ Close Trade", use_container_width=True):
            result = close_trade(int(trade_id), exit_price, exit_reason)
            if "error" not in str(result):
                pnl = result[0].get("pnl_pct",0) if isinstance(result, list) else 0
                win = result[0].get("result","?") if isinstance(result, list) else "?"
                badge = '<span class="win-badge">WIN</span>' if win=="WIN" else '<span class="loss-badge">LOSS</span>'
                st.markdown(f"Trade closed! {badge} P&L: **{pnl:+.2f}%**", unsafe_allow_html=True)
            else:
                st.error(f"Error: {result}")

    st.markdown("---")
    st.markdown("**Trade History**")
    all_trades = get_trades(limit=50)
    if all_trades:
        df_trades = pd.DataFrame(all_trades)
        show_cols = [c for c in ["id","symbol","signal","entry_price","exit_price",
                                   "pnl_pct","result","status","created_at"] if c in df_trades.columns]
        st.dataframe(df_trades[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Trade history නැහැ.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 8: SETUP
# ════════════════════════════════════════════════════════════════════════════
with tab8:
    st.markdown("### ⚙️ Setup Guide")

    with st.expander("📊 Google Sheets Setup", expanded=True):
        st.markdown(SETUP_GUIDE, unsafe_allow_html=False)
        if is_configured():
            st.success("✅ Google Sheets connected!")
            if st.button("🔄 Refresh Stats Sheet"):
                update_stats_sheet()
                st.success("Stats sheet updated!")
        else:
            st.warning("⚠️ Google Sheets not configured yet. Add secrets above.")

    with st.expander("📧 Email Setup (Gmail)"):
        st.markdown("""
**Gmail App Password හදාගන්නේ:**

1. [myaccount.google.com](https://myaccount.google.com) → Security
2. 2-Step Verification → ON කරන්න
3. Search "App passwords" → Mail → Generate
4. 16-digit password copy කරන්න → secrets.toml එකට `app_password` හැටියට දාන්න
        """)
        if st.button("📧 Send Test Email"):
            with st.spinner("Sending..."):
                ok, msg = send_test_email()
            if ok: st.success(msg)
            else:  st.error(msg)

    with st.expander("🔌 API Status Check"):
        if st.button("Test All APIs Now"):
            with st.spinner("Testing all APIs..."):
                statuses = get_api_status()
            for name, status in statuses.items():
                st.markdown(f"**{name}:** {status}")
            st.info("Binance block වෙලා නම් CoinGecko/CryptoCompare auto-fallback වෙනවා. Data still works!")

st.markdown("---")
st.markdown('<div style="text-align:center;color:#1E2A3A;font-family:monospace;font-size:0.7rem;">CryptoAI Terminal · Educational purposes only · Not financial advice</div>', unsafe_allow_html=True)
