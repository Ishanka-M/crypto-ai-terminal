# utils/sheets_manager.py
# ============================================
# Google Sheets — Persistent Data Manager
# ALL data saves here permanently:
#   - API Keys (encrypted mask display)
#   - Settings
#   - Signals Log
#   - Trade History
#   - Backtest Results
#   - Chat History
#   - Equity Snapshots
# API Keys never deleted until explicit Reset
# ============================================

import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

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

# ── Sheet tab names ──────────────────────────
TAB_KEYS      = "🔑 API_Keys"
TAB_SETTINGS  = "⚙️ Settings"
TAB_SIGNALS   = "📊 Signals"
TAB_TRADES    = "💰 Trades"
TAB_BACKTEST  = "📉 Backtest"
TAB_EQUITY    = "📈 Equity"
TAB_CHAT      = "💬 Chat_Log"
TAB_AUDIT     = "🔒 Audit_Log"

ALL_TABS = {
    TAB_KEYS:     ["key_name","key_value","saved_at","note","locked"],
    TAB_SETTINGS: ["setting","value","updated_at","category"],
    TAB_SIGNALS:  ["timestamp","symbol","timeframe","signal","confidence",
                   "price","sl","tp","rr","source","ai_comment"],
    TAB_TRADES:   ["timestamp","symbol","direction","entry","sl","tp",
                   "size_usdt","confidence","pnl","status","exit_reason"],
    TAB_BACKTEST: ["timestamp","symbol","timeframe","initial_bal","final_bal",
                   "pnl_pct","win_rate","trades","profit_factor","max_dd","sharpe"],
    TAB_EQUITY:   ["timestamp","balance","pnl","pnl_pct","note"],
    TAB_CHAT:     ["timestamp","role","message","model"],
    TAB_AUDIT:    ["timestamp","action","detail","user_agent"],
}


# ─────────────────────────────────────────
# CLIENT & AUTH
# ─────────────────────────────────────────

def get_gsheet_client():
    if not GSPREAD_AVAILABLE:
        return None
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
            return gspread.authorize(creds)
        if "gcp_credentials" in st.session_state and st.session_state.gcp_credentials:
            creds = Credentials.from_service_account_info(
                st.session_state.gcp_credentials, scopes=SCOPES)
            return gspread.authorize(creds)
        if os.path.exists("service_account.json"):
            creds = Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES)
            return gspread.authorize(creds)
        return None
    except Exception as e:
        return None


def get_spreadsheet(sid: str = None):
    """Opens spreadsheet. Uses session state ID if not provided."""
    client = get_gsheet_client()
    if not client:
        return None
    sid = sid or st.session_state.get("spreadsheet_id", "")
    if not sid:
        return None
    try:
        return client.open_by_key(sid)
    except Exception:
        return None


def ensure_tab(ss, tab_name: str, headers: list):
    """Gets or creates a worksheet tab with headers."""
    try:
        ws = ss.worksheet(tab_name)
        # Check if header row exists
        existing = ws.row_values(1)
        if not existing:
            ws.append_row(headers)
        return ws
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows=2000, cols=len(headers)+2)
        ws.append_row(headers)
        # Format header row
        try:
            ws.format("1:1", {
                "backgroundColor": {"red":0.05,"green":0.08,"blue":0.12},
                "textFormat": {"bold": True, "foregroundColor": {"red":0.0,"green":0.83,"blue":1.0}},
            })
        except Exception:
            pass
        return ws


def setup_all_tabs(sid: str = None) -> bool:
    """Creates ALL required tabs in the spreadsheet."""
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    for tab_name, headers in ALL_TABS.items():
        ensure_tab(ss, tab_name, headers)
    _audit_log(ss, "SETUP", "All tabs initialized")
    return True


def _audit_log(ss, action: str, detail: str):
    """Writes to audit log tab silently."""
    try:
        ws = ensure_tab(ss, TAB_AUDIT, ALL_TABS[TAB_AUDIT])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action, detail, "streamlit-cloud"
        ])
    except Exception:
        pass


# ─────────────────────────────────────────
# API KEYS — Persistent & Locked
# ─────────────────────────────────────────

