# proxy_server.py - Simple HTTP proxy for XRP price + Central Time (run on Ubuntu desktop)
from flask import Flask
import requests
import time

app = Flask(__name__)

@app.route('/xrp')
def get_xrp_price():
    try:
        r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd', timeout=10)
        r.raise_for_status()
        price = r.json()['ripple']['usd']
        return f"{price:.4f}"  # Plain text, e.g., "1.8542"
    except:
        return "error"

@app.route('/time')
def get_central_time():
    try:
        r = requests.get('http://worldtimeapi.org/api/timezone/America/Chicago', timeout=10)
        r.raise_for_status()
        dt = r.json()['datetime']
        return dt[11:19]  # HH:MM:SS 24h format
    except:
        return "error"

@app.route('/')
def index():
    return "XH-C2X Proxy Server - /xrp or /time"

if __name__ == '__main__':
    print("Proxy server starting on http://0.0.0.0:9020")
    print("Use your desktop IP (e.g., 108.254.1.184:9021) from ESP")
    app.run(host='0.0.0.0', port=9021)
