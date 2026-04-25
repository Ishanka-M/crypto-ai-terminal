"""
Chart Engine - Plotly Charts
Candlestick + Indicators + SMC zones
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

DARK_BG = "#0A0E1A"
GRID_COLOR = "#1E2A3A"
GREEN = "#00FFA3"
RED = "#FF4466"
YELLOW = "#FFD700"
BLUE = "#4488FF"
PURPLE = "#9B59FF"

def create_candlestick_chart(df: pd.DataFrame, symbol: str, show_smc: bool = True) -> go.Figure:
    """Full candlestick chart with indicators and SMC"""
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.02,
        subplot_titles=[symbol, "RSI", "MACD", "Volume"]
    )

    # ── Candlestick ──────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="Price",
        increasing_line_color=GREEN,
        decreasing_line_color=RED,
        increasing_fillcolor=GREEN,
        decreasing_fillcolor=RED,
    ), row=1, col=1)

    # ── EMAs ─────────────────────────────────────────────────
    ema_colors = {"ema_9": YELLOW, "ema_21": BLUE, "ema_50": PURPLE, "ema_200": "#FF8800"}
    ema_widths = {"ema_9": 1, "ema_21": 1.5, "ema_50": 2, "ema_200": 2.5}
    for col, color in ema_colors.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=col.upper(), line=dict(color=color, width=ema_widths[col]),
                opacity=0.8,
            ), row=1, col=1)

    # ── Bollinger Bands ───────────────────────────────────────
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["bb_upper"], name="BB Upper",
            line=dict(color=BLUE, dash="dot", width=1), opacity=0.5
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["bb_lower"], name="BB Lower",
            line=dict(color=BLUE, dash="dot", width=1), opacity=0.5,
            fill="tonexty", fillcolor="rgba(68,136,255,0.05)"
        ), row=1, col=1)

    # ── SMC: Order Blocks ─────────────────────────────────────
    if show_smc and "ob_bull" in df.columns:
        ob_bulls = df[df["ob_bull"] == True].tail(5)
        for idx, row in ob_bulls.iterrows():
            if not pd.isna(row.get("ob_bull_high")):
                fig.add_hrect(
                    y0=row["ob_bull_low"], y1=row["ob_bull_high"],
                    fillcolor="rgba(0,255,163,0.1)", line_width=0,
                    annotation_text="Bull OB", annotation_position="right",
                    annotation=dict(font_color=GREEN, font_size=10),
                    row=1, col=1
                )

        ob_bears = df[df["ob_bear"] == True].tail(5)
        for idx, row in ob_bears.iterrows():
            if not pd.isna(row.get("ob_bear_high")):
                fig.add_hrect(
                    y0=row["ob_bear_low"], y1=row["ob_bear_high"],
                    fillcolor="rgba(255,68,102,0.1)", line_width=0,
                    annotation_text="Bear OB", annotation_position="right",
                    annotation=dict(font_color=RED, font_size=10),
                    row=1, col=1
                )

    # ── FVG ───────────────────────────────────────────────────
    if show_smc and "fvg_bull" in df.columns:
        fvg_bulls = df[df["fvg_bull"] == True].tail(3)
        for idx, row in fvg_bulls.iterrows():
            if not pd.isna(row.get("fvg_bull_top")):
                fig.add_hrect(
                    y0=row["fvg_bull_bot"], y1=row["fvg_bull_top"],
                    fillcolor="rgba(0,255,163,0.07)", line_color=GREEN,
                    line_width=0.5, line_dash="dot",
                    row=1, col=1
                )

    # ── RSI ───────────────────────────────────────────────────
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["rsi"], name="RSI",
            line=dict(color=PURPLE, width=1.5)
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color=RED, opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color=GREEN, opacity=0.5, row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,68,102,0.05)", row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,255,163,0.05)", row=2, col=1)

    # ── MACD ──────────────────────────────────────────────────
    if "macd" in df.columns:
        colors = [GREEN if v >= 0 else RED for v in df["macd_hist"].fillna(0)]
        fig.add_trace(go.Bar(
            x=df.index, y=df["macd_hist"], name="MACD Hist",
            marker_color=colors, opacity=0.7
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd"], name="MACD",
            line=dict(color=BLUE, width=1.2)
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["macd_signal"], name="Signal",
            line=dict(color=YELLOW, width=1.2)
        ), row=3, col=1)

    # ── Volume ────────────────────────────────────────────────
    vol_colors = [GREEN if df["close"].iloc[i] >= df["open"].iloc[i] else RED for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"], name="Volume",
        marker_color=vol_colors, opacity=0.7
    ), row=4, col=1)

    # ── Layout ────────────────────────────────────────────────
    fig.update_layout(
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_BG,
        font=dict(color="#E2E8F0", family="monospace"),
        height=750,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode="x unified",
    )
    for i in range(1, 5):
        fig.update_xaxes(
            showgrid=True, gridcolor=GRID_COLOR,
            zeroline=False, row=i, col=1
        )
        fig.update_yaxes(
            showgrid=True, gridcolor=GRID_COLOR,
            zeroline=False, row=i, col=1
        )

    return fig


def create_equity_curve(equity: list, trades: list = None) -> go.Figure:
    """Backtest equity curve chart"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=equity, mode="lines",
        line=dict(color=GREEN, width=2),
        fill="tozeroy",
        fillcolor="rgba(0,255,163,0.1)",
        name="Equity"
    ))
    if trades:
        buy_x = [t["idx"] for t in trades if t["type"] == "BUY"]
        sell_x = [t["idx"] for t in trades if t["type"] == "SELL"]
        buy_y = [equity[i] for i in buy_x if i < len(equity)]
        sell_y = [equity[i] for i in sell_x if i < len(equity)]
        fig.add_trace(go.Scatter(
            x=buy_x, y=buy_y, mode="markers",
            marker=dict(color=GREEN, symbol="triangle-up", size=10),
            name="Buy"
        ))
        fig.add_trace(go.Scatter(
            x=sell_x, y=sell_y, mode="markers",
            marker=dict(color=RED, symbol="triangle-down", size=10),
            name="Sell"
        ))
    fig.update_layout(
        plot_bgcolor=DARK_BG, paper_bgcolor=DARK_BG,
        font=dict(color="#E2E8F0", family="monospace"),
        height=300, showlegend=True,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    return fig


def create_compound_chart(curve: list) -> go.Figure:
    """Auto compounding growth chart"""
    months = [c["month"] for c in curve]
    capitals = [c["capital"] for c in curve]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=capitals, mode="lines+markers",
        line=dict(color=YELLOW, width=2),
        marker=dict(size=6, color=GREEN),
        fill="tozeroy",
        fillcolor="rgba(255,215,0,0.07)",
        name="Capital"
    ))
    fig.update_layout(
        plot_bgcolor=DARK_BG, paper_bgcolor=DARK_BG,
        font=dict(color="#E2E8F0", family="monospace"),
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Month", yaxis_title="Capital ($)"
    )
    return fig