def save_api_keys(keys_data: dict, sid: str = None) -> bool:
    """
    Saves API keys to Sheets permanently.
    Keys are LOCKED — only deletable via reset_api_keys().

    keys_data = {
        "BINANCE_API_KEY":    "...",
        "BINANCE_API_SECRET": "...",
        "GEMINI_KEY_1":       "...",
        "GEMINI_KEY_2":       "...",
        "TELEGRAM_TOKEN":     "...",
        "TELEGRAM_CHAT_ID":   "...",
        "EMAIL_SENDER":       "...",
        "EMAIL_PASSWORD":     "...",
    }
    """
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws  = ensure_tab(ss, TAB_KEYS, ALL_TABS[TAB_KEYS])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Read existing keys to avoid duplicates
        existing = {}
        try:
            records = ws.get_all_records()
            for r in records:
                existing[r.get("key_name","")] = r
        except Exception:
            pass

        rows_to_add = []
        rows_to_update = []

        for key_name, key_value in keys_data.items():
            if not key_value or not key_name:
                continue
            if key_name in existing:
                # Update existing row (find row number)
                rows_to_update.append((key_name, key_value, now))
            else:
                rows_to_add.append([key_name, key_value, now,
                                     _key_note(key_name), "TRUE"])

        # Add new rows
        if rows_to_add:
            ws.append_rows(rows_to_add)

        # Update existing rows
        for key_name, key_value, now in rows_to_update:
            try:
                cell = ws.find(key_name, in_column=1)
                ws.update_cell(cell.row, 2, key_value)
                ws.update_cell(cell.row, 3, now)
            except Exception:
                ws.append_row([key_name, key_value, now, _key_note(key_name), "TRUE"])

        _audit_log(ss, "SAVE_KEYS", f"Saved {len(keys_data)} keys")
        return True
    except Exception as e:
        return False


def load_api_keys(sid: str = None) -> dict:
    """Loads all API keys from Sheets into session state."""
    ss = get_spreadsheet(sid)
    if not ss:
        return {}
    try:
        ws      = ensure_tab(ss, TAB_KEYS, ALL_TABS[TAB_KEYS])
        records = ws.get_all_records()
        result  = {}
        gemini_keys = []

        for r in records:
            name = r.get("key_name","").strip()
            val  = r.get("key_value","").strip()
            if not name or not val:
                continue

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
            elif name.startswith("GEMINI_KEY"):
                gemini_keys.append(val)
            elif name == "SPREADSHEET_ID":
                result["spreadsheet_id"] = val

        result["gemini_api_keys"] = gemini_keys

        # Push to session state immediately
        for k, v in result.items():
            st.session_state[k] = v

        _audit_log(ss, "LOAD_KEYS", f"Loaded {len(result)} keys")
        return result
    except Exception:
        return {}


def reset_api_keys(sid: str = None, confirm_text: str = "") -> bool:
    """
    PERMANENTLY deletes all API keys from Sheets.
    Requires confirm_text == "RESET" to proceed.
    """
    if confirm_text != "RESET":
        return False
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws      = ensure_tab(ss, TAB_KEYS, ALL_TABS[TAB_KEYS])
        headers = ws.row_values(1)
        ws.clear()
        ws.append_row(headers)
        _audit_log(ss, "RESET_KEYS", "ALL API keys deleted by user")
        # Clear session state
        for k in ["binance_api_key","binance_api_secret","gemini_api_keys",
                  "telegram_token","telegram_chat_id"]:
            st.session_state[k] = "" if isinstance(st.session_state.get(k,""), str) else []
        if "gemini_rotator" in st.session_state:
            del st.session_state["gemini_rotator"]
        return True
    except Exception:
        return False


def _key_note(key_name: str) -> str:
    notes = {
        "BINANCE_API_KEY": "Binance REST API Key",
        "BINANCE_API_SECRET": "Binance Secret Key",
        "TELEGRAM_TOKEN": "Telegram Bot Token",
        "TELEGRAM_CHAT_ID": "Telegram Chat ID",
        "EMAIL_SENDER": "Gmail sender address",
        "EMAIL_PASSWORD": "Gmail App Password",
        "SPREADSHEET_ID": "Google Spreadsheet ID",
    }
    if key_name.startswith("GEMINI_KEY"):
        return f"Gemini API Key #{key_name.split('_')[-1]}"
    return notes.get(key_name, key_name)


