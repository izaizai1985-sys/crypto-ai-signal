import os, requests, json
from statistics import mean

# تنظیمات ربات
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PAIRS = ["bitcoin","ethereum","arbitrum"]  # ارزهای موردنظر
THRESHOLD = 0.6  # حداقل نمره برای ارسال سیگنال

# تابع ارسال پیام به تلگرام
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode":"Markdown"})

# گرفتن قیمت‌ها از CoinGecko
def fetch_prices(pair):
    url = f"https://api.coingecko.com/api/v3/coins/{pair}/market_chart?vs_currency=usd&days=1"
    r = requests.get(url).json()
    return [p[1] for p in r.get("prices",[])]

# تحلیل ساده momentum
def analyze_pair(pair):
    prices = fetch_prices(pair)
    if len(prices)<10: return None
    last = prices[-1]
    avg = mean(prices[-20:]) if len(prices)>=20 else mean(prices)
    momentum = (last - avg)/avg
    if momentum>0.01:
        return {"side":"LONG","score":0.7,"entry":f"{last:.2f}","sl":f"{last*0.97:.2f}","tp":f"{last*1.03:.2f}","reason":"momentum positive"}
    else:
        return {"side":"NONE","score":0.2,"entry":str(last),"sl":str(last),"tp":str(last),"reason":"no momentum"}

# اجرای اصلی ربات
def main():
    for p in PAIRS:
        res = analyze_pair(p)
        if not res: continue
        if res.get("side")!="NONE" and float(res.get("score",0))>=THRESHOLD:
            text = f"*AI Signal*\nPair: {p}\nSide: {res['side']}\nEntry: {res['entry']}\nSL: {res['sl']}\nTP: {res['tp']}\nReason: {res['reason']}"
            send_telegram(text)

if __name__=="__main__":
    main()
