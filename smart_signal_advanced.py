# smart_signal_advanced.py
# نسخهٔ پیشرفتهٔ سیگنال‌دهی با محدودیت ارسال ۲ سیگنال در هر run
# وابستگی‌ها: ccxt, pandas, requests

import os
import json
import time
import math
import requests
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import subprocess

# =======================
# تنظیمات
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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
        except:
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
        print("Couldn't write state file:", e)
    # optional commit
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
        except:
            pass

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=15)
        return r.json().get("ok", False)
    except:
        return False

# =======================
# محاسبه اندیکاتورها
# =======================
def compute_indicators(df):
    df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14,min_periods=1).mean()
    avg_loss = loss.rolling(14,min_periods=1).mean()
    rs = avg_gain / (avg_loss.replace(0,1e-9))
    df['RSI'] = 100 - (100 / (1+rs))
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1,tr2,tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14,min_periods=1).mean()
    df['AvgVol20'] = df['volume'].rolling(20,min_periods=1).mean()
    ema12 = df['close'].ewm(span=12,adjust=False).mean()
    ema26 = df['close'].ewm(span=26,adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9,adjust=False).mean()
    df['L14'] = df['low'].rolling(14,min_periods=1).min()
    df['H14'] = df['high'].rolling(14,min_periods=1).max()
    denom = (df['H14']-df['L14']).replace(0,1e-9)
    df['STO_K'] = (df['close']-df['L14'])/denom*100
    df['STO_D'] = df['STO_K'].rolling(3,min_periods=1).mean()
    return df

# =======================
# تحلیل هر نماد
# =======================
def analyze_symbol(symbol, state):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=OHLCV_LIMIT)
        if not ohlcv or len(ohlcv)<20: return None
        df = pd.DataFrame(ohlcv,columns=['ts','open','high','low','close','volume'])
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        df = compute_indicators(df)
        latest = df.iloc[-1]
        price = latest['close']
        ema10 = latest['EMA10']
        ema50 = latest['EMA50']
        ema200 = latest['EMA200']
        rsi = latest['RSI']
        atr = latest['ATR'] if not math.isnan(latest['ATR']) else 0
