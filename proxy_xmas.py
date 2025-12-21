# proxy_server.py - Cached proxy for XRP/LTC price + Central Time (fetches every 5 min)
from flask import Flask
import requests
import threading
import time

app = Flask(__name__)

# Cached data
cached_xrp_price = "error"
cached_ltc_price = "error"
cached_time = "error"
last_fetch_time = 0
CACHE_SECONDS = 300  # 5 minutes

lock = threading.Lock()

def fetch_data():
    global cached_xrp_price, cached_ltc_price, cached_time, last_fetch_time
    while True:
        try:
            # Fetch XRP
            r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd', timeout=10)
            r.raise_for_status()
            cached_xrp_price = f"{r.json()['ripple']['usd']:.4f}"
        except:
            cached_xrp_price = "error"

        try:
            # Fetch LTC
            r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd', timeout=10)
            r.raise_for_status()
            cached_ltc_price = f"{r.json()['litecoin']['usd']:.4f}"
        except:
            cached_ltc_price = "error"

        try:
            # Fetch time
            r = requests.get('http://worldtimeapi.org/api/timezone/America/Chicago', timeout=10)
            r.raise_for_status()
            dt = r.json()['datetime']
            cached_time = dt[11:19]
        except:
            cached_time = "error"

        with lock:
            last_fetch_time = time.time()

        print(f"[{time.strftime('%H:%M:%S')}] Data refreshed: XRP=${cached_xrp_price}, LTC=${cached_ltc_price}, Time={cached_time}")
        time.sleep(CACHE_SECONDS)

@app.route('/xrp')
def get_xrp_price():
    with lock:
        return cached_xrp_price

@app.route('/ltc')
def get_ltc_price():
    with lock:
        return cached_ltc_price

@app.route('/time')
def get_central_time():
    with lock:
        return cached_time

@app.route('/')
def index():
    return "XH-C2X Proxy (cached every 5 min) - /xrp | /ltc | /time"

if __name__ == '__main__':
    # Start background fetch thread
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Cached proxy server starting on http://0.0.0.0:9021")
    app.run(host='0.0.0.0', port=9021)
