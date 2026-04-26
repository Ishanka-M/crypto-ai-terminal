# utils/sheets_manager.py
# ============================================
# Google Sheets Integration
# Save/Load: API Keys, Settings, Trade History
# Works with Service Account credentials
# ============================================

import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

# ── Safe import ─────────────────────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet tab names
SHEET_SETTINGS     = "Settings"
SHEET_API_KEYS     = "API_Keys"
SHEET_TRADE_LOG    = "Trade_Log"
SHEET_SIGNALS      = "Signals"


# ─────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────

def get_gsheet_client():
    """
    Returns authenticated gspread client.
    Credentials from Streamlit secrets or service_account.json file.
    """
    if not GSPREAD_AVAILABLE:
        return None

    try:
        # Method 1: From Streamlit secrets (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            return gspread.authorize(creds)

        # Method 2: From local service_account.json file
        if os.path.exists("service_account.json"):
            creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
            return gspread.authorize(creds)

        # Method 3: From session state (uploaded via UI)
        if "gcp_credentials" in st.session_state and st.session_state.gcp_credentials:
            creds = Credentials.from_service_account_info(
                st.session_state.gcp_credentials, scopes=SCOPES
            )
            return gspread.authorize(creds)

        return None

    except Exception as e:
        st.error(f"Google Sheets auth failed: {e}")
        return None


def open_or_create_sheet(spreadsheet_id: str, client=None):
    """Opens a Google Spreadsheet by ID."""
    if client is None:
        client = get_gsheet_client()
    if not client:
        return None
    try:
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        st.error(f"Cannot open spreadsheet: {e}")
        return None


def ensure_tab(spreadsheet, tab_name: str, headers: list):
    """Creates a worksheet tab if it doesn't exist, with headers."""
    try:
        return spreadsheet.worksheet(tab_name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=20)
        ws.append_row(headers)
        return ws


# ─────────────────────────────────────────
# API KEYS — Save & Load
# ─────────────────────────────────────────

def save_api_keys_to_sheet(spreadsheet_id: str, keys_data: dict) -> bool:
    """
    Saves API keys to Google Sheets.

    keys_data format:
    {
        "binance_api_key":    "...",
        "binance_api_secret": "...",
        "gemini_keys":        ["key1", "key2"],
        "telegram_token":     "...",
        "telegram_chat_id":   "...",
    }
    """
    client = get_gsheet_client()
    if not client:
        return False

    try:
        ss = open_or_create_sheet(spreadsheet_id, client)
        if not ss:
            return False

        ws = ensure_tab(ss, SHEET_API_KEYS, [
            "key_name", "key_value", "updated_at", "note"
        ])

        # Clear existing data (keep header)
        ws.clear()
        ws.append_row(["key_name", "key_value", "updated_at", "note"])

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = [
            ["BINANCE_API_KEY",    keys_data.get("binance_api_key", ""),    now, "Binance API Key"],
            ["BINANCE_API_SECRET", keys_data.get("binance_api_secret", ""), now, "Binance Secret"],
            ["TELEGRAM_TOKEN",     keys_data.get("telegram_token", ""),     now, "Telegram Bot Token"],
            ["TELEGRAM_CHAT_ID",   keys_data.get("telegram_chat_id", ""),   now, "Telegram Chat ID"],
            ["EMAIL_SENDER",       keys_data.get("email_sender", ""),       now, "Gmail sender"],
            ["EMAIL_PASSWORD",     keys_data.get("email_password", ""),     now, "Gmail app password"],
        ]

        # Add Gemini keys as separate rows
        for i, gkey in enumerate(keys_data.get("gemini_keys", []), 1):
            rows.append([f"GEMINI_API_KEY_{i}", gkey, now, f"Gemini Key #{i}"])

        ws.append_rows(rows)
        return True

    except Exception as e:
        st.error(f"Failed to save keys: {e}")
        return False


