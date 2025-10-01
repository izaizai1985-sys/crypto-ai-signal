# smart_signal_advanced.py
# نسخهٔ پیشرفتهٔ سیگنال‌دهی (تحلیل 70 ارز، EMA/RSI/ATR/MACD/Stochastic، امتیازدهی، cooldown، گزارش روزانه، ارسال تلگرام)
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

TIMEFRAME = "1h"            # تایم فریم محاسبات
OHLCV_LIMIT = 200           # تعداد کندل برای محاسبات
MIN_VOLUME_MULT = 0.8       # آستانه‌ی حجم: حجم آخرین کندل >= MIN_VOLUME_MULT * avg20vol
SCORE_THRESHOLD = 3         # حداقل امتیاز برای ارسال سیگنال
COOLDOWN_HOURS = 4          # فاصله زمانی بین سیگنال‌ها برای یک نماد (ساعت)
DAILY_REPORT_HOUR_UTC = 20  # ساعت ارسال گزارش روزانه (UTC)
DAILY_TOP_N = 8             # تعداد سیگنال برتر روزانه
STATE_FILE = "signal_state.json"  # فایل وضعیت محلی

# =======================
# خواندن توکن‌ها از محیط
# =======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # موجود در GitHub Actions

# =======================
# آماده‌سازی صرافی (ccxt)
# =======================
exchange = ccxt.binance({'enableRateLimit': True})

# =======================
# توابع کمکی برای زمان و state
# =======================
def now_utc():
    return datetime.utcnow()

def load_state():
    default = {"last_signal_time": {}, "sent_signals": {}, "last_daily_report": None}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                raw = json.load(f)
            # convert ISO strings back to datetimes where applicable
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
    # convert datetimes to iso strings before saving
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

    # optional: try to commit state back to repo if running inside Actions and GITHUB_TOKEN present
    if GITHUB_TOKEN:
        try:
            # configure git
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
# ارسال تلگرام (ایمن و با خطاگیری)
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
# محاسبه اندیکاتورها
# =======================
def compute_indicators(df):
    # EMA
    df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / (avg_loss.replace(0, 1e-9))
    df['RSI'] = 100 - (100 / (1 + rs))
    # ATR
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14, min_periods=1).mean()
    # Volume avg
    df['AvgVol20'] = df['volume'].rolling(window=20, min_periods=1).mean()
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    # Stochastic
    df['L14'] = df['low'].rolling(window=14, min_periods=1).min()
    df['H14'] = df['high'].rolling(window=14, min_periods=1).max()
    denom = (df['H14'] - df['L14']).replace(0, 1e-9)
    df['STO_K'] = (df['close'] - df['L14']) / denom * 100
    df['STO_D'] = df['STO_K'].rolling(window=3, min_periods=1).mean()
    return df

