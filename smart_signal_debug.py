import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import ccxt
import pandas as pd

# ======================
# لیست 70 ارز (50 اصلی + 20 غیر معروف)
# ======================
cryptos = [
    # 50 ارز اصلی
    "SUI/USDT", "ADA/USDT", "LTC/USDT", "DOGE/USDT", "LINK/USDT",
    "DOT/USDT", "MATIC/USDT", "TON/USDT", "AAVE/USDT", "SHIB/USDT",
    "UNI/USDT", "XMR/USDT", "TRX/USDT", "ETC/USDT", "AVAX/USDT",
    "ATOM/USDT", "ALGO/USDT", "VET/USDT", "FIL/USDT", "XTZ/USDT",
    "ZIL/USDT", "EGLD/USDT", "HBAR/USDT", "FTM/USDT", "NEAR/USDT",
    "ICP/USDT", "THETA/USDT", "ENJ/USDT", "GRT/USDT", "KSM/USDT",
    "HGET/USDT", "INJ/USDT", "CELO/USDT", "AUDIO/USDT", "SRM/USDT",
    "RNDR/USDT", "FRAX/USDT", "PAX/USDT", "TUSD/USDT", "UST/USDT",
    "DAI/USDT", "USDC/USDT", "USDT/USDT", "APT/USDT", "STX/USDT",
    "IMX/USDT", "FLOW/USDT", "MANA/USDT", "SAND/USDT",
    # 20 ارز غیر معروف و با پتانسیل بالا
    "SUI/USDT", "TON/USDT", "FRAX/USDT", "RNDR/USDT", "CELO/USDT",
    "AUDIO/USDT", "SRM/USDT", "KSM/USDT", "HGET/USDT", "STX/USDT",
    "IMX/USDT", "FLOW/USDT", "GRT/USDT", "THETA/USDT", "EGLD/USDT",
    "ZIL/USDT", "ALGO/USDT", "cUSD/USDT", "HBAR/USDT", "NEAR/USDT"
]

# ======================
# تنظیمات تلگرام
# ======================
TELEGRAM_TOKEN = "توکن_تلگرام_تو"
CHAT_ID = "چت_آیدی_تو"

# ======================
# تنظیمات ایمیل
# ======================
EMAIL_FROM = "ایمیل_فرستنده"
EMAIL_PASSWORD = "رمز_ایمیل"
EMAIL_TO = "ایمیل_گیرنده"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ======================
# ارسال تلگرام
# ======================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
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
# تحلیل تکنیکال ساده (RSI و EMA) برای سیگنال
# ======================
def analyze_signal(symbol, limit=50):
    exchange = ccxt.binance()
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        latest = df.iloc[-1]
        price = latest['close']
        ema10 = latest['EMA10']
        ema50 = latest['EMA50']
        rsi = latest['RSI']

        # تصمیم‌گیری سیگنال
        if ema10 > ema50 and rsi < 70:
            action = "LONG 📈"
            stop_loss = price * 0.98
            take_profit = price * 1.04
        elif ema10 < ema50 and rsi > 30:
            action = "SHORT 📉"
            stop_loss = price * 1.02
            take_profit = price * 0.96
        else:
            return None

        return f"{symbol} | {action} | Price: {price:.2f} | Stop Loss: {stop_loss:.2f} | Take Profit: {take_profit:.2f} | RSI: {rsi:.2f}"
    except Exception as e:
        print("Error fetching", symbol, e)
        return None

# ======================
# حلقه اصلی
# ======================
def main():
    for symbol in cryptos:
        signal = analyze_signal(symbol)
        if signal:
            print(signal)  # برای Logs
            send_telegram(signal)
            send_email(f"Signal {symbol}", signal)
        time.sleep(1)

if __name__ == "__main__":
    main()
