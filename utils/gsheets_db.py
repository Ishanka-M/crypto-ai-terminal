"""
Google Sheets Database Manager
Sheets auto-create වෙනවා — Trades, Alerts, Stats
"""
import streamlit as st
import requests
import json
from datetime import datetime

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_config():
    try:
        return {
            "spreadsheet_id": st.secrets["gsheets"]["spreadsheet_id"],
            "service_account": st.secrets["gsheets"]["service_account_json"],
        }
    except:
        return None

def get_access_token(service_account_json: str) -> str:
    """Get OAuth2 access token from service account"""
    import time, base64, hashlib, hmac
    try:
        sa = json.loads(service_account_json) if isinstance(service_account_json, str) else service_account_json
        import jwt as pyjwt  # PyJWT
        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/spreadsheets",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        private_key = sa["private_key"]
        token = pyjwt.encode(payload, private_key, algorithm="RS256")
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": token,
        }, timeout=10)
        return r.json().get("access_token", "")
    except Exception as e:
        return ""

@st.cache_resource(ttl=3000)
def get_token_cached(sa_json_str: str) -> str:
    return get_access_token(sa_json_str)

def sheets_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

BASE = "https://sheets.googleapis.com/v4/spreadsheets"

# ── Sheet Setup ───────────────────────────────────────────────────────────────

SHEET_CONFIGS = {
    "Trades": {
        "headers": ["ID","Symbol","Signal","Entry Price","Exit Price","Stop Loss",
                    "Take Profit","PnL %","Result","Status","Confidence",
                    "Exit Reason","Notes","Opened At","Closed At"],
        "tab_color": {"red":0.0,"green":1.0,"blue":0.6},
    },
    "Alerts": {
        "headers": ["ID","Symbol","Alert Type","Message","Price","Sent At"],
        "tab_color": {"red":0.27,"green":0.53,"blue":1.0},
    },
    "Stats": {
        "headers": ["Metric","Value","Updated At"],
        "tab_color": {"red":1.0,"green":0.85,"blue":0.0},
    },
}

def ensure_sheets(spreadsheet_id: str, token: str) -> dict:
    """Create missing sheets and add headers automatically"""
    r = requests.get(f"{BASE}/{spreadsheet_id}", headers=sheets_headers(token), timeout=10)
    if r.status_code != 200:
        return {"error": r.text}

    existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                for s in r.json().get("sheets", [])}

    requests_body = []
    new_sheets = {}

    for name, cfg in SHEET_CONFIGS.items():
        if name not in existing:
            requests_body.append({
                "addSheet": {
                    "properties": {
                        "title": name,
                        "tabColor": cfg["tab_color"],
                        "gridProperties": {"rowCount": 1000, "columnCount": len(cfg["headers"])},
                    }
                }
            })
            new_sheets[name] = cfg["headers"]

    if requests_body:
        r2 = requests.post(
            f"{BASE}/{spreadsheet_id}:batchUpdate",
            json={"requests": requests_body},
            headers=sheets_headers(token), timeout=15
        )
        if r2.status_code == 200:
            replies = r2.json().get("replies", [])
            for i, name in enumerate(new_sheets.keys()):
                sid = replies[i].get("addSheet", {}).get("properties", {}).get("sheetId")
                if sid:
                    existing[name] = sid

    # Write headers for new sheets
    header_data = []
    for name, headers in new_sheets.items():
        header_data.append({
            "range": f"{name}!A1:{chr(64+len(headers))}1",
            "values": [headers],
        })

    if header_data:
        requests.post(
            f"{BASE}/{spreadsheet_id}/values:batchUpdate",
            json={"valueInputOption": "RAW", "data": header_data},
            headers=sheets_headers(token), timeout=15
        )

        # Bold + freeze headers
        fmt_requests = []
        for name, cfg in SHEET_CONFIGS.items():
            if name in new_sheets and name in existing:
                sid = existing[name]
                fmt_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {
                            "backgroundColor": {"red":0.067,"green":0.086,"blue":0.102},
                            "textFormat": {"bold": True, "foregroundColor": {"red":0.0,"green":1.0,"blue":0.64}},
                        }},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                })
                fmt_requests.append({
                    "updateSheetProperties": {
                        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount"
                    }
                })
        if fmt_requests:
            requests.post(
                f"{BASE}/{spreadsheet_id}:batchUpdate",
                json={"requests": fmt_requests},
                headers=sheets_headers(token), timeout=15
            )

    return existing