def load_api_keys_from_sheet(spreadsheet_id: str) -> dict:
    """Loads API keys from Google Sheets."""
    client = get_gsheet_client()
    if not client:
        return {}

    try:
        ss = open_or_create_sheet(spreadsheet_id, client)
        if not ss:
            return {}

        ws  = ss.worksheet(SHEET_API_KEYS)
        df  = pd.DataFrame(ws.get_all_records())

        if df.empty:
            return {}

        result = {}
        gemini_keys = []

        for _, row in df.iterrows():
            name = row.get("key_name", "")
            val  = row.get("key_value", "")

            if name == "BINANCE_API_KEY":
                result["binance_api_key"] = val
            elif name == "BINANCE_API_SECRET":
                result["binance_api_secret"] = val
            elif name == "TELEGRAM_TOKEN":
                result["telegram_token"] = val
            elif name == "TELEGRAM_CHAT_ID":
                result["telegram_chat_id"] = val
            elif name == "EMAIL_SENDER":
                result["email_sender"] = val
            elif name == "EMAIL_PASSWORD":
                result["email_password"] = val
            elif name.startswith("GEMINI_API_KEY"):
                if val:
                    gemini_keys.append(val)

        result["gemini_keys"] = gemini_keys
        return result

    except Exception as e:
        st.error(f"Failed to load keys: {e}")
        return {}


# ─────────────────────────────────────────
# SETTINGS — Save & Load
# ─────────────────────────────────────────

def save_settings_to_sheet(spreadsheet_id: str, settings: dict) -> bool:
    """Saves trading settings to Google Sheets."""
    client = get_gsheet_client()
    if not client:
        return False

    try:
        ss = open_or_create_sheet(spreadsheet_id, client)
        ws = ensure_tab(ss, SHEET_SETTINGS, ["setting", "value", "updated_at"])
        ws.clear()
        ws.append_row(["setting", "value", "updated_at"])

        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [[k, str(v), now] for k, v in settings.items()]
        ws.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
        return False


def load_settings_from_sheet(spreadsheet_id: str) -> dict:
    """Loads trading settings from Google Sheets."""
    client = get_gsheet_client()
    if not client:
        return {}
    try:
        ss  = open_or_create_sheet(spreadsheet_id, client)
        ws  = ss.worksheet(SHEET_SETTINGS)
        df  = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return {}
        return dict(zip(df["setting"], df["value"]))
    except Exception:
        return {}


# ─────────────────────────────────────────
# TRADE LOG — Append trades
# ─────────────────────────────────────────

def log_trade_to_sheet(spreadsheet_id: str, trade: dict) -> bool:
    """Appends a single trade to the Trade_Log sheet."""
    client = get_gsheet_client()
    if not client:
        return False
    try:
        ss = open_or_create_sheet(spreadsheet_id, client)
        ws = ensure_tab(ss, SHEET_TRADE_LOG, [
            "timestamp", "symbol", "direction", "entry", "sl", "tp",
            "size_usdt", "confidence", "signal_source", "status"
        ])
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade.get("symbol", ""),
            trade.get("direction", ""),
            trade.get("entry", ""),
            trade.get("sl", ""),
            trade.get("tp", ""),
            trade.get("size_usdt", ""),
            trade.get("confidence", ""),
            trade.get("signal_source", "manual"),
            trade.get("status", "open"),
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"Trade log failed: {e}")
        return False


def get_trade_history(spreadsheet_id: str) -> pd.DataFrame:
    """Returns trade history as a DataFrame."""
    client = get_gsheet_client()
    if not client:
        return pd.DataFrame()
    try:
        ss  = open_or_create_sheet(spreadsheet_id, client)
        ws  = ss.worksheet(SHEET_TRADE_LOG)
        df  = pd.DataFrame(ws.get_all_records())
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# SIGNAL LOG — Save signals
# ─────────────────────────────────────────

def log_signal_to_sheet(spreadsheet_id: str, signal: dict) -> bool:
    """Logs a trading signal to Signals sheet."""
    client = get_gsheet_client()
    if not client:
        return False
    try:
        ss = open_or_create_sheet(spreadsheet_id, client)
        ws = ensure_tab(ss, SHEET_SIGNALS, [
            "timestamp", "symbol", "timeframe", "signal",
            "confidence", "price", "sl", "tp", "rr", "source"
        ])
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            signal.get("symbol", ""),
            signal.get("timeframe", ""),
            signal.get("signal", ""),
            signal.get("confidence", ""),
            signal.get("price", ""),
            signal.get("stop_loss", ""),
            signal.get("take_profit", ""),
            signal.get("risk_reward", ""),
            signal.get("source", "system"),
        ]
        ws.append_row(row)
        return True
    except Exception as e:
        return False


# ─────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────

def is_sheets_available() -> bool:
    return GSPREAD_AVAILABLE and get_gsheet_client() is not None


def get_sheets_status() -> dict:
    return {
        "library_installed": GSPREAD_AVAILABLE,
        "authenticated":     get_gsheet_client() is not None,
        "spreadsheet_id":    st.session_state.get("spreadsheet_id", ""),
    }
