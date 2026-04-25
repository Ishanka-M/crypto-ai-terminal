"""
🚀 Crypto Trading Analysis System
Binance + AI (Gemini) + ML Signals + SMC + Elliott Wave
"""
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CryptoAI Terminal",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Rajdhani', sans-serif;
    background-color: #0A0E1A;
}
.stApp { background-color: #0A0E1A; }

/* Header */
.main-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 2.2rem;
    color: #00FFA3;
    text-shadow: 0 0 20px rgba(0,255,163,0.5);
    letter-spacing: 4px;
    margin-bottom: 0;
}
.sub-title {
    color: #4488FF;
    font-size: 0.9rem;
    letter-spacing: 6px;
    font-family: 'Share Tech Mono', monospace;
}

/* Metric Cards */
.metric-card {
    background: linear-gradient(135deg, #111827 0%, #0D1520 100%);
    border: 1px solid #1E2A3A;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 2px;
    background: linear-gradient(90deg, #00FFA3, #4488FF);
}
.metric-value {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.6rem;
    color: #00FFA3;
    font-weight: bold;
}
.metric-label {
    color: #64748B;
    font-size: 0.75rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* Signal Badge */
.signal-buy {
    background: rgba(0,255,163,0.15);
    border: 1px solid #00FFA3;
    color: #00FFA3;
    padding: 4px 14px;
    border-radius: 20px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.9rem;
    font-weight: bold;
}
.signal-sell {
    background: rgba(255,68,102,0.15);
    border: 1px solid #FF4466;
    color: #FF4466;
    padding: 4px 14px;
    border-radius: 20px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.9rem;
    font-weight: bold;
}

/* Price Card */
.price-card {
    background: #111827;
    border: 1px solid #1E2A3A;
    border-radius: 8px;
    padding: 12px;
    margin: 4px 0;
}
.price-pos { color: #00FFA3; }
.price-neg { color: #FF4466; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0D1520 !important;
    border-right: 1px solid #1E2A3A;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111827;
    border-radius: 8px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    color: #64748B;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.85rem;
    letter-spacing: 1px;
}
.stTabs [aria-selected="true"] {
    color: #00FFA3 !important;
    background: rgba(0,255,163,0.1) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00FFA3, #4488FF);
    color: #0A0E1A;
    border: none;
    border-radius: 6px;
    font-family: 'Share Tech Mono', monospace;
    font-weight: bold;
    letter-spacing: 1px;
}
.stButton > button:hover {
    opacity: 0.85;
    transform: translateY(-1px);
}

/* Select box */
.stSelectbox > div > div {
    background: #111827;
    border-color: #1E2A3A;
    color: #E2E8F0;
}

/* Dividers */
hr { border-color: #1E2A3A; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0A0E1A; }
::-webkit-scrollbar-thumb { background: #1E2A3A; border-radius: 2px; }

/* Blinking dot */
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
.live-dot {
    display: inline-block;
    width: 8px; height: 8px;
    background: #00FFA3;
    border-radius: 50%;
    animation: blink 1.5s infinite;
    margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── Imports ───────────────────────────────────────────────────────────────────
from utils.binance_data import get_live_price, get_klines, POPULAR_COINS, TIMEFRAMES
from utils.indicators import run_all_indicators, detect_structure, detect_elliott_wave
from utils.ml_model import train_model, predict_signal, run_backtest
from utils.charts import create_candlestick_chart, create_equity_curve, create_compound_chart
from utils.gemini_rotator import get_gemini_rotator
from utils.news_fetcher import fetch_news, get_overall_market_sentiment
from utils.risk_manager import (
    calculate_position_size, calculate_sl_tp,
    auto_compound, kelly_criterion, get_risk_label
)

# ── Header ────────────────────────────────────────────────────────────────────
col_logo, col_time = st.columns([3, 1])
with col_logo:
    st.markdown('<div class="main-title">⚡ CRYPTO AI TERMINAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">BINANCE · SMC · ELLIOTT · ML · GEMINI AI</div>', unsafe_allow_html=True)
with col_time:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    st.markdown(f'<div style="text-align:right; color:#64748B; font-family:monospace; font-size:0.8rem; margin-top:16px;"><span class="live-dot"></span>LIVE · {now}</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="color:#00FFA3; font-family:monospace; font-weight:bold; font-size:1rem; letter-spacing:2px;">⚙️ SETTINGS</div>', unsafe_allow_html=True)
    st.markdown("---")

    selected_coins = st.multiselect(
        "Select Coins",
        POPULAR_COINS,
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        help="Choose coins to analyze"
    )

    primary_coin = st.selectbox("Primary Coin (for charts)", selected_coins if selected_coins else ["BTCUSDT"])

    timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=2,
                             format_func=lambda x: f"{x} — {TIMEFRAMES[x]}")

    st.markdown("---")
    st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:2px;">CHART OPTIONS</div>', unsafe_allow_html=True)
    show_smc = st.toggle("Show SMC Zones", value=True)
    show_ema = st.toggle("Show EMAs", value=True)
    candle_limit = st.slider("Candles", 100, 500, 200)

    st.markdown("---")
    st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:2px;">RISK SETTINGS</div>', unsafe_allow_html=True)
    capital = st.number_input("Capital ($)", value=1000.0, step=100.0)
    risk_pct = st.slider("Risk per Trade (%)", 0.5, 10.0, 1.0, 0.5)
    st.markdown(f'<div style="text-align:center; margin-top:4px;">{get_risk_label(risk_pct)}</div>', unsafe_allow_html=True)

    st.markdown("---")
    auto_refresh = st.toggle("Auto Refresh (30s)", value=False)

# ── Auto Refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.rerun()

# ── Main Tabs ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 DASHBOARD", "📈 CHART", "🤖 AI SIGNALS", "📰 NEWS", "⚗️ BACKTEST", "💰 RISK"
])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1: LIVE DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    if not selected_coins:
        st.warning("Select at least one coin from the sidebar.")
    else:
        st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:12px;">LIVE MARKET PRICES</div>', unsafe_allow_html=True)

        cols = st.columns(min(len(selected_coins), 4))
        price_data = {}

        for i, coin in enumerate(selected_coins):
            data = get_live_price(coin)
            price_data[coin] = data
            col_idx = i % 4

            change = data.get("change_pct", 0)
            color = "#00FFA3" if change >= 0 else "#FF4466"
            arrow = "▲" if change >= 0 else "▼"

            with cols[col_idx]:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{coin.replace('USDT','')}</div>
                    <div class="metric-value">${data.get('price', 0):,.4f}</div>
                    <div style="color:{color}; font-size:0.9rem; font-family:monospace;">{arrow} {change:+.2f}%</div>
                    <div style="color:#64748B; font-size:0.7rem; margin-top:4px;">Vol: {data.get('volume',0):,.0f}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Market Overview Table
        st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:8px;">MARKET OVERVIEW</div>', unsafe_allow_html=True)
        rows = []
        for coin, d in price_data.items():
            rows.append({
                "Coin": coin.replace("USDT", ""),
                "Price ($)": f"{d.get('price', 0):,.4f}",
                "24h Change": f"{d.get('change_pct', 0):+.2f}%",
                "24h High": f"{d.get('high', 0):,.4f}",
                "24h Low": f"{d.get('low', 0):,.4f}",
                "Volume": f"{d.get('volume', 0):,.0f}",
            })

        df_market = pd.DataFrame(rows)
        st.dataframe(
            df_market,
            use_container_width=True,
            hide_index=True,
        )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2: CHART
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(f'<div style="color:#00FFA3; font-family:monospace; letter-spacing:2px;">{primary_coin} · {timeframe}</div>', unsafe_allow_html=True)

    with st.spinner("Loading chart data..."):
        df = get_klines(primary_coin, timeframe, limit=candle_limit)

    if df.empty:
        st.error("⚠️ Could not load chart data. Check your internet connection.")
    else:
        df_ind = run_all_indicators(df.copy())
        structure = detect_structure(df_ind)
        waves = detect_elliott_wave(df_ind)

        # Structure info
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">MARKET STRUCTURE</div><div style="font-size:1rem; color:#E2E8F0; font-family:monospace; margin-top:4px;">{structure["structure"]}</div></div>', unsafe_allow_html=True)
        with col_s2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">ELLIOTT WAVE</div><div style="font-size:0.9rem; color:#FFD700; font-family:monospace; margin-top:4px;">{waves["wave_label"]}</div></div>', unsafe_allow_html=True)
        with col_s3:
            rsi_val = df_ind["rsi"].iloc[-1] if "rsi" in df_ind.columns and not df_ind["rsi"].isna().all() else 0
            rsi_color = "#FF4466" if rsi_val > 70 else "#00FFA3" if rsi_val < 30 else "#E2E8F0"
            st.markdown(f'<div class="metric-card"><div class="metric-label">RSI</div><div style="font-size:1.4rem; color:{rsi_color}; font-family:monospace;">{rsi_val:.1f}</div></div>', unsafe_allow_html=True)
        with col_s4:
            price_now = df["close"].iloc[-1]
            st.markdown(f'<div class="metric-card"><div class="metric-label">CURRENT PRICE</div><div class="metric-value">${price_now:,.4f}</div></div>', unsafe_allow_html=True)

        # Main Chart
        fig = create_candlestick_chart(df_ind, f"{primary_coin} / {timeframe}", show_smc=show_smc)
        st.plotly_chart(fig, use_container_width=True)

        # Elliott Wave pivots
        if waves["pivots"]:
            with st.expander("📊 Elliott Wave Pivots"):
                pivot_df = pd.DataFrame(waves["pivots"])
                st.dataframe(pivot_df, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3: AI SIGNALS
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:12px;">ML MODEL SIGNALS</div>', unsafe_allow_html=True)

    col_train, col_predict = st.columns([1, 2])

    with col_train:
        st.markdown("**Train Models**")
        train_coins = st.multiselect("Coins to Train", POPULAR_COINS,
                                     default=selected_coins[:3] if selected_coins else ["BTCUSDT"])
        train_tf = st.selectbox("Training Timeframe", ["1h", "4h", "1d"], index=0)

        if st.button("🔥 Train All Models", use_container_width=True):
            for coin in train_coins:
                with st.spinner(f"Training {coin}..."):
                    df_train = get_klines(coin, train_tf, limit=500)
                    if not df_train.empty:
                        result = train_model(df_train, coin)
                        if "error" in result:
                            st.error(f"{coin}: {result['error']}")
                        else:
                            st.success(f"✅ {coin} — Accuracy: {result['accuracy']}%")
                    else:
                        st.warning(f"⚠️ {coin}: No data")

    with col_predict:
        st.markdown("**Live Signals**")
        if st.button("🔍 Generate Signals", use_container_width=True):
            for coin in (selected_coins if selected_coins else ["BTCUSDT"]):
                df_sig = get_klines(coin, timeframe, limit=300)
                if df_sig.empty:
                    continue
                sig = predict_signal(df_sig, coin)
                price_info = get_live_price(coin)

                signal_text = sig.get("signal", "N/A")
                conf = sig.get("confidence", 0)
                color = "#00FFA3" if "BUY" in signal_text else "#FF4466" if "SELL" in signal_text else "#64748B"

                st.markdown(f"""
                <div class="metric-card" style="margin-bottom:8px; text-align:left; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#E2E8F0; font-family:monospace; font-size:0.95rem;">{coin.replace('USDT','/USDT')}</div>
                        <div style="color:#64748B; font-size:0.75rem;">${price_info.get('price',0):,.4f}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:{color}; font-family:monospace; font-size:1.1rem; font-weight:bold;">{signal_text}</div>
                        <div style="color:#64748B; font-size:0.75rem;">Confidence: {conf}%</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Gemini AI Analysis ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**🤖 Gemini AI Market Analysis**")
    gemini = get_gemini_rotator()

    if st.button("💬 Get Gemini AI Analysis", use_container_width=True):
        with st.spinner("Consulting Gemini AI (with key rotation)..."):
            df_ai = get_klines(primary_coin, timeframe, limit=100)
            if not df_ai.empty:
                df_ai = run_all_indicators(df_ai)
                structure = detect_structure(df_ai)
                rsi_now = df_ai["rsi"].iloc[-1] if "rsi" in df_ai.columns else "N/A"
                price_now = df_ai["close"].iloc[-1]

                prompt = f"""
You are a professional crypto trading analyst. Analyze {primary_coin} on {timeframe} timeframe:

Current Price: ${price_now:,.4f}
RSI: {rsi_now:.1f if isinstance(rsi_now, float) else rsi_now}
Market Structure: {structure['structure']}
Last High: ${structure['last_high']:,.4f}
Last Low: ${structure['last_low']:,.4f}

Provide:
1. Overall market sentiment (BULLISH/BEARISH/NEUTRAL)
2. Key levels to watch (support/resistance)
3. Trading recommendation (BUY/SELL/WAIT) with brief reasoning
4. Risk warning

Keep response under 300 words. Use clear structure.
"""
                response = gemini.generate(prompt)
                st.markdown(f"""
                <div style="background:#111827; border:1px solid #1E2A3A; border-radius:8px; padding:16px; font-size:0.9rem; line-height:1.7; color:#CBD5E1;">
                {response.replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 4: NEWS
# ════════════════════════════════════════════════════════════════════════════════
with tab4:
    col_n1, col_n2 = st.columns([3, 1])
    with col_n1:
        st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:12px;">CRYPTO NEWS FEED</div>', unsafe_allow_html=True)
    with col_n2:
        news_filter = st.selectbox("Filter by coin", ["All"] + selected_coins)

    if st.button("📰 Fetch Latest News"):
        with st.spinner("Fetching news..."):
            filter_sym = None if news_filter == "All" else news_filter
            articles = fetch_news(filter_sym, max_articles=20)
            market_sent = get_overall_market_sentiment(articles)

            st.markdown(f'<div style="color:#64748B; font-size:0.8rem; margin-bottom:12px;">Market Sentiment: <span style="font-family:monospace; font-size:1rem;">{market_sent}</span></div>', unsafe_allow_html=True)

            if articles:
                for art in articles:
                    sent_color = "#00FFA3" if "Bullish" in art["sentiment"] else "#FF4466" if "Bearish" in art["sentiment"] else "#64748B"
                    st.markdown(f"""
                    <div class="price-card" style="margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div style="flex:1; margin-right:12px;">
                                <a href="{art['link']}" target="_blank" style="color:#E2E8F0; text-decoration:none; font-size:0.9rem; font-weight:600;">{art['title']}</a>
                                <div style="color:#64748B; font-size:0.75rem; margin-top:4px;">{art['source']} · {art['published'][:16] if art.get('published') else ''}</div>
                            </div>
                            <div style="color:{sent_color}; font-size:0.8rem; font-family:monospace; white-space:nowrap;">{art['sentiment']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No news articles found. Try 'All' filter.")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 5: BACKTEST
# ════════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:12px;">BACKTESTING ENGINE</div>', unsafe_allow_html=True)

    bt_col1, bt_col2 = st.columns([1, 2])
    with bt_col1:
        bt_coin = st.selectbox("Coin", POPULAR_COINS, index=0)
        bt_tf = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=2)
        bt_capital = st.number_input("Starting Capital ($)", value=1000.0, step=100.0)
        bt_limit = st.slider("Candles for Backtest", 200, 1000, 500)

    with bt_col2:
        if st.button("▶️ Run Backtest", use_container_width=True):
            with st.spinner("Loading data and running backtest..."):
                df_bt = get_klines(bt_coin, bt_tf, limit=bt_limit)
                if df_bt.empty:
                    st.error("No data available")
                else:
                    # First ensure model is trained
                    check_result = predict_signal(df_bt, bt_coin)
                    if not check_result.get("trained"):
                        st.info("Model not trained. Training now...")
                        train_result = train_model(df_bt, bt_coin)
                        st.success(f"Model trained — Accuracy: {train_result.get('accuracy', '?')}%")

                    result = run_backtest(df_bt, bt_coin, bt_capital)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        ret_color = "#00FFA3" if result["total_return_pct"] >= 0 else "#FF4466"
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f'<div class="metric-card"><div class="metric-label">FINAL CAPITAL</div><div class="metric-value">${result["final_capital"]:,.2f}</div></div>', unsafe_allow_html=True)
                        c2.markdown(f'<div class="metric-card"><div class="metric-label">TOTAL RETURN</div><div style="font-size:1.4rem; color:{ret_color}; font-family:monospace;">{result["total_return_pct"]:+.2f}%</div></div>', unsafe_allow_html=True)
                        c3.markdown(f'<div class="metric-card"><div class="metric-label">TOTAL TRADES</div><div class="metric-value">{result["total_trades"]}</div></div>', unsafe_allow_html=True)
                        c4.markdown(f'<div class="metric-card"><div class="metric-label">WIN RATE</div><div class="metric-value">{result["win_rate"]}%</div></div>', unsafe_allow_html=True)

                        st.markdown("**Equity Curve**")
                        fig_eq = create_equity_curve(result["equity_curve"], result["trades"])
                        st.plotly_chart(fig_eq, use_container_width=True)

                        if result["trades"]:
                            with st.expander("📋 Trade History"):
                                st.dataframe(pd.DataFrame(result["trades"]), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 6: RISK MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<div style="color:#64748B; font-size:0.75rem; letter-spacing:3px; margin-bottom:12px;">RISK MANAGEMENT TOOLS</div>', unsafe_allow_html=True)

    r_col1, r_col2 = st.columns(2)

    with r_col1:
        st.markdown("**Position Size Calculator**")
        entry_price = st.number_input("Entry Price ($)", value=50000.0, step=100.0)
        sl_price = st.number_input("Stop Loss Price ($)", value=49000.0, step=100.0)
        direction = st.radio("Direction", ["long", "short"], horizontal=True)

        if st.button("Calculate Position", use_container_width=True):
            pos = calculate_position_size(capital, risk_pct, entry_price, sl_price)
            if "error" not in pos:
                atr_est = abs(entry_price - sl_price)
                sl_tp = calculate_sl_tp(entry_price, direction, atr_est)

                st.markdown(f"""
                <div class="metric-card" style="text-align:left; margin-top:12px;">
                    <div style="font-family:monospace; line-height:2; font-size:0.9rem;">
                    💰 Risk Amount: <span style="color:#FFD700;">${pos['risk_amount']}</span><br>
                    📊 Units: <span style="color:#00FFA3;">{pos['units']}</span><br>
                    💵 Position Value: <span style="color:#4488FF;">${pos['position_value']}</span><br>
                    🛑 Stop Loss: <span style="color:#FF4466;">${sl_tp['stop_loss']:,.4f}</span><br>
                    🎯 Take Profit: <span style="color:#00FFA3;">${sl_tp['take_profit']:,.4f}</span><br>
                    ⚖️ R:R Ratio: <span style="color:#FFD700;">1:{sl_tp['rr_ratio']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with r_col2:
        st.markdown("**Auto Compounding Calculator**")
        comp_return = st.slider("Monthly Return (%)", 1.0, 50.0, 10.0, 0.5)
        comp_months = st.slider("Months", 3, 60, 24)
        comp_capital = st.number_input("Starting Capital ($) ", value=capital, step=100.0)

        if st.button("📈 Calculate Growth", use_container_width=True):
            curve = auto_compound(comp_capital, comp_return, comp_months)
            final = curve[-1]["capital"]
            gain = curve[-1]["gain"]
            mult = final / comp_capital

            st.markdown(f"""
            <div class="metric-card" style="text-align:left; margin-top:12px;">
                <div style="font-family:monospace; line-height:2; font-size:0.9rem;">
                🚀 Final Capital: <span style="color:#00FFA3;">${final:,.2f}</span><br>
                📈 Total Gain: <span style="color:#FFD700;">+${gain:,.2f}</span><br>
                ✖️ Multiplier: <span style="color:#4488FF;">{mult:.2f}x</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            fig_comp = create_compound_chart(curve)
            st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("---")
    st.markdown("**Kelly Criterion**")
    k_col1, k_col2, k_col3 = st.columns(3)
    with k_col1:
        k_winrate = st.number_input("Win Rate (%)", value=55.0, step=1.0)
    with k_col2:
        k_avgwin = st.number_input("Avg Win ($)", value=150.0, step=10.0)
    with k_col3:
        k_avgloss = st.number_input("Avg Loss ($)", value=100.0, step=10.0)

    if st.button("🎯 Calculate Kelly", use_container_width=True):
        kelly_pct = kelly_criterion(k_winrate, k_avgwin, k_avgloss)
        kelly_amount = capital * kelly_pct / 100
        st.markdown(f"""
        <div class="metric-card" style="text-align:center; margin-top:12px;">
            <div class="metric-label">KELLY CRITERION (HALF-KELLY)</div>
            <div class="metric-value">{kelly_pct:.1f}% of Capital</div>
            <div style="color:#FFD700; font-family:monospace;">${kelly_amount:,.2f} per trade</div>
        </div>
        """, unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#1E2A3A; font-family:monospace; font-size:0.7rem; letter-spacing:2px;">
CryptoAI Terminal · Powered by Binance API + Gemini AI · For educational purposes only · Not financial advice
</div>
""", unsafe_allow_html=True)