def get_next_id(spreadsheet_id: str, token: str, sheet: str) -> int:
    r = requests.get(
        f"{BASE}/{spreadsheet_id}/values/{sheet}!A:A",
        headers=sheets_headers(token), timeout=10
    )
    if r.status_code != 200:
        return 1
    values = r.json().get("values", [])
    if len(values) <= 1:
        return 1
    try:
        ids = [int(v[0]) for v in values[1:] if v and v[0].isdigit()]
        return max(ids) + 1 if ids else 1
    except:
        return len(values)

def append_row(spreadsheet_id: str, token: str, sheet: str, row: list):
    r = requests.post(
        f"{BASE}/{spreadsheet_id}/values/{sheet}!A1:append",
        params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
        json={"values": [row]},
        headers=sheets_headers(token), timeout=10
    )
    return r.status_code == 200

def get_all_rows(spreadsheet_id: str, token: str, sheet: str) -> list:
    r = requests.get(
        f"{BASE}/{spreadsheet_id}/values/{sheet}",
        headers=sheets_headers(token), timeout=10
    )
    if r.status_code != 200:
        return []
    data = r.json().get("values", [])
    if len(data) <= 1:
        return []
    headers = data[0]
    return [dict(zip(headers, row + [""]*(len(headers)-len(row)))) for row in data[1:]]

def update_row(spreadsheet_id: str, token: str, sheet: str,
               row_index: int, row: list):
    """row_index is 1-based (row 2 = first data row)"""
    r = requests.put(
        f"{BASE}/{spreadsheet_id}/values/{sheet}!A{row_index}",
        params={"valueInputOption": "USER_ENTERED"},
        json={"values": [row]},
        headers=sheets_headers(token), timeout=10
    )
    return r.status_code == 200


# ── Public API ────────────────────────────────────────────────────────────────

def _setup():
    cfg = get_config()
    if not cfg:
        return None, None, None
    token = get_token_cached(cfg["service_account"] if isinstance(cfg["service_account"], str)
                             else json.dumps(cfg["service_account"]))
    if not token:
        return None, None, None
    sid = cfg["spreadsheet_id"]
    ensure_sheets(sid, token)
    return sid, token, cfg

def save_trade(symbol, signal, entry_price, confidence,
               stop_loss=None, take_profit=None, notes=""):
    sid, token, _ = _setup()
    if not sid:
        return {"error": "Google Sheets not configured"}
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    trade_id = get_next_id(sid, token, "Trades")
    row = [trade_id, symbol, signal, entry_price, "", stop_loss or "",
           take_profit or "", "", "", "OPEN", confidence, "", notes, now, ""]
    ok = append_row(sid, token, "Trades", row)
    return {"id": trade_id, "ok": ok}

def close_trade(trade_id: int, exit_price: float, exit_reason: str = "Manual"):
    sid, token, _ = _setup()
    if not sid:
        return {"error": "Not configured"}
    rows = get_all_rows(sid, token, "Trades")
    for i, row in enumerate(rows):
        if str(row.get("ID","")) == str(trade_id):
            entry = float(row.get("Entry Price", 0) or 0)
            signal = row.get("Signal", "BUY")
            if "BUY" in signal:
                pnl = round(((exit_price - entry) / entry) * 100, 2) if entry else 0
            else:
                pnl = round(((entry - exit_price) / entry) * 100, 2) if entry else 0
            result = "WIN" if pnl > 0 else "LOSS"
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            updated = [trade_id, row.get("Symbol",""), row.get("Signal",""),
                       entry, exit_price, row.get("Stop Loss",""),
                       row.get("Take Profit",""), pnl, result, "CLOSED",
                       row.get("Confidence",""), exit_reason,
                       row.get("Notes",""), row.get("Opened At",""), now]
            update_row(sid, token, "Trades", i + 2, updated)
            return {"pnl_pct": pnl, "result": result}
    return {"error": "Trade not found"}

