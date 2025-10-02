# smart_signal_advanced.py
import os
import time
import requests
import ccxt
import pandas as pd
from datetime import datetime
import feedparser  # RSS feeds

# =======================
# Symbols to analyze
# =======================
SYMBOLS = [
    "ADA/USDT","BCH/USDT","BNB/USDT","DOT/USDT","DOGE/USDT","ETC/USDT","LTC/USDT",
    "LINK/USDT","MATIC/USDT","TON/USDT","AAVE/USDT","SHIB/USDT","UNI/USDT","XMR/USDT",
    "TRX/USDT","AVAX/USDT","ATOM/USDT","ALGO/USDT","VET/USDT","FIL/USDT","XTZ/USDT",
    "ZIL/USDT","EGLD/USDT","HBAR/USDT","FTM/USDT","NEAR/USDT","ICP/USDT","THETA/USDT",
    "ENJ/USDT","GRT/USDT","KSM/USDT","INJ/USDT","CELO/USDT","AUDIO/USDT","SRM/USDT",
    "RNDR/USDT","NEO/USDT","ZEC/USDT","DASH/USDT","QTUM/USDT","HNT/USDT","CHZ/USDT",
    "POLS/USDT","FLOW/USDT","MANA/USDT","SAND/USDT","AXS/USDT","KAVA/USDT","CRV/USDT",
    "RUNE/USDT","ZRX/USDT","CAKE/USDT","1INCH/USDT","MKR/USDT","SUSHI/USDT"
]

TIMEFRAME = "15m"
OHLCV_LIMIT = 200
SCORE_THRESHOLD = 3

# =======================
# Telegram credentials
# =======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =======================
# Exchanges setup
# =======================
EXCHANGES = []
for ex_name in ['binance', 'kraken', 'kucoin', 'gateio', 'bitfinex']:
    try:
        EXCHANGES.append(getattr(ccxt, ex_name)({'enableRateLimit': True}))
    except Exception as e:
        print(f"{ex_name} init error: {e}")

# =======================
# Telegram sender
# =======================
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN or CHAT_ID not set")
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text},
                          timeout=10)
        if not r.ok:
            print("Telegram send failed:", r.text)
    except Exception as e:
        print("Telegram error:", e)

# =======================
# Compute indicators
# =======================
def compute_indicators(df):
    df = df.copy()
    df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()

    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / (loss.rolling(14).mean().replace(0, 1e-9))
    df['RSI'] = 100 - (100 / (1 + rs))

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df

# =======================
# RSS / external signals
# =======================
RSS_FEEDS = [
    "https://cryptonews.com/news/feed", 
    "https://cointelegraph.com/rss",
    "https://news.bitcoin.com/feed/"
]

def fetch_external_signals(symbol):
    signals = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                if symbol.split('/')[0] in entry.title.upper():
                    signals.append(entry.title)
        except Exception as e:
            print(f"RSS fetch error from {feed_url}: {e}")
            continue
    return signals

# =======================
# Analyze a symbol
# =======================
def analyze(symbol):
    for exchange in EXCHANGES:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=OHLCV_LIMIT)
            if not ohlcv or len(ohlcv) < 20:
                continue
            df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
            df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
            df = compute_indicators(df)
            latest = df.iloc[-1]

            price = float(latest['close'])
            ema10, ema50, ema200 = latest['EMA10'], latest['EMA50'], latest['EMA200']
            rsi, macd, macd_signal = latest['RSI'], latest['MACD'], latest['MACD_signal']

            score, trend = 0, None
            if ema10 > ema50 > ema200: score += 1; trend = "LONG"
            elif ema10 < ema50 < ema200: score += 1; trend = "SHORT"
            if 40 <= rsi <= 60: score += 1
            if (macd > macd_signal and trend=="LONG") or (macd < macd_signal and trend=="SHORT"): score += 1

            external_signals = fetch_external_signals(symbol)
            if external_signals:
                score += 1

            if score < SCORE_THRESHOLD or trend is None:
                continue

            stop_loss = price * 0.99 if trend=="LONG" else price * 1.01
            take_profit = price * 1.02 if trend=="LONG" else price * 0.98

            return {"symbol": symbol, "score": score, "trend": trend,
                    "price": price, "sl": stop_loss, "tp": take_profit,
                    "external_signals": external_signals}
        except Exception as e:
            print(f"{symbol} on {exchange.id} error: {e}")
            continue
    return None

# =======================
# Main function
# =======================
def main():
    results = []
    for sym in SYMBOLS:
        res = analyze(sym)
        if res: results.append(res)
        time.sleep(0.8)

    results = sorted(results, key=lambda x:x["score"], reverse=True)[:2]
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    if results:
        for r in results:
            msg = (f"💹 {r['symbol']}\n"
                   f"📈 Action: {r['trend']}\n"
                   f"💰 Entry: {r['price']:.4f}\n"
                   f"⚠️ Stop Loss: {r['sl']:.4f}\n"
                   f"🏁 Take Profit: {r['tp']:.4f}\n"
                   f"⏰ {now} UTC")
            if r.get('external_signals'):
                msg += "\n📰 Related News: " + "; ".join(r['external_signals'])
            send_telegram(msg)
    else:
        send_telegram(f"⚠️ No reliable signal found at {now} UTC")

if __name__ == "__main__":
    main()
