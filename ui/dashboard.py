# ui/dashboard.py
# ============================================
# Crypto Trading Dashboard (Streamlit)
# Run: streamlit run ui/dashboard.py
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
from datetime import datetime
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DEFAULT_COINS, TIMEFRAMES, DEFAULT_TIMEFRAME
from config.logger import get_logger
from data.fetcher import get_ohlcv, get_current_price
from strategy.indicators import add_all_indicators, detect_market_structure
from strategy.smc import run_smc_analysis
from strategy.signal_engine import generate_signal

logger = get_logger(__name__)

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────

st.set_page_config(
    page_title="CryptoAI Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# CUSTOM CSS - Dark Trading Terminal Style
# ─────────────────────────────────────────

st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0a0e1a; color: #e0e0e0; }
    
    /* Sidebar */
    .css-1d391kg { background-color: #0d1117; }
    
    /* Signal cards */
    .signal-buy {
        background: linear-gradient(135deg, #0d2d1a, #1a4a2a);
        border: 1px solid #00ff88;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .signal-sell {
        background: linear-gradient(135deg, #2d0d0d, #4a1a1a);
        border: 1px solid #ff4466;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .signal-hold {
        background: linear-gradient(135deg, #1a1a0d, #2a2a1a);
        border: 1px solid #ffaa00;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    
    /* Metric cards */
    .metric-card {
        background: #0d1117;
        border: 1px solid #1e2a3a;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
    }
    
    /* Headers */
    h1 { color: #00d4ff !important; font-family: 'Courier New', monospace; }
    h2, h3 { color: #88ccff !important; }
    
    /* Price display */
    .price-up { color: #00ff88; font-weight: bold; font-size: 1.3em; }
    .price-down { color: #ff4466; font-weight: bold; font-size: 1.3em; }
    
    /* Table styling */
    .dataframe { background-color: #0d1117 !important; color: #e0e0e0 !important; }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #1a2a4a, #2a3a6a);
        color: #00d4ff;
        border: 1px solid #00d4ff;
        border-radius: 8px;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab"] { color: #88ccff; }
    .stTabs [aria-selected="true"] { color: #00d4ff; border-bottom-color: #00d4ff; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────

if "coins" not in st.session_state:
    st.session_state.coins = DEFAULT_COINS.copy()

if "settings" not in st.session_state:
    st.session_state.settings = {
        "risk_percent":    1.0,
        "timeframe":       DEFAULT_TIMEFRAME,
        "auto_trading":    False,
        "ai_signals":      True,
        "news_filter":     True,
        "binance_api_key": "",
        "binance_secret":  "",
    }

if "signals_cache" not in st.session_state:
    st.session_state.signals_cache = {}


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────

with st.sidebar:
    st.markdown("# 📈 CryptoAI")
    st.markdown("---")

    # Coin Management
    st.markdown("### 🪙 Coin Selection")
    new_coin = st.text_input("Add coin (e.g. BNBUSDT)", "").upper()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Add") and new_coin:
            if new_coin not in st.session_state.coins:
                st.session_state.coins.append(new_coin)
                st.success(f"Added {new_coin}")
    with col2:
        if st.button("🗑 Clear"):
            st.session_state.coins = DEFAULT_COINS.copy()

    # Coin toggles
    selected_coins = st.multiselect(
        "Active coins",
        st.session_state.coins,
        default=st.session_state.coins[:4],
    )

    st.markdown("---")

    # Timeframe
    st.markdown("### ⏱ Timeframe")
    timeframe = st.select_slider(
        "Select timeframe",
        options=TIMEFRAMES,
        value=st.session_state.settings["timeframe"],
    )

    st.markdown("---")

    # Quick Settings
    st.markdown("### ⚙️ Quick Settings")
    auto_trading = st.toggle("🤖 Auto Trading", value=False)
    ai_signals   = st.toggle("🧠 AI Signals",   value=True)
    news_filter  = st.toggle("📰 News Filter",  value=True)

    if auto_trading:
        st.warning("⚠️ Auto trading active! Real money at risk.")

    st.markdown("---")
    risk_pct = st.slider("Risk per trade (%)", 0.5, 5.0, 1.0, 0.5)

    st.markdown("---")

    # Refresh
    refresh_rate = st.selectbox("Auto refresh", ["Off", "30s", "1m", "5m"])
    if st.button("🔄 Refresh Now"):
        st.session_state.signals_cache = {}
        st.rerun()


# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────

col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown("# 📊 CryptoAI Trading Terminal")
with col_time:
    st.markdown(f"<br><small style='color:#666'>Last update: {datetime.now().strftime('%H:%M:%S')}</small>", 
                unsafe_allow_html=True)

st.markdown("---")


# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────

tab_dashboard, tab_chart, tab_signals, tab_settings = st.tabs([
    "📊 Dashboard", "📈 Charts", "🎯 Signals", "⚙️ Settings"
])


# ──────────────────────────────────────────
# TAB 1: DASHBOARD - Live price table + signal overview
# ──────────────────────────────────────────

with tab_dashboard:
    st.markdown("### 💹 Live Market Overview")

    if not selected_coins:
        st.warning("Select at least one coin in the sidebar.")
    else:
        # Fetch data and generate signals for all selected coins
        market_data = []
        signals_dict = {}

        progress = st.progress(0, text="Fetching market data...")

        for idx, symbol in enumerate(selected_coins):
            progress.progress((idx + 1) / len(selected_coins), f"Analyzing {symbol}...")

            # Use cache if available (avoid re-fetching on every rerender)
            cache_key = f"{symbol}_{timeframe}"
            if cache_key not in st.session_state.signals_cache:
                df = get_ohlcv(symbol, timeframe, 300)
                signal = generate_signal(symbol, df, timeframe)
                st.session_state.signals_cache[cache_key] = {
                    "df": df, "signal": signal
                }

            cached = st.session_state.signals_cache[cache_key]
            df = cached["df"]
            signal = cached["signal"]
            signals_dict[symbol] = signal

            # Calculate 24h change (demo approximation)
            price_24h_ago = float(df["close"].iloc[-96]) if len(df) > 96 else float(df["close"].iloc[0])
            current_price = float(df["close"].iloc[-1])
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100

            market_data.append({
                "Symbol":       symbol,
                "Price":        f"${current_price:,.4f}",
                "24h Change":   f"{change_24h:+.2f}%",
                "Signal":       signal.signal,
                "Confidence":   f"{signal.confidence:.1f}%",
                "Stop Loss":    f"${signal.stop_loss:,.4f}",
                "Take Profit":  f"${signal.take_profit:,.4f}",
            })

        progress.empty()

        # Display market table
        market_df = pd.DataFrame(market_data)

        # Color-code the signal column
        def style_signal(val):
            colors = {"BUY": "#00ff88", "SELL": "#ff4466", "HOLD": "#ffaa00"}
            c = colors.get(val, "white")
            return f"color: {c}; font-weight: bold"

        def style_change(val):
            v = float(val.replace("%", "").replace("+", ""))
            return "color: #00ff88" if v >= 0 else "color: #ff4466"

        styled_df = market_df.style.applymap(
            style_signal, subset=["Signal"]
        ).applymap(
            style_change, subset=["24h Change"]
        )

        st.dataframe(styled_df, use_container_width=True, height=250)

        # ── Summary Stats Row ──────────────
        st.markdown("### 📈 Signal Summary")
        buy_count  = sum(1 for s in signals_dict.values() if s.signal == "BUY")
        sell_count = sum(1 for s in signals_dict.values() if s.signal == "SELL")
        hold_count = sum(1 for s in signals_dict.values() if s.signal == "HOLD")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🟢 BUY Signals",  buy_count)
        with col2:
            st.metric("🔴 SELL Signals", sell_count)
        with col3:
            st.metric("🟡 HOLD Signals", hold_count)
        with col4:
            avg_conf = np.mean([s.confidence for s in signals_dict.values()])
            st.metric("📊 Avg Confidence", f"{avg_conf:.1f}%")

        # ── Mini Signal Cards ──────────────
        st.markdown("### 🎯 Signal Cards")
        cols = st.columns(min(len(selected_coins), 4))

        for i, (symbol, signal) in enumerate(signals_dict.items()):
            with cols[i % 4]:
                css_class = {
                    "BUY": "signal-buy",
                    "SELL": "signal-sell",
                    "HOLD": "signal-hold",
                }[signal.signal]

                color = {"BUY": "#00ff88", "SELL": "#ff4466", "HOLD": "#ffaa00"}[signal.signal]
                emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[signal.signal]

                st.markdown(f"""
                <div class="{css_class}">
                    <h4 style="color:{color}; margin:0">{emoji} {symbol}</h4>
                    <h3 style="color:{color}; margin:4px 0">{signal.signal}</h3>
                    <p style="margin:2px; font-size:0.85em">Confidence: <b>{signal.confidence:.1f}%</b></p>
                    <p style="margin:2px; font-size:0.85em">Price: ${signal.price:,.4f}</p>
                    <p style="margin:2px; font-size:0.8em; color:#aaa">SL: ${signal.stop_loss:,.4f}</p>
                    <p style="margin:2px; font-size:0.8em; color:#aaa">TP: ${signal.take_profit:,.4f}</p>
                </div>
                """, unsafe_allow_html=True)


# ──────────────────────────────────────────
# TAB 2: CHART - Candlestick + indicators
# ──────────────────────────────────────────

with tab_chart:
    st.markdown("### 📈 Price Chart")

    if not selected_coins:
        st.warning("Select coins in sidebar.")
    else:
        chart_coin = st.selectbox("Select coin to chart", selected_coins)
        chart_tf   = st.select_slider("Chart timeframe", TIMEFRAMES, value=timeframe, key="chart_tf")
        candles    = st.slider("Number of candles", 50, 500, 200, key="candle_count")

        with st.spinner(f"Loading chart for {chart_coin}..."):
            df = get_ohlcv(chart_coin, chart_tf, candles)
            df = add_all_indicators(df)
            smc = run_smc_analysis(df)

        # ── Build Plotly Chart ────────────
        fig = make_subplots(
            rows=3, cols=1,
            row_heights=[0.6, 0.2, 0.2],
            shared_xaxes=True,
            subplot_titles=[
                f"{chart_coin} Price ({chart_tf})",
                "RSI",
                "Volume",
            ],
            vertical_spacing=0.04,
        )

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="Price",
            increasing_line_color="#00ff88",
            decreasing_line_color="#ff4466",
        ), row=1, col=1)

        # EMAs
        colors_ema = {"ema_9": "#ffaa00", "ema_21": "#00aaff", "ema_50": "#ff44aa", "ema_200": "#ffffff"}
        for ema_col, ema_color in colors_ema.items():
            if ema_col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[ema_col],
                    name=ema_col.upper().replace("_", " "),
                    line=dict(color=ema_color, width=1.5),
                ), row=1, col=1)

        # Bollinger Bands
        if "bb_upper" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["bb_upper"],
                name="BB Upper", line=dict(color="#444466", dash="dot"),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df["bb_lower"],
                name="BB Lower", line=dict(color="#444466", dash="dot"),
                fill="tonexty", fillcolor="rgba(100,100,255,0.05)",
            ), row=1, col=1)

        # Order Blocks (shaded rectangles)
        for ob in smc.get("order_blocks", [])[-5:]:
            color = "rgba(0,255,136,0.15)" if ob["type"] == "bullish" else "rgba(255,68,102,0.15)"
            border = "#00ff88" if ob["type"] == "bullish" else "#ff4466"
            fig.add_hrect(
                y0=ob["bottom"], y1=ob["top"],
                fillcolor=color,
                line_color=border, line_width=1,
                annotation_text=f"OB {ob['type'][:4].upper()}",
                annotation_font_color=border,
                row=1, col=1,
            )

        # FVG zones
        for fvg in smc.get("fvgs", [])[-3:]:
            color = "rgba(0,200,255,0.1)" if fvg["type"] == "bullish" else "rgba(255,150,0,0.1)"
            fig.add_hrect(
                y0=fvg["bottom"], y1=fvg["top"],
                fillcolor=color,
                line_color="#4488ff", line_width=0.5, line_dash="dot",
                annotation_text="FVG",
                annotation_font_color="#4488ff",
                row=1, col=1,
            )

        # RSI
        fig.add_trace(go.Scatter(
            x=df.index, y=df["rsi"],
            name="RSI", line=dict(color="#ffaa00"),
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#ff4466", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00ff88", row=2, col=1)
        fig.add_hline(y=50, line_dash="dot",  line_color="#444",    row=2, col=1)

        # Volume
        colors_vol = ["#00ff88" if c >= o else "#ff4466"
                      for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["volume"],
            name="Volume", marker_color=colors_vol,
        ), row=3, col=1)

        # Volume MA
        if "volume_ma" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["volume_ma"],
                name="Vol MA", line=dict(color="#ffaa00"),
            ), row=3, col=1)

        # Layout
        fig.update_layout(
            height=750,
            paper_bgcolor="#0a0e1a",
            plot_bgcolor="#0d1117",
            font=dict(color="#e0e0e0"),
            legend=dict(bgcolor="#0d1117", bordercolor="#1e2a3a"),
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        fig.update_xaxes(gridcolor="#1e2a3a", showgrid=True)
        fig.update_yaxes(gridcolor="#1e2a3a", showgrid=True)

        st.plotly_chart(fig, use_container_width=True)

        # ── SMC Summary ──────────────────
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🔶 Active Order Blocks")
            if smc["order_blocks"]:
                for ob in smc["order_blocks"][-5:]:
                    color = "#00ff88" if ob["type"] == "bullish" else "#ff4466"
                    st.markdown(f"<span style='color:{color}'>● {ob['type'].upper()}</span> "
                                f"${ob['bottom']:.2f} — ${ob['top']:.2f}", 
                                unsafe_allow_html=True)
            else:
                st.info("No active order blocks")

        with col2:
            st.markdown("#### 💧 Liquidity Zones")
            liq = smc["liquidity"]
            if liq.get("buy_side"):
                st.markdown("**Buy-side (above):**")
                for z in liq["buy_side"][:3]:
                    st.markdown(f"  🟢 ${z['price']:.2f}")
            if liq.get("sell_side"):
                st.markdown("**Sell-side (below):**")
                for z in liq["sell_side"][:3]:
                    st.markdown(f"  🔴 ${z['price']:.2f}")


# ──────────────────────────────────────────
# TAB 3: SIGNALS - Detailed signal breakdown
# ──────────────────────────────────────────

with tab_signals:
    st.markdown("### 🎯 Detailed Signal Analysis")

    if not selected_coins:
        st.warning("Select coins in sidebar.")
    else:
        sig_coin = st.selectbox("Analyze coin", selected_coins, key="sig_coin")

        with st.spinner(f"Generating signal for {sig_coin}..."):
            df = get_ohlcv(sig_coin, timeframe, 300)
            signal = generate_signal(sig_coin, df, timeframe)
            smc = run_smc_analysis(df)
            ms = detect_market_structure(add_all_indicators(df))

        sig = signal.to_dict()

        # Signal header
        sig_color = {"BUY": "#00ff88", "SELL": "#ff4466", "HOLD": "#ffaa00"}[sig["signal"]]
        sig_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[sig["signal"]]

        st.markdown(f"""
        <div style="background: #0d1117; border: 2px solid {sig_color}; border-radius: 16px; padding: 24px; text-align:center; margin: 16px 0;">
            <h1 style="color: {sig_color}; margin: 0; font-size: 3em">{sig_emoji} {sig['signal']}</h1>
            <h2 style="color: #ccc; margin: 4px 0">{sig['symbol']} · {sig['timeframe']}</h2>
            <h3 style="color: {sig_color}; margin: 4px 0">Confidence: {sig['confidence']}%</h3>
            <small style="color: #666">{sig['timestamp']}</small>
        </div>
        """, unsafe_allow_html=True)

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Entry Price",  f"${sig['price']:,.4f}")
        col2.metric("Stop Loss",    f"${sig['stop_loss']:,.4f}",
                    delta=f"{((sig['stop_loss'] - sig['price']) / sig['price'] * 100):+.2f}%")
        col3.metric("Take Profit",  f"${sig['take_profit']:,.4f}",
                    delta=f"{((sig['take_profit'] - sig['price']) / sig['price'] * 100):+.2f}%")
        col4.metric("Risk:Reward",  f"1 : {sig['risk_reward']:.1f}")

        st.markdown("---")

        # Reasons breakdown
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📋 Signal Reasons")
            for reason in sig["reason"]:
                icon = "✅" if sig["signal"] == "BUY" else "⚠️" if sig["signal"] == "SELL" else "ℹ️"
                st.markdown(f"{icon} {reason}")

        with col2:
            st.markdown("#### 🏗️ Market Context")
            st.markdown(f"**Market Structure:** {ms['structure']}")
            st.markdown(f"_{ms['description']}_")
            st.markdown(f"**SMC Context:** {sig['smc_context']}")

            if smc.get("latest_event"):
                ev = smc["latest_event"]
                st.markdown(f"**Latest Event:** {ev['description']}")

        # Confidence gauge
        st.markdown("---")
        st.markdown("#### 📊 Confidence Breakdown")

        conf = sig["confidence"]
        bar_color = "#00ff88" if sig["signal"] == "BUY" else "#ff4466" if sig["signal"] == "SELL" else "#ffaa00"

        fig_conf = go.Figure(go.Indicator(
            mode="gauge+number",
            value=conf,
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#888"},
                "bar": {"color": bar_color},
                "bgcolor": "#0d1117",
                "bordercolor": "#1e2a3a",
                "steps": [
                    {"range": [0, 40],   "color": "#1a0d0d"},
                    {"range": [40, 60],  "color": "#1a1a0d"},
                    {"range": [60, 100], "color": "#0d1a0d"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 2},
                    "thickness": 0.75, "value": 60
                },
            },
            number={"suffix": "%", "font": {"color": bar_color, "size": 40}},
            title={"text": "Signal Confidence", "font": {"color": "#888"}},
        ))

        fig_conf.update_layout(
            height=300,
            paper_bgcolor="#0a0e1a",
            font=dict(color="#e0e0e0"),
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_conf, use_container_width=True)


# ──────────────────────────────────────────
# TAB 4: SETTINGS
# ──────────────────────────────────────────

with tab_settings:
    st.markdown("### ⚙️ System Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔑 API Configuration")
        api_key = st.text_input(
            "Binance API Key",
            value=st.session_state.settings["binance_api_key"],
            type="password",
            help="Get from Binance → Account → API Management"
        )
        api_secret = st.text_input(
            "Binance Secret Key",
            value=st.session_state.settings["binance_secret"],
            type="password"
        )
        testnet = st.checkbox("Use Testnet (Paper Trading)", value=True)

        st.markdown("---")
        st.markdown("#### 📊 Trading Parameters")
        risk_pct = st.number_input("Risk per trade (%)", 0.5, 10.0, 1.0, 0.5)
        rr_ratio = st.number_input("Risk:Reward ratio", 1.0, 5.0, 2.0, 0.5)
        max_loss = st.number_input("Max daily loss (%)", 1.0, 20.0, 5.0, 1.0)

    with col2:
        st.markdown("#### 🔔 Alerts Configuration")
        tg_token = st.text_input("Telegram Bot Token", type="password")
        tg_chat  = st.text_input("Telegram Chat ID")
        email    = st.text_input("Email address (for alerts)")

        st.markdown("---")
        st.markdown("#### 🤖 Feature Toggles")
        feat_auto   = st.toggle("Enable Auto Trading",  value=False)
        feat_ai     = st.toggle("Enable AI Signals",    value=True)
        feat_news   = st.toggle("Enable News Filter",   value=True)
        feat_comp   = st.toggle("Auto Compounding",     value=False)
        feat_ml     = st.toggle("ML Predictions",       value=False,
                                help="Requires ML module - Phase 5")

        if feat_auto:
            st.error("⚠️ Auto trading will place REAL orders on Binance!")

    st.markdown("---")
    if st.button("💾 Save Settings", type="primary"):
        st.session_state.settings.update({
            "binance_api_key": api_key,
            "binance_secret":  api_secret,
            "risk_percent":    risk_pct,
            "auto_trading":    feat_auto,
            "ai_signals":      feat_ai,
            "news_filter":     feat_news,
        })
        st.success("✅ Settings saved successfully!")

    st.markdown("---")
    st.markdown("#### ℹ️ System Info")
    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        st.info("**Mode:** Demo" if not feat_auto else "**Mode:** LIVE")
    with info_col2:
        st.info(f"**Coins tracked:** {len(selected_coins)}")
    with info_col3:
        st.info(f"**Active timeframe:** {timeframe}")

    st.markdown("""
    > **⚠️ DISCLAIMER:** This software is for educational purposes only.  
    > Cryptocurrency trading involves significant risk. Never trade with money you cannot afford to lose.  
    > Past performance does not guarantee future results.
    """)


# ─────────────────────────────────────────
# AUTO REFRESH LOGIC
# ─────────────────────────────────────────

refresh_map = {"30s": 30, "1m": 60, "5m": 300}
if refresh_rate != "Off":
    seconds = refresh_map.get(refresh_rate, 60)
    time.sleep(seconds)
    st.session_state.signals_cache = {}
    st.rerun()
