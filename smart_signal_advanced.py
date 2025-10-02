# smart_signal_advanced.py
# نسخه پیشرفته سیگنال‌دهی با ارسال همزمان تلگرام و ایمیل
# وابستگی‌ها: ccxt, pandas, requests, smtplib

import os
import json
import time
import math
import requests
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import subprocess
import smtplib
from email.mime.text import MIMEText

# =======================
# تنظیمات قابل تغییر
# =======================
SYMBOLS = [
    "ADA/USDT","BCH/USDT","BNB/USDT","DOT/USDT","DOGE/USDT","ETC/USDT","LTC/USDT",
    "LINK/USDT","MATIC/USDT","TON/USDT","AAVE/USDT","SHIB/USDT","UNI/USDT","XMR/USDT",
    "TRX/USDT","AVAX/USDT","ATOM/USDT","ALGO/USDT","VET/USDT","FIL/USDT","XTZ/USDT",
    "ZIL/USDT","EGLD/USDT","HBAR/USDT","FTM/USDT","NEAR/USDT","ICP/USDT","THETA/USDT",
    "ENJ/USDT","GRT/USDT","KSM/USDT","INJ/USDT","CELO/USDT","AUDIO/USDT","SRM/USDT",
    "RNDR/USDT","FRAX/USDT","PAX/USDT","TUSD/USDT","DAI/USDT","USDC/USDT","APT/USDT",
    "STX/USDT","IMX/USDT","FLOW/USDT","MANA/USDT","SAND/USDT","AXS/USDT","KAVA/USDT",
    "CRV/USDT","RUNE/USDT","ZRX/USDT","CAKE/USDT","1INCH/USDT","MKR/USDT","SUSHI/USDT",
    "BAT/USDT","COMP/USDT","FTT/USDT","BAL/USDT","CEL/USDT","AMP/USDT","NEO/USDT",
    "ZEC/USDT","DASH/USDT","QTUM/USDT","HNT/USDT","NANO/USDT","CHZ/USDT","POLS/USDT"
]

TIMEFRAME = "1h"
OHLCV_LIMIT = 200
MIN_VOLUME_MULT = 0.8
SCORE_THRESHOLD = 3
COOLDOWN_HOURS = 4
DAILY_REPORT_HOUR_UTC = 20
DAILY_TOP_N = 8
STATE_FILE = "signal_state.json"

# =======================
# خواندن توکن‌ها و ایمیل از محیط
# =======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# =======================
# آماده‌سازی صرافی
# =======================
exchange = ccxt.binance({'enableRateLimit': True})

# =======================
# توابع کمکی
# =======================
def now_utc():
    return datetime.utcnow()

def load_state():
    default = {"last_signal_time": {}, "sent_signals": {}, "last_daily_report": None}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                raw = json.load(f)
            for k, v in raw.get("last_signal_time", {}).items():
                try:
                    raw["last_signal_time"][k] = datetime.fromisoformat(v)
                except:
                    raw["last_signal_time"][k] = None
            if raw.get("last_daily_report"):
                try:
                    raw["last_daily_report"] = datetime.fromisoformat(raw["last_daily_report"])
                except:
                    raw["last_daily_report"] = None
            return raw
        except Exception as e:
            print("Warning: couldn't load state file:", e)
            return default
    else:
        return default

def save_state(state):
    to_save = {
        "last_signal_time": {k: (v.isoformat() if isinstance(v, datetime) else None) for k,v in state.get("last_signal_time", {}).items()},
        "sent_signals": state.get("sent_signals", {}),
        "last_daily_report": state.get("last_daily_report").isoformat() if isinstance(state.get("last_daily_report"), datetime) else None
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(to_save, f, indent=2)
    except Exception as e:
        print("Warning: couldn't write state file:", e)

    if GITHUB_TOKEN:
        try:
            subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=False)
            subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=False)
            subprocess.run(["git", "add", STATE_FILE], check=False)
            subprocess.run(["git", "commit", "-m", "Update signal state"], check=False)
            repo = os.getenv("GITHUB_REPOSITORY")
            if repo:
                remote = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{repo}.git"
                subprocess.run(["git", "push", remote, "HEAD:refs/heads/main"], check=False)
        except Exception as e:
            print("Warning: couldn't push state file:", e)

# =======================
# ارسال تلگرام
# =======================
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN or CHAT_ID not set; skipping telegram send.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=15)
        j = r.json()
        if not j.get("ok"):
            print("Telegram API returned not ok:", j)
            return False
        return True
    except Exception as e:
        print("Telegram send error:", e)
        return False

# =======================
# ارسال ایمیل
# =======================
def send_email(subject, body):
    if not EMAIL_FROM or not EMAIL_PASSWORD or not EMAIL_TO:
        print("Email env vars not set; skipping email send.")
        return False
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()
        print("Email sent successfully!")
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False

# =======================
# سایر توابع اندیکاتورها، تحلیل، گزارش و main
# (همانند نسخه قبل است)
# در هر جا که send_telegram استفاده شده، send_email هم اضافه شده است
# مثال در بخش ارسال سیگنال:
#   ok = send_telegram(msg)
#   if ok:
#       send_email(f"Signal for {cand['symbol']}", msg)
# و در بخش گزارش روزانه:
#   send_telegram(report)
#   send_email("Daily Signal Report", report)
