"""
Email Alert System
Gmail SMTP use කරලා BUY/SELL alerts යවනවා
"""
import smtplib
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def get_email_config():
    try:
        return {
            "sender":   st.secrets["email"]["sender"],
            "password": st.secrets["email"]["app_password"],
            "receiver": st.secrets["email"]["receiver"],
        }
    except:
        return None

def send_alert_email(symbol, signal, price, confidence, notes=""):
    config = get_email_config()
    if not config:
        return False, "Email not configured in secrets"

    is_buy = "BUY" in signal.upper()
    color  = "#00FFA3" if is_buy else "#FF4466"
    emoji  = "🟢" if is_buy else "🔴"
    now    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <html><body style="font-family:monospace; background:#0A0E1A; color:#E2E8F0; padding:24px;">
      <div style="max-width:500px; margin:auto; background:#111827;
                  border:1px solid #1E2A3A; border-radius:12px; overflow:hidden;">
        <div style="background:linear-gradient(135deg,#00FFA3,#4488FF);
                    padding:4px;"></div>
        <div style="padding:24px;">
          <h2 style="color:{color}; margin:0 0 8px;">{emoji} {signal} SIGNAL</h2>
          <h1 style="color:#E2E8F0; margin:0 0 20px; font-size:2rem;">{symbol}</h1>
          <table style="width:100%; border-collapse:collapse;">
            <tr><td style="color:#64748B; padding:8px 0;">Price</td>
                <td style="color:#E2E8F0; text-align:right;">${price:,.4f}</td></tr>
            <tr><td style="color:#64748B; padding:8px 0;">Signal</td>
                <td style="color:{color}; text-align:right; font-weight:bold;">{signal}</td></tr>
            <tr><td style="color:#64748B; padding:8px 0;">Confidence</td>
                <td style="color:#FFD700; text-align:right;">{confidence}%</td></tr>
            <tr><td style="color:#64748B; padding:8px 0;">Time</td>
                <td style="color:#E2E8F0; text-align:right;">{now}</td></tr>
          </table>
          {"<p style='color:#94A3B8; margin-top:16px; font-size:0.85rem;'>"+notes+"</p>" if notes else ""}
          <p style="color:#1E2A3A; font-size:0.7rem; margin-top:24px;">
            CryptoAI Terminal · Not financial advice
          </p>
        </div>
      </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{emoji} CryptoAI: {signal} {symbol} @ ${price:,.2f}"
    msg["From"]    = config["sender"]
    msg["To"]      = config["receiver"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config["sender"], config["password"])
            server.sendmail(config["sender"], config["receiver"], msg.as_string())
        return True, "✅ Email sent!"
    except Exception as e:
        return False, f"❌ Email failed: {str(e)}"

def send_test_email():
    return send_alert_email(
        symbol="BTCUSDT", signal="🟢 BUY", price=65000.0,
        confidence=87.5, notes="This is a test alert from CryptoAI Terminal."
    )
