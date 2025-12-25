# proxy_server.py - Cached proxy for prices, time, and RGB565 logos (with local logo storage)
from flask import Flask
import requests
import threading
import time
from PIL import Image
import io
import os
from zoneinfo import ZoneInfo  # Available in Python 3.9+, standard on modern Ubuntu
import datetime

app = Flask(__name__)

# Directories and files
LOGO_DIR = "logos"
os.makedirs(LOGO_DIR, exist_ok=True)

# Cached data
cached_prices = { 'btc': "error", 'sol': "error", 'doge': "error", 'pepe': "error", 'xrp': "error", 'ltc': "error" }
cached_time = "error"
cached_logos = {}  # coin -> "0xFFFF,0x0000,..." string
last_fetch_time = 0
CACHE_SECONDS = 180
lock = threading.Lock()

def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def load_or_download_logo(coin, url):
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    if os.path.exists(local_path):
        print(f"[{time.strftime('%H:%M:%S')}] Using local logo for {coin}")
        try:
            img = Image.open(local_path).convert('RGB')
        except Exception as e:
            print(f"Failed to open local {coin} logo: {e}")
            return "error"
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Downloading logo for {coin}...")
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert('RGB')
            img.save(local_path)
            print(f"Saved logo to {local_path}")
        except Exception as e:
            print(f"Failed to download {coin} logo: {e}")
            return "error"
    try:
        img = img.resize((24, 24), Image.LANCZOS)
        pixels = []
        for y in range(24):
            for x in range(24):
                r, g, b = img.getpixel((x, y))
                pixels.append(f"0x{rgb565(r,g,b):04X}")
        return ','.join(pixels)
    except Exception as e:
        print(f"Logo processing error for {coin}: {e}")
        return "error"

def fetch_data():
    global cached_prices, cached_logos, last_fetch_time
    while True:
        # Prices only
        ids = "bitcoin,solana,dogecoin,pepe,ripple,litecoin"
        try:
            r = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd', timeout=10)
            r.raise_for_status()
            data = r.json()
            cached_prices['btc'] = f"{data['bitcoin']['usd']:.8f}"
            cached_prices['sol'] = f"{data['solana']['usd']:.4f}"
            cached_prices['doge'] = f"{data['dogecoin']['usd']:.6f}"
            cached_prices['pepe'] = f"{data['pepe']['usd']:.10f}"
            cached_prices['xrp'] = f"{data['ripple']['usd']:.4f}"
            cached_prices['ltc'] = f"{data['litecoin']['usd']:.4f}"
        except Exception as e:
            print(f"Price fetch error: {e}")
       
        # Logos (only on first run)
        logo_urls = {
            'btc': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            'sol': 'https://cryptologos.cc/logos/solana-sol-logo.png',
            'doge': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png',
            'pepe': 'https://cryptologos.cc/logos/pepe-pepe-logo.png',
            'xrp': 'https://cryptologos.cc/logos/xrp-xrp-logo.png',
            'ltc': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png',
        }
        for coin, url in logo_urls.items():
            if coin not in cached_logos:
                cached_logos[coin] = load_or_download_logo(coin, url)
       
        with lock:
            last_fetch_time = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] Prices and logos refreshed")
        time.sleep(CACHE_SECONDS)

@app.route('/<coin>')
def get_price(coin):
    coin = coin.lower()
    with lock:
        return cached_prices.get(coin, "error")

@app.route('/time')
def get_central_time():
    try:
        chicago_tz = ZoneInfo("America/Chicago")
        now_central = datetime.datetime.now(chicago_tz)
        current_time = now_central.strftime('%H:%M:%S')
        return current_time
    except Exception as e:
        print(f"Time generation error: {e}")
        return "error"

@app.route('/logo/<coin>')
def get_logo(coin):
    coin = coin.lower()
    with lock:
        logo_data = cached_logos.get(coin, "error")
        if logo_data == "error":
            return "error", 404
        return logo_data  # Plain text comma-separated

@app.route('/')
def index():
    return "Proxy - /btc /sol /doge /pepe /xrp /ltc /time /logo/<coin>"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Proxy with local logo caching starting on http://0.0.0.0:9021")
    print("Logos will be saved in ./logos/ folder")
    app.run(host='0.0.0.0', port=9021)