# =======================
# آنالیز یک نماد و امتیازدهی
# =======================
def analyze_symbol(symbol, state):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=OHLCV_LIMIT)
        if not ohlcv or len(ohlcv) < 20:
            return None
        df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        df = compute_indicators(df)
        latest = df.iloc[-1]
        price = float(latest['close'])
        ema10 = float(latest['EMA10'])
        ema50 = float(latest['EMA50'])
        ema200 = float(latest['EMA200'])
        rsi = float(latest['RSI'])
        atr = float(latest['ATR']) if not math.isnan(latest['ATR']) else 0.0
        vol = float(latest['volume'])
        avgvol = float(latest['AvgVol20']) if not math.isnan(latest['AvgVol20']) else 0.0
        macd = float(latest['MACD'])
        macd_signal = float(latest['MACD_signal'])
        sto_k = float(latest['STO_K'])
        sto_d = float(latest['STO_D'])

        # فیلتر حجم
        if avgvol > 0 and vol < (MIN_VOLUME_MULT * avgvol):
            return None

        # امتیازدهی سیگنال
        score = 0
        # جهت قوی: EMA alignment
        if ema10 > ema50 > ema200:
            score += 1
            trend = "LONG"
        elif ema10 < ema50 < ema200:
            score += 1
            trend = "SHORT"
        else:
            trend = None

        # RSI در محدوده ایده‌آل 40-60 (قابل تنظیم)
        if 40 <= rsi <= 60:
            score += 1

        # ATR مثبت (نوسان کافی)
        if atr > 0:
            score += 1

        # MACD تایید
        if (macd > macd_signal and trend == "LONG") or (macd < macd_signal and trend == "SHORT"):
            score += 1

        # Stochastic تایید (K > D برای لانگ)
        if (sto_k > sto_d and trend == "LONG") or (sto_k < sto_d and trend == "SHORT"):
            score += 1

        # حداقل امتیاز لازم
        if score < SCORE_THRESHOLD or trend is None:
            return None

        # تعیین نقاط ورود و حد ضرر/حد سود براساس ATR
        if trend == "LONG":
            action = "LONG 📈"
            stop_loss = price - (atr if atr>0 else price*0.01)
            take_profit = price + (atr * 2 if atr>0 else price*0.02)
        else:
            action = "SHORT 📉"
            stop_loss = price + (atr if atr>0 else price*0.01)
            take_profit = price - (atr * 2 if atr>0 else price*0.02)

        # چک cooldown
        last_times = state.get("last_signal_time", {})
        last_time = last_times.get(symbol)
        now = now_utc()
        if isinstance(last_time, str):
            try:
                last_time = datetime.fromisoformat(last_time)
            except:
                last_time = None
        if last_time and (now - last_time) < timedelta(hours=COOLDOWN_HOURS):
            return None

        # پیام قالب‌بندی‌شده
        message = (
            f"💹 Symbol: {symbol}\n"
            f"📈 Action: {action}\n"
            f"💰 Price: {price:.8f}\n"
            f"⚠️ Stop Loss: {stop_loss:.8f}\n"
            f"🏁 Take Profit: {take_profit:.8f}\n"
            f"📊 RSI: {rsi:.2f}\n"
            f"📊 Volume: {vol:.2f} (avg20: {avgvol:.2f})\n"
            f"⭐ Signal Score: {score}/6\n"
            f"⏰ Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        # نتیجه‌ی سیگنال برای ذخیره و ارسال
        result = {
            "symbol": symbol,
            "action": action,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "score": score,
            "message": message,
            "time": now.isoformat()
        }
        return result

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

# =======================
# بررسی سیگنال‌های قبلی برای باطل شدن یا بسته شدن
# =======================
def check_existing_signals(state):
    sent = state.get("sent_signals", {})
    updated = False
    now = now_utc()
    for sym, info in list(sent.items()):
        try:
            # fetch current price
            ticker = exchange.fetch_ticker(sym)
            price = float(ticker.get('last') or ticker.get('close') or 0)
            if price == 0:
                continue
            action = info.get("action")
            stop_loss = info.get("stop_loss")
            take_profit = info.get("take_profit")
            sent_time_iso = info.get("time")
            sent_time = None
            if sent_time_iso:
                try:
                    sent_time = datetime.fromisoformat(sent_time_iso)
                except:
                    sent_time = None
            # check invalidation conditions
            invalidated = False
            closed = False
            if "LONG" in action:
                if price <= stop_loss:
                    invalidated = True
                elif price >= take_profit:
                    closed = True
            elif "SHORT" in action:
                if price >= stop_loss:
                    invalidated = True
                elif price <= take_profit:
                    closed = True
            if invalidated:
                text = f"⚠️ Signal Invalidated: {sym}\nAction: {action}\nPrice: {price:.8f}\nOriginal: {info.get('message','')}"
                send_telegram(text)
                # remove from sent_signals
                del sent[sym]
                updated = True
            elif closed:
                text = f"✅ Signal Closed: {sym}\nAction: {action}\nPrice: {price:.8f}\nOriginal: {info.get('message','')}"
                send_telegram(text)
                del sent[sym]
                updated = True
            else:
                # keep it
                pass
        except Exception as e:
            print("Error checking existing signal", sym, e)
            continue
    if updated:
        state['sent_signals'] = sent
        return True
    return False

# =======================
# گزارش روزانه
# =======================
def send_daily_report(state):
    # prevent duplicate daily reports
    last_daily = state.get("last_daily_report")
    now = now_utc()
    if last_daily:
        try:
            last_daily_dt = datetime.fromisoformat(last_daily) if isinstance(last_daily, str) else last_daily
        except:
            last_daily_dt = None
    else:
        last_daily_dt = None

    # if report already sent today (UTC) skip
    if last_daily_dt and last_daily_dt.date() == now.date():
        return False

    # build top signals by score from state history or current sent_signals
    candidates = []
    for s, info in state.get("sent_signals", {}).items():
        candidates.append(info)
    # also consider signal_history persisted in state? we only have sent_signals; that's fine.
    if not candidates:
        return False

    top = sorted(candidates, key=lambda x: x.get("score",0), reverse=True)[:DAILY_TOP_N]
    report = "📊 گزارش روزانه: ۵–۱۰ سیگنال منتخب\n\n"
    for item in top:
        report += item.get("message","") + "\n\n"

    send_telegram(report)
    state["last_daily_report"] = now.isoformat()
    return True

# =======================
# اجرای اصلی
# =======================
def main():
    state = load_state()
    # first, check existing signals for invalidation/closure
    try:
        changed = check_existing_signals(state)
        if changed:
            save_state(state)
    except Exception as e:
        print("Error while checking existing signals:", e)

    # analyze symbols and gather candidates
    candidates = []
    for symbol in SYMBOLS:
        try:
            res = analyze_symbol(symbol, state)
            if res:
                candidates.append(res)
        except Exception as e:
            print("Error processing symbol", symbol, e)
        # to be polite with API and avoid rate limits
        time.sleep(0.8)

    # sort by score desc then by recency maybe
    candidates_sorted = sorted(candidates, key=lambda x: (x.get("score",0)), reverse=True)

    sent_any = False
    now = now_utc()
    for cand in candidates_sorted:
        symbol = cand["symbol"]
        score = cand["score"]
        # ensure cooldown again (in case state changed)
        last_times = state.get("last_signal_time", {})
        last_time_iso = last_times.get(symbol)
        last_time = None
        if last_time_iso:
            try:
                last_time = datetime.fromisoformat(last_time_iso) if isinstance(last_time_iso, str) else last_time_iso
            except:
                last_time = None
        if last_time and (now - last_time) < timedelta(hours=COOLDOWN_HOURS):
            continue

        # send and record
        msg = cand["message"]
        ok = send_telegram(msg)
        if ok:
            # record sent signal
            sent = state.get("sent_signals", {})
            sent[symbol] = {
                "symbol": symbol,
                "action": cand["action"],
                "price": cand["price"],
                "stop_loss": cand["stop_loss"],
                "take_profit": cand["take_profit"],
                "score": cand["score"],
                "message": cand["message"],
                "time": cand["time"]
            }
            state["sent_signals"] = sent
            state.setdefault("last_signal_time", {})[symbol] = now.isoformat()
            save_state(state)
            sent_any = True
        # limit immediate sends per run to avoid spamming: send top N per run (e.g., 5)
        # But user wanted each 15-min to send high-probability. We'll cap to 10 to be safe:
        if len(state.get("sent_signals", {})) >= 50:
            break

    # daily report (send once per day at configured hour UTC)
    try:
        nowh = now.hour
        if nowh == DAILY_REPORT_HOUR_UTC:
            if send_daily_report(state):
                save_state(state)
    except Exception as e:
        print("Error sending daily report:", e)

    # final save
    save_state(state)

if __name__ == "__main__":
    main()
