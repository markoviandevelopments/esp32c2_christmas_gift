# ultra_simple_tracker.py
from flask import Flask, request
from datetime import datetime
import time

app = Flask(__name__)

devices = {}

@app.route('/')
def index():
    if not devices:
        return "<h1>No devices online yet</h1>"
    sorted_dev = sorted(devices.items(), key=lambda x: x[1]['last_seen'], reverse=True)
    html = "<h1>Crypto Gifts Live</h1><table border='1'><tr><th>MAC</th><th>IP</th><th>Uptime (s)</th><th>Coin</th><th>Price</th><th>Value</th><th>Last Seen</th></tr>"
    for mac, info in sorted_dev:
        html += f"<tr><td>{mac}</td><td>{info['ip']}</td><td>{info['uptime']}</td><td>{info['coin']}</td><td>{info['price']}</td><td>{info['value']}</td><td>{datetime.fromtimestamp(info['last_seen']).strftime('%H:%M:%S')}</td></tr>"
    html += "</table>"
    return html

@app.route('/ping', methods=['GET', 'POST'])
def ping():
    try:
        data = request.args if request.method == 'GET' else request.get_json(force=True) or {}
        mac = data.get('mac')
        if not mac:
            return "No mac", 400
        devices[mac] = {
            'ip': data.get('ip', 'unknown'),
            'uptime': data.get('uptime', 0),
            'coin': data.get('coin', 'unknown'),
            'price': data.get('price', '---'),
            'value': data.get('value', '---'),
            'last_seen': time.time()
        }
        print(f"[{datetime.now()}] PING RECEIVED from {mac}")
        return "OK", 200
    except Exception as e:
        print(f"BAD PING: {e}")
        return "ERROR", 400

if __name__ == '__main__':
    print("Ultra simple tracker on http://0.0.0.0:9020")
    app.run(host='0.0.0.0', port=9020)
