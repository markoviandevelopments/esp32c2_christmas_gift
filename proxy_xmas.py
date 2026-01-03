from flask import Flask, jsonify
import requests
import threading
import time
from PIL import Image
import io
import os
from zoneinfo import ZoneInfo
import datetime

app = Flask(__name__)

LOGO_DIR = "logos"
os.makedirs(LOGO_DIR, exist_ok=True)

cached_prices = {'btc': "error", 'sol': "error", 'doge': "error", 'pepe': "error", 'xrp': "error", 'ltc': "error"}
cached_time = "error"
cached_logos = {}
last_fetch_time = 0
CACHE_SECONDS = 180
lock = threading.Lock()

# Updated HOLDINGS: test chip now PEPE +1 for clear hypo gold #1 (real ranks unaffected)
HOLDINGS = {
    '34:98:7A:07:13:B4': {'coin': 'xrp', 'amount': 2.76412},
    '34:98:7A:07:14:D0': {'coin': 'sol', 'amount': 0.042486},
    '34:98:7A:06:FC:A0': {'coin': 'doge', 'amount': 40.7874},
    '34:98:7A:06:FB:D0': {'coin': 'pepe', 'amount': 1291895},
    '34:98:7A:07:11:24': {'coin': 'ltc', 'amount': 0.067632},
    '34:98:7A:07:12:B8': {'coin': 'pepe', 'amount': 1291896},  # Testing chip - +1 PEPE for hypo #1 gold
    '34:98:7A:07:06:B4': {'coin': 'btc', 'amount': 0.0000566},  # Chris
}

TEST_MAC = '34:98:7A:07:12:B8'

# (rgb565, load_or_download_logo, fetch_data unchanged - keep as-is)

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
        return now_central.strftime('%H:%M:%S')
    except Exception as e:
        print(f"Time error: {e}")
        return "error"

@app.route('/logo/<coin>')
def get_logo(coin):
    coin = coin.lower()
    with lock:
        logo_data = cached_logos.get(coin, "error")
        if logo_data == "error":
            return "error", 404
        return logo_data

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
    
    # Real ranking (exclude test)
    real_macs = [m for m in values if m != TEST_MAC]
    real_sorted = sorted(real_macs, key=lambda m: values[m], reverse=True)
    real_rank = {mac: idx + 1 for idx, mac in enumerate(real_sorted)}
    
    # Hypo including test
    all_sorted = sorted(values.keys(), key=lambda m: values[m], reverse=True)
    hypo_rank = {mac: idx + 1 for idx, mac in enumerate(all_sorted)}
    
    response = {}
    for mac in HOLDINGS:
        if mac == TEST_MAC:
            response[mac] = int(hypo_rank[mac])
        else:
            response[mac] = int(real_rank.get(mac, 99))
    return jsonify(response)

@app.route('/')
def index():
    return "Proxy - /btc /sol /doge /pepe /xrp /ltc /time /logo/<coin>"

if __name__ == '__main__':
    threading.Thread(target=fetch_data, daemon=True).start()
    print("Proxy starting on http://0.0.0.0:9021")
    app.run(host='0.0.0.0', port=9021)
