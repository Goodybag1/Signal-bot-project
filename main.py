import ccxt
import time
import requests
import pandas as pd
from datetime import datetime
from flask import Flask
from threading import Thread
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import BollingerBands

# Telegram Config
TELEGRAM_API_URL = "https://api.telegram.org/bot7950917429:AAFqWid_MpXMOCKUL0h9v6zRqKgvgEQCyXY/sendMessage"
CHAT_ID = "809952021"

# Signals memory
signal_memory = {}

def send_telegram_alert(message):
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        requests.post(TELEGRAM_API_URL, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_current_datetime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def initialize_exchange():
    return ccxt.mexc({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })


def validate_pairs(exchange, target_pairs):
    try:
        exchange.load_markets()
        supported = [p for p in target_pairs if p in exchange.symbols]
        unsupported = [p for p in target_pairs if p not in exchange.symbols]
        if unsupported:
            print(f"⚠️ Unsupported pairs: {', '.join(unsupported)}")
            send_telegram_alert(f"Unsupported pairs on mexc: {', '.join(unsupported)}")
        return supported
    except Exception as e:
        send_telegram_alert(f"Error loading markets: {e}")
        return []
    
def fetch_data(pair):
    exchange = ccxt.mexc({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot'
        }
    })
    try:
        exchange.load_markets()
        if pair not in exchange.symbols:
            print(f"❌ Pair not found on mexc: {pair}")
            return None

        # Add delay between requests to avoid rate limits
        time.sleep(1)

        ohlcv = exchange.fetch_ohlcv(pair, timeframe='1h', limit=100)
        if not ohlcv or len(ohlcv) == 0:
            print(f"⚠️ No data received for {pair}")
            return None

        return ohlcv
    except Exception as e:
        print(f"❌ Exception while fetching {pair}: {type(e).__name__} - {e}")
        return None

def calculate_indicators(ohlcv):
    closes = [c[4] for c in ohlcv]
    close_series = pd.Series(closes)

    rsi = RSIIndicator(close_series).rsi()[-1]
    ema_20 = EMAIndicator(close_series, window=20).ema_indicator()[-1]
    bb = BollingerBands(close_series)
    upper = bb.bollinger_hband()[-1]
    lower = bb.bollinger_lband()[-1]
    price = closes[-1]

    return rsi, ema_20, upper, lower, price

def check_signals(exchange, pair):
    global signal_memory

    try:
        ohlcv = fetch_data(pair)
        if not ohlcv:
            print(f"No OHLCV data available for {pair}")
            return

        if len(ohlcv) < 100:  # We need at least 100 candles for indicators
            print(f"Insufficient data for {pair}: got {len(ohlcv)} candles")
            return

        rsi, ema_20, upper, lower, price = calculate_indicators(ohlcv)
        signal_key = f"{pair}_signal"
        time_now = get_current_datetime()

        message = f"[{time_now}]\nPair: {pair}\nPrice: {price:.2f}\nRSI: {rsi:.2f}\nEMA20: {ema_20:.2f}"

        if rsi < 30 and price < lower and signal_memory.get(signal_key) != 'buy':
            stop_loss = price * 0.97
            target = price * 1.05
            message += f"\n\n🚀 BUY SIGNAL\nSL: {stop_loss:.2f} | TP: {target:.2f}"
            send_telegram_alert(message)
            signal_memory[signal_key] = 'buy'
        elif rsi > 70 and price > upper and signal_memory.get(signal_key) != 'sell':
            stop_loss = price * 1.03
            target = price * 0.95
            message += f"\n\n🔻 SELL SIGNAL\nSL: {stop_loss:.2f} | TP: {target:.2f}"
            send_telegram_alert(message)
            signal_memory[signal_key] = 'sell'
        else:
            signal_memory[signal_key] = 'neutral'
            print(f"{pair}: No signal at {time_now}")
    except Exception as e:
        print(f"Error in check_signals for {pair}: {e}")
def monitor_market():
    print(f"\n[{get_current_datetime()}] Starting monitoring cycle...")
    exchange = initialize_exchange()

    trading_pairs = ['BABYDOGE/USDT', 'MOG/USDT', 'PEIPEI/USDT', 'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 
                    'DOGE/USDT', 'SHIB/USDT', 'SOL/USDT', 'XRP/USDT', 'LTC/USDT', 'ADA/USDT']


    supported_pairs = validate_pairs(exchange, trading_pairs)

    for idx, pair in enumerate(supported_pairs, 1):
        print(f"\rChecking {idx}/{len(supported_pairs)}: {pair}", end="", flush=True)
        try:
            check_signals(exchange, pair)
        except Exception as e:
            print(f"\nError checking {pair}: {e}")
            send_telegram_alert(f"Error checking {pair}: {e}")

# Flask keep-alive server
app = Flask(__name__)
@app.route('/')
def home():
    return "Crypto trading bot is live"
def keep_alive():    
    Thread(target=app.run, args=('0.0.0.0', 5000)).start()  # Start Flask app in a thread

if __name__ == "__main__":
    print("\n=== Crypto Trading Bot Starting ===")
    send_telegram_alert("Bot starting up! 🚀")
    keep_alive()

    while True:
        try:
            # Quick test to list available USDT pairs on MEXC
            test_exchange = ccxt.mexc()
            test_exchange.load_markets()
           # if test_exchange.symbols is not None:
               # available_pairs = [s for s in test_exchange.symbols if '/USDT' in s]
               # print("\n✅ Available USDT pairs on MEXC:", available_pairs[:10])  # Print first 10
            #else:
               # print("Error: Unable to load markets. test_exchange.symbols is None")

            monitor_market()
            print("\nMonitoring complete. Sleeping 10 minutes...\n")
            time.sleep(10 * 60)
        except Exception as e:
            error_msg = f"Main loop error: {e}"
            print(error_msg)
            send_telegram_alert(error_msg)
            time.sleep(60)