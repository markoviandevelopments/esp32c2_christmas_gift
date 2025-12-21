# proxy_server.py - Cached proxy for prices, time, and coin logos (5 min cache)
from flask import Flask, send_file, Response
import requests
import threading
import time
import io
from PIL import Image

app = Flask(__name__)

# Cached data
cached_prices = {
    'btc': "error",
    'sol': "error",
    'doge': "error",
    'pepe': "error",
    'xrp': "error",
    'ltc': "error"
}
cached_time = "error"
cached_logos = {}  # coin -> resized PNG bytes
last_fetch_time = 0
CACHE_SECONDS = 300

lock = threading.Lock()

def fetch_data():
    global cached_prices, cached_time, cached_logos, last_fetch_time
    while True:
        # Prices
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
        except:
            pass

        # Time
        try:
            r = requests.get('http://worldtimeapi.org/api/timezone/America/Chicago', timeout=10)
            r.raise_for_status()
            dt = r.json()['datetime']
            cached_time = dt[11:19]
        except:
            pass

        # Logos (download and resize to 20x20 for your display size)
        logo_urls = {
            'btc': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png',
            'sol': 'https://cryptologos.cc/logos/solana-sol-logo.png',
            'doge': 'https://cryptologos.cc/logos/dogecoin-doge-logo.png',
            'pepe': 'https://cryptologos.cc/logos/pepe-pepe-logo.png',
            'xrp': 'https://cryptologos.cc/logos/ripple-xrp-logo.png',
            'ltc': 'https://cryptologos.cc/logos/litecoin-ltc-logo.png',
        }
        for coin, url in logo_urls.items():
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content))
                img = img.resize((20, 20), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                cached_logos[coin] = buf.getvalue()
            except:
                cached_logos[coin] = None  # Failed

        with lock:
            last_fetch_time = time.time()

        print(f"[{time.strftime('%H:%M:%S')}] Data + logos refreshed")
        time.sleep(CACHE_SECONDS)

@app.route('/<coin>')
def get_price(coin):
    coin = coin.lower()
    with lock:
        return cached_prices.get(coin, "error")

@app.route('/time')
def get_central_time():
    with lock:
        return cached_time

@app.route('/logo/<coin>')
def get_logo(coin):
    coin = coin.lower()
    with lock:
        logo_bytes = cached_logos.get(coin)
        if logo_bytes:
            return Response(logo_bytes, mimetype='image/png')
        else:
            return "error", 404

@app.route('/')
def index():
    return "Proxy - /btc /sol /doge /pepe /xrp /ltc /time /logo/<coin>"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Cached proxy with logos starting on http://0.0.0.0:9021")
    app.run(host='0.0.0.0', port=9021)
