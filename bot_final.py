import asyncio
import os
import logging
import requests
import random
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.ext import Application, CommandHandler
from flask import Flask
from threading import Thread

# --- إعداد السيرفر للبقاء حياً على Render ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Shatha Trading Bot is Online!"

def run_flask(): app_flask.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- إعدادات البوت واللوجر ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RIYADH_TZ = pytz.timezone('Asia/Riyadh')

# --- إعدادات الحساب (كما هي في ملفك) ---
ACCOUNT = {
    "balance": 100000.0,
    "max_drawdown": 10.0,
    "daily_drawdown": 5.0,
    "drawdown_used": 0.0,
    "daily_used": 0.0,
    "trades_week": 0,
    "pnl_percent": 0.0,
}

SYMBOLS = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "BTCUSD": "BTC-USD",
    "USDCHF": "USDCHF=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X"
}

HIGH_IMPACT_KEYWORDS = ["Fed", "Federal Reserve", "CPI", "NFP", "Non-Farm", "FOMC", "Interest Rate", "GDP", "Powell", "ECB", "BOE", "BOJ"]

# --- رسائل باللهجة السعودية (نفس نصوصك تماماً) ---
WAITING_MSGS = ["جالس أفحص الأسواق لك.. لحظة صبر يا بطلة", "عيني على الشارت، لحظة وأخبرك ..", "البحث مستمر، السوق مو دايم يعطي فرص، بس أنا صاحي", "فاحص كل زوج بعين.. لا شي يفوتني"]
NO_SETUP_MSGS = ["ما لقيت سيتاب يستاهل الحين.", "ديري عمرك بشغلة ثانية وأنا أراقب لك", "السوق هادي الحين ما في فرصة تستاهل روحي اتقهوي وأنا هنا", "فحصت كل شيء ما في سيتاب بشروطنا الحين. الصبر مفتاح، والفرص تجي"]
DAILY_TIPS = ["ما في صفقة تستاهل تخليك تكسري خطتك.. الخطة هي الملك", "السوينق يحتاج صبر. الصفقة الصح تجيك، ما تروحين إليها", "الخسارة جزء من التداول. المهم إدارة المخاطرة مو الربح السريع"]

# --- الدوال الفنية (نفس منطق ICT/SMC الخاص بك) ---
def check_news():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        if r.status_code != 200: return {"has_news": False, "events": []}
        now = datetime.utcnow()
        upcoming = []
        for ev in r.json():
            if ev.get("impact") != "High": continue
            t = datetime.fromisoformat(ev.get("date","").replace("Z",""))
            diff = t - now
            if timedelta(hours=-1) <= diff <= timedelta(hours=24):
                upcoming.append({"title": ev.get("title"), "currency": ev.get("country"), "hours": round(diff.total_seconds()/3600, 1)})
        return {"has_news": len(upcoming)>0, "events": upcoming[:3]}
    except: return {"has_news": False, "events": []}

def get_candles(yf_sym, tf, limit=100):
    try:
        period = {"1h":"7d", "4h":"60d"}.get(tf, "60d")
        df = yf.Ticker(yf_sym).history(period=period, interval=tf)
        df = df.rename(columns={'Open':'open', 'High':'high', 'Low':'low', 'Close':'close'})
        return df.tail(limit)
    except: return pd.DataFrame()

def detect_trend(df):
    if len(df) < 20: return "neutral"
    r = df.tail(20)
    if r['high'].iloc[-1] > r['high'].iloc[0] and r['low'].iloc[-1] > r['low'].iloc[0]: return "bullish"
    if r['high'].iloc[-1] < r['high'].iloc[0] and r['low'].iloc[-1] < r['low'].iloc[0]: return "bearish"
    return "neutral"

def find_swings(df, lb=3):
    highs, lows = [], []
    for i in range(lb, len(df)-lb):
        if df['high'].iloc[i] == df['high'].iloc[i-lb:i+lb+1].max(): highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i-lb:i+lb+1].min(): lows.append((i, df['low'].iloc[i]))
    return highs, lows

def detect_dbos(df, highs, lows, direction):
    if direction == "bullish" and len(highs) >= 2:
        for i in range(len(highs)-1, 0, -1):
            if highs[i][1] > highs[i-1][1]:
                for j in range(highs[i-1][0], len(df)):
                    if df['close'].
