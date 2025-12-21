# proxy_server.py - Cached proxy for multiple coins + Central Time (fetches every 5 min)
from flask import Flask
import requests
import threading
import time

app = Flask(__name__)

# Cached data
cached_prices = {
    'btc': "error",
    'xrp': "error",
    'ltc': "error",
    'sol': "error",
    'doge': "error",
    'pepe': "error",
}
cached_time = "error"
last_fetch_time = 0
CACHE_SECONDS = 300  # 5 minutes

lock = threading.Lock()

def fetch_data():
    global cached_prices, cached_time, last_fetch_time
    while True:
        try:
            # Fetch all prices in one call (efficient)
            ids = "bitcoin,ripple,litecoin,solana,dogecoin,pepe"
            r = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd', timeout=10)
            r.raise_for_status()
            data = r.json()
            cached_prices['btc'] = f"{data['bitcoin']['usd']:.8f}"
            cached_prices['xrp'] = f"{data['ripple']['usd']:.4f}"
            cached_prices['ltc'] = f"{data['litecoin']['usd']:.4f}"
            cached_prices['sol'] = f"{data['solana']['usd']:.4f}"
            cached_prices['doge'] = f"{data['dogecoin']['usd']:.6f}"
            cached_prices['pepe'] = f"{data['pepe']['usd']:.10f}"
        except:
            pass  # Keep old values on error

        try:
            r = requests.get('http://worldtimeapi.org/api/timezone/America/Chicago', timeout=10)
            r.raise_for_status()
            dt = r.json()['datetime']
            cached_time = dt[11:19]
        except:
            pass

        with lock:
            last_fetch_time = time.time()

        print(f"[{time.strftime('%H:%M:%S')}] Data refreshed")
        time.sleep(CACHE_SECONDS)

@app.route('/btc')
def get_btc():
    with lock:
        return cached_prices['btc']

@app.route('/xrp')
def get_xrp():
    with lock:
        return cached_prices['xrp']

@app.route('/ltc')
def get_ltc():
    with lock:
        return cached_prices['ltc']

@app.route('/sol')
def get_sol():
    with lock:
        return cached_prices['sol']

@app.route('/doge')
def get_doge():
    with lock:
        return cached_prices['doge']

@app.route('/pepe')
def get_pepe():
    with lock:
        return cached_prices['pepe']

@app.route('/time')
def get_central_time():
    with lock:
        return cached_time

@app.route('/')
def index():
    return "XH-C2X Proxy (cached every 5 min) - /btc|/xrp|/ltc|/sol|/doge|/pepe|/time"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Proxy server starting on http://0.0.0.0:9021")
    app.run(host='0.0.0.0', port=9021)
