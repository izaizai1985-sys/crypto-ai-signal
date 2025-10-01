import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import ccxt

# ======================
# لیست 50 ارز اصلی + 20 ارز غیر معروف
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
    # 20 ارز غیر معروف و با پتانسیل
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
# تابع ارسال پیام تلگرام
# ======================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ======================
# تابع ارسال ایمیل
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
# تابع تحلیل قیمت
# ======================
def analyze_price(symbol):
    exchange = ccxt.binance()
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker["last"]
        change = ticker["percentage"]  # درصد تغییر 24 ساعته
        if change >= 1:
            return f"💹 {symbol} افزایش {change:.2f}%"
        elif change <= -1:
            return f"📉 {symbol} کاهش {change:.2f}%"
        else:
            return None
    except Exception as e:
        print("Error fetching", symbol, e)
        return None

# ======================
# حلقه اصلی
# ======================
def main():
    for symbol in cryptos:
        signal = analyze_price(symbol)
        if signal:
            send_telegram(signal)
            send_email(f"Signal {symbol}", signal)
        time.sleep(1)  # فاصله کوتاه بین درخواست‌ها برای جلوگیری از محدودیت API

if __name__ == "__main__":
    main()
