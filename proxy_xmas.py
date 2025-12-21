# proxy_server.py - Cached proxy for multiple coins + Central Time (fetches every 5 min)
from flask import Flask
import requests
import threading
import time

app = Flask(__name__)

# Cached data
cached_prices = {
    'btc': "error",
    'sol': "error",
    'doge': "error",
    'pepe': "error",
    'xrp': "error",
    'ltc': "error"  # Keep for special case if needed
}
cached_time = "error"
last_fetch_time = 0
CACHE_SECONDS = 300  # 5 minutes

lock = threading.Lock()

def fetch_data():
    global cached_prices, cached_time, last_fetch_time
    while True:
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

        print(f"[{time.strftime('%H:%M:%S')}] Prices refreshed")
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

@app.route('/')
def index():
    return "Proxy - /btc /sol /doge /pepe /xrp /ltc /time"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Multi-coin cached proxy starting on http://0.0.0.0:9021")
    app.run(host='0.0.0.0', port=9021)