def get_trades(status=None, limit=50):
    sid, token, _ = _setup()
    if not sid: return []
    rows = get_all_rows(sid, token, "Trades")
    if status:
        rows = [r for r in rows if r.get("Status","") == status]
    return rows[-limit:][::-1]

def get_trade_stats():
    sid, token, _ = _setup()
    if not sid:
        return {"total":0,"wins":0,"losses":0,"open":0,"win_rate":0,"avg_pnl":0,"total_pnl":0}
    rows = get_all_rows(sid, token, "Trades")
    closed = [r for r in rows if r.get("Status","") == "CLOSED"]
    open_t = [r for r in rows if r.get("Status","") == "OPEN"]
    wins   = [r for r in closed if r.get("Result","") == "WIN"]
    pnls   = []
    for r in closed:
        try: pnls.append(float(r.get("PnL %", 0) or 0))
        except: pass
    return {
        "total":    len(closed),
        "wins":     len(wins),
        "losses":   len(closed) - len(wins),
        "open":     len(open_t),
        "win_rate": round(len(wins)/len(closed)*100, 1) if closed else 0,
        "avg_pnl":  round(sum(pnls)/len(pnls), 2) if pnls else 0,
        "total_pnl":round(sum(pnls), 2),
    }

def save_alert(symbol, alert_type, message, price):
    sid, token, _ = _setup()
    if not sid: return {"error": "Not configured"}
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    alert_id = get_next_id(sid, token, "Alerts")
    row = [alert_id, symbol, alert_type, message, price, now]
    append_row(sid, token, "Alerts", row)
    return {"id": alert_id}

def get_alerts(limit=20):
    sid, token, _ = _setup()
    if not sid: return []
    rows = get_all_rows(sid, token, "Alerts")
    return rows[-limit:][::-1]

def update_stats_sheet():
    """Stats sheet refresh"""
    sid, token, _ = _setup()
    if not sid: return
    stats = get_trade_stats()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        ["Total Closed Trades", stats["total"], now],
        ["Open Trades",         stats["open"],  now],
        ["Wins",                stats["wins"],  now],
        ["Losses",              stats["losses"],now],
        ["Win Rate %",          stats["win_rate"], now],
        ["Avg PnL %",           stats["avg_pnl"],  now],
        ["Total PnL %",         stats["total_pnl"],now],
    ]
    requests.put(
        f"{BASE}/{sid}/values/Stats!A2:C{len(rows)+1}",
        params={"valueInputOption": "USER_ENTERED"},
        json={"values": rows},
        headers=sheets_headers(token), timeout=10
    )

def is_configured() -> bool:
    return get_config() is not None

SETUP_GUIDE = """
**Google Sheets Setup — Step by Step**

1. [console.cloud.google.com](https://console.cloud.google.com) → New Project
2. APIs & Services → Enable **Google Sheets API**
3. IAM & Admin → Service Accounts → Create → Download JSON key
4. [sheets.google.com](https://sheets.google.com) → New spreadsheet create කරන්න
5. Sheet URL එකෙන් ID copy කරන්න:
   `https://docs.google.com/spreadsheets/d/**SPREADSHEET_ID**/edit`
6. Spreadsheet → Share → Service account email paste කරලා **Editor** access දෙන්න
7. Streamlit Secrets:

```toml
[gsheets]
spreadsheet_id = "your_sheet_id_here"
service_account_json = '''
{paste entire service account JSON here}
'''
```

App open කළාම **Trades, Alerts, Stats** sheets auto-create වෙනවා! 🚀
"""