def get_saved_keys_display(sid: str = None) -> pd.DataFrame:
    """Returns masked key display for the UI."""
    ss = get_spreadsheet(sid)
    if not ss:
        return pd.DataFrame()
    try:
        ws      = ensure_tab(ss, TAB_KEYS, ALL_TABS[TAB_KEYS])
        records = ws.get_all_records()
        rows = []
        for r in records:
            val = r.get("key_value","")
            masked = f"{val[:6]}{'*'*8}{val[-3:]}" if len(val)>12 else "****"
            rows.append({
                "Key Name":   r.get("key_name",""),
                "Value":      masked,
                "Saved At":   r.get("saved_at",""),
                "Note":       r.get("note",""),
                "Locked":     "🔒" if r.get("locked","TRUE")=="TRUE" else "🔓",
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# SETTINGS — Persistent
# ─────────────────────────────────────────

def save_settings(settings: dict, sid: str = None) -> bool:
    """Saves all settings. Updates existing, adds new."""
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws  = ensure_tab(ss, TAB_SETTINGS, ALL_TABS[TAB_SETTINGS])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        existing = {}
        try:
            for r in ws.get_all_records():
                existing[r.get("setting","")] = r
        except Exception:
            pass

        for key, val in settings.items():
            category = _setting_category(key)
            if key in existing:
                try:
                    cell = ws.find(key, in_column=1)
                    ws.update_cell(cell.row, 2, str(val))
                    ws.update_cell(cell.row, 3, now)
                except Exception:
                    ws.append_row([key, str(val), now, category])
            else:
                ws.append_row([key, str(val), now, category])

        _audit_log(ss, "SAVE_SETTINGS", f"Saved {len(settings)} settings")
        return True
    except Exception:
        return False


def load_settings(sid: str = None) -> dict:
    """Loads settings and pushes to session state."""
    ss = get_spreadsheet(sid)
    if not ss:
        return {}
    try:
        ws      = ensure_tab(ss, TAB_SETTINGS, ALL_TABS[TAB_SETTINGS])
        records = ws.get_all_records()
        result  = {}
        for r in records:
            k = r.get("setting","")
            v = r.get("value","")
            if k:
                result[k] = v
                # Push to session state with type conversion
                if k in st.session_state:
                    orig = st.session_state[k]
                    try:
                        if isinstance(orig, bool):
                            st.session_state[k] = v.lower() in ("true","1","yes")
                        elif isinstance(orig, float):
                            st.session_state[k] = float(v)
                        elif isinstance(orig, int):
                            st.session_state[k] = int(v)
                        elif isinstance(orig, list):
                            st.session_state[k] = [x.strip() for x in v.split(",") if x.strip()]
                        else:
                            st.session_state[k] = v
                    except Exception:
                        st.session_state[k] = v
        return result
    except Exception:
        return {}


def _setting_category(key: str) -> str:
    cats = {
        "risk_pct":"Trading","timeframe":"Trading","coins":"Trading",
        "auto_trading":"Trading","ai_signals":"Features","news_filter":"Features",
        "gemini_model":"AI","spreadsheet_id":"Integration",
    }
    return cats.get(key, "General")


# ─────────────────────────────────────────
# SIGNALS LOG
# ─────────────────────────────────────────

def log_signal(signal: dict, ai_comment: str = "", sid: str = None) -> bool:
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws = ensure_tab(ss, TAB_SIGNALS, ALL_TABS[TAB_SIGNALS])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            signal.get("symbol",""),
            signal.get("timeframe",""),
            signal.get("signal",""),
            signal.get("confidence",""),
            signal.get("price",""),
            signal.get("stop_loss",""),
            signal.get("take_profit",""),
            signal.get("risk_reward",""),
            signal.get("source","system"),
            ai_comment[:200] if ai_comment else "",
        ])
        return True
    except Exception:
        return False


def get_signals_log(sid: str = None, limit: int = 100) -> pd.DataFrame:
    ss = get_spreadsheet(sid)
    if not ss:
        return pd.DataFrame()
    try:
        ws  = ensure_tab(ss, TAB_SIGNALS, ALL_TABS[TAB_SIGNALS])
        all_rows = ws.get_all_records()
        df  = pd.DataFrame(all_rows[-limit:] if len(all_rows)>limit else all_rows)
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# TRADE LOG
# ─────────────────────────────────────────

