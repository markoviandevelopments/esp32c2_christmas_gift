# proxy_server.py - Cached proxy for prices, time, and RGB565 logos (with local logo storage)
from flask import Flask, jsonify
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
cached_big_logos = {}  # coin -> list of int RGB565 pixels (160x80 = 12800)
BIG_WIDTH = 160
BIG_HEIGHT = 80
CHUNK_SIZE = 1000  # ~1000 pixels/chunk (~5-6KB response, safe)
lock = threading.Lock()

# Hard-coded holdings
HOLDINGS = {
    '34:98:7A:07:13:B4': {'coin': 'xrp', 'amount': 2.76412},
    '34:98:7A:07:14:D0': {'coin': 'sol', 'amount': 0.042486},
    '34:98:7A:06:FC:A0': {'coin': 'doge', 'amount': 40.7874},
    '34:98:7A:06:FB:D0': {'coin': 'pepe', 'amount': 1291895},
    '34:98:7A:07:11:24': {'coin': 'ltc', 'amount': 0.067632},
    '34:98:7A:07:12:B8': {'coin': 'doge', 'amount': 40.7874},  # Testing chip
    '34:98:7A:07:06:B4': {'coin': 'btc', 'amount': 0.0000566},
}

TEST_MAC = '34:98:7A:07:12:B8'

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
        img = img.resize((20, 20), Image.LANCZOS)
        pixels = []
        for y in range(20):
            for x in range(20):
                r, g, b = img.getpixel((x, y))
                pixels.append(f"0x{rgb565(r,g,b):04X}")
        return ','.join(pixels)
    except Exception as e:
        print(f"Logo processing error for {coin}: {e}")
        return "error"

def generate_big_logo(coin):
    if coin in cached_big_logos:
        return cached_big_logos[coin]
    
    local_path = os.path.join(LOGO_DIR, f"{coin}.png")
    if not os.path.exists(local_path):
        cached_big_logos[coin] = None
        return None
    
    try:
        img = Image.open(local_path).convert('RGB')
        img = img.resize((BIG_WIDTH, BIG_HEIGHT), Image.LANCZOS)
        pixels = []
        for y in range(BIG_HEIGHT):
            for x in range(BIG_WIDTH):
                r, g, b = img.getpixel((x, y))
                pixels.append(rgb565(r, g, b))
        cached_big_logos[coin] = pixels
        print(f"[{time.strftime('%H:%M:%S')}] Generated big 160x80 logo for {coin}")
        return pixels
    except Exception as e:
        print(f"Big logo error {coin}: {e}")
        cached_big_logos[coin] = None
        return None

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
        
        for coin in logo_urls:
            generate_big_logo(coin)  # Pre-generate big versions
       
        with lock:
            last_fetch_time = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] Prices and logos refreshed")
        time.sleep(CACHE_SECONDS)

@app.route('/<coin>')
def get_price(coin):
    coin = coin.lower()
    with lock:
        return cached_prices.get(coin, "error")

@app.route('/biglogo_chunks/<coin>')
def biglogo_chunks(coin):
    coin = coin.lower()
    pixels = generate_big_logo(coin)
    if pixels is None:
        return "0"
    chunks = (len(pixels) + CHUNK_SIZE - 1) // CHUNK_SIZE
    return str(chunks)

@app.route('/biglogo/<coin>/<int:chunk>')
def biglogo_chunk(coin, chunk):
    coin = coin.lower()
    pixels = generate_big_logo(coin)
    if pixels is None:
        return "error"
    start = chunk * CHUNK_SIZE
    if start >= len(pixels):
        return "error"
    end = min(start + CHUNK_SIZE, len(pixels))
    chunk_pixels = pixels[start:end]
    return ','.join(f"0x{p:04X}" for p in chunk_pixels)

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

@app.route('/rank')
def get_rank():
    with lock:
        prices = cached_prices.copy()
    
    values = {}
    for mac, info in HOLDINGS.items():
        coin_key = info['coin']
        try:
            price = float(prices.get(coin_key, "0"))
            usd = price * info['amount']
            values[mac] = usd
        except:
            values[mac] = 0.0
    
    # Helper to assign competition ranks (tied get same rank, next skips)
    def assign_ranks(mac_list):
        if not mac_list:
            return {}
        # Sort by USD descending
        sorted_macs = sorted(mac_list, key=lambda m: values[m], reverse=True)
        rank_dict = {}
        i = 0
        while i < len(sorted_macs):
            current_mac = sorted_macs[i]
            current_usd = values[current_mac]
            # Find tie group size
            tie_end = i + 1
            while tie_end < len(sorted_macs) and values[sorted_macs[tie_end]] == current_usd:
                tie_end += 1
            # Assign the current rank (best in group) to all tied
            current_rank = i + 1
            for j in range(i, tie_end):
                rank_dict[sorted_macs[j]] = current_rank
            i = tie_end
        return rank_dict
    
    # Real ranking (exclude test)
    real_macs = [m for m in HOLDINGS if m != TEST_MAC]
    real_rank = assign_ranks(real_macs)
    
    # Hypo ranking (include test)
    hypo_rank = assign_ranks(list(HOLDINGS.keys()))
    
    response = {}
    for mac in HOLDINGS:
        if mac == TEST_MAC:
            response[mac] = int(hypo_rank.get(mac, 99))
        else:
            response[mac] = int(real_rank.get(mac, 99))
    
    return jsonify(response)

@app.route('/')
def index():
    return "Proxy - /btc /sol /doge /pepe /xrp /ltc /time /logo/<coin>"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Proxy with local logo caching starting on http://0.0.0.0:9021")
    print("Logos will be saved in ./logos/ folder")
    app.run(host='0.0.0.0', port=9021)
