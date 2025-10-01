import os
import requests
import smtplib
from email.mime.text import MIMEText
import pandas as pd
import numpy as np
import ccxt
import traceback

# =====================
# تنظیمات تلگرام
# =====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": message}
        r = requests.get(url, params=params)
        r.raise_for_status()
        print("پیام تلگرام ارسال شد ✅")
    except Exception as e:
        print("خطا در ارسال تلگرام:", e)
        traceback.print_exc()

# =====================
# تنظیمات ایمیل
# =====================
FROM_EMAIL = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("EMAIL_TO")

def send_email(subject, body, to_email):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(FROM_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            print("ایمیل ارسال شد ✅")
    except Exception as e:
        print("خطا در ارسال ایمیل:", e)
        traceback.print_exc()

# =====================
# محاسبه اندیکاتورها
# =====================
def calculate_indicators(df):
    df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=14).mean()
    avg_loss = pd.Series(loss).rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# =====================
# بررسی سیگنال
# =====================
def check_signal(df):
    latest = df.iloc[-1]
    if latest['MACD'] > latest['Signal'] and latest['RSI'] < 30:
        return "خرید"
    elif latest['MACD'] < latest['Signal'] and latest['RSI'] > 70:
        return "فروش"
    else:
        return None

# =====================
# لیست ارزها و صرافی
# =====================
cryptos = ["BTC/USDT"]  # فقط یک ارز برای تست
exchange = ccxt.binance()

# =====================
# اجرای ربات
# =====================
for symbol in cryptos:
    try:
        print(f"در حال پردازش {symbol} ...")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df = calculate_indicators(df)
        signal = check_signal(df)
        if signal:
            message = f"🚀 سیگنال قوی: {symbol} - {signal}"
            send_telegram(message)
            send_email(f"سیگنال {symbol}", message, TO_EMAIL)
        else:
            print(f"سیگنال برای {symbol} وجود ندارد")
    except Exception as e:
        print(f"خطا برای {symbol}: {e}")
        traceback.print_exc()