def log_trade(trade: dict, sid: str = None) -> bool:
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws = ensure_tab(ss, TAB_TRADES, ALL_TABS[TAB_TRADES])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade.get("symbol",""),
            trade.get("direction",""),
            trade.get("entry",""),
            trade.get("sl",""),
            trade.get("tp",""),
            trade.get("size_usdt",""),
            trade.get("confidence",""),
            trade.get("pnl",""),
            trade.get("status","open"),
            trade.get("exit_reason",""),
        ])
        return True
    except Exception:
        return False


def get_trades(sid: str = None) -> pd.DataFrame:
    ss = get_spreadsheet(sid)
    if not ss:
        return pd.DataFrame()
    try:
        ws = ensure_tab(ss, TAB_TRADES, ALL_TABS[TAB_TRADES])
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# BACKTEST RESULTS
# ─────────────────────────────────────────

def log_backtest(result: dict, sid: str = None) -> bool:
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws = ensure_tab(ss, TAB_BACKTEST, ALL_TABS[TAB_BACKTEST])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result.get("symbol",""),
            result.get("timeframe",""),
            result.get("initial_balance",""),
            result.get("final_balance",""),
            result.get("pnl_pct",""),
            result.get("win_rate",""),
            result.get("total_trades",""),
            result.get("profit_factor",""),
            result.get("max_drawdown_pct",""),
            result.get("sharpe_ratio",""),
        ])
        return True
    except Exception:
        return False


def get_backtests(sid: str = None) -> pd.DataFrame:
    ss = get_spreadsheet(sid)
    if not ss:
        return pd.DataFrame()
    try:
        ws = ensure_tab(ss, TAB_BACKTEST, ALL_TABS[TAB_BACKTEST])
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# EQUITY SNAPSHOTS
# ─────────────────────────────────────────

def log_equity(balance: float, pnl: float = 0, note: str = "", sid: str = None) -> bool:
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws = ensure_tab(ss, TAB_EQUITY, ALL_TABS[TAB_EQUITY])
        pnl_pct = (pnl / (balance - pnl) * 100) if (balance - pnl) != 0 else 0
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            round(balance, 2), round(pnl, 2), round(pnl_pct, 2), note
        ])
        return True
    except Exception:
        return False


def get_equity_curve(sid: str = None) -> pd.DataFrame:
    ss = get_spreadsheet(sid)
    if not ss:
        return pd.DataFrame()
    try:
        ws = ensure_tab(ss, TAB_EQUITY, ALL_TABS[TAB_EQUITY])
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────
# CHAT LOG
# ─────────────────────────────────────────

def log_chat(role: str, message: str, model: str = "", sid: str = None) -> bool:
    ss = get_spreadsheet(sid)
    if not ss:
        return False
    try:
        ws = ensure_tab(ss, TAB_CHAT, ALL_TABS[TAB_CHAT])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            role, message[:500], model
        ])
        return True
    except Exception:
        return False


# ─────────────────────────────────────────
# STATUS & UTILS
# ─────────────────────────────────────────

def is_sheets_available() -> bool:
    if not GSPREAD_AVAILABLE:
        return False
    return get_gsheet_client() is not None


def get_sheets_status() -> dict:
    client = get_gsheet_client()
    sid    = st.session_state.get("spreadsheet_id", "")
    ss_ok  = False
    tab_count = 0
    if client and sid:
        try:
            ss = client.open_by_key(sid)
            tab_count = len(ss.worksheets())
            ss_ok = True
        except Exception:
            pass
    return {
        "library_installed": GSPREAD_AVAILABLE,
        "authenticated":     client is not None,
        "spreadsheet_ok":    ss_ok,
        "spreadsheet_id":    sid,
        "tab_count":         tab_count,
    }


# Backwards compatibility aliases
def save_api_keys_to_sheet(sid, data):  return save_api_keys(data, sid)
def load_api_keys_from_sheet(sid):      return load_api_keys(sid)
def save_settings_to_sheet(sid, data):  return save_settings(data, sid)
def load_settings_from_sheet(sid):      return load_settings(sid)
def log_signal_to_sheet(sid, sig):      return log_signal(sig, sid=sid)
def log_trade_to_sheet(sid, trade):     return log_trade(trade, sid)
def get_trade_history(sid):             return get_trades(sid)
