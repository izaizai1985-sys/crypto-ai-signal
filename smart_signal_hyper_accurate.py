# =======================
# Install libraries (if needed in Colab)
# =======================
# !pip install ccxt feedparser scikit-learn --quiet

# =======================
# Imports
# =======================
import time
import traceback
import json
from datetime import datetime, timedelta
import requests
import ccxt
import pandas as pd
import feedparser
import numpy as np
from scipy.stats import linregress
from sklearn.preprocessing import StandardScaler

# =======================
# Load Telegram config
# =======================
with open('telegram_config.json', 'r') as f:
    config = json.load(f)

BOT_TOKEN = config['BOT_TOKEN']
CHAT_ID = config['CHAT_ID']

def send_telegram(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except:
        pass

# =======================
# Symbols and parameters
# =======================
SYMBOLS = [
    "ADA/USDT","BCH/USDT","DOT/USDT","DOGE/USDT","ETC/USDT","LTC/USDT",
    "LINK/USDT","MATIC/USDT","TON/USDT","AAVE/USDT","SHIB/USDT","UNI/USDT",
    "XMR/USDT","TRX/USDT","AVAX/USDT","ATOM/USDT","ALGO/USDT","VET/USDT",
    "FIL/USDT","XTZ/USDT","ZIL/USDT","EGLD/USDT","HBAR/USDT","FTM/USDT",
    "NEAR/USDT","ICP/USDT","THETA/USDT","ENJ/USDT","GRT/USDT","KSM/USDT",
    "INJ/USDT","CELO/USDT","AUDIO/USDT","SRM/USDT","RNDR/USDT","NEO/USDT",
    "ZEC/USDT","DASH/USDT","QTUM/USDT","HNT/USDT","CHZ/USDT","POLS/USDT",
    "FLOW/USDT","MANA/USDT","SAND/USDT","AXS/USDT","KAVA/USDT","CRV/USDT",
    "RUNE/USDT","ZRX/USDT","CAKE/USDT","1INCH/USDT","MKR/USDT","SUSHI/USDT",
    "ALPHA/USDT","BNT/USDT","BAT/USDT","CVC/USDT","DGB/USDT","FET/USDT",
    "HOT/USDT","IOST/USDT","KNC/USDT","LRC/USDT","MTL/USDT","NANO/USDT",
    "NKN/USDT","OCEAN/USDT","ONG/USDT","ONT/USDT","REN/USDT","REP/USDT",
    "SC/USDT","SKL/USDT","SNX/USDT","STORJ/USDT","STMX/USDT","STX/USDT",
    "STRAX/USDT","TOMO/USDT","TROY/USDT","UMA/USDT","VTHO/USDT","WAVES/USDT",
    "WAXP/USDT","XEM/USDT","XLM/USDT","XVG/USDT","YFI/USDT","GNO/USDT",
    "CELR/USDT","CHR/USDT","COMP/USDT","CTSI/USDT","DENT/USDT","DODO/USDT",
    "ERD/USDT","FIO/USDT","GLM/USDT","ANKR/USDT","BAL/USDT","BAND/USDT",
    "BZRX/USDT","CKB/USDT","COTI/USDT","DAO/USDT","DUSK/USDT","FARM/USDT",
    "FIS/USDT","GTC/USDT","JST/USDT","KEEP/USDT","LIT/USDT","LPT/USDT","LINA/USDT",
    # 10 new high-volatility coins not in previous list
    "SOL/USDT","BNB/USDT","LUNA/USDT","FTM/USDT","NEAR/USDT",
    "AVAX/USDT","SAND/USDT","MANA/USDT","THOR/USDT","CELO/USDT"
]

TIMEFRAME = "5m"
OHLCV_LIMIT = 300
ATR_PERIOD = 14
INTERVAL = 15*60
RETRY_INTERVAL = 60
RUN_DURATION_HOURS = 6

# =======================
# Exchanges setup
# =======================
EXCHANGES = []
for ex_name in ['binance','kraken','kucoin','gateio','bitfinex','okx','huobi','bitstamp',
                'poloniex','bittrex','ftx','bitmart','digifinex','whitebit','bybit','bitget']:
    try:
        EXCHANGES.append(getattr(ccxt, ex_name)({'enableRateLimit': True}))
    except:
        continue

# =======================
# Indicators
# =======================
def compute_indicators(df):
    df = df.copy()
    df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / (loss.rolling(14).mean().replace(0,1e-9))
    df['RSI'] = 100 - (100 / (1 + rs))
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L','H-PC','L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(ATR_PERIOD).mean().fillna(0)
    df['VOL_AVG'] = df['volume'].rolling(20).mean()
    df['VOL_HIGH'] = df['volume'] > df['VOL_AVG']*1.5
    df['ROC'] = df['close'].pct_change(periods=9)*100
    df['EMA_CROSS'] = np.where(df['EMA10']>df['EMA50'],1,-1)
    df['BOLL_BREAK'] = np.where(df['close']>df['close'].rolling(20).mean()+2*df['close'].rolling(20).std(),
                                1,
                                np.where(df['close']<df['close'].rolling(20).mean()-2*df['close'].rolling(20).std(),-1,0))
    df['MOMENTUM'] = df['close'].diff(5)
    df['LINEAR_REG_SLOPE'] = df['close'].rolling(14).apply(lambda x: linregress(range(len(x)), x)[0])
    df['TREND_STRENGTH'] = df['EMA_CROSS'] + df['BOLL_BREAK'] + np.where(df['RSI']>50,1,-1)
    features = ['EMA10','EMA50','EMA200','RSI','ATR','VOL_AVG','ROC','MOMENTUM','LINEAR_REG_SLOPE']
    df_scaled = StandardScaler().fit_transform(df.fillna(0)[features])
    df['ML_SCORE'] = np.mean(df_scaled, axis=1)
    return df

# =======================
# Run signals
# =======================
def run_signals(duration_hours=RUN_DURATION_HOURS):
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=duration_hours)
    send_telegram(f"✅ Signal script started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    while datetime.now() < end_time:
        try:
            all_signals = []
            for symbol in SYMBOLS:
                ohlcv = None
                for ex in EXCHANGES:
                    try:
                        ohlcv = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=OHLCV_LIMIT)
                        if ohlcv: break
                    except: continue
                if not ohlcv: continue
                df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = compute_indicators(df)
                last_row = df.iloc[-1]
                all_signals.append({
                    "symbol": symbol,
                    "signal": "LONG" if last_row['EMA_C
