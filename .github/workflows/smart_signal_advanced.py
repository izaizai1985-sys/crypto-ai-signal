import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import ccxt
import pandas as pd
import os
from datetime import datetime, timedelta

# ======================
# لیست 70 ارز
# ======================
cryptos = [
    "ADA/USDT", "BCH/USDT", "BNB/USDT", "BTC/USDT", "DOT/USDT", "DOGE/USDT", "EOS/USDT", 
    "ETC/USDT", "ETH/USDT", "FIL/USDT", "LINK/USDT", "LTC/USDT", "MATIC/USDT", "NEAR/USDT",
    "SOL/USDT", "TRX/USDT", "XLM/USDT", "XMR/USDT", "XRP/USDT", "ZEC/USDT",
    # ادامه 50 ارز دیگر...
]

# ======================
# تنظیمات تلگرام
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ======================
# تنظیمات ایمیل
# ======================
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ======================
# حافظه آخرین سیگنال برای هر ارز
# ======================
last_signal_time = {}
signal_history = {}

# ======================
# ارسال تلگرام
# ======================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ======================
# ارسال ایمیل
# ======================
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email Error:", e)

# ======================
# تحلیل سیگنال و محاسبه Signal Score
# ======================
def analyze_signal(symbol, limit=50):
    exchange = ccxt.binance()
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # EMA
        df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()

        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # ATR
        df['TR'] = df['high'] - df['low']
        df['ATR'] = df['TR'].rolling(window=14).mean()

        # Volume
        df['AvgVol20'] = df['volume'].rolling(window=20).mean()

        # MACD
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['SignalLine'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # Stochastic
        df['L14'] = df['low'].rolling(window=14).min()
        df['H14'] = df['high'].rolling(window=14).max()
        df['%K'] = (df['close'] - df['L14']) / (df['H14'] - df['L14']) * 100
        df['%D'] = df['%K'].rolling(window=3).mean()

        latest = df.iloc[-1]
        price = latest['close']
        ema10, ema50, ema200 = latest['EMA10'], latest['EMA50'], latest['EMA200']
        rsi, volume, avgvol = latest['RSI'], latest['volume'], latest['AvgVol20']
        atr = latest['ATR']
        macd, signal_line = latest['MACD'], latest['SignalLine']
        stochastic_k, stochastic_d = latest['%K'], latest['%D']

        # اعتبار حجم
        if volume < avgvol:
            return None

        # Signal Score
        score = 0
        if ema10 > ema50 > ema200 or ema10 < ema50 < ema200:
            score += 1
        if 40 <= rsi <= 60:
            score += 1
        if atr > 0:
            score += 1
        if (macd > signal_line and ema10 > ema50) or (macd < signal_line and ema10 < ema50):
            score += 1
        if stochastic_k > stochastic_d:
            score += 1

        if score < 3:
            return None

        # تصمیم‌گیری سیگنال
        if ema10 > ema50 > ema200:
            action = "LONG 📈"
            stop_loss = price - atr
            take_profit = price + atr * 2
        else:
            action = "SHORT 📉"
            stop_loss = price + atr
            take_profit = price - atr * 2

        # فاصله زمانی (15 دقیقه)
        now = datetime.utcnow()
        if symbol in last_signal_time and now - last_signal_time[symbol] < timedelta(minutes=15):
            return None
        last_signal_time[symbol] = now

        message = (
            f"💹 Symbol: {symbol}\n"
            f"📈 Action: {action}\n"
            f"💰 Price: {price:.2f}\n"
            f"⚠️ Stop Loss: {stop_loss:.2f}\n"
            f"🏁 Take Profit: {take_profit:.2f}\n"
            f"📊 RSI: {rsi:.2f}\n"
            f"📊 Volume: {volume:.2f}\n"
            f"⭐ Signal Score: {score}/5\n"
            f"⏰ Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        # ذخیره برای گزارش روزانه
        signal_history[symbol] = {'score': score, 'message': message, 'time': now}

        return message

    except Exception as e:
        print("Error fetching", symbol, e)
        return None

# ======================
# حلقه اصلی
# ======================
def main():
    send_telegram("✅ بات سیگنال پیشرفته آماده به کار است")

    for symbol in cryptos:
        signal = analyze_signal(symbol)
        if signal:
            print(signal)
            send_telegram(signal)
            send_email(f"Signal {symbol}", signal)
        time.sleep(1)

# ======================
# گزارش روزانه 5-10 سیگنال برتر
# ======================
def daily_report():
    now = datetime.utcnow()
    top_signals = sorted(signal_history.values(), key=lambda x: x['score'], reverse=True)[:10]
    report = "📊 گزارش روزانه بهترین سیگنال‌ها:\n\n"
    for s in top_signals:
        report += s['message'] + "\n\n"
    send_telegram(report)
    send_email("Daily Top Signals", report)

if __name__ == "__main__":
    main()
